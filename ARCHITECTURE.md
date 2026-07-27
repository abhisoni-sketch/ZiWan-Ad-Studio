# 🏗️ ZiWan - Ad Studio - The Complete Technical & Architecture Dossier

**Enterprise-Grade Automated Video Ad Generation Pipeline**

This document serves as the exhaustive engineering masterclass for the ZiWan - Ad Studio. It outlines the system-level components, micro-agent reasoning logic, exact API data schemas, compositing commands, and the deployment topology used to transform raw e-commerce product catalogs into broadcast-ready, 60-second video advertisements.

---

## 1. High-Level System Architecture

The system leverages an asynchronous, event-driven microservices architecture via Google Cloud Pub/Sub to prevent blocking during long video rendering tasks.

```mermaid
flowchart TB
    subgraph Client Layer
        UI["User / Web Application<br>(React + Tailwind CSS)"]
    end

    subgraph API & Messaging Gateway
        FastAPI["FastAPI App Gateway<br>(/api/upload, /api/jobs)"]
        Broker{{"Event Broker<br>(Pub/Sub Topology)"}}
    end

    subgraph Data & Storage Layer
        DB[("Database Provider<br>(JSON / Firestore)")]
        GCS_Ingest[("Ingest Vault (GCS)<br>(Raw Spreads & Images)")]
        GCS_Output[("Production Vault (GCS)<br>(1080p MP4s)")]
    end

    subgraph Phase 1: Ingestion & Vision Analytics
        Context["Context Agent<br>(Extracts specs, detects form-factor)"]
        Vision["Gemini 3.1 Pro Vision<br>(Image Analysis Schema)"]
    end

    subgraph Phase 2 & 3: Cognitive & Directorial
        Script["Scripting Agent<br>(60s Voiceover Synthesis)"]
        Seg["Segmentation Agent<br>(Scene Splitting & VFX Physics)"]
        GeminiPro["Gemini 3.1 Pro<br>(Reasoning Engine)"]
    end

    subgraph Phase 4 & 5: Generative Media & Post-Production
        Gen["Generation Agent<br>(Multi-pass Rendering)"]
        TTS["Gemini 3.1 Flash TTS<br>(Audio Tracks)"]
        Veo["Veo 3.1 Fast / Omni API<br>(Video Frames)"]
        Stitcher["Master Stitcher Engine<br>(FFmpeg CLI Wrapper)"]
    end

    %% Entry Flow
    UI -->|POST /api/upload| FastAPI
    FastAPI -->|Reads/Writes Job State| DB
    FastAPI -->|Stages Assets| GCS_Ingest
    FastAPI -->|Publishes Job Payload| Broker

    %% Phase 1
    Broker -->|TOPIC_CONTEXT_AGENT| Context
    Context <-->|Parses Images| GCS_Ingest
    Context <-->|Vision QC Analytics| Vision
    Context -->|Publishes Context Payload| Broker

    %% Phase 2 & 3
    Broker -->|TOPIC_SCRIPTING| Script
    Script <-->|Synthesizes Copy| GeminiPro
    Script -->|Publishes Script| Broker

    Broker -->|TOPIC_SEGMENTATION| Seg
    Seg <-->|Breaks down scenes| GeminiPro
    Seg -->|Publishes Scenes| Broker

    %% Phase 4 & 5
    Broker -->|TOPIC_GENERATION| Gen
    Gen <-->|Synthesizes Audio| TTS
    Gen <-->|Renders Video Clips| Veo
    Gen -->|Uploads Raw Clips| GCS_Ingest
    Gen -->|Publishes Media Array| Broker

    Broker -->|TOPIC_STITCH| Stitcher
    Stitcher <-->|Downloads Raw Clips| GCS_Ingest
    Stitcher -->|FFmpeg text/audio overlays| Stitcher
    Stitcher -->|Uploads Master Ad| GCS_Output
    Stitcher -->|Updates Status: COMPLETED| DB
```

