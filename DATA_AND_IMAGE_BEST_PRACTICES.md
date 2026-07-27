# 📊 Data & Image Preparation Best Practices

**Maximizing Generative Output Quality for ZiWan - Ad Studio**

Because ZiWan - Ad Studio is a fully autonomous Generative AI pipeline, the final video quality is directly tied to the clarity and quality of your input catalog data and reference imagery. The underlying foundation models (Gemini Vision, Veo Video) apply strict heuristics to prevent hallucinations (like the "Chimera effect" or 3D object melting). 

This guide outlines exactly how you should prepare your inputs to ensure the highest tier of broadcast-ready video ads.

> [!TIP]
> **Looking for an example?** We have provided a perfect benchmark dataset located in the `sample_dataset/` directory. It contains 15 products with exactly 3 reference angles each, and a properly formatted `sample_catalog.csv`. We highly recommend reviewing it to see these best practices in action!

---

## 1. Product Catalog Data (Spreadsheets)

ZiWan - Ad Studio ingests `.csv` or `.xlsx` files to extract product specifications and synthesize the marketing voiceover script.

### ✅ DO: Use Human-Readable Naming
While your internal systems might track items as `ACNHGCG5KXYME36M`, ensure your spreadsheet contains a prominent column for the **Brand** and **Model Name** (e.g., "Sony Alpha 7 IV"). The Scripting Agent is instructed to strip out raw SKUs, but providing rich, natural-language titles yields significantly better voiceover copywriting.

### ✅ DO: Separate Specs into Distinct Rows/Columns
Instead of dumping a massive paragraph of text into one "Description" column, structure your data logically. Use specific headers like `Display Specs`, `Processor`, `Battery Life`, or `Material`. The Context Agent parses these structures more effectively when deducing the product's category (`rule_id`).

### ❌ DON'T: Hide the Product Category
Ensure the category (e.g., "Smartphones", "Televisions", "Laptops", "Home Appliances") is clearly stated either in the tab name or a dedicated column. The pipeline uses this to determine the `physical_form_factor`. Misclassifying a flat-panel TV as a volumetric object will cause the AI to attempt 360-degree camera orbits, resulting in visual distortion.

---

## 2. Reference Image Best Practices

The Generation Agent is highly selective about which images it passes to the Gemini Enterprise Agent Platform Video API. It uses Gemini Vision to score and rank your folder of images. Supplying the right images ensures the video model has a clean "anchor" to generate accurate physics.

### ✅ DO: Provide Clean Studio Shots (`is_clean_product_shot`)
**The absolute best images to provide are clean, high-resolution product shots on plain white, black, or neutral backgrounds.** 
* **Why?** The image ranking algorithm heavily prioritizes images flagged as `is_clean_product_shot = True`. These images give the video diffusion model a perfect, unobstructed view of the product's geometry, allowing it to seamlessly hallucinate new dynamic backgrounds and lighting.

### ❌ DON'T: Upload Images with Multiple Devices (`has_multiple_devices`)
Do not use images that show two phones overlapping, three laptops stacked on top of each other, or multiple color variants grouped in one frame.
* **Why?** **The Multi-Device Blacklist.** Video diffusion models frequently hallucinate extra floating parts (e.g., giving a headphone three ear cups) if trained on images containing multiple devices. The Vision agent will immediately flag and reject these images to prevent the "Chimera effect."

### ❌ DON'T: Use Heavy Infographics or Text Overlays (`text_density_score`)
Avoid images plastered with "50% OFF" stickers, large technical specification overlays, or heavy promotional text.
* **Why?** The Vision agent calculates a `text_density_score`. Images with high text density are severely penalized in the ranking algorithm because diffusion models often warp or scramble static text during camera movements, ruining the professional look of the final video.

### ✅ DO: Provide Multiple Angles
Provide a variety of shots (Front, Back, Side Profile, Open, etc.). The pipeline categorizes these into view pools and will automatically select the best angle depending on the video segment's camera movement.

---

## 3. Special Considerations by Product Form-Factor

ZiWan - Ad Studio dynamically applies physical guardrails depending on the geometry of the product.

### Volumetric / 3D Objects (Laptops, Appliances, Headphones, Motorcycles)
* **What to expect:** The AI understands these objects have 3D depth. It will employ aggressive cinematic physics (e.g., 360-degree orbits, 180-degree pans, dynamic fly-throughs).
* **Image Advice:** Provide images showing the product open, closed, from the side, and top-down to give the AI maximum geometric context.

### Flat Panel Displays (Smartphones, Tablets, TVs, Monitors)
* **What to expect:** Thin, flat products are notoriously difficult for AI video models; if instructed to pan 90-degrees, the AI often "melts" or bends the chassis. The pipeline's **Hybrid Safety Net** detects these products and strictly locks the camera physics to "Slow linear push-ins" and "Static premium hero shots."
* **Image Advice:** Focus on providing ultra-clean, head-on (Front) and pure rear (Back) shots. The pipeline's *Empty Slot Enforcer* will automatically discard weird side-angle shots of flat products unless they are certified as 100% clean studio shots.
