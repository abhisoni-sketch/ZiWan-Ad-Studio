# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import wave
import math
import struct
import shutil
import subprocess
import logging
import uuid
import imageio_ffmpeg
from backend.config import RUNNING_ON_GCP, LOCAL_STORAGE_DIR, PROJECT_ID, INGEST_BUCKET, GCS_FUSE_MOUNT, FONT_DIR
from backend.storage_provider import StorageProvider
from backend.db_provider import DatabaseProvider
import time
from backend.services.pricing_service import GCPBillingService

logger = logging.getLogger(__name__)

class Stitcher:
    def __init__(self):
        self.storage = StorageProvider()
        self.db = DatabaseProvider()
        
        # Prioritize system ffmpeg (which supports libfreetype/drawtext) over package-embedded static binary
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            logger.info(f"Using system-installed FFmpeg binary at: {system_ffmpeg}")
            self.ffmpeg_exe = system_ffmpeg
        else:
            logger.warning("System-installed FFmpeg not found. Falling back to imageio_ffmpeg static binary.")
            self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def check_has_audio(self, file_path: str) -> bool:
        cmd = [self.ffmpeg_exe, "-i", file_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return "Audio:" in res.stderr

    def get_video_duration(self, path: str) -> float:
        """Query FFmpeg to extract actual video duration in seconds."""
        try:
            cmd = [self.ffmpeg_exe, "-i", path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in res.stderr.splitlines():
                if "Duration:" in line:
                    parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
                    hours = float(parts[0])
                    minutes = float(parts[1])
                    seconds = float(parts[2])
                    return hours * 3600 + minutes * 60 + seconds
        except Exception as e:
            logger.error(f"Error getting video duration: {e}")
        return 5.0

    def generate_fallback_voiceover(self, text: str, output_path: str):
        """Generates fallback voiceover audio using Google Cloud Text-to-Speech or local gTTS."""
        if not text:
            return False
            
        try:
            from google.cloud import texttospeech
            client = texttospeech.TextToSpeechClient()
            synthesis_input = texttospeech.SynthesisInput(text=text)
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Journey-F"  # Premium expressive voice
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )
            response = client.synthesize_speech(
                input=synthesis_input, voice=voice, audio_config=audio_config
            )
            with open(output_path, "wb") as out:
                out.write(response.audio_content)
            return True
        except Exception as e:
            logger.warning(f"Fallback voiceover API call failed: {e}. Trying gTTS.")
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang='en', slow=False)
                tts.save(output_path)
                return True
            except Exception as ge:
                logger.error(f"gTTS fallback failed: {ge}")
                return False

    def generate_lyria_bgm(self, prompt: str, duration_sec: int, output_path: str, job_id: str = None, client = None, model_bgm = None) -> str:
        """Generates background music using Lyria 3 pro via Gemini Enterprise interactions API with fallback."""
        if model_bgm == "python-synth":
            logger.info("Using python-synth BGM generator directly.")
            self.generate_synth_music(output_path, duration_sec)
            return "python-synth"

        logger.info(f"Generating background music via Lyria 3: '{prompt}'")
        
        try:
            from google import genai
            from google.genai import types
            import base64
            import time
            
            if not client:
                client = genai.Client(
                    vertexai=True,
                    project=PROJECT_ID,
                    location="global",
                    http_options=types.HttpOptions(headers={"Api-Revision": "2026-05-20"}),
                )
            
            interaction = None
            max_retries = 4
            backoff_factor = 2
            initial_delay = 5
            
            for attempt in range(max_retries):
                try:
                    interaction = client.interactions.create(
                        model=model_bgm or 'lyria-3-pro-preview',
                        input=[{'type': 'user_input', 'content': [{'type': 'text', 'text': prompt}]}],
                        generation_config={
                            "safety_settings": [
                                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}
                            ]
                        },
                        timeout=600
                    )
                    break
                except Exception as api_err:
                    err_str = str(api_err).lower()
                    if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
                        delay = initial_delay * (backoff_factor ** attempt)
                        logger.warning(f"Lyria BGM API hit quota limit. Attempt {attempt + 1}/{max_retries}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        raise api_err
            else:
                raise RuntimeError("Failed to generate Lyria BGM after max retries due to quota limits.")
            
            raw_audio_bytes = None
            
            # Direct extraction from output_audio property (standard GenAI SDK schema)
            if hasattr(interaction, "output_audio") and interaction.output_audio and hasattr(interaction.output_audio, "data") and interaction.output_audio.data:
                raw_audio_bytes = base64.b64decode(interaction.output_audio.data)
            
            # Fallback to parsing interaction steps
            if not raw_audio_bytes:
                for step in interaction.steps:
                    step_dict = step.model_dump()
                    if step_dict.get("type") == "model_output" and step_dict.get("content"):
                        parts = step_dict["content"]
                        if isinstance(parts, dict) and "parts" in parts:
                            parts = parts["parts"]
                        
                        if isinstance(parts, list):
                            for part in parts:
                                if isinstance(part, dict) and part.get("type") == "audio":
                                    audio_b64 = part.get("data")
                                    if audio_b64:
                                        raw_audio_bytes = base64.b64decode(audio_b64)
                                        break
            
            if not raw_audio_bytes:
                raise ValueError("No audio bytes found in Lyria response.")
                
            temp_mp3 = f"/tmp/temp_lyria_bgm_{uuid.uuid4().hex}.mp3"
            with open(temp_mp3, "wb") as out:
                out.write(raw_audio_bytes)
                
            # Convert to target output WAV format
            import subprocess
            cmd = [self.ffmpeg_exe, "-y", "-i", temp_mp3, "-acodec", "pcm_s16le", "-ac", "2", "-ar", "44100", output_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)
                
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg MP3 to WAV conversion failed: {res.stderr}")
                
            logger.info(f"Lyria BGM generated and converted successfully at {output_path}")
            return "Lyria 3 Pro (Dynamic)"
        except Exception as e:
            logger.warning(f"Lyria BGM generation failed: {e}. Attempting GCS stock fallback...")
            fallback_source = self.fetch_gcs_fallback_bgm(output_path, job_id=job_id)
            if fallback_source:
                return fallback_source
            else:
                logger.warning("GCS fallback failed. Falling back to synthetic Python music.")
                self.generate_synth_music(output_path, duration_sec)
                return "Python Synth (Emergency)"

    def fetch_gcs_fallback_bgm(self, output_path: str, job_id: str = None) -> str:
        """Fetches a random pre-cleared stock music track from GCS."""
        import os
        import random
        import subprocess
        from backend.config import PROJECT_ID
        
        # Randomly select a track between 1 and 10
        track_id = random.randint(1, 10)
        bucket_name = f"{PROJECT_ID}-ingest-vault"
        gcs_uri = f"gs://{bucket_name}/fallback_bgm/track_{track_id}.mp3"
        temp_mp3 = os.path.join("/tmp", f"fallback_track_{job_id or 'default'}_{track_id}.mp3")
        
        try:
            logger.info(f"Attempting to fetch GCS fallback track: {gcs_uri}")
            self.storage.download_file(gcs_uri, temp_mp3)
            
            # Convert the MP3 to the expected WAV format for the stitcher
            cmd = [self.ffmpeg_exe, "-y", "-i", temp_mp3, "-acodec", "pcm_s16le", "-ac", "2", "-ar", "44100", output_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if os.path.exists(temp_mp3):
                os.remove(temp_mp3)
                
            if res.returncode == 0 and os.path.exists(output_path):
                logger.info("Successfully loaded GCS fallback track.")
                return f"GCS Fallback (Track {track_id})"
            else:
                logger.error(f"Failed to convert GCS fallback track: {res.stderr}")
                return ""
        except Exception as e:
            logger.error(f"GCS fallback fetch failed: {e}")
            return ""

    def generate_synth_music(self, output_path: str, duration_sec: int, sample_rate: int = 22050):
        """Generates a warm, deep, atmospheric ambient pad chord progression."""
        logger.info(f"Synthesizing ambient background score ({duration_sec}s) at {output_path}...")
        num_samples = duration_sec * sample_rate
        
        with wave.open(output_path, 'wb') as wav:
            wav.setnchannels(1)  # Mono
            wav.setsampwidth(2)  # 16-bit PCM
            wav.setframerate(sample_rate)
            
            # Atmospheric ambient chords pitched up 2 octaves for standard speaker audibility
            chords = [
                [f * 4.0 for f in [65.41, 130.81, 164.81, 196.00, 293.66]],  # Cmaj9
                [f * 4.0 for f in [55.00, 110.00, 130.81, 164.81, 246.94]],  # Am9
                [f * 4.0 for f in [43.65, 87.31, 130.81, 174.61, 220.00]],   # Fmaj9
                [f * 4.0 for f in [49.00, 98.00, 146.83, 196.00, 293.66]]    # G11
            ]
            
            chord_duration = 8.0  # Align chord changes to match 8-second video segments!
            
            prev_val = 0.0
            alpha = 0.6  # Higher filter factor to keep sound bright and audible
            
            for i in range(num_samples):
                t = i / sample_rate
                chord_idx = int(t / chord_duration) % len(chords)
                active_chord = chords[chord_idx]
                
                # Combine chord frequencies with sub-bass weight
                raw_val = 0.0
                for idx, freq in enumerate(active_chord):
                    # Add a sub-bass roots (C2, A1, F1, G1) with higher weight to make it deep
                    weight = 0.45 if idx == 0 else 0.15
                    raw_val += weight * math.sin(2 * math.pi * freq * t)
                
                # Slowly swell volume once per chord (breathing LFO)
                lfo = 0.6 + 0.4 * math.sin(2 * math.pi * (1.0 / (2.0 * chord_duration)) * t - math.pi/2)
                raw_val *= lfo
                
                # Apply low-pass filter (smoothes high-frequency click/buzzer tone)
                filtered_val = alpha * raw_val + (1.0 - alpha) * prev_val
                prev_val = filtered_val
                
                # Soft volume multiplier
                final_val = filtered_val * 0.85
                
                # Pack to 16-bit PCM integer
                packed = struct.pack('<h', int(final_val * 32767))
                wav.writeframesraw(packed)
        logger.info("Synth music generation complete.")

    def run(self, pubsub_payload: dict) -> dict:
        start_time = time.perf_counter()
        job_id = pubsub_payload['job_id']
        clips = pubsub_payload['clips']
        
        logger.info(f"Stitcher starting for Job {job_id}. Stitching {len(clips)} clips.")
        self.db.update_job(job_id, {"status": "stitching"})

        # Fetch job info to check model target
        job_data = self.db.get_job(job_id) or {}
        model_target = job_data.get('model_target', '')
        is_omni = "omni" in model_target.lower()
        
        location = job_data.get("gcp_location") or "global"
        model_bgm = job_data.get("model_bgm")
        
        # Dynamically instantiate client
        from google import genai
        from google.genai import types
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key)
        else:
            client = genai.Client(
                vertexai=True,
                project=PROJECT_ID,
                location=location,
                http_options=types.HttpOptions(headers={"Api-Revision": "2026-05-20"}) if location == "global" else None
            )

        # Determine if we should concatenate native clip audio (Omni) or mix separate GCP TTS + synthesized BGM tracks.
        use_native_audio = not any(c.get('audio_gcs_uri', '') for c in clips)
        logger.info(f"Stitcher: use_native_audio={use_native_audio}, is_omni={is_omni}")
        bgm_source = "Native Omni Audio" if use_native_audio else ""

        local_videos = []
        local_audios = []
        durations = []
        
        try:
            # 1. Download and pre-process all video and voiceover audio clips
            for c in clips:
                seq = c['clip_sequence']
                dur = c['duration']
                video_uri = c['gcs_uri']
                audio_uri = c.get('audio_gcs_uri', '')
                text_overlay = c.get('text_overlay', '')
                
                # Video file
                local_vid_path = f"/tmp/stitch_vid_raw_{job_id}_{seq}.mp4"
                self.storage.download_file(video_uri, local_vid_path)
                
                # Apply text overlay and normalize video settings (fps=24, yuv420p)
                overlayed_vid_path = f"/tmp/stitch_vid_{job_id}_{seq}.mp4"
                font_file = os.path.join(FONT_DIR, "Arial.ttf")
                
                filters = []
                # Apply deterministic FFmpeg text overlay whenever using generated voiceover tracks.
                # This guarantees 100% spelling accuracy (e.g. '2MP BOKEH CAMERA') with zero spelling glitches or double overlays!
                if not use_native_audio and text_overlay:
                    idx = seq
                    # 1. Clean the LLM string: convert literal '\\n' to actual newlines, make uppercase
                    clean_text = text_overlay.replace('\\n', '\n').replace('\\N', '\n').upper()
                    
                    # 2. Write to a temporary file to bypass FFmpeg command-line escaping bugs
                    text_file_path = f"/tmp/overlay_text_{job_id}_{idx}.txt"
                    with open(text_file_path, "w", encoding="utf-8") as f:
                        f.write(clean_text)

                    font_file = os.path.join(FONT_DIR, "Futura.ttc")
                    
                    # 3. Elite Creative Direction: Dynamic styling based on whether it is the finale block
                    is_finale = '\n' in clean_text
                    
                    if is_finale:
                        # FINALE: Center-aligned, clean shadow, elegant studio ad look
                        drawtext_filter = (
                            f"drawtext=textfile='{text_file_path}':fontfile={font_file}:fontsize=40:fontcolor=white:"
                            f"shadowcolor=black@0.6:shadowx=3:shadowy=3:line_spacing=15:"
                            f"alpha='if(lt(t,0.5),t/0.5,1)':"
                            f"x=(w-text_w)/2:y=(h-text_h)/2"
                        )
                    else:
                        # MIDDLE CLIPS: Bottom-centered, sleek modern drop shadow
                        drawtext_filter = (
                            f"drawtext=textfile='{text_file_path}':fontfile={font_file}:fontsize=35:fontcolor=white:"
                            f"shadowcolor=black@0.6:shadowx=2:shadowy=2:"
                            f"alpha='if(lt(t,0.3),t/0.3,1)':"
                            f"x=(w-text_w)/2:y=h-th-100"
                        )
                    
                    filters.append(drawtext_filter)
                    
                    # Force video to exact duration to prevent A/V sync drift
                    target_dur = dur
                    filters.append(f"trim=0:{target_dur},setpts=PTS-STARTPTS")
                # Resample frame rate to 24fps and fix SAR to prevent concat/xfade mismatches
                filters.append("fps=fps=24,setsar=1/1")
                
                filter_str = ",".join(filters)
                
                has_audio = self.check_has_audio(local_vid_path)
                logger.info(f"Stitcher: Clip {seq} has_audio={has_audio}")
                
                if use_native_audio and not has_audio:
                    # Input has no audio (safety fallback/mock). Generate a fallback voiceover track using GCP TTS
                    # and overlay it onto the video so the audio doesn't break!
                    logger.info(f"Stitcher: Generating fallback voiceover and segment music for silent clip {seq}...")
                    fallback_voice_path = f"/tmp/fallback_voice_{job_id}_{seq}.mp3"
                    fallback_music_path = f"/tmp/fallback_music_{job_id}_{seq}.wav"
                    mixed_fallback_audio = f"/tmp/mixed_fallback_{job_id}_{seq}.m4a"
                    
                    vo_text = c.get('voiceover_script', '')
                    has_fallback_vo = self.generate_fallback_voiceover(vo_text, fallback_voice_path)
                    
                    if has_fallback_vo:
                        # Synthesize background music segment matching this clip duration
                        self.generate_synth_music(fallback_music_path, int(dur) + 2)
                        # Mix voiceover and music segment
                        mix_cmd = [
                            self.ffmpeg_exe, "-y",
                            "-i", fallback_voice_path,
                            "-i", fallback_music_path,
                            "-filter_complex", "amix=inputs=2:duration=first:weights=1.0 0.12",
                            "-c:a", "aac",
                            mixed_fallback_audio
                        ]
                        subprocess.run(mix_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Now overlay the mixed audio onto the mock video
                        overlay_cmd = [
                            self.ffmpeg_exe, "-y",
                            "-i", local_vid_path,
                            "-i", mixed_fallback_audio,
                            "-vf", filter_str,
                            "-c:v", "libx264",
                            "-pix_fmt", "yuv420p",
                            "-c:a", "aac",
                            "-map", "0:v",
                            "-map", "1:a",
                            "-t", str(dur),
                            "-shortest",
                            overlayed_vid_path
                        ]
                    else:
                        # Fallback to pure silence if TTS fails
                        overlay_cmd = [
                            self.ffmpeg_exe, "-y",
                            "-i", local_vid_path,
                            "-f", "lavfi",
                            "-i", "anullsrc=r=48000:channel_layout=stereo",
                            "-vf", filter_str,
                            "-c:v", "libx264",
                            "-pix_fmt", "yuv420p",
                            "-c:a", "aac",
                            "-map", "0:v",
                            "-map", "1:a",
                            "-t", str(dur),
                            "-shortest",
                            overlayed_vid_path
                        ]
                else:
                    overlay_cmd = [
                        self.ffmpeg_exe, "-y",
                        "-i", local_vid_path,
                        "-vf", filter_str,
                        "-c:v", "libx264",
                        "-pix_fmt", "yuv420p"
                    ]
                    if use_native_audio:
                        overlay_cmd.extend(["-c:a", "aac"])
                    overlay_cmd.extend(["-t", str(dur)])
                    overlay_cmd.append(overlayed_vid_path)
                logger.info(f"Stitcher: Pre-processing clip {seq} (filters: {filter_str})")
                overlay_res = subprocess.run(overlay_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if overlay_res.returncode != 0:
                    logger.error(f"Pre-processing failed for clip {seq}: {overlay_res.stderr}. Using raw clip.")
                    os.rename(local_vid_path, overlayed_vid_path)
                else:
                    if os.path.exists(local_vid_path):
                        os.remove(local_vid_path)
                
                local_videos.append(overlayed_vid_path)
                actual_dur = self.get_video_duration(overlayed_vid_path)
                logger.info(f"Stitcher: Clip {seq} actual duration={actual_dur:.2f}s (requested={dur}s)")
                durations.append(actual_dur)
                
                # Voiceover file (only downloaded if we're not using native audio)
                if not use_native_audio and audio_uri:
                    ext = audio_uri.split('.')[-1].lower() if '.' in audio_uri else 'mp3'
                    local_aud_path = f"/tmp/stitch_aud_{job_id}_{seq}.{ext}"
                    self.storage.download_file(audio_uri, local_aud_path)
                    local_audios.append(local_aud_path)
                else:
                    local_audios.append(None)
            
            # Calculate total duration
            total_duration_sec = int(sum(durations))
            
            # 2. Generate premium Lyria background music score (only if not using native audio)
            if not use_native_audio:
                local_music_path = f"/tmp/stitch_music_{job_id}.wav"
                
                # Fetch product metadata from database to customize background track
                job_data = self.db.get_job(job_id)
                product_meta = job_data.get('product_metadata', {})
                product_name = (
                    product_meta.get('title') or
                    product_meta.get('model_name') or
                    product_meta.get('Title') or
                    product_meta.get('Model Name') or
                    'this tech product'
                )
                brand = product_meta.get('brand') or product_meta.get('Brand') or ''
                
                # Clamp the requested duration to the Lyria API maximum of 60 seconds
                safe_lyria_duration = min(int(total_duration_sec + 2), 60)

                bgm_prompt = "Upbeat instrumental electronic synth track."
                bgm_source = self.generate_lyria_bgm(bgm_prompt, safe_lyria_duration, local_music_path, job_id=job_id, client=client, model_bgm=model_bgm)

            # Define final output path
            output_filename = f"{job_id}_final.mp4"
            local_output_path = os.path.join(LOCAL_STORAGE_DIR, "output", output_filename)
            os.makedirs(os.path.dirname(local_output_path), exist_ok=True)

            # 3. Construct FFmpeg command
            cmd = [self.ffmpeg_exe, "-y"]
            
            # Add video inputs
            for lv in local_videos:
                cmd.extend(["-i", lv])
            
            # Add voiceover and BGM audio inputs only if not using native audio
            if not use_native_audio:
                # Add voiceover audio inputs
                valid_audio_inputs = []
                audio_index_offset = len(local_videos)
                for idx, la in enumerate(local_audios):
                    if la:
                        cmd.extend(["-i", la])
                        valid_audio_inputs.append(audio_index_offset)
                        audio_index_offset += 1
                    else:
                        silent_path = f"/tmp/silent_{job_id}_{idx}.mp3"
                        silence_cmd = [
                            self.ffmpeg_exe, "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:channel_layout=mono",
                            "-t", str(durations[idx]), "-c:a", "libmp3lame", silent_path
                        ]
                        subprocess.run(silence_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        cmd.extend(["-i", silent_path])
                        valid_audio_inputs.append(audio_index_offset)
                        audio_index_offset += 1

                # Add background music input
                bg_music_index = audio_index_offset
                cmd.extend(["-i", local_music_path])

            # 4. Build filter graph
            filter_complex = []
            
            # Video Hard Cuts (Concat) - NO XFADE
            if len(local_videos) > 1:
                if use_native_audio:
                    concat_inputs = "".join([f"[{i}:v][{i}:a]" for i in range(len(local_videos))])
                    filter_complex.append(
                        f"{concat_inputs}concat=n={len(local_videos)}:v=1:a=1[v_concat][a_concat]"
                    )
                    video_map_label = "[v_concat]"
                    audio_map_label = "[a_concat]"
                else:
                    concat_inputs = "".join([f"[{i}:v]" for i in range(len(local_videos))])
                    filter_complex.append(
                        f"{concat_inputs}concat=n={len(local_videos)}:v=1:a=0[v_concat]"
                    )
                    video_map_label = "[v_concat]"
            else:
                video_map_label = "0:v"
                if use_native_audio:
                    audio_map_label = "0:a"

            # Audio processing
            if not use_native_audio:
                # Pad and trim each voiceover input to match exact video clip step duration.
                # This guarantees 100% sequential audio alignment without overlapping voices or timebase discontinuities!
                padded_audio_labels = []
                crossfade_len = 0.2
                for idx, a_idx in enumerate(valid_audio_inputs):
                    pad_label = f"a_pad_{idx}"
                    # Every clip except the last one contributes (duration + 0.2s crossfade)
                    # before the next clip starts crossfading in
                    if idx < len(valid_audio_inputs) - 1:
                        target_dur = durations[idx] + crossfade_len
                    else:
                        target_dur = durations[idx]
                    filter_complex.append(
                        f"[{a_idx}:a]apad,atrim=0:{target_dur:.3f}[{pad_label}]"
                    )
                    padded_audio_labels.append(f"[{pad_label}]")
                
                # Smoothly crossfade the padded voiceover streams to eliminate hard cut pops and noise floor jumps
                last_voice_label = padded_audio_labels[0]
                for i in range(1, len(padded_audio_labels)):
                    next_voice_label = f"voice_blend_{i}"
                    filter_complex.append(
                        f"{last_voice_label}{padded_audio_labels[i]}acrossfade=d={crossfade_len}:c1=tri:c2=tri[{next_voice_label}]"
                    )
                    last_voice_label = f"[{next_voice_label}]"
                
                # Split the final blended voiceover track
                filter_complex.append(
                    f"{last_voice_label}asplit=2[voice_main][voice_sc]"
                )
                # Duck background music using sidechain compression when voiceover speaks, then mix with duration=first so it doesn't cut off video
                filter_complex.append(
                    f"[{bg_music_index}:a]aresample=44100,aformat=channel_layouts=stereo[bgm_norm];"
                    f"[voice_sc]aresample=44100,aformat=channel_layouts=stereo[voice_sc_norm];"
                    f"[bgm_norm][voice_sc_norm]sidechaincompress=threshold=0.15:ratio=3:attack=50:release=300[bgm_ducked]"
                )
                filter_complex.append(
                    f"[voice_main][bgm_ducked]amix=inputs=2:duration=first:weights=1.0 0.8[audio_final]"
                )
                audio_map_label = "[audio_final]"

            # Cinematic Fade Out (2.0 seconds for smooth finish without cutoff)
            final_duration = sum(durations)
            fade_duration = 2.0
            fade_start = max(0.0, final_duration - fade_duration)
            
            filter_complex.append(f"{video_map_label}fade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}[v_fade]")
            filter_complex.append(f"{audio_map_label}afade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}[a_fade]")

            cmd.extend(["-filter_complex", ";".join(filter_complex)])
            cmd.extend(["-map", "[v_fade]", "-map", "[a_fade]"])

            # Map streams and output settings
            cmd.extend([
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                local_output_path
            ])

            logger.info(f"Running FFmpeg crossfade & audio mixing command: {' '.join(cmd)}")
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                logger.error(f"FFmpeg stitching/mixing failed: {result.stderr}")
                raise RuntimeError(f"FFmpeg error: {result.stderr}")
            
            logger.info(f"Successfully stitched and mixed final video for Job {job_id} at {local_output_path}")

            # Upload final mixed video to storage
            bucket_name = INGEST_BUCKET if RUNNING_ON_GCP else "output"
            try:
                self.storage.upload_file(bucket_name, local_output_path, output_filename)
                final_video_uri = f"gs://{bucket_name}/{output_filename}"
                logger.info(f"Final mixed video uploaded to GCS via SDK: {final_video_uri}")
            except Exception as upload_err:
                logger.warning(f"Failed to upload final video to GCS ({upload_err}). Using local file path as fallback URI.")
                final_video_uri = f"file://{local_output_path}"

            # Calculate worker cost
            end_time = time.perf_counter()
            duration = end_time - start_time
            vcpu_sec = duration * 2.0  # 2 vCPUs allocation
            ram_gib_sec = duration * 4.0  # 4 GiB allocation
            
            # Fetch usage metadata
            job_data = self.db.get_job(job_id) or {}
            usage_text = job_data.get("usage_text") or {}
            usage_video = job_data.get("usage_video") or {}
            usage_tts = job_data.get("usage_tts") or {}
            
            usage_metadata = {
                "text_input_tokens": usage_text.get("input_tokens", 0),
                "text_output_tokens": usage_text.get("output_tokens", 0),
                "video_model": usage_video.get("model", "gemini-omni-flash-preview"),
                "video_duration_sec": usage_video.get("video_duration_sec", 0),
                "tts_chars": usage_tts.get("tts_chars", 0),
                "bgm_duration_sec": usage_video.get("video_duration_sec", 0),
                "worker_vcpu_sec": vcpu_sec,
                "worker_ram_gib_sec": ram_gib_sec
            }
            
            billing_service = GCPBillingService()
            gcp_location = job_data.get("gcp_location") or "asia-south1"
            cost_details = billing_service.calculate_job_cost(usage_metadata, gcp_location)

            # Update database to completed
            self.db.update_job(job_id, {
                "status": "COMPLETED",
                "final_video_uri": final_video_uri,
                "bgm_source": bgm_source,
                "cost_breakdown": cost_details
            })

        except Exception as e:
            logger.error(f"Error during stitching/mixing process: {e}")
            self.db.update_job(job_id, {
                "status": "failed",
                "error": f"Stitching/mixing error: {str(e)}"
            })
            raise e
            
        finally:
            # Clean up local temporary video, audio, and silence files
            for lv in local_videos:
                if os.path.exists(lv):
                    os.remove(lv)
            for la in local_audios:
                if la and os.path.exists(la):
                    os.remove(la)
            if 'local_music_path' in locals() and os.path.exists(local_music_path):
                os.remove(local_music_path)
            
            # Clean up any generated silent files or fallback segments
            for idx in range(len(local_videos)):
                silence_temp = f"/tmp/silent_{job_id}_{idx}.mp3"
                if os.path.exists(silence_temp):
                    os.remove(silence_temp)
                
                # Fallback files
                seq = idx + 1
                for f_temp in [
                    f"/tmp/fallback_voice_{job_id}_{seq}.mp3",
                    f"/tmp/fallback_music_{job_id}_{seq}.wav",
                    f"/tmp/mixed_fallback_{job_id}_{seq}.m4a",
                    f"/tmp/overlay_text_{job_id}_{seq}.txt"
                ]:
                    if os.path.exists(f_temp):
                        os.remove(f_temp)

        return {"job_id": job_id, "final_video_uri": final_video_uri}
