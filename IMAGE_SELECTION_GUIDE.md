# 🖼️ Product Image Selection & Safety Guardrails Guide

This document details the architecture, filtering criteria, dynamic guardrails, and ranking algorithms used by **ZiWan - Ad Studio** to select, analyze, and map e-commerce product shots to AI video generation segments.

---

## 📐 High-Level Architecture

The Image Selection Pipeline operates across **5 distinct phases**:

```
 [Raw Catalog Images]
          │
          ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Phase 1: Gemini 2.5/3.1 Vision Feature Extraction           │
 │ (Extracts: view_type, is_clean, has_multiple_devices, etc.) │
 └─────────────────────────────────────────────────────────────┘
          │
          ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Phase 2: Multi-Device Blacklist                             │
 │ (Filters out images with stacked or multiple devices)       │
 └─────────────────────────────────────────────────────────────┘
          │
          ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Phase 3: Chimera & Geometry Protections (is_flat_product)   │
 │ (Restricts camera sweeps for 2D flat surfaces like TVs)     │
 └─────────────────────────────────────────────────────────────┘
          │
          ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Phase 4: Text Density & Clean Studio Ranking                │
 │ (Ranks images: Clean Studio > Lowest Text Density Score)   │
 └─────────────────────────────────────────────────────────────┘
          │
          ▼
 ┌─────────────────────────────────────────────────────────────┐
 │ Phase 5: GCS Reference Image Upload & Segment Binding        │
 │ (Binds selected reference image URIs to Video API payload)   │
 └─────────────────────────────────────────────────────────────┘
```

---

## 🔍 Phase 1: Vision Model Feature Classification (`context_agent.py`)

Every product image uploaded in the catalog is analyzed using Gemini Vision (`gemini-3.1-pro-preview`) with structured Pydantic output (`SingleImageAnalysis`).

### **Pydantic Schema Definition**
```python
class SingleImageAnalysis(BaseModel):
    view_type: str = Field(
        ..., 
        description="The primary angle/view of the product: 'FRONT', 'BACK', 'SIDE_PORTS', 'OPEN_SCREEN_AND_DECK', 'TOP_PANEL', or 'OTHER'."
    )
    is_clean_product_shot: bool = Field(
        ..., 
        description="True ONLY if this is a clean studio product shot on a plain neutral/white background without heavy infographic text, banner overlays, or extra props."
    )
    has_multiple_devices: bool = Field(
        ..., 
        description="True if more than one instance of the product is visible in the image (e.g. 2 phones, stacked laptops, or multiple color variants shown together)."
    )
    text_density_score: int = Field(
        ..., 
        description="Estimated percentage of image area covered by text, spec callouts, or infographic banners (0 to 100)."
    )
    prominence_score: int = Field(
        ..., 
        description="Rating from 1 to 10 of how prominent and centered the product is."
    )
```

### **Dynamic Category Injection Guardrail**
To prevent leaky filters when analyzing non-phone products (like motorcycles, washing machines, or laptops), the vision prompt dynamically injects the exact product noun (`rule_id`):

```python
# In context_agent.py
product_name = rule_id.replace('_', ' ')
classification_contents = [
    image_part,
    f"Analyze this product image for a {product_name} video ad campaign.\n"
    f"CRITICAL: If the image shows more than one {product_name} (e.g. multiple units, comparison shots), set has_multiple_devices to True."
]
```

---

## 🚫 Phase 2: Multi-Device Blacklist (`generation_agent.py`)

Video diffusion models frequently hallucinate extra floating parts (e.g. 3 ear cups on a headphone or 2 screens on a laptop) if trained on images containing multiple devices. Any image where `has_multiple_devices == True` is strictly rejected:

```python
for filename, analysis in image_analyses.items():
    if analysis.get("has_multiple_devices", True):
        continue  # Strictly ban images with multiple devices
```

---

## 🛡️ Phase 3: Chimera & Geometry Protections (`generation_agent.py`)

Flat products (such as Mobile Phones and Televisions) suffer from "chassis melting" when video diffusion models attempt 360-degree camera orbits across side profiles. 

### **1. Flat Product Detection**
```python
is_flat_product = any(x in category_tab for x in ['mobile', 'phone', 'tv', 'television']) or any(x in rule_id for x in ['mobile', 'phone', 'tv', 'television'])
```

### **2. View Restricting & Empty Slot Enforcer**
For flat products, non-front/back views are downgraded to `OTHER`. The **Empty Slot Enforcer** then drops all `OTHER` images unless they are certified 100% clean studio shots (`is_clean == True`):

```python
vt = analysis.get("view_type", "OTHER").upper()

if is_flat_product:
    if vt not in ["FRONT", "BACK"]:
        vt = "OTHER"

view_pools[vt].append({
    "filename": filename,
    "is_clean": analysis.get("is_clean_product_shot", False),
    "text_density": analysis.get("text_density_score", 100)
})

# Empty Slot Enforcer for flat products
if is_flat_product and vt == "OTHER":
    clean_images = [img for img in images if img["is_clean"]]
    if not clean_images:
        continue  # Safely drop unsafe/unclean images
    images = clean_images
```

---

## 📊 Phase 4: Text Density & Clean Studio Ranking (`generation_agent.py`)

Once images are grouped into valid view pools (`FRONT`, `BACK`, `SIDE_PORTS`, etc.), they are sorted using a **two-tier priority key**:

```python
# Priority 1: is_clean=True comes first
# Priority 2: Lowest text_density (using -x["text_density"] in descending order)
images.sort(key=lambda x: (x["is_clean"], -x["text_density"]), reverse=True)

best_image = images[0]["filename"]
img_path = path_lookup[best_image]
deduplicated_images.append((img_path, best_image, vt))
```

### **Ranking Order Example**
| Image | `is_clean` | `text_density` | Selection Status | Rationale |
| :--- | :--- | :--- | :--- | :--- |
| `image_A.jpg` | `True` | 5 | 🥇 **SELECTED** | 100% Clean Studio Shot |
| `image_B.jpg` | `False` | 10 | 🥈 Second Choice | Unclean, but low text density |
| `image_C.jpg` | `False` | 85 | ❌ Rejected | High infographic clutter |

---

## 🎬 Phase 5: Hero Bookends & Fallback Engine

1. **Hero Bookends:** The first and last video segments (Segment 1 and Segment N) prioritize `best_front_image` to ensure strong brand identity at the start and end of the ad.
2. **Safe Fallback:** If all catalog images are rejected due to clutter or multi-device rules, the pipeline safely falls back to pure prompt-driven 3D text generation or a round-robin fallback image, ensuring the video generation never crashes.

---

## 📌 Summary Checklist for Adding New Product Categories

When introducing a new product category (e.g. `smartwatch`):
1. **Clamshell / 3D Objects (e.g. Laptops, Headphones, ACs):** Do **NOT** add to `is_flat_product`. They will automatically utilize dynamic view pools (like `OPEN_SCREEN_AND_DECK`) sorted by lowest text density.
2. **Flat Panel Surfaces (e.g. Tablets, Phones, Monitors):** Add category keyword to `is_flat_product` array to trigger the Empty Slot Enforcer and linear camera motion constraints.
