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
import base64
import glob
import shutil
import subprocess
import logging
import imageio_ffmpeg
from google import genai
from google.genai import types
from backend.config import USE_REAL_GCS_AND_MODELS, TOPIC_VERIFICATION, LOCAL_STORAGE_DIR, PROJECT_ID, BASE_DIR, PRODUCT_ALIASES
from backend.storage_provider import StorageProvider
from backend.db_provider import DatabaseProvider
from backend.event_broker import EventBroker

logger = logging.getLogger(__name__)

class GenerationAgent:
    def __init__(self):
        self.storage = StorageProvider()
        self.db = DatabaseProvider()
        self.broker = EventBroker()
        
        # Prioritize system ffmpeg (which supports libfreetype/drawtext) over package-embedded static binary
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            logger.info(f"Using system-installed FFmpeg binary at: {system_ffmpeg}")
            self.ffmpeg_exe = system_ffmpeg
        else:
            logger.warning("System-installed FFmpeg not found. Falling back to imageio_ffmpeg static binary.")
            self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Instantiate Gemini client (supports Developer API Key or GCP ADC)
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = genai.Client(vertexai=True, project=PROJECT_ID, location="us-central1")

    def find_product_image_folder(self, base_path: str, target_psn: str) -> str:
        """Finds the directory matching target_psn recursively, supporting product aliases and prefix fallbacks."""
        target = target_psn.strip().upper()
        
        # 1. Direct match
        for root, dirs, files in os.walk(base_path):
            for d in dirs:
                if d.strip().upper() == target:
                    return os.path.join(root, d)
                    
        # 2. Dynamic product catalog anomaly alias mapping
        aliases = PRODUCT_ALIASES
        
        if target in aliases:
            fallback = aliases[target]
            logger.info(f"Using product alias fallback mapping: {target} -> {fallback}")
            for root, dirs, files in os.walk(base_path):
                for d in dirs:
                    if d.strip().upper() == fallback:
                        return os.path.join(root, d)
                        
        # 3. Prefix match fallback (first 4 characters)
        prefix = target[:4]
        for root, dirs, files in os.walk(base_path):
            for d in dirs:
                if d.strip().upper().startswith(prefix):
                    logger.info(f"Using prefix match fallback for {target_psn}: matched folder {d}")
                    return os.path.join(root, d)
                    
        return None

    def make_mock_video_clip(self, image_path: str, duration: int, seq: int, output_path: str):
        """Uses FFmpeg zoompan filter to generate a cinematic panning/zooming clip from a static image."""
        logger.info(f"Generating mock clip with cinematic motion from image {image_path} (Seq: {seq}, Duration: {duration}s)")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        fps = 25
        total_frames = duration * fps
        
        # Scale to 1920x1080 first to provide extra pixels for smooth zoom/pan motions
        scale_in = "scale=1920:1080"
        
        # Apply different motion effects depending on clip sequence
        if seq == 1:
            # Slow Zoom In (z goes from 1.0 to 1.15)
            filter_str = f"{scale_in},zoompan=z='1.0+0.15*(on/{total_frames})':x='iw/2-ow/2':y='ih/2-oh/2':d={total_frames},scale=1280:720"
        elif seq == 2:
            # Slow Pan Left to Right (x shifts across cropped zoomed boundary)
            filter_str = f"{scale_in},zoompan=z='1.15':x='(iw-ow)*(on/{total_frames})':y='ih/2-oh/2':d={total_frames},scale=1280:720"
        elif seq == 3:
            # Slow Pan Top to Bottom (y shifts vertically)
            filter_str = f"{scale_in},zoompan=z='1.15':x='iw/2-ow/2':y='(ih-oh)*(on/{total_frames})':d={total_frames},scale=1280:720"
        else:
            # Slow Zoom Out (z goes from 1.15 down to 1.0)
            filter_str = f"{scale_in},zoompan=z='1.15-0.15*(on/{total_frames})':x='iw/2-ow/2':y='ih/2-oh/2':d={total_frames},scale=1280:720"

        cmd = [
            self.ffmpeg_exe,
            "-y",
            "-loop", "1",
            "-i", image_path,
            "-c:v", "libx264",
            "-t", str(duration),
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            "-vf", filter_str,
            output_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            logger.error(f"FFmpeg zoompan error: {result.stderr}")
            raise RuntimeError(f"FFmpeg zoompan failed: {result.stderr}")

    def create_image_collage(self, image_paths: list[str], output_path: str):
        """Creates a side-by-side collage of the input images."""
        from PIL import Image
        logger.info(f"Creating collage for images: {image_paths} -> {output_path}")
        try:
            images = [Image.open(p) for p in image_paths]
            widths, heights = zip(*(i.size for i in images))
            
            total_width = sum(widths)
            max_height = max(heights)
            
            new_img = Image.new('RGB', (total_width, max_height), (255, 255, 255))
            x_offset = 0
            for im in images:
                if im.height != max_height:
                    im = im.resize((int(im.width * max_height / im.height), max_height))
                new_img.paste(im, (x_offset, 0))
                x_offset += im.width
            new_img.save(output_path)
        except Exception as e:
            logger.error(f"Failed to create image collage: {e}")

    def generate_voiceover(self, text: str, output_path: str, voice_name: str = None, language_code: str = None):
        """Generates voiceover audio file using Gemini 3.1 Flash TTS, Google Cloud Text-to-Speech, or local gTTS fallback."""
        logger.info(f"Generating voiceover audio for: '{text}' (Voice: {voice_name}, Lang: {language_code})")
        
        is_gemini_tts = voice_name and "chirp" not in voice_name.lower()
        
        if USE_REAL_GCS_AND_MODELS:
            if is_gemini_tts:
                try:
                    from google.genai import types
                    import wave
                    import re
                    # Strip out XML tags since Gemini TTS parses emotion/tone directives from natural language prompts
                    clean_text = re.sub(r'<[^>]+>', '', text)
                    lang_instruction = "Read the following text in a natural, professional English (India) accent: " if (language_code and "in" in language_code.lower()) else ""
                    prompt_payload = f"{lang_instruction}{clean_text}"
                    logger.info(f"Calling gemini-3.1-flash-tts-preview with voice {voice_name} and prompt: '{prompt_payload}'")
                    
                    response = self.client.models.generate_content(
                        model="gemini-3.1-flash-tts-preview",
                        contents=prompt_payload,
                        config=types.GenerateContentConfig(
                            response_modalities=["AUDIO"],
                            speech_config=types.SpeechConfig(
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=voice_name,
                                    )
                                )
                            ),
                        )
                    )
                    audio_data = response.candidates[0].content.parts[0].inline_data.data
                    
                    # Save raw PCM binary audio data as a valid WAV file (24kHz, 1-channel, 16-bit)
                    with wave.open(output_path, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(audio_data)
                        
                    logger.info(f"Gemini 3.1 Flash TTS generated successfully at {output_path}")
                    return
                except Exception as e:
                    logger.warning(f"Gemini 3.1 Flash TTS failed: {e}. Falling back to GCP Cloud TTS...")

            try:
                from google.cloud import texttospeech
                client = texttospeech.TextToSpeechClient()
                
                # If text contains XML/SSML tags, pass as ssml= so tags are parsed (for emphasis, pitch, rate) instead of spoken literally!
                if "<" in text and ">" in text:
                    ssml_payload = text if text.strip().startswith("<speak>") else f"<speak>{text}</speak>"
                    synthesis_input = texttospeech.SynthesisInput(ssml=ssml_payload)
                else:
                    synthesis_input = texttospeech.SynthesisInput(text=text)
                
                voice = texttospeech.VoiceSelectionParams(
                    language_code=language_code or "en-US",
                    name=voice_name or "en-US-Journey-F"
                )
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.MP3
                )
                
                response = client.synthesize_speech(
                    input=synthesis_input, voice=voice, audio_config=audio_config
                )
                
                with open(output_path, "wb") as out:
                    out.write(response.audio_content)
                logger.info(f"GCP TTS generated successfully at {output_path}")
                return
            except Exception as e:
                logger.warning(f"GCP TTS API call failed: {e}. Falling back to gTTS.")
                
        try:
            from gtts import gTTS
            import re
            # Clean out any XML/SSML tags if falling back to gTTS which only supports plain text
            clean_text = re.sub(r'<[^>]+>', '', text)
            tts = gTTS(text=clean_text, lang='en', slow=False)
            tts.save(output_path)
            logger.info(f"gTTS generated successfully at {output_path}")
        except Exception as e:
            logger.error(f"gTTS library call failed: {e}. Generating silent fallback audio.")
            cmd = [
                self.ffmpeg_exe,
                "-y",
                "-f", "lavfi",
                "-i", "anullsrc=r=22050:c=1",
                "-t", "5",
                "-c:a", "libmp3lame",
                output_path
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.warning(f"Created silent fallback audio at {output_path}")

    def get_media_duration(self, path: str) -> float:
        """Query FFmpeg to extract actual media duration in seconds."""
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
            logger.error(f"Error getting media duration: {e}")
        return 4.0

    def run_gcp_generation(self, visual_prompt: str, image_gcs_uris: list[str], duration: int, model_target: str, image_analyses: dict = None, best_front_image: str = None) -> bytes:
        """Calls the real Vertex AI Video API to generate video bytes."""
        logger.info(f"Calling Google GenAI Video API. Model: {model_target}, Prompt: {visual_prompt}")
        try:
            import time
            max_retries = 5
            backoff_factor = 2
            initial_delay = 10
            
            for attempt in range(max_retries):
                try:
                    if "omni" in model_target.lower():
                        logger.info(f"Using Omni Video client for model: {model_target}")
                        omni_client = genai.Client(
                            vertexai=True,
                            project=PROJECT_ID,
                            location="global",
                            http_options=types.HttpOptions(headers={"Api-Revision": "2026-05-20"}, timeout=600000),
                        )
                
                        # Build multimodal input data list WITH LABELS from pre-deduplicated image list
                        input_data = []
                        # Build deduplicated_uris from image_gcs_uris and image_analyses
                        deduplicated_uris = []
                        for uri in image_gcs_uris:
                            if uri.startswith("gs://"):
                                fname = os.path.basename(uri)
                                lookup_key = fname
                                if "_" in fname:
                                    parts = fname.split("_", 1)
                                    if len(parts) > 1:
                                        lookup_key = parts[1]
                                
                                view_type = "PRODUCT"
                                if image_analyses and lookup_key in image_analyses:
                                    analysis = image_analyses[lookup_key]
                                    if isinstance(analysis, dict):
                                        view_type = analysis.get("view_type", "PRODUCT").upper()
                                    elif isinstance(analysis, str):
                                        view_type = analysis.upper()
                                deduplicated_uris.append((uri, view_type))

                        # Dynamically construct payload and strict mapping instructions based on whatever labels the ContextAgent assigned
                        input_data = []
                        mapping_instructions = []
                        image_index = 0

                        for uri, view_type in deduplicated_uris:
                            ext = uri.lower()
                            mime_type = "image/png" if ext.endswith(".png") else "image/jpeg"
                    
                            input_data.append({"type": "image", "uri": uri, "mime_type": mime_type})
                            mapping_instructions.append(f"- Image {image_index} is the {view_type} view of the product.")
                            image_index += 1

                        mapping_text = "\n".join(mapping_instructions)

                        # Append strict, streamlined guardrails with the dynamic index map
                        final_prompt = (
                            f"{visual_prompt}\n\n"
                            "CRITICAL DIRECTIVE: You MUST dynamically generate the specific environment and visual contents requested in the prompt above. Prioritize the text description over any static background from the reference images.\n"
                            "ANTI-BLEED GUARDRAIL: Do NOT render any typography, floating text, or labels. (Animated media and UI on the device screen IS allowed). Ignore promotional text from reference images.\n"
                            "BRAND FIDELITY: The product MUST be exclusively the item depicted. DO NOT hallucinate competitor logos.\n"
                            "SINGLE PRODUCT GUARANTEE: EXACTLY ONE product visible. NO stacked products.\n"
                            "SPATIAL ISOLATION MAPPING:\n"
                            f"{mapping_text}\n"
                            "Use this exact index mapping to understand the 3D geometry of the product. Never blend features from the FRONT view onto the REAR view."
                        )
                
                        # The final item in the payload array
                        input_data.append({
                            "type": "text",
                            "text": final_prompt
                        })
                
                        logger.info("Calling omni_client.interactions.create...")
                        interaction = omni_client.interactions.create(
                            model=model_target,
                            input=input_data,
                            generation_config={
                                "safety_settings": [
                                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}
                                ]
                            },
                            response_format={
                                "type": "video",
                                "aspect_ratio": "16:9",
                                "duration": f"{duration}s"
                            },
                            timeout=600
                        )
                
                        logger.info("Extracting video bytes from Omni interaction steps...")
                        raw_video_bytes = None
                        for step in interaction.steps:
                            step_dict = step.model_dump()
                            if step_dict.get("type") == "model_output" and step_dict.get("content"):
                                parts = step_dict["content"]
                                if isinstance(parts, dict) and "parts" in parts:
                                    parts = parts["parts"]
                        
                                if isinstance(parts, list):
                                    for part in parts:
                                        if isinstance(part, dict) and part.get("type") == "video":
                                             video_b64 = part.get("data")
                                             if video_b64:
                                                 raw_video_bytes = base64.b64decode(video_b64)
                                                 break
                        if not raw_video_bytes:
                            raise ValueError("No video bytes found in Omni response steps.")
                        return raw_video_bytes
                    else:
                        config_params = {
                            "duration_seconds": duration,
                            "aspect_ratio": "16:9",
                            "number_of_videos": 1
                        }
                
                        if image_gcs_uris:
                            ref_images = []
                            for uri in image_gcs_uris:
                                if uri.startswith("gs://"):
                                    ext = uri.lower()
                                    mime_type = "image/png" if ext.endswith(".png") else "image/jpeg"
                                    ref_image = types.VideoGenerationReferenceImage(
                                        image=types.Image(gcs_uri=uri, mime_type=mime_type),
                                        reference_type="ASSET"
                                    )
                                    ref_images.append(ref_image)
                            if ref_images:
                                config_params["reference_images"] = ref_images

                        operation = self.client.models.generate_videos(
                            model=model_target,
                            prompt=visual_prompt,
                            config=types.GenerateVideosConfig(**config_params)
                        )
                
                        logger.info("Operation started. Polling status...")
                        import time
                        while not operation.done:
                            time.sleep(10)
                            operation = self.client.operations.get(operation)
                            logger.info("Polling video generation status...")
                    
                        result = operation.result
                        if result and result.generated_videos:
                            video_bytes = result.generated_videos[0].video.video_bytes
                            logger.info("Video generation completed successfully.")
                            return video_bytes
                        else:
                            raise RuntimeError("No videos returned from API.")
                    
                except Exception as api_err:
                    err_str = str(api_err).lower()
                    if "429" in err_str or "resource_exhausted" in err_str or "rate" in err_str or "quota" in err_str:
                        delay = initial_delay * (backoff_factor ** attempt)
                        logger.warning(f"Video API hit 429 Quota Limit. Attempt {attempt + 1}/{max_retries}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        # If it's a structural error (like bad parameters), don't retry, just fail
                        raise api_err
            else:
                raise RuntimeError("Failed to generate video after max retries due to quota limits.")
        except Exception as e:
            logger.error(f"Error during video generation API call: {e}")
            raise e

    def run(self, pubsub_payload: dict) -> dict:
        job_id = pubsub_payload['job_id']
        segments = pubsub_payload['segments']
        image_analyses = pubsub_payload.get('image_analyses', {})
        best_front_image = pubsub_payload.get('best_front_image')
        model_target = pubsub_payload.get('model_target', 'veo-2.0-generate-001')
        psn = pubsub_payload['psn']
        voice_name = pubsub_payload.get('voice_name') or "Puck"
        language_code = pubsub_payload.get('language_code') or "en-IN"
        
        logger.info(f"GenerationAgent starting for Job {job_id}. Processing {len(segments)} segments. Voice: {voice_name}, Lang: {language_code}")
        self.db.update_job(job_id, {"status": "generating_clips"})

        # Scan the parent ProductData folder recursively for reference images
        image_base_dir = os.path.join(BASE_DIR, "ProductData")
        product_img_folder = self.find_product_image_folder(image_base_dir, psn)
        
        if product_img_folder:
            logger.info(f"Found product image folder: {product_img_folder}")
            extensions = ('*.png', '*.jpg', '*.jpeg', '*.webp')
            product_images = []
            for ext in extensions:
                product_images.extend(glob.glob(os.path.join(product_img_folder, ext)))
            product_images.sort()
        else:
            logger.warning(f"Product image folder not found for PSN {psn}. Fallback mock images will be empty.")
            product_images = []

        logger.info(f"Using {len(product_images)} raw product images for individual segment conditioning.")

        generated_clips = []

        for idx, seg in enumerate(segments):
            seq = seg['clip_sequence']
            dur = seg['duration']
            prompt = seg['visual_prompt']
            raw_prompt_lower = prompt.lower() if prompt else ""
            vo_text = seg['voiceover_script']
            
            # Globally replace "mAh" or "mah" (with or without spaces) with "milliamp-hours" to bypass Vertex resolution parser
            if prompt:
                prompt = prompt.replace(" mAh", " milliamp-hours").replace("mAh", "milliamp-hours").replace(" mah", " milliamp-hours").replace("mah", "milliamp-hours").replace("7200", "7,200")
            if vo_text:
                vo_text = vo_text.replace(" mAh", " milliamp-hours").replace("mAh", "milliamp-hours").replace(" mah", " milliamp-hours").replace("mah", "milliamp-hours").replace("7200", "seven thousand two hundred")
            
            is_omni = "omni" in model_target.lower()
            text_overlay = seg.get('text_overlay', '')
            if text_overlay:
                text_overlay = text_overlay.replace(" mAh", "mAh").replace(" mah", "mah").replace("7200", "7,200")
            force_tts = True
            if is_omni and not force_tts:
                if vo_text:
                    prompt += (
                        f"\n\nVOICEOVER: The video must contain a native voiceover track speaking the following script: '{vo_text}'."
                        f"\nVOICEOVER DIRECTIVE: The voiceover must be highly expressive, natural, and engaging (like a professional product ad campaign voice actor). "
                        "Use proper inflections, dramatic emphasis on key specs, and clear pronunciation. Avoid a robotic, monotone, or flat tone."
                        f"\nVOICEOVER PERSONA CONTINUITY (CRITICAL): You MUST use the EXACT same voice actor persona across EVERY scene in this advertisement: a warm, authoritative, professional 35-year-old male American voice actor with a deep commercial timbre. DO NOT switch gender to female, DO NOT change speaker identity, vocal tone, or accent."
                    )
                if text_overlay:
                    clean_overlay = text_overlay.upper().replace("MAH", "Milliamp-Hours").replace("7200", "7,200")
                    prompt += (
                        f"\n\nNATIVE TEXT OVERLAY (CRITICAL): Draw a native, creative text overlay/callout in the frame that says: '{clean_overlay}'."
                        " The text should be styled beautifully in a clean, modern, high-contrast sans-serif font. Stack multiple words vertically if necessary to prevent cropping. "
                        "Position it elegantly at the bottom-center or side-middle of the screen, ensuring it aligns perfectly with the visual elements of this segment."
                    )
                prompt += (
                    f"\n\nBGM DIRECTIVE: The background music track must be a premium, high-fidelity, upbeat modern electronic tech-product showcase instrumental beat (clean bass synths, warm pads, e-commerce tech-house groove). "
                    "Strictly instrumental, no lyrics, no vocals, only the background music track running continuously under the voiceover."
                )
                prompt += (
                    f"\n\nSYNCHRONICITY CONSTRAINT: The video action, the spoken voiceover words, and the native text overlay must be perfectly synchronized. "
                    "When the voiceover mentions a specific feature (e.g. display size, processor, battery capacity), that exact feature must be actively highlighted in the visuals at that moment, and the text overlay must render the matching feature name simultaneously."
                )

            # Add dynamic anti-hallucination guardrail to prevent competitor logos and multiple stacked products
            product_metadata = pubsub_payload.get('product_metadata', {})
            prod_brand = product_metadata.get("brand") or "the reference brand"
            
            # Extract product model or series name
            prod_name = product_metadata.get("model_name")
            if not prod_name or prod_name.lower() == "n/a":
                prod_name = product_metadata.get("series") or "product"
            
            # Determine product type noun based on unique specification attributes
            item_noun = "product"
            specs_lower = {k.lower(): v for k, v in product_metadata.items()}
            if "display technology" in specs_lower or "size (inches)" in specs_lower:
                item_noun = "television"
            elif "capacity (in tonnes)" in specs_lower:
                item_noun = "air conditioner"
            elif "washing type" in specs_lower or "rpm" in specs_lower:
                item_noun = "washing machine"
            elif "headset_design" in specs_lower:
                item_noun = "headphones"
            elif "displacement" in specs_lower or "engine_technology" in specs_lower:
                item_noun = "bike"
            elif "processor_name" in specs_lower or "series" in specs_lower:
                item_noun = "laptop"
            elif "primary_camera_megapixel" in specs_lower or "internal_storage" in specs_lower:
                item_noun = "phone"
                
            # Removed Brand Fidelity prompt appendage to avoid contradiction with interleaving payload
            
            logger.info(f"Processing segment {seq}/{len(segments)} (Duration: {dur}s)")
            
            clip_filename = f"{job_id}_clip_{seq}.mp4"
            # Use wav extension for Gemini 3.1 TTS (since it generates raw PCM), mp3 for others
            voice_ext = "wav" if (voice_name and "chirp" not in voice_name.lower()) else "mp3"
            voice_filename = f"{job_id}_voice_{seq}.{voice_ext}"
            
            local_clip_path = os.path.join(LOCAL_STORAGE_DIR, "temp_clips", job_id, clip_filename)
            local_voice_path = os.path.join(LOCAL_STORAGE_DIR, "temp_clips", job_id, voice_filename)
            os.makedirs(os.path.dirname(local_clip_path), exist_ok=True)
            
            # Determine GCS URIs for all clean reference images with intelligent deduplication
            clean_image_uris = []
            clean_image_labels = []
            selected_img = ""
            
            if product_images:
                category_tab = pubsub_payload.get('category_tab', '').lower()
                rule_id = pubsub_payload.get('rule_id', '').lower()
                product_metadata = pubsub_payload.get('product_metadata', {})
                is_known_flat = any(x in category_tab for x in ['mobile', 'phone', 'tv', 'television']) or any(x in rule_id for x in ['mobile', 'phone', 'tv', 'television'])
                is_ai_detected_flat = (product_metadata.get('physical_form_factor') == 'FLAT_PANEL_DISPLAY')
                is_flat_product = is_known_flat or is_ai_detected_flat
                
                # Group valid images by dynamic view (NEVER allow multiple devices)
                from collections import defaultdict
                view_pools = defaultdict(list)
                
                path_lookup = {os.path.basename(p): p for p in product_images}
                
                for filename, analysis in image_analyses.items():
                    if filename not in path_lookup:
                        continue
                    if not isinstance(analysis, dict):
                        continue
                    if analysis.get("has_multiple_devices", True):
                        continue # Strictly ban multiple devices
                        
                    # Use whatever dynamic view_type was assigned by ContextAgent
                    vt = analysis.get("view_type", "OTHER").upper()
                    
                    if is_flat_product:
                        # Chimera prevention: restrict mapping
                        if vt not in ["FRONT", "BACK"]:
                            vt = "OTHER"
                            
                    view_pools[vt].append({
                        "filename": filename,
                        "is_clean": analysis.get("is_clean_product_shot", False),
                        "text_density": analysis.get("text_density_score", 100)
                    })

                # Priority 1: Clean | Priority 2: Lowest Text Density (Fallback)
                deduplicated_images = []
                for vt, images in view_pools.items():
                    if not images:
                        continue # No images available for this view
                        
                    if is_flat_product and vt == "OTHER":
                        # Empty Slot Enforcer for dangerous flat surfaces
                        clean_images = [img for img in images if img["is_clean"]]
                        if not clean_images:
                            continue
                        images = clean_images
                        
                    # Sort so Priority 1 (is_clean=True) comes first, followed by the lowest text density
                    images.sort(key=lambda x: (x["is_clean"], -x["text_density"]), reverse=True)
                    
                    # RELAXED ENFORCER: We accept infographic-heavy e-commerce images if they are the only representation
                    # of a critical surface (like an outdoor compressor). The ANTI-BLEED prompt guardrail will handle text scrubbing.
                    best_image = images[0]["filename"]
                    img_path = path_lookup[best_image]
                    deduplicated_images.append((img_path, best_image, vt))


                # 3. Upload deduplicated images to GCS and populate clean_image_uris / clean_image_labels
                for img_path, fname, view_type in deduplicated_images:
                    if not selected_img:
                        selected_img = img_path
                    ref_img_filename = f"reference_images/{psn}_{fname}"
                    bucket_name = f"{PROJECT_ID}-ingest-vault"
                    try:
                        uri = self.storage.upload_file(bucket_name, img_path, ref_img_filename)
                        clean_image_uris.append(uri)
                        clean_image_labels.append((len(clean_image_uris) - 1, view_type))
                    except Exception as upload_err:
                        logger.warning(f"Failed to upload reference image to GCS: {upload_err}")
                
                if not clean_image_uris:
                    img_idx = (seq - 1) % len(product_images)
                    selected_img = product_images[img_idx]
                    ref_img_filename = f"reference_images/{psn}_{os.path.basename(selected_img)}"
                    bucket_name = f"{PROJECT_ID}-ingest-vault"
                    try:
                        uri = self.storage.upload_file(bucket_name, selected_img, ref_img_filename)
                        clean_image_uris.append(uri)
                    except Exception as upload_err:
                        logger.warning(f"Failed to upload fallback image to GCS: {upload_err}")

            # If it is the first or last segment, ensure the video starts/ends with the best front image
            best_front_idx = None
            if product_images and clean_image_uris and best_front_image:
                for idx, img_path in enumerate(product_images):
                    fname = os.path.basename(img_path)
                    if fname == best_front_image:
                        ref_img_filename = f"reference_images/{psn}_{fname}"
                        bucket_name = f"{PROJECT_ID}-ingest-vault"
                        expected_uri = f"gs://{bucket_name}/{ref_img_filename}"
                        if expected_uri in clean_image_uris:
                            best_front_idx = clean_image_uris.index(expected_uri)
                        
                        # Override representative selected_img for mock generation fallback
                        if seq == 1 or seq == len(segments):
                            selected_img = img_path
                        break

            # Removed Reference Images Configuration prompt appendage to avoid contradiction with interleaving payload


            # Generate voiceover audio track first to determine dynamic video duration (Option 1)
            voice_duration = float(dur)
            if not is_omni or force_tts:
                try:
                    self.generate_voiceover(vo_text, local_voice_path, voice_name=voice_name, language_code=language_code)
                    if os.path.exists(local_voice_path):
                        voice_duration = self.get_media_duration(local_voice_path)
                        logger.info(f"Segment {seq}: Measured actual voiceover duration = {voice_duration:.2f}s")
                except Exception as e:
                    logger.error(f"Audio generation failed: {e}")

            # Option 1: Adjust visual video clip duration dynamically to cover voiceover + crossfade buffer
            import math
            # Add 1.0s buffer for breathing space and transition crossfade
            dur = int(math.ceil(voice_duration + 1.0))
            # Clamp between 3 and 10 seconds (Gemini Omni API limits)
            dur = max(3, min(10, dur))
            logger.info(f"Segment {seq}: Dynamic visual duration set to {dur}s (voiceover={voice_duration:.2f}s)")

            video_success = False
            
            if USE_REAL_GCS_AND_MODELS:
                try:
                    actual_model = "veo-2.0-generate-001" if ("veo" not in model_target.lower() and "omni" not in model_target.lower()) else model_target
                    video_bytes = self.run_gcp_generation(prompt, clean_image_uris, dur, actual_model, image_analyses, best_front_image)
                    with open(local_clip_path, "wb") as f:
                        f.write(video_bytes)
                    video_success = True
                except Exception as e:
                    logger.warning(f"Real Video Gen API failed: {e}. Falling back to mock generation.")
            
            # Local FFmpeg fallback
            if not video_success:
                if selected_img:
                    try:
                        self.make_mock_video_clip(selected_img, dur, seq, local_clip_path)
                        video_success = True
                    except Exception as e:
                        logger.error(f"Failed to generate mock video clip: {e}")
                else:
                    logger.error(f"No product images available for mock generation.")
            
            if not video_success:
                self.db.update_job(job_id, {"status": "failed", "error": f"Failed to generate clip sequence {seq}"})
                raise RuntimeError(f"Could not generate video clip for sequence {seq}")

            bucket_name_clips = f"{PROJECT_ID}-ingest-vault" if USE_REAL_GCS_AND_MODELS else "clips"
            video_uri = self.storage.upload_file(bucket_name_clips, local_clip_path, clip_filename)
            
            audio_uri = ""
            if os.path.exists(local_voice_path):
                audio_uri = self.storage.upload_file(bucket_name_clips, local_voice_path, voice_filename)
                
            logger.info(f"Uploaded clip {seq}. Video URI: {video_uri}, Audio URI: {audio_uri}")
            
            generated_clips.append({
                "clip_sequence": seq,
                "duration": dur,
                "visual_prompt": prompt,
                "voiceover_script": vo_text,
                "text_overlay": seg.get("text_overlay", ""),
                "gcs_uri": video_uri,
                "audio_gcs_uri": audio_uri,
                "reference_image_gcs_uri": clean_image_uris[0] if clean_image_uris else ""
            })
            
            if os.path.exists(local_clip_path):
                os.remove(local_clip_path)
            if os.path.exists(local_voice_path):
                os.remove(local_voice_path)

        pubsub_payload['clips'] = generated_clips

        self.db.update_job(job_id, {
            "status": "clips_generated",
            "clips": generated_clips
        })

        # Clean up any generated collage files
        for i in range(1, 3):
            c_path = f"/tmp/collage_{job_id}_{i}.jpg"
            if os.path.exists(c_path):
                os.remove(c_path)

        # Clean up job-specific temp clips directory
        job_dir = os.path.join(LOCAL_STORAGE_DIR, "temp_clips", job_id)
        if os.path.exists(job_dir):
            try:
                os.rmdir(job_dir)
            except Exception as rmdir_err:
                logger.warning(f"Could not remove temp clips job directory: {rmdir_err}")

        logger.info(f"GenerationAgent success. Publishing to {TOPIC_VERIFICATION}")
        self.broker.publish(TOPIC_VERIFICATION, pubsub_payload)

        return pubsub_payload
