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
import logging
from google import genai
from google.genai import types
from backend.config import DEFAULT_MODEL, TOPIC_SEGMENTATION, PROJECT_ID, DEFAULT_LOCATION, get_model_location
from backend.db_provider import DatabaseProvider
from backend.event_broker import EventBroker

logger = logging.getLogger(__name__)

class ScriptingAgent:
    def __init__(self):
        self.db = DatabaseProvider()
        self.broker = EventBroker()
        
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            logger.info("Initializing GenAI client using GEMINI_API_KEY")
            self.client = genai.Client(api_key=api_key)
        else:
            logger.info(f"Initializing GenAI client in Vertex AI mode for project: {PROJECT_ID}")
            loc = get_model_location(DEFAULT_MODEL, DEFAULT_LOCATION)
            self.client = genai.Client(vertexai=True, project=PROJECT_ID, location=loc)

    def run(self, pubsub_payload: dict) -> dict:
        job_id = pubsub_payload['job_id']
        system_instruction = pubsub_payload['system_instruction']
        metadata = pubsub_payload.get('product_metadata', {})
        
        logger.info(f"ScriptingAgent starting for Job {job_id}")
        self.db.update_job(job_id, {"status": "script_generating"})

        prompt = """
Write a 60-second voiceover ad script for the product described.
Follow these constraints strictly:
1. Write in a neutral, informative, and value-focused tone. 
2. You MUST output the script using valid SSML (Speech Synthesis Markup Language).
3. Use <emphasis level="strong"> on key technical specs.
4. Use <break time="500ms"/> between major segment transitions.
5. Use <prosody rate="fast" pitch="+1st"> for exciting features, and neutral prosody for standard specs.
6. OPENING CONSTRAINT: The very first sentence of the script MUST explicitly introduce the product by its full Brand and Model name. Do not start immediately with technical specifications.
7. NEVER read aloud raw alphanumeric product codes, PSNs, or FSNs (like 'WMNH2DJCJASPFZE2') in the voiceover. Use only the clean, human-readable Brand and Model Name.
8. FINALE CONSTRAINT: The script MUST end with a high-impact, professional closing tagline/summary sentence (e.g., 'The [Brand] [Model]. A device focused on [Key Benefit 1], [Key Benefit 2], and [Key Benefit 3].'). DO NOT end the script by listing dry specifications like storage options, RAM options, or color options.
9. SENTENCE LENGTH LIMIT: Each sentence in the script MUST be short and concise, containing a MAXIMUM of 15 words. This is critical to ensure the spoken voiceover fits within the video segment timing without getting cut off.
10. Do not use ANY marketing hyperbole, exclamation marks, or adjectives like 'stunning', 'incredible', 'best', 'game-changing', 'revolutionary'.
11. WORD BUDGET & SENTENCE COUNT (CRITICAL): The entire script MUST contain between 90 and 110 words total (excluding XML tags), structured into strictly 6 to 8 short sentences. You MUST cover all key specifications in the metadata: Product Opening Hook, Display Size & Resolution, Processor Utility, RAM & Storage, Camera Megapixels & Daylight Utility, Battery Capacity & Fast Charging, and a Closing Summary Tagline. This tight word count is STRICTLY REQUIRED so that the total voiceover and transition buffers do not exceed the 60-second limit.
Output ONLY valid SSML starting with <speak> and ending with </speak>.
"""

        import time
        max_retries = 5
        backoff_factor = 2
        initial_delay = 2
        response = None

        try:
            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model=DEFAULT_MODEL,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            temperature=0.2
                        )
                    )
                    break
                except Exception as api_err:
                    err_str = str(api_err).lower()
                    if "429" in err_str or "resource_exhausted" in err_str or "rate" in err_str:
                        delay = initial_delay * (backoff_factor ** attempt)
                        logger.warning(f"ScriptingAgent hit 429 rate limit. Attempt {attempt + 1}/{max_retries}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        raise api_err
            else:
                raise RuntimeError("Failed to generate script after max retries due to rate limit blocks.")
            
            script_text = response.text.strip()
            logger.info(f"ScriptingAgent successfully generated SSML script for Job {job_id}")
            
        except Exception as e:
            logger.warning(f"Gemini client generation failed: {e}. Triggering local scripting fallback.")
            
            # Local Scripting Fallback
            brand = metadata.get('brand', 'Product')
            model = metadata.get('model_name', 'Model')
            display = metadata.get('new_display_size', 'standard display')
            res = metadata.get('display_description', 'clear')
            ram = metadata.get('ram', 'sufficient RAM')
            ram_imp = metadata.get('ram_implications', 'switching apps smoothly')
            storage = metadata.get('internal_storage', 'adequate storage')
            processor = metadata.get('processor_name', 'powerful processor')
            proc_imp = metadata.get('processor_implication', 'smooth operation')
            camera = metadata.get('primary_camera_megapixel', 'high-definition')
            cam_imp = metadata.get('camera_implication_01', 'steady video recording')
            battery = metadata.get('battery_capacity', 'long-lasting')
            bat_imp = metadata.get('battery_implication', 'extended runtime')
            fast_charge = metadata.get('fast_charging', 'quick charge capabilities')
            
            script_text = (
                f"<speak>"
                f"The <emphasis level='strong'>{brand} {model}</emphasis> features a high quality <emphasis level='strong'>{display}</emphasis> screen. "
                f"The device delivers a crisp resolution of {res} for clear media viewing. <break time='500ms'/>"
                f"Equipped with a {processor}, it enables {proc_imp} during intensive tasks. "
                f"The system includes <emphasis level='strong'>{ram}</emphasis> which allows {ram_imp} without lag. "
                f"You also get <emphasis level='strong'>{storage}</emphasis> of internal storage for all your files. <break time='500ms'/>"
                f"<prosody rate='fast' pitch='+1st'>For visual capture, the <emphasis level='strong'>{camera}</emphasis> main camera enables {cam_imp} in daylight.</prosody> <break time='500ms'/>"
                f"Power is supplied by a <emphasis level='strong'>{battery}</emphasis> battery, supporting {bat_imp} and {fast_charge}. "
                f"The {brand} {model} is a reliable device focused on display, performance, and battery utility."
                f"</speak>"
            )
            logger.info(f"Mock SSML script generated successfully: {script_text}")

        # Update payload
        pubsub_payload['script'] = script_text

        # Update database state
        self.db.update_job(job_id, {
            "status": "script_generated",
            "script": script_text
        })

        # Publish to topic-segmentation
        logger.info(f"ScriptingAgent success. Publishing to {TOPIC_SEGMENTATION}")
        self.broker.publish(TOPIC_SEGMENTATION, pubsub_payload)

        return pubsub_payload
