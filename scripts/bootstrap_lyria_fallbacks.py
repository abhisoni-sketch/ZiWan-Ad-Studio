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
import sys
import time
import base64
import logging
from google import genai
from google.genai import types

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import PROJECT_ID
from backend.storage_provider import StorageProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_fallback_library():
    storage = StorageProvider()
    bucket_name = f"{PROJECT_ID}-ingest-vault"
    
    client = genai.Client(
        vertexai=True,
        project=PROJECT_ID,
        location="global",
        http_options=types.HttpOptions(headers={"Api-Revision": "2026-05-20"}),
    )

    prompts = [
        "Upbeat electronic tech-house instrumental, clean bass, modern e-commerce.",
        "Warm, deep ambient lo-fi beat, slow tempo, relaxing tech review vibe.",
        "Cinematic synthwave instrumental, driving bassline, futuristic.",
        "Minimalist corporate tech pad, very soft, unobtrusive background music.",
        "Energetic pop-electronic crossover instrumental, bright and inspiring.",
        "Deep sub-bass modern trap instrumental, slow and heavy, no vocals.",
        "Light, airy atmospheric drone with subtle pulsing beats.",
        "Fast-paced futuristic cyberpunk beat, aggressive synths.",
        "Smooth R&B-infused electronic beat, warm chords, relaxed.",
        "Classic premium tech product showcase instrumental, crisp percussion."
    ]

    os.makedirs("/tmp/fallbacks", exist_ok=True)

    for i, prompt in enumerate(prompts):
        track_num = i + 1
        logger.info(f"Generating Track {track_num}/10: '{prompt}'")
        
        try:
            interaction = client.interactions.create(
                model='lyria-3-pro-preview',
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
            
            raw_audio_bytes = None
            if hasattr(interaction, "output_audio") and interaction.output_audio and interaction.output_audio.data:
                raw_audio_bytes = base64.b64decode(interaction.output_audio.data)
            else:
                for step in interaction.steps:
                    step_dict = step.model_dump()
                    if step_dict.get("type") == "model_output" and step_dict.get("content"):
                        parts = step_dict.get("content", {}).get("parts", [])
                        for part in parts:
                            if isinstance(part, dict) and part.get("type") == "audio":
                                raw_audio_bytes = base64.b64decode(part.get("data", ""))
                                break
            
            if not raw_audio_bytes:
                logger.error(f"Failed to extract audio bytes for track {track_num}")
                continue

            local_path = f"/tmp/fallbacks/track_{track_num}.mp3"
            with open(local_path, "wb") as f:
                f.write(raw_audio_bytes)
            
            gcs_filename = f"fallback_bgm/track_{track_num}.mp3"
            uri = storage.upload_file(bucket_name, local_path, gcs_filename)
            logger.info(f"✅ Track {track_num} successfully uploaded to {uri}")
            
            # Sleep to respect rate limits during bootstrapping
            time.sleep(15)
            
        except Exception as e:
            logger.error(f"Error generating track {track_num}: {e}")

    logger.info("Fallback BGM library bootstrap complete!")

if __name__ == "__main__":
    generate_fallback_library()
