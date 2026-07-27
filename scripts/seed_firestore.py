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
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database.firestore_client import CategoryRulesDB
from backend.database.schemas.category_schema import CategoryRuleSet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_database():
    db_client = CategoryRulesDB()
    if not db_client.db:
        logger.error("Firestore client failed to initialize.")
        return

    categories = []

    # UPDATED HEADPHONE RULES: Banned orbital pans, removed "stand" from bookends, added negative prompts.
    categories.append(CategoryRuleSet(
        category_id="headphones",
        scripting_rules={
            "philosophy": "Inform, Don't Advertise.",
            "banned_words": ["stunning", "game-changing", "magic", "best", "unbelievable"],
            "focus_areas": "Translate driver size to bass depth. Translate battery mAh to hours of playback. Highlight active noise cancellation utility."
        },
        segmentation_rules={
            "allowed_camera_physics": ["Static premium hero shot", "Slow push-in (dolly in)", "Slight lateral pan"],
            "surface_isolation_labels": ["EARCUP_EXTERIOR", "HEADBAND", "EARPAD_CUSHION", "CONTROL_BUTTONS"],
            "compositional_bookends": {
                "first_segment": "Static premium hero shot of the headphones hovering elegantly in a clean, dark studio space.",
                "last_segment": "Static premium hero shot of the headphones hovering elegantly in a clean, dark studio space."
            }
        },
        generation_rules={"negative_prompt_additions": "stands, mounts, pillars, dummy heads, people wearing headphones, messy desks, UI viewfinders"}
    ))

    # MOTORCYCLES
    categories.append(CategoryRuleSet(
        category_id="motorcycles",
        scripting_rules={
            "philosophy": "Inform, Don't Advertise. Embrace lifestyle and motion.",
            "banned_words": ["stunning", "beast", "monster", "magic"],
            "focus_areas": "Translate CC/displacement to highway stability and acceleration. Highlight braking tech (ABS) and fuel efficiency. Strictly ignore and drop any input images where text_density_score is > 50 or is_clean_product_shot is false. Do not map these images to any video segments. Rely on the remaining clean images."
        },
        segmentation_rules={
            "allowed_camera_physics": [
                "Dynamic tracking shot of the motorcycle being ridden by a rider in a closed full-face helmet and full protective gear on a scenic coastal highway", 
                "Cinematic panning shot while cruising with a rider in a closed full-face helmet and full protective gear", 
                "Action shot being ridden by a rider in a closed full-face helmet and full protective gear through a beautiful landscape", 
                "Slow cinematic push-in of the motorcycle safely parked on its kickstand in a dramatic, atmospheric studio with volumetric fog"
            ],
            "surface_isolation_labels": ["SIDE_PROFILE", "FRONT_HEADLIGHT", "DASHBOARD_TANK", "REAR_EXHAUST"],
            "compositional_bookends": {
                "first_segment": "Cinematic wide action shot of the motorcycle being ridden by a rider in a closed full-face helmet and full protective gear cruising down a beautiful scenic road.",
                "last_segment": "Cinematic wide action shot of the motorcycle being ridden by a rider in a closed full-face helmet and full protective gear cruising down a beautiful scenic road into the sunset."
            }
        },
        generation_rules={"negative_prompt_additions": "plain white background, gibberish text, visible human face, open helmet, casual clothes, riding without a helmet, missing kickstand, UI viewfinders, ARRI camera UI, floating text, distorted wheels"}
    ))

    # LAPTOPS
    categories.append(CategoryRuleSet(
        category_id="laptops",
        scripting_rules={
            "philosophy": "Inform, Don't Advertise.",
            "banned_words": ["stunning", "game-changing", "magic"],
            "focus_areas": "Translate RAM to multitasking capability. Translate processor cores to rendering/compiling speed."
        },
        segmentation_rules={
            "allowed_camera_physics": ["Static premium hero shot", "Slow push-in (dolly in) on the screen", "Slight lateral pan across the keyboard", "Dynamic tracking shot of typing"],
            "surface_isolation_labels": ["OPEN_SCREEN_AND_DECK", "KEYBOARD_TRACKPAD", "SIDE_PORTS"],
            "compositional_bookends": {
                "first_segment": "Static premium hero shot of the laptop fully open in a modern workspace.",
                "last_segment": "Static premium hero shot of the laptop fully open in a modern workspace."
            }
        },
        generation_rules={"negative_prompt_additions": "closed lids, multiple laptops, double logos, detached lids, floating screens, UI viewfinders"}
    ))

    # AC
    categories.append(CategoryRuleSet(
        category_id="ac",
        scripting_rules={
            "philosophy": "Inform, Don't Advertise.",
            "banned_words": ["stunning", "chilling", "arctic", "magic"],
            "focus_areas": "Translate ton capacity to room square footage (e.g. 1 Ton for 110-120 sq ft). Highlight inverter efficiency, split-system cooling, and noise reduction. Strictly ban duplicated logos or multiple temperature displays. Do not prompt the video model to invent, duplicate, or 'fade in' new UI elements. Anchor all visual effects strictly to the existing physical product geometry, preserving the exact original location of any displays without adding new ones. To prevent text mutation, if the source image features a digital temperature display, the visual_prompt MUST explicitly describe the EXACT number shown in the source image to anchor it (e.g., 'The display clearly and stably reads 35°C'). NEVER attempt to change the original number to a new temperature, as forcing a new number will conflict with the source pixels and cause UI melting and duplication."
        },
        segmentation_rules={
            "allowed_camera_physics": ["Static premium hero shot", "Slow push-in (dolly in) on the indoor unit", "Slight lateral pan across the louvers", "Static hero shot of the robust outdoor compressor unit"],
            "surface_isolation_labels": ["INDOOR_FRONT_PANEL", "LOUVERS", "OUTDOOR_COMPRESSOR", "REMOTE_CONTROL"],
            "compositional_bookends": {
                "first_segment": "Static premium hero shot of the sleek AC indoor unit mounted on a modern wall.",
                "last_segment": "Static premium hero shot of the sleek AC indoor unit mounted on a modern wall."
            }
        },
        generation_rules={"negative_prompt_additions": "water dripping, ice, snow, freezing, people, UI viewfinders, messy rooms, dimension lines, human silhouettes, infographics"}
    ))

    # MICROWAVES
    categories.append(CategoryRuleSet(
        category_id="microwave",
        scripting_rules={
            "philosophy": "Inform, Don't Advertise.",
            "banned_words": ["stunning", "magic", "best"],
            "focus_areas": "Translate wattage to heating speed. Highlight auto-cook menus and cavity capacity for family sizes."
        },
        segmentation_rules={
            "allowed_camera_physics": ["Static premium hero shot", "Slow push-in (dolly in)"],
            "surface_isolation_labels": ["FRONT_CLOSED_DOOR", "CONTROL_PANEL", "OPEN_CAVITY", "SIDE_PROFILE"],
            "compositional_bookends": {
                "first_segment": "Static premium hero shot of the microwave perfectly closed in a clean modern kitchen setting.",
                "last_segment": "Static premium hero shot of the microwave perfectly closed in a clean modern kitchen setting."
            }
        },
        generation_rules={"negative_prompt_additions": "food splatters, messy kitchens, people, UI viewfinders"}
    ))

    # TV
    categories.append(CategoryRuleSet(
        category_id="tv",
        scripting_rules={
            "philosophy": "Inform, Don't Advertise.",
            "banned_words": ["stunning"],
            "focus_areas": "Translate display tech to visual vibrancy. EXPLICITLY highlight HDMI/USB ports and rear connectivity. Translate watts to room-filling audio."
        },
        segmentation_rules={
            "allowed_camera_physics": [
                "Static premium hero shot locked exclusively on the FRONT_SCREEN", 
                "Slow push-in (dolly in) targeting EXACTLY ONE surface", 
                "Slight lateral pan isolated to EXACTLY ONE surface"
            ],
            "surface_isolation_labels": ["FRONT_SCREEN", "SIDE_PROFILE", "BACK_PANEL"],
            "compositional_bookends": {
                "first_segment": "Static premium hero shot of the TV perfectly head-on. The TV screen MUST be turned ON, actively playing a breathtaking, vibrant 4K cinematic nature scene.",
                "last_segment": "Static premium hero shot of the TV perfectly head-on. The TV screen MUST be turned ON, actively playing a breathtaking, vibrant 4K cinematic nature scene."
            }
        },
        generation_rules={"negative_prompt_additions": "black screens, blank screens, TVs turned off, double back panels, distorted bezels, people, living rooms, messy background, UI viewfinders, remote controls"}
    ))

    # WASHING MACHINES (Large)
    categories.append(CategoryRuleSet(
        category_id="large",
        scripting_rules={
            "philosophy": "Inform, Don't Advertise.",
            "banned_words": ["stunning", "game-changing", "magic", "best"],
            "focus_areas": "Translate capacity to family size utility. Highlight RPM spin speed, built-in heater, and smart features. Strictly ban orbital camera pans and extreme lateral pans to prevent 'Chimera' hallucinations (e.g., front doors appearing on the back/sides). Restrict camera motion to static shots or slow push-ins (dolly in) strictly along the existing visual axis. Never map front-panel features to a SIDE view image. For visual effects, strictly avoid abstract or 'metaphorical' descriptions. Mandate concrete, aggressive, and highly visible physical VFX (e.g., 'hyper-realistic water splashing dynamically', 'thick cinematic glowing blue mist pouring from the drum', 'bright neon amber light emitting from the base'). Anchor these literal physics directly to the appliance. CRITICAL PERSPECTIVE ANCHORING: To prevent geometric warping and 'hexagon' shape hallucinations, the visual_prompt MUST accurately describe the true physical camera angle of the source image. If the image shows the appliance at an angle, the prompt MUST say 'angled 3/4 perspective shot'. If it is flat, say 'straight-on flat front view'. Never command a 'front' view if the source image is angled. CINEMATIC PRACTICAL EFFECTS: Stop using abstract, philosophical metaphors like 'ethereal auras' or 'symbolic fabrics'. Channel all creativity into high-end, physical Hollywood practical effects and lighting. Use commands like 'cinematic volumetric fog', 'dynamic sweeping neon rim lights', 'slow-motion physical water droplets', or 'glowing LED particle dust'. Describe exact physical lighting and particles that exist in the real world."
        },
        segmentation_rules={
            "allowed_camera_physics": ["Static premium hero shot", "Slow push-in (dolly in)"],
            "surface_isolation_labels": ["FRONT", "BACK", "SIDE", "OTHER"],
            "compositional_bookends": {
                "first_segment": "Static premium hero shot of the washing machine front.",
                "last_segment": "Static premium hero shot of the washing machine front."
            }
        },
        generation_rules={"negative_prompt_additions": "orbital pans, multiple doors, doors on side, UI viewfinders, water splashing out"}
    ))

    # MOBILE (Smartphones)
    categories.append(CategoryRuleSet(
        category_id="mobile",
        scripting_rules={
            "philosophy": "Inform, Don't Advertise.",
            "banned_words": ["stunning", "game-changing", "magic", "best", "unbelievable"],
            "focus_areas": "Translate display specs to screen clarity. Highlight processor performance and gaming stability. Translate mAh to battery standby and usage hours. Strictly ban 'metaphorical' visual descriptions. Visuals MUST be literal and strictly match the specific feature discussed in the voiceover. IF discussing IP rating/durability, mandate 'Environmental VFX' like hyper-realistic water splashing on the device. IF discussing battery, gaming, or display, mandate 'Screen Animation' on FRONT views. CRITICAL: To prevent pixel-melting, Screen Animations must respect the source image. If the source screen is off/blank, you may prompt a new UI to illuminate (e.g., 'A bright battery charging UI appears and animates'). If the source image already displays a UI, you must prompt the video model to animate THAT specific existing UI (e.g., 'The existing text on screen smoothly scrolls', or 'The displayed game scene dynamically animates in motion'). Never force a completely new UI over an existing, conflicting static screen."
        },
        segmentation_rules={
            "allowed_camera_physics": ["Static premium hero shot", "Slow push-in (dolly in)", "Slight lateral pan"],
            "surface_isolation_labels": ["FRONT", "BACK", "SIDE", "OTHER"],
            "compositional_bookends": {
                "first_segment": "Static premium hero shot of the phone front display.",
                "last_segment": "Static premium hero shot of the phone front display."
            }
        },
        generation_rules={"negative_prompt_additions": "hands, fingers, holding, people, UI viewfinders"}
    ))

    # Push all to Firestore
    try:
        col_ref = db_client.db.collection(db_client.collection_name)
        for cat in categories:
            col_ref.document(cat.category_id).set(cat.model_dump())
            logger.info(f"Successfully seeded '{cat.category_id}' rules.")
    except Exception as e:
        logger.error(f"Failed to push to Firestore: {e}")

if __name__ == "__main__":
    seed_database()
