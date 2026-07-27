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
import json
import logging
from typing import List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from backend.config import DEFAULT_MODEL, TOPIC_GENERATION, PROJECT_ID, DEFAULT_LOCATION
from backend.db_provider import DatabaseProvider
from backend.event_broker import EventBroker

logger = logging.getLogger(__name__)

class VideoSegment(BaseModel):
    clip_sequence: int = Field(..., description="The sequential number of the clip, starting from 1.")
    duration: int = Field(..., description="The duration of the clip in seconds.")
    visual_prompt: str = Field(..., description="Detailed description of the product scene. Must include camera motion (e.g. pan, zoom) and lighting details. Must connect motion smoothly with the previous clip.")
    voiceover_script: str = Field(..., description="The text of the voiceover that aligns with this clip.")
    text_overlay: str = Field(..., description="Short highlight text (max 4 words). EXCEPTION: For the final segment ONLY, this MUST be a multiline summary of the brand and 5 salient features, using '\\n' for line breaks.")

class SegmentationResponse(BaseModel):
    segments: List[VideoSegment]

class SegmentationAgent:
    def __init__(self):
        self.db = DatabaseProvider()
        self.broker = EventBroker()
        
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            from backend.config import get_model_location
            loc = get_model_location(DEFAULT_MODEL, DEFAULT_LOCATION)
            self.client = genai.Client(vertexai=True, project=PROJECT_ID, location=loc)

    def run(self, pubsub_payload: dict) -> dict:
        job_id = pubsub_payload['job_id']
        script = pubsub_payload['script']
        model_target = pubsub_payload.get('model_target', 'gemini-omni-flash-preview')
        metadata = pubsub_payload.get('product_metadata', {})
        video_cues = metadata.get('video_cues', [])

        category_rules = pubsub_payload.get('category_rules', {})
        seg_rules = category_rules.get('segmentation_rules', {})
        
        # SMART CHIMERA PREVENTION
        category_tab = pubsub_payload.get('category_tab', '').lower()
        rule_id = pubsub_payload.get('rule_id', '').lower()
        
        # Hybrid Safety Net: Guarantees 0% regression for existing products while auto-detecting new display categories
        is_known_flat = any(x in category_tab for x in ['mobile', 'phone', 'tv', 'television']) or any(x in rule_id for x in ['mobile', 'phone', 'tv', 'television'])
        is_ai_detected_flat = (metadata.get('physical_form_factor') == 'FLAT_PANEL_DISPLAY')
        is_flat_product = is_known_flat or is_ai_detected_flat
        
        raw_allowed_physics = seg_rules.get('allowed_camera_physics', ["Slow push-in", "Static premium hero shot"])
        if is_flat_product:
            raw_allowed_physics = ["Slow linear push-in", "Static premium hero shot"]
            
        allowed_physics = ", ".join(raw_allowed_physics)
        bookends = seg_rules.get('compositional_bookends', {})
        first_segment_rule = bookends.get('first_segment', "Static premium hero shot of the full front display/face")
        last_segment_rule = bookends.get('last_segment', "Static premium hero shot of the full front display/face")
        
        # Detect model target requirements
        is_fast_model = "fast" in model_target.lower() or "veo-3" in model_target.lower() or "omni" in model_target.lower()
        max_duration = 8 if is_fast_model else 10
        
        logger.info(f"SegmentationAgent starting for Job {job_id}. Target model: {model_target} (Fast model: {is_fast_model})")
        self.db.update_job(job_id, {"status": "segments_creating"})

        # Build cues context with sanitization
        cues_text = ""
        if video_cues:
            cues_text = "\nUse these guidelines/cues provided for the product segments:\n"
            cues_text += "CRITICAL: If the cues below request a 360, 180, or 90 degree rotation, you MUST IGNORE THAT and use a 'slow push-in' instead to protect the video geometry.\n"
            for c in video_cues:
                # Sanitize dangerous physics requests from the raw CSV data
                safe_cue = c['cue'].lower().replace("360", "slow push-in").replace("180", "slow push-in").replace("90", "slow push-in")
                cues_text += f"- Time Frame {c['time_frame']}: {safe_cue}\n"

        duration_instruction = (
            "Each clip duration MUST be exactly 4, 6, or 8 seconds. No other duration values are supported by this model."
            if is_fast_model else
            f"No clip duration can exceed {max_duration} seconds."
        )

        # Extract dynamic product name from metadata
        brand_name = metadata.get('brand') or metadata.get('Brand') or ''
        model_name = metadata.get('model_name') or metadata.get('Model') or metadata.get('series') or metadata.get('Series') or ''
        product_full_name = f"{brand_name} {model_name}".strip()
        if not product_full_name:
            product_full_name = "PREMIUM SHOWCASE"

        model_specific_directives = ""
        if is_fast_model:
            model_specific_directives = (
                f"6. DYNAMIC GEOMETRY & CAMERA PHYSICS (CRITICAL): You are STRICTLY RESTRICTED to these allowed camera movements: {allowed_physics}. Ban 360/180/90 rotations to prevent 3D melting unless explicitly allowed in the list.\n"
                "7. CSV-DRIVEN METAPHORICAL VFX (CRITICAL): Read the 'Attribute', 'Attribute Data', and 'Implication' fields from the CSV context provided for this exact segment. You MUST dynamically invent hyper-specific, premium visual effects that visually demonstrate the CSV Implication. Do NOT use generic effects. Invent premium visual metaphors (e.g., environmental elements, UI animations, physical material reactions) that perfectly match the active feature being discussed in the CSV.\n"
                "   - ISOLATION RULE (ANTI-CHIMERA): You MUST focus on exactly ONE surface of the product per clip. NEVER mix the front screen and the rear panel in the same prompt. NEVER ask to see the front and back at the same time.\n"
            )
        else:
            model_specific_directives = (
                "6. CONTINUITY LOCK: For every segment, specify the exact audio that must play. Do NOT allow dead air.\n"
                "7. FINALE CONSTRAINT: The final clip in the sequence MUST end with the visual directive 'Smooth fade to black' and the BGM directive 'Audio fades out smoothly to silence.'\n"
            )

        if "omni" in model_target.lower():
            model_specific_directives += (
                "8. OMNI BRAND & DEVICE CONTINUITY: Explicitly state 'Product is [BRAND/MODEL]; exactly ONE product visible in the scene at any time; no competitor logos, no stacked products.'\n"
                f"9. COMPOSITIONAL BOOKENDS: The VERY FIRST segment MUST be explicitly described as: '{first_segment_rule}'. The VERY LAST segment MUST be explicitly described as: '{last_segment_rule}'.\n"
                "10. NO CAMERA UI OR JARGON: You are strictly forbidden from using technical camera terms (e.g., 35mm, ARRI, f/1.4, lens, viewfinder). Describe the scene beautifully, but do NOT trigger camera recording overlays.\n"
            )

        prompt = f"""
Break the following voiceover script into sequential visual segments.

CONSTRAINTS:
1. {duration_instruction}
2. The sum of all segment durations should total approximately 60 seconds.
3. Maintain visual continuity across clips. Keep lighting conditions consistent (e.g., 'soft studio rim lighting').
4. TEXT OVERLAYS: For the VERY FIRST segment, the text_overlay MUST exactly be the product name ('{product_full_name}'). For all other segments, output a max 4-word feature highlight.
5. SENTENCE INTEGRITY & WORD LIMIT: The voiceover script for a single segment MUST contain a MAXIMUM of 18 words. However, you MUST preserve natural sentence flow. Do NOT split a single sentence across multiple clips unless it strictly exceeds the 18-word limit. Always try to end a segment's voiceover on a natural pause, such as a period (.) or comma (,).
{model_specific_directives}
{cues_text}

VOICEOVER SCRIPT:
{script}
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
                            response_mime_type="application/json",
                            response_schema=SegmentationResponse,
                            temperature=0.2
                        )
                    )
                    break
                except Exception as api_err:
                    err_str = str(api_err).lower()
                    if "429" in err_str or "resource_exhausted" in err_str or "rate" in err_str:
                        delay = initial_delay * (backoff_factor ** attempt)
                        logger.warning(f"SegmentationAgent hit 429 rate limit. Attempt {attempt + 1}/{max_retries}. Retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        raise api_err
            else:
                raise RuntimeError("Failed to segment script after max retries due to rate limit blocks.")
            
            parsed_res = json.loads(response.text)
            segments = parsed_res.get("segments", [])
            
            # DETERMINISTIC GUARDRAIL: Force the first segment text overlay to be the Product Name
            if segments and product_full_name:
                segments[0]["text_overlay"] = product_full_name.upper()
            logger.info(f"SegmentationAgent successfully split script into {len(segments)} segments for Job {job_id}")
            
        except Exception as e:
            logger.warning(f"Gemini client segmentation failed: {e}. Triggering local fallback.")
            
            brand = metadata.get('brand', 'Product')
            model = metadata.get('model_name', 'Model')
            display = metadata.get('new_display_size', 'screen')
            camera = metadata.get('primary_camera_megapixel', 'primary camera')
            battery = metadata.get('battery_capacity', 'battery')
            
            # Use 6 seconds per clip as default supported fast duration
            clip_dur = 6 if is_fast_model else 5
            
            segments = [
                {
                    "clip_sequence": 1,
                    "duration": clip_dur,
                    "visual_prompt": f"Close-up of {brand} {model} frame chassis. Slow linear push-in with soft studio rim lighting.",
                    "voiceover_script": f"The new {brand} {model} is engineered for daily utility.",
                    "text_overlay": f"{brand} {model}"
                },
                {
                    "clip_sequence": 2,
                    "duration": clip_dur,
                    "visual_prompt": f"Focus on the {display} screen rendering an interface. Continuous soft studio rim lighting, slow linear push-in.",
                    "voiceover_script": f"It features a {display} display with clear resolution.",
                    "text_overlay": f"{display} Display"
                },
                {
                    "clip_sequence": 3,
                    "duration": clip_dur,
                    "visual_prompt": f"Detail of the {camera} rear camera modules. Continuous soft studio rim lighting, slow linear push-in.",
                    "voiceover_script": f"The {camera} camera supports clear capture and steady video recording.",
                    "text_overlay": f"{camera} Rear Camera"
                },
                {
                    "clip_sequence": 4,
                    "duration": clip_dur,
                    "visual_prompt": f"Static shot of the phone highlighting {battery} capacity. Warm studio illumination.",
                    "voiceover_script": f"A high capacity {battery} supports extended multi-day operation.",
                    "text_overlay": f"{battery} Battery"
                }
            ]
            logger.info(f"Mock segmentation list created with {len(segments)} segments.")

        # Update payload
        pubsub_payload['max_clip_duration_sec'] = max_duration
        pubsub_payload['segments'] = segments

        # Update database state
        self.db.update_job(job_id, {
            "status": "segments_created",
            "segments": segments
        })

        # Publish to topic-generation
        logger.info(f"SegmentationAgent success. Publishing to {TOPIC_GENERATION}")
        self.broker.publish(TOPIC_GENERATION, pubsub_payload)

        return pubsub_payload
