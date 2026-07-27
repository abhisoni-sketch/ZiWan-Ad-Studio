# 🛡️ AI Guardrails, Prompt Engineering & Anomaly Mitigation Guide

This document presents a comprehensive technical breakdown of all AI visual anomalies, diffusion hallucinations, chimera blending effects, and voiceover defects encountered during the development of **ZiWan - Ad Studio**, along with the precise prompt engineering rules, negative directives, and code guardrails engineered to mitigate them.

---

## 🎯 Executive Summary & Problem Matrix

Video diffusion models (Veo 2.0, Veo 3.1 Fast, Gemini Omni) and LLM Scripting engines are highly expressive, but without strict constraints they suffer from five primary categories of defects:

| Anomaly Category | Visual/Audio Artifact | Root Cause | Implemented Guardrail / Prompt Directive |
| :--- | :--- | :--- | :--- |
| **1. Chimera Effect** | Front glass screen superimposed with rear camera lenses; 3D panel melting. | Mixing front/rear prompts in a single clip; extreme 360° camera orbits on 2D surfaces. | Anti-Chimera Surface Isolation Directive & Restricted 2D Linear Camera Physics. |
| **2. Object Multiplication** | Floating third earcup on headphones; 3 stacked laptops. | Reference images showing multiple variants; diffusion model geometric confusion. | Dynamic Vision Multi-Device Count Prompting & Single-Instance Isolation Directives. |
| **3. Raw FSN Callouts** | Voiceover reading alphanumeric strings like `"ACNHGCG5KXYME36M"`. | LLM pulling raw catalog table primary keys into text scripts. | Dynamic `product_full_name` Extraction & Alphanumeric Sanity Filters. |
| **4. Camera UI Overlay Bleed** | Viewfinder grids, `REC` icons, or focal ratios rendered on screen. | Using professional cinematography jargon (`35mm`, `ARRI`, `f/1.4`, `viewfinder`). | Banned Camera Jargon Directive. |
| **5. Text Overlay Clutter** | Multiline spec text obscuring visual VFX animations. | Unbounded LLM text overlay output. | Strict 4-Word Highlight Constraint (with multiline Finale exception). |

---

## 🔬 Deep Dive: Anomaly Analysis & Specific Prompt Directives

### 1. The Chimera Effect & Chassis Melting

#### **The Issue:**
When asking the video diffusion model to display a smartphone or TV, naive prompts such as *"Show the front screen and the rear camera setup"* cause the model to generate a hybrid "Chimera" object—placing camera lenses directly on top of the front glass screen. Furthermore, requesting 360°, 180°, or 90° rotations on ultra-thin flat products causes the side profiles to "melt" into distorted liquid geometry.

#### **Prompt Directives Implemented (`segmentation_agent.py`):**
```text
ISOLATION RULE (ANTI-CHIMERA): You MUST focus on exactly ONE surface of the product per clip. NEVER mix the front screen and the rear panel in the same prompt. NEVER ask to see the front and back at the same time.

DYNAMIC GEOMETRY & CAMERA PHYSICS (CRITICAL): You are STRICTLY RESTRICTED to these allowed camera movements: ["Slow linear push-in", "Static premium hero shot"]. Ban 360/180/90 rotations to prevent 3D melting.
```

#### **Code-Level Sanitization Guardrail:**
Even if user input or CSV cues explicitly ask for a 360° rotation, `SegmentationAgent` dynamically sanitizes the raw cue string before it reaches the prompt:
```python
# In segmentation_agent.py
safe_cue = c['cue'].lower().replace("360", "slow push-in").replace("180", "slow push-in").replace("90", "slow push-in")
```

---

### 2. Geometric Hallucination & Object Multiplication

#### **The Issue:**
Symmetric 3D products (like headphones or open laptops) can trigger diffusion hallucinations where 3 earcups or 2 overlapping keyboards appear in mid-air. This is exacerbated if source e-commerce images display multiple color variants side-by-side.

#### **Prompt Directives Implemented (`segmentation_agent.py` & `context_agent.py`):**
```text
# Segmentation Agent Prompt Directive:
OMNI BRAND & DEVICE CONTINUITY: Explicitly state 'Product is [BRAND/MODEL]; exactly ONE product visible in the scene at any time; no competitor logos, no stacked products.'
```

```python
# Context Agent Vision Prompt Directive:
product_name = rule_id.replace('_', ' ')
classification_contents = [
    image_part,
    f"Analyze this product image for a {product_name} video ad campaign.\n"
    f"CRITICAL: If the image shows more than one {product_name} (e.g. multiple units, comparison shots), set has_multiple_devices to True."
]
```

---

### 3. Raw Alphanumeric FSN / PSN Voiceover Callouts

#### **The Issue:**
Raw catalog exports contain internal SKU/FSN numbers (e.g. `ACNHGCG5KXYME36M` or `MOBHH69N2XATECZZ`). Naive LLM script generators read these as product names, producing voiceover audio like: *"Experience the MarQ A-C-N-H-G-C-G-5-K-X-Y-M-E-3-6-M air conditioner today."*

#### **Code & Prompt Fix (`segmentation_agent.py` & `generation_agent.py`):**
1. **Dynamic Name Extraction:** The backend extracts human-readable brand and series names:
   ```python
   brand_name = metadata.get('brand') or metadata.get('Brand') or ''
   model_name = metadata.get('model_name') or metadata.get('Model') or ''
   product_full_name = f"{brand_name} {model_name}".strip()
   ```
2. **TTS Phonetic Normalization:** Specs like `"7200 mAh"` are converted phonetically for TTS (`"seven thousand two hundred milliamp-hours"`) and formatted visually for overlays (`"7,200 mAh"`).

---

### 4. Technical Camera Jargon Triggering UI Overlays

#### **The Issue:**
Including technical film terms in prompts (such as *"Shot on 35mm f/1.4 lens with viewfinder framing"*) tricks the diffusion model into thinking the video is a camera monitor display. As a result, it renders battery indicators, `REC` red dots, and crosshair grids over the advertisement.

#### **Prompt Directives Implemented (`segmentation_agent.py`):**
```text
NO CAMERA UI OR JARGON: You are strictly forbidden from using technical camera terms (e.g., 35mm, ARRI, f/1.4, lens, viewfinder). Describe the scene beautifully, but do NOT trigger camera recording overlays.
```

---

### 5. Text Overlay & Spec Bleed Control

#### **The Issue:**
Unconstrained text overlays create ugly 3-line paragraphs that block visual product rendering and crossfade transitions.

#### **Prompt Directives Implemented (`segmentation_agent.py`):**
```text
TEXT OVERLAYS: For the VERY FIRST segment, the text_overlay MUST exactly be the product name ('{product_full_name}'). For all other segments, output a max 4-word feature highlight. Preserving short highlights ensures text overlay readability.
```

---

## 📌 Summary: Operational Checklist for Prompt Tuning

When editing system prompts in `SegmentationAgent`, `ScriptingAgent`, or `GenerationAgent`:
1. **Always enforce single-surface focus** to avoid Chimera front/back blending.
2. **Never allow technical camera terms** (`35mm`, `f-stop`, `lens`) in visual prompts.
3. **Keep `has_multiple_devices` checks dynamically typed** to the specific product noun (`rule_id`).
4. **Use phonetic spellouts** for TTS scripts (e.g. `milliamp-hours` vs `mAh`).
