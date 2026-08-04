# 🎬 ZiWan - Ad Studio

**ZiWan - Ad Studio** is an enterprise-grade AI video generation pipeline built on the **Google Gemini Enterprise Agent Platform** (Gemini 3.5 Flash, Gemini Pro Vision, Veo 3.1 Fast, and Gemini Flash TTS). It transforms e-commerce product catalogs (CSVs/Excel specifications and studio product images) into professional 60-second video advertisements with dynamic visual effects, TTS voiceovers, background music, and text overlays.

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
   │Scripting Agent │ ──> (Gemini Script Synthesis)
   └────────────────┘
           │
           ▼
  ┌──────────────────┐
  │Segmentation Agent│ ──> (Dynamic Camera Physics & Metaphorical VFX Placement)
  └──────────────────┘
           │
           ▼
  ┌──────────────────┐
  │ Generation Agent │ ──> (Gemini Enterprise Agent Platform API: Gemini Omni / Veo 3.1 Fast)
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
* **Dynamic Audio Engine:** Gemini Flash TTS voiceover generation with automatic FFmpeg media duration synchronization (`atempo` time-stretching).
* **Infrastructure as Code (Terraform):** Exhaustive GCP HCL module for automated provisioning of Cloud Run, GCS vaults, Pub/Sub event queues, Artifact Registry, and IAM service accounts.
* **CI/CD Pipeline:** GitHub Actions workflow for automated code linting, Terraform validation, container building, and Cloud Run deployment.

---

## 📂 Repository Structure

```
.
├── backend/                        # Multi-agent Python core (FastAPI, Context, Scripting, Stitcher)
├── frontend/                       # Web Application interface (React 18 + Tailwind CSS)
├── terraform/                      # Production-ready Terraform (HCL) GCP infrastructure module
├── scripts/                        # Automated deployment scripts (deploy_to_gcp.sh)
├── .github/workflows/              # GitHub Actions CI/CD deployment pipeline (ci_cd_deploy.yml)
├── sample_dataset/                 # Sample product images & CSV catalogs for testing
├── ARCHITECTURE.md                 # Deep-dive architectural breakdown & diagrams
├── TECHNICAL_DOSSIER.md            # Complete enterprise technical dossier & specifications
├── DOCS_FFMPEG_AND_AUDIO_ENGINE.md # Procedural FFmpeg video compositing & audio mix guide
├── SECURITY.md                     # Data privacy policy & security controls
├── AI_GUARDRAILS_AND_PROMPT.md     # Vision guardrails & prompt engineering rules
├── DATA_AND_IMAGE_BEST_PRACTICES.md# Image quality & dataset selection guide
├── Dockerfile                      # Container containerization manifest
├── requirements.txt                # Python package dependencies
└── openapi.yaml                    # OpenAPI / REST API specification
```

---

## 🚀 Quick Start Guide

### Option A: Automated GCP Infrastructure Deployment (Terraform)

Deploy the entire Google Cloud Platform infrastructure in minutes using Terraform:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your GCP Project ID
terraform init
terraform plan
terraform apply
```

*For complete Terraform details, refer to the [Terraform Documentation](file:///Users/abhisoni/Documents/Ad_Creator/forPublicgit/terraform/README.md).*

---

### Option B: Local Development Server

1. **Clone & Set Up Virtual Environment:**
   ```bash
   git clone https://github.com/abhisoni-sketch/ZiWan-Ad-Studio.git
   cd ZiWan-Ad-Studio

   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   # Edit .env to set your GOOGLE_CLOUD_PROJECT
   ```

3. **Authenticate with Google Cloud:**
   ```bash
   gcloud auth application-default login
   ```

4. **Launch Development Server:**
   ```bash
   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
   ```

---

## 🔒 Security & Data Privacy

ZiWan Ad Studio enforces strict data privacy policies:
* **Zero Model Training:** No customer assets or prompt payloads processed via Vertex AI are used to train foundation models.
* **Least-Privilege IAM:** Service accounts are bound strictly to required GCP scopes (`roles/aiplatform.user`, `roles/storage.objectAdmin`).
* **Auto-Purging Storage:** Temporary rendering files in GCS are automatically purged after 7 days via lifecycle rules.

*Read our full [Security Policy](file:///Users/abhisoni/Documents/Ad_Creator/forPublicgit/SECURITY.md).*

---

## 📄 License

Distributed under the [MIT License](file:///Users/abhisoni/Documents/Ad_Creator/forPublicgit/LICENSE).