### Component Breakdown & Architectural Rationale
*   **FastAPI Gateway:** Chosen for high concurrency support when accepting massive catalog uploads.
*   **Event Broker (Pub/Sub):** Video generation is notoriously slow. Synchronous HTTP would time out. Pub/Sub allows agents to pick up jobs asynchronously and retry on failures.
*   **Gemini Enterprise Agent Platform Foundation Models:** Uses Gemini 3.1 Pro for complex reasoning, Vision for Image QC, Flash TTS for ultra-fast audio, and Veo 3.1 for state-of-the-art multimodal video generation.
*   **Stitcher Engine (FFmpeg):** Uses system-level FFmpeg for blazingly fast compositing, avoiding heavy and costly cloud-rendering services.

---

## 2. End-to-End Execution Sequence Flow

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Client
    participant API as FastAPI Gateway
    participant Context as Context Agent
    participant Script as Scripting Agent
    participant Seg as Segmentation Agent
    participant Gen as Generation Agent
    participant Stitch as Stitcher Engine
    participant Vertex as Gemini Enterprise Agent Platform APIs
    participant Storage as GCS Storage Vault

    User->>API: Upload CSV/XLSX Sheet + PSN Identifier
    API->>Storage: Stage Raw Sheet & Asset Folders
    API->>Context: Dispatch Job Payload (TOPIC_CONTEXT_AGENT)
    
    rect rgb(240, 248, 255)
        note over Context,Vertex: Phase 1: Context Ingestion & Vision Analysis
        Context->>Context: Parse Specs & Deduce rule_id & physical_form_factor
        Context->>Vertex: Run SingleImageAnalysis (Pydantic Vision Schema)
        Vertex-->>Context: Return view_type, is_clean, has_multiple_devices, text_density
        Context->>Storage: Upload Valid Reference Images (gs://ingest-vault/)
    end

    Context->>Script: Dispatch Context Payload (TOPIC_SCRIPTING)
    
    rect rgb(255, 245, 238)
        note over Script,Vertex: Phase 2: Scripting & Marketing Copy
        Script->>Vertex: Generate 60s Voiceover Script (Gemini 3.1 Pro)
        Vertex-->>Script: Return Sanitized Script (Raw SKUs stripped)
    end

    Script->>Seg: Dispatch Script Payload (TOPIC_SEGMENTATION)

    rect rgb(245, 255, 250)
        note over Seg,Vertex: Phase 3: Segmentation & Physics Guardrails
        Seg->>Seg: Evaluate Hybrid Safety Net (is_flat_product)
        Seg->>Vertex: Breakdown Script into Clips (Gemini 3.1 Pro Pydantic Schema)
        Vertex-->>Seg: Return Segments (Visual prompts, camera physics, text overlays)
    end

    Seg->>Gen: Dispatch Segment Payload (TOPIC_GENERATION)

    rect rgb(255, 250, 240)
        note over Gen,Vertex: Phase 4: Media Generation & API Calls
        Gen->>Gen: Rank Images (is_clean > lowest text_density_score)
        Gen->>Vertex: Generate Voiceover WAV (Gemini 3.1 Flash TTS)
        Gen->>Gen: Measure Voiceover Duration via FFmpeg
        Gen->>Vertex: Generate Video Bytes (Veo 3.1 Fast / Omni Video API)
        Vertex-->>Gen: Return MP4 Video Bytes
        Gen->>Storage: Upload Intermediate Clips
    end

    Gen->>Stitch: Dispatch Clip Array Payload (TOPIC_STITCH)

    rect rgb(240, 240, 255)
        note over Stitch,Storage: Phase 5: Master Assembly & Output Delivery
        Stitch->>Stitch: Render FFmpeg Complex Filters (drawtext overlays, BGM mixing)
        Stitch->>Stitch: Concatenate Segments into 60s 1080p MP4
        Stitch->>Storage: Upload Master MP4 (gs://production-vault/)
    end

    Stitch-->>API: Mark Job Status: COMPLETED
    API-->>User: Return Video Stream & GCS Download URL
```

---

## 3. Exhaustive Micro-Agent Workflows & Data Schemas

### Phase 1: Context & Vision Agent Workflow
Data ingestion and strict visual quality assurance to prevent AI hallucination.

```mermaid
flowchart TD
    Start(["Start: Context Agent"]) --> ExtractSpecs["Parse Product Specs from CSV/XLSX"]
    ExtractSpecs --> DeduceRule["Deduce rule_id & physical_form_factor"]
    
    DeduceRule --> DetectFlat{"Is Flat Panel Display?"}
    DetectFlat -- "Yes" --> SetFlat["Set form_factor = FLAT_PANEL_DISPLAY"]
    DetectFlat -- "No" --> SetVol["Set form_factor = VOLUMETRIC_3D"]
    
    SetFlat --> ScanImages["Fetch Image Candidates"]
    SetVol --> ScanImages
    
    ScanImages --> IterImage{"For Each Image"}
    IterImage --> InvokeVision["Invoke Gemini Pro Vision API"]
    
    InvokeVision --> CheckMulti{"has_multiple_devices?"}
    CheckMulti -- "Yes" --> Blacklist["Blacklist Image<br>(Prevents Chimera effect)"]
    CheckMulti -- "No" --> ScoreImage["Store metrics"]
    
    ScoreImage --> UploadValid["Upload Valid Images to GCS"]
    Blacklist --> NextImage["Next Image"]
    UploadValid --> NextImage
    NextImage --> IterImage
    IterImage -- "All Processed" --> PubTopic["Publish TOPIC_SCRIPTING"]
```

**Implementation Details & Schemas:**
To ensure precise evaluation, the Vision model is constrained by a strict Pydantic JSON schema:
```python
class SingleImageAnalysis(BaseModel):
    view_type: Literal["FRONT", "BACK", "SIDE_PORTS", "OPEN_SCREEN_AND_DECK", "TOP_PANEL", "OTHER"]
    is_clean_product_shot: bool
    has_multiple_devices: bool # If True, immediately blacklisted
    text_density_score: int    # 0 to 100
    color_family: str
    primary_material_guess: str
```

### Phase 3: Segmentation Agent Workflow
Acts as the "Director", planning the shot list and implementing physical camera constraints.

```mermaid
flowchart TD
    Start(["Start: Segmentation Agent"]) --> ReadScript["Read 60s Script"]
    ReadScript --> CheckForm{"Check physical_form_factor"}
    
    CheckForm -- FLAT_PANEL_DISPLAY --> ApplySafety["Apply Hybrid Safety Net<br>(Disable 3D/Orbit physics)"]
    CheckForm -- VOLUMETRIC_3D --> FullPhysics["Allow All Camera Physics"]
    
    ApplySafety --> InvokeGemini["Invoke Gemini 3.1 Pro"]
    FullPhysics --> InvokeGemini
    
    InvokeGemini --> SplitClips["Split Script into Segments"]
    SplitClips --> AssignCam["Assign Camera Movements"]
    AssignCam --> AssignOverlay["Limit text overlays (Max 4 words)"]
    AssignOverlay --> PubTopic["Publish TOPIC_GENERATION"]
```

**Implementation Details & Schemas:**
The **Hybrid Safety Net** forces constraints. If `is_flat_product` is true, the prompt explicitly blocks orbital movements that cause 2D objects to "melt" in diffusion models.
```python
class VideoSegment(BaseModel):
    segment_number: int
    duration_seconds: Literal[4, 6, 8]
    voiceover_text: str
    visual_prompt: str
    camera_movement: str
    text_overlay_highlight: str # Guaranteed <= 4 words
```

### Phase 4 & 5: Media Generation & Stitching Pipeline
Handles exact audio-visual alignment and final rendering.

```mermaid
flowchart TD
    Start(["Start: Gen & Stitcher"]) --> SelectBest["Select Top Image as Reference"]
    SelectBest --> IterSegment{"For Each Segment"}
    
    IterSegment --> CallTTS["Call Gemini Flash TTS"]
    CallTTS --> MeasureDuration["Measure exact ms duration via ffprobe"]
    MeasureDuration --> CheckRound{"If Audio > 5s?"}
    CheckRound -- "Yes (5.2s)" --> RoundUp["Round Video to 6.0s"]
    CheckRound -- "No" --> KeepDuration["Keep Original Duration"]
    
    RoundUp --> CallVeo["Call Veo 3.1 API (VideoGenerationReferenceImage)"]
    KeepDuration --> CallVeo
    
    CallVeo --> PollLRO["Poll Vertex LRO Status"]
    PollLRO --> SaveClip["Save Raw MP4"]
    SaveClip --> NextSegment["Next Segment"]
    NextSegment --> IterSegment
    
    IterSegment -- "All Generated" --> GenerateBGM["Fetch BGM Track"]
    GenerateBGM --> LoopRender{"For Each Clip"}
    
    LoopRender --> FFmpegText["Apply FFmpeg drawtext filter"]
    FFmpegText --> RenderNext["Next Render"]
    RenderNext --> LoopRender
    
    LoopRender -- "All Rendered" --> Concat["FFmpeg Concat Engine"]
    Concat --> AudioDuck["Apply Audio Ducking (amix)"]
    AudioDuck --> Export["Export job_final.mp4"]
```

**Implementation Details & Commands:**
*   **Exact Audio Duration Logic:** Generates TTS audio *first*, preventing videos from clipping spoken words prematurely.
*   **Compositing Command (FFmpeg):** Draws custom typography directly over the video using native filters.
    ```bash
    ffmpeg -i clip_1_raw.mp4 -vf "drawtext=fontfile=Outfit-Bold.ttf:text='120Hz OLED Display':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-120:box=1:boxcolor=black@0.6" -c:a copy clip_1_text.mp4
    ```

---

## 4. Environment & Deployment Configuration

### Critical Environment Variables
| Variable | Description |
| :--- | :--- |
| `GOOGLE_CLOUD_PROJECT` | GCP Project ID (e.g., `your-gcp-project-id`) |
| `DEFAULT_LOCATION` | Region for Gemini Enterprise Agent Platform (e.g., `us-central1`) |
| `INGEST_BUCKET` | Vault for raw catalog sheets and images |
| `OUTPUT_BUCKET` | Vault for finalized video ads |
| `DEFAULT_MODEL` | Set to `gemini-3.1-pro-preview` |
| `DEFAULT_VIDEO_MODEL` | Set to `gemini-omni-flash-preview` / `veo-3.1-fast` |

### Containerization (Docker)
Built on a lightweight Python image with system FFmpeg installed for rapid compositing.
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y ffmpeg curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Cloud Run Deployment
A single command deploys the entire asynchronous suite:
```bash
gcloud run deploy ad-creator-studio \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=your-gcp-project-id
```

---

## 5. Sample Dataset Reference

To help you get started immediately, we have included a `sample_dataset/` directory in this repository. It serves as a "North Star" example for data formatting.

The dataset includes:
- **15 Distinct Products:** Ranging from flat panel displays (smartphones, TVs) to volumetric appliances (motorcycles, blenders) to fully test the Hybrid Safety Net.
- **45 Clean Studio Images:** Exactly 3 angles per product (e.g., Front, Side, Back) on pure white backgrounds, ensuring the `is_clean_product_shot` flag returns `True`.
- **`sample_catalog.csv`:** A properly formatted catalog mapping the products to their `Image Path 1`, `Image Path 2`, and `Image Path 3`.


---

## ⚠️ Prototype Disclaimer & Production Readiness

**ZiWan - Ad Studio** is provided as an open-source architectural blueprint and Proof-of-Concept (PoC). While the underlying Gemini Enterprise Agent Platform (including **Gemini Omni Flash and Veo**) offers enterprise-grade capabilities, the orchestration layer in this repository has been designed for demonstration and foundational prototyping purposes. 

**Important considerations before production deployment:**
This solution should **not** be deployed into a production environment without undergoing rigorous, enterprise-standard validations. If adapting this architecture for a live project, organizations must implement and validate proper Non-Functional Requirements (NFRs) and functional test suites, including but not limited to:
* **Functional & Integration Testing:** Ensuring end-to-end multi-agent workflows gracefully handle data anomalies, API timeouts, and edge cases.
* **Comprehensive Load Testing:** Validating system stability and throughput under massive, concurrent asynchronous job volumes.
* **Quota & Throttling Management:** Implementing strict API rate-limiting, robust Dead Letter Queues (DLQs), and enforcing quota limits to prevent runaway billing or throttling errors.
* **Security & Auditing:** Conducting thorough security reviews prior to handling live customer data. 

This repository is strictly for educational, prototyping, and foundational architectural design.
