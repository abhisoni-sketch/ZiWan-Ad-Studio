# 🎬 ZiWan - Ad Studio

ZiWan - Ad Studio is an enterprise-grade AI video generation pipeline built on Google Vertex AI (Gemini 3.1 Pro, Gemini Omni Flash, Veo 3.1 Fast, and Lyria). It transforms e-commerce product catalogs (CSVs/Excel specifications and studio product images) into professional 60-second video advertisements with dynamic visual effects, TTS voiceovers, background music, and text overlays.

---

## 🏗️ Architecture Overview

```
[Product Catalog / Images] 
           │
           ▼
   ┌────────────────┐
   │ Context Agent  │ ──> (Vision Analysis, Clean Background & Multi-Device Filtering)
   └────────────────┘
           │
           ▼
   ┌────────────────┐
   │Scripting Agent │ ──> (Gemini 3.1 Pro Script Generation)
   └────────────────┘
           │
           ▼
  ┌──────────────────┐
  │Segmentation Agent│ ──> (Dynamic Camera Physics & Metaphorical VFX Placement)
  └──────────────────┘
           │
           ▼
  ┌──────────────────┐
  │ Generation Agent │ ──> (Vertex AI Video API: Gemini Omni / Veo 3.1 Fast)
  └──────────────────┘
           │
           ▼
  ┌──────────────────┐
  │  Stitcher Engine │ ──> (FFmpeg Composition: Video, TTS Audio, BGM & Overlays)
  └──────────────────┘
```

---

## ⚡ Key Features

* **Multi-Model Support:** Native support for both **Gemini Omni Flash** (multimodal interaction API) and **Veo 3.1 Fast** (pure video diffusion).
* **Smart Guardrails:**
  * **Dynamic Multi-Device Filter:** Prevents video hallucination by filtering out non-clean images containing multiple/stacked items based on product categories (`rule_id`).
  * **Chimera Protections:** Enforces 2D linear camera constraints on flat products (e.g. phones, TVs) to prevent 3D chassis melting during camera sweeps.
  * **Text-Density Scrubber:** Sorts and selects source product shots based on minimal text overlays.
* **Dynamic Audio Engine:** Gemini 3.1 TTS voiceover generation with automatic FFmpeg media duration synchronization.

---

## 🛠️ Prerequisites

1. **Python 3.12+**
2. **FFmpeg** (installed on system PATH with `drawtext` support):
   * macOS: `brew install ffmpeg`
   * Linux: `sudo apt-get install ffmpeg`
3. **Google Cloud SDK (`gcloud` CLI):**
   * Configured with Vertex AI API access (`aiplatform.googleapis.com`).

---

## 🚀 Quick Start Guide

### 1. Clone & Set Up Virtual Environment

```bash
git clone https://github.com/your-username/Ad_Creator.git
cd Ad_Creator

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Copy the template environment file:

```bash
cp .env.example .env
```

Edit `.env` to set your Google Cloud Project ID:

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
DEFAULT_LOCATION=asia-south1
```

Authenticate with Google Cloud:

```bash
gcloud auth application-default login
```

### 3. Launch Local Development Server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Access the UI at: `http://localhost:8000`

---

## ☁️ Deploying to Google Cloud Run

To deploy the backend and frontend service to Google Cloud Run in a single command:

```bash
gcloud run deploy ad-creator-studio \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated
```

---

## 📄 License

Distributed under the Apache License, Version 2.0. See `LICENSE` for more information.
