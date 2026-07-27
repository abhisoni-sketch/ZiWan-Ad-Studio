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
import uuid
import base64
import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
import asyncio

from backend.config import (
    RUNNING_ON_GCP, LOCAL_STORAGE_DIR, PROJECT_ID, INGEST_BUCKET, GCS_FUSE_MOUNT,
    TOPIC_CONTEXT_AGENT, TOPIC_SCRIPTING, TOPIC_SEGMENTATION,
    TOPIC_GENERATION, TOPIC_VERIFICATION, TOPIC_STITCH
)
from backend.storage_provider import StorageProvider
from backend.db_provider import DatabaseProvider
from backend.event_broker import EventBroker
from google.cloud import run_v2
from backend.services.pricing_service import GCPBillingService

STATUS_LEVELS = {
    "ingesting": 1,
    "context_extracting": 2,
    "context_extracted": 3,
    "script_generating": 4,
    "script_generated": 5,
    "segments_creating": 6,
    "segments_created": 7,
    "generating_clips": 8,
    "clips_generated": 9,
    "verifying_clips": 10,
    "clips_verified": 11,
    "stitching": 12,
    "COMPLETED": 13,
    "failed": -1
}

def check_duplicate_trigger(job_id: str, target_level: int) -> bool:
    """Returns True if the job has already processed or is processing this level, indicating a duplicate trigger."""
    if not job_id:
        return False
    from backend.db_provider import DatabaseProvider
    db = DatabaseProvider()
    job = db.get_job(job_id)
    if not job:
        return False
    current_status = job.get("status", "ingesting")
    if current_status == "failed":
        return False  # Always allow retrying failed jobs
    current_level = STATUS_LEVELS.get(current_status, 1)
    return current_level >= target_level

def trigger_batch_worker(job_id: str, task: str = "generation"):
    """Triggers Cloud Run Job ad-creator-worker programmatically with overridden task args."""
    target_level = 8 if task == "generation" else 12
    if check_duplicate_trigger(job_id, target_level):
        logger.warning(f"Cloud Run Job trigger bypassed: Job {job_id} task {task} already processed or processing.")
        return "skipped_duplicate"
    
    if not RUNNING_ON_GCP:
        logger.info(f"Local environment: Spawning local batch worker for Job {job_id} ({task})...")
        import subprocess
        import sys
        python_exe = sys.executable or "python3"
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "run_batch_worker.py")
        cmd = [python_exe, script_path, f"--job_id={job_id}", f"--task={task}"]
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Successfully spawned local batch worker for {job_id} ({task}).")
            return "local-execution-started"
        except Exception as e:
            logger.error(f"Failed to spawn local batch worker for {job_id} ({task}): {e}")
            return None

    try:
        client = run_v2.JobsClient()
        name = f"projects/{PROJECT_ID}/locations/asia-south1/jobs/ad-creator-worker"
        request = run_v2.RunJobRequest(
            name=name,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        args=["run_batch_worker.py", f"--job_id={job_id}", f"--task={task}"]
                    )
                ]
            )
        )
        operation = client.run_job(request=request)
        logger.info(f"Triggered Cloud Run Job for {job_id} ({task}). Operation: {operation.operation.name}")
        return operation.operation.name
    except Exception as e:
        logger.error(f"Failed to trigger Cloud Run Job for {job_id} ({task}): {e}")
        return None

def find_matching_sheet(xl, requested_tab: str):
    """Helper to perform case-insensitive / prefix matching on sheet tabs, falling back to first sheet."""
    sheet_names = xl.sheet_names
    if not sheet_names:
        return None
    
    req_clean = requested_tab.strip().lower()
    
    # Exact case-insensitive match
    for sheet in sheet_names:
        if sheet.strip().lower() == req_clean:
            return sheet
            
    # Fuzzy prefix match
    for sheet in sheet_names:
        if sheet.strip().lower().startswith(req_clean) or req_clean.startswith(sheet.strip().lower()):
            return sheet
            
    # Fallback to the first sheet tab
    return sheet_names[0]

# Import Agent instances
from backend.agents.context_agent import ContextAgent
from backend.agents.scripting_agent import ScriptingAgent
from backend.agents.segmentation_agent import SegmentationAgent
from backend.agents.verification_agent import VerificationAgent
from backend.agents.batch_ingestion_agent import BatchIngestionAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="GenAI Production Studio API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate providers and agents
storage = StorageProvider()
db = DatabaseProvider()
broker = EventBroker()

context_agent = ContextAgent()
scripting_agent = ScriptingAgent()
segmentation_agent = SegmentationAgent()
verification_agent = VerificationAgent()
batch_agent = BatchIngestionAgent() # NEW: Batch Agent

# ----------------- Helper Functions -----------------

def unpack_pubsub_message(envelope: dict) -> dict:
    """Extracts and decodes the JSON payload from a Pub/Sub push envelope."""
    try:
        message = envelope.get("message", {})
        data_base64 = message.get("data", "")
        if not data_base64:
            raise HTTPException(status_code=400, detail="Invalid Pub/Sub envelope: missing message.data")
        
        decoded_bytes = base64.b64decode(data_base64)
        payload = json.loads(decoded_bytes.decode("utf-8"))
        return payload
    except Exception as e:
        logger.error(f"Failed to unpack Pub/Sub message: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse Pub/Sub envelope: {str(e)}")

# ----------------- API Endpoints -----------------

@app.post("/api/upload")
async def upload_file_endpoint(file: UploadFile = File(...)):
    """Uploads the CSV/Excel sheet to ingestion storage and inspects available tabs."""
    try:
        # Save temp file locally
        temp_dir = "/tmp/uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, file.filename)
        
        with open(temp_path, "wb") as buffer:
            shutil_contents = await file.read()
            buffer.write(shutil_contents)
        
        sheet_names = []
        ext = os.path.splitext(file.filename)[1].lower()
        if ext in [".xlsx", ".xls"]:
            import openpyxl
            wb = openpyxl.load_workbook(temp_path, read_only=True)
            sheet_names = wb.sheetnames
            wb.close()

        # Upload using storage provider
        gcs_uri = storage.upload_file(INGEST_BUCKET, temp_path, file.filename)
        
        # Clean up temp
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return {"filename": file.filename, "file_gcs_uri": gcs_uri, "available_tabs": sheet_names}
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@app.get("/api/catalogs")
def list_catalogs():
    """Lists uploaded .xlsx, .xls, and .csv files in the INGEST_BUCKET."""
    try:
        files = storage.list_files(INGEST_BUCKET)
        valid_exts = {".xlsx", ".xls", ".csv"}
        catalogs = [f for f in files if any(f.get("filename", "").lower().endswith(ext) for ext in valid_exts)]
        return {"catalogs": catalogs}
    except Exception as e:
        logger.error(f"Failed to list catalogs: {e}")
        raise HTTPException(status_code=500, detail="Failed to list catalogs")

@app.delete("/api/catalogs/{filename}")
def delete_catalog(filename: str):
    """Deletes a specific catalog file from the INGEST_BUCKET."""
    try:
        storage.delete_file(INGEST_BUCKET, filename)
        return {"status": "deleted", "filename": filename}
    except Exception as e:
        logger.error(f"Failed to delete catalog {filename}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete catalog")

@app.post("/api/inspect-psns")
def inspect_psns(
    file_gcs_uri: str = Form(...),
    category_tabs: Optional[str] = Form(None)
):
    """Scans a catalog sheet for 16-character alphanumeric PSN/FSN codes."""
    import re
    import pandas as pd
    try:
        temp_dir = "/tmp/psn_inspect"
        os.makedirs(temp_dir, exist_ok=True)
        filename = os.path.basename(file_gcs_uri)
        local_path = os.path.join(temp_dir, filename)
        
        # Download from GCS / local
        storage.download_file(file_gcs_uri, local_path)
        
        psns = set()
        psn_pattern = re.compile(r'^[A-Za-z0-9]{16}$')
        
        tabs_to_process = []
        if category_tabs:
            tabs_to_process = [t.strip() for t in category_tabs.split(",")]
        
        if local_path.lower().endswith('.csv'):
            df = pd.read_csv(local_path)
            dfs = [df]
        else:
            xl = pd.ExcelFile(local_path)
            if not tabs_to_process:
                dfs = [xl.parse(sheet) for sheet in xl.sheet_names]
            else:
                dfs = []
                for tab in tabs_to_process:
                    matched = find_matching_sheet(xl, tab)
                    if matched:
                        dfs.append(xl.parse(matched))
            
        for df in dfs:
            for col in df.columns:
                col_str = str(col).lower()
                if any(keyword in col_str for keyword in ['psn', 'fsn', 'product serial', 'id']):
                    for val in df[col].dropna().astype(str):
                        val = val.strip()
                        if psn_pattern.match(val):
                            psns.add(val)
                else:
                    # Scan all rows in the dataframe just in case
                    for val in df[col].dropna().astype(str):
                        val = val.strip()
                        if psn_pattern.match(val):
                            psns.add(val)

        return {"available_psns": list(psns), "total_count": len(psns)}
    except Exception as e:
        logger.error(f"Failed to inspect PSNs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to inspect PSNs: {str(e)}")

@app.post("/api/jobs")
async def create_job(
    category_tab: str = Form("mobile v2"),
    model_target: str = Form("gemini-omni-flash-preview"),
    psn: str = Form(...),
    file_gcs_uri: str = Form(...),
    voice_name: Optional[str] = Form(None),
    language_code: Optional[str] = Form(None),
    image_source_type: Optional[str] = Form("auto"),
    image_gcs_folder: Optional[str] = Form(None),
    gdrive_folder_url: Optional[str] = Form(None),
    model_text: Optional[str] = Form(None),
    model_video: Optional[str] = Form(None),
    model_tts: Optional[str] = Form(None),
    model_bgm: Optional[str] = Form(None),
    gcp_location: Optional[str] = Form(None)
):
    """Creates a video production job and dispatches the pipeline."""
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    logger.info(f"Creating Job {job_id} for PSN {psn}")
    
    # Initialize job payload
    payload = {
        "job_id": job_id,
        "file_gcs_uri": file_gcs_uri,
        "psn": psn.strip(),
        "category_tab": category_tab,
        "model_target": model_target,
        "voice_name": voice_name,
        "language_code": language_code,
        "image_source_type": image_source_type,
        "image_gcs_folder": image_gcs_folder,
        "gdrive_folder_url": gdrive_folder_url,
        "model_text": model_text,
        "model_video": model_video,
        "model_tts": model_tts,
        "model_bgm": model_bgm,
        "gcp_location": gcp_location,
        "video_specs": {
            "resolution": "1080p",
            "aspect_ratio": "16:9"
        }
    }
    
    # Write initial job status to database
    db.create_job(job_id, {
        "status": "ingesting",
        "psn": psn,
        "category": category_tab,
        "model_target": model_target,
        "file_gcs_uri": file_gcs_uri,
        "voice_name": voice_name,
        "language_code": language_code,
        "image_source_type": image_source_type,
        "image_gcs_folder": image_gcs_folder,
        "gdrive_folder_url": gdrive_folder_url,
        "model_text": model_text,
        "model_video": model_video,
        "model_tts": model_tts,
        "model_bgm": model_bgm,
        "gcp_location": gcp_location
    })
    
    # Trigger Context Agent by publishing ingestion payload
    broker.publish(TOPIC_CONTEXT_AGENT, payload)
    
    return {"job_id": job_id, "status": "ingesting"}

@app.post("/api/gemini/jobs")
async def create_gemini_job(
    category_tab: str = Form("mobile v2"),
    model_target: str = Form("gemini-omni-flash-preview"),
    psn: str = Form(...),
    file_gcs_uri: str = Form(...),
    voice_name: Optional[str] = Form(None),
    language_code: Optional[str] = Form(None),
    image_source_type: Optional[str] = Form("auto"),
    image_gcs_folder: Optional[str] = Form(None),
    gdrive_folder_url: Optional[str] = Form(None),
    model_text: Optional[str] = Form(None),
    model_video: Optional[str] = Form(None),
    model_tts: Optional[str] = Form(None),
    model_bgm: Optional[str] = Form(None),
    gcp_location: Optional[str] = Form(None)
):
    """Creates a video production job and dispatches the pipeline for Gemini Enterprise."""
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    logger.info(f"Creating Gemini Job {job_id} for PSN {psn}")
    
    # Initialize job payload
    payload = {
        "job_id": job_id,
        "file_gcs_uri": file_gcs_uri,
        "psn": psn.strip(),
        "category_tab": category_tab,
        "model_target": model_target,
        "voice_name": voice_name,
        "language_code": language_code,
        "image_source_type": image_source_type,
        "image_gcs_folder": image_gcs_folder,
        "gdrive_folder_url": gdrive_folder_url,
        "model_text": model_text,
        "model_video": model_video,
        "model_tts": model_tts,
        "model_bgm": model_bgm,
        "gcp_location": gcp_location,
        "video_specs": {
            "resolution": "1080p",
            "aspect_ratio": "16:9"
        }
    }
    
    # Write initial job status to database
    db.create_job(job_id, {
        "status": "ingesting",
        "psn": psn,
        "category": category_tab,
        "model_target": model_target,
        "file_gcs_uri": file_gcs_uri,
        "voice_name": voice_name,
        "language_code": language_code,
        "image_source_type": image_source_type,
        "image_gcs_folder": image_gcs_folder,
        "gdrive_folder_url": gdrive_folder_url,
        "model_text": model_text,
        "model_video": model_video,
        "model_tts": model_tts,
        "model_bgm": model_bgm,
        "gcp_location": gcp_location
    })
    
    # Trigger Context Agent by publishing ingestion payload
    broker.publish(TOPIC_CONTEXT_AGENT, payload)
    
    return {
        "actionResponse": {"type": "NEW_MESSAGE"},
        "cardsV2": [{
            "cardId": f"job-status-{job_id}",
            "card": {
                "header": {"title": "🎬 Creative Studio", "subtitle": "Job Dispatched"},
                "sections": [{"widgets": [{"textParagraph": {"text": f"Your video job for PSN **{psn}** has been queued and is extracting context. I will notify you when rendering is complete."}}]}]
            }
        }]
    }

@app.post("/api/batch")
async def create_batch_job(
    file_gcs_uri: str = Form(...),
    model_target: str = Form("gemini-omni-flash-preview"),
    voice_name: Optional[str] = Form(None),
    language_code: Optional[str] = Form(None)
):
    """Creates a batch production job, parsing a full spreadsheet to fan-out individual jobs."""
    batch_id = f"batch-{uuid.uuid4().hex[:8]}"
    logger.info(f"Creating Batch Job {batch_id} for file {file_gcs_uri}")
    
    payload = {
        "batch_id": batch_id,
        "file_gcs_uri": file_gcs_uri,
        "model_target": model_target,
        "voice_name": voice_name,
        "language_code": language_code
    }
    
    # Trigger Batch Agent by publishing to a dedicated topic
    broker.publish("topic-batch-ingest", payload)
    
    return {"batch_id": batch_id, "status": "batch_processing_started"}

@app.post("/api/gemini/batch")
async def create_gemini_batch_job(
    file_gcs_uri: str = Form(...),
    model_target: str = Form("gemini-omni-flash-preview"),
    voice_name: Optional[str] = Form(None),
    language_code: Optional[str] = Form(None)
):
    """Creates a batch production job for Gemini Enterprise."""
    batch_id = f"batch-{uuid.uuid4().hex[:8]}"
    logger.info(f"Creating Gemini Batch Job {batch_id} for file {file_gcs_uri}")
    
    payload = {
        "batch_id": batch_id,
        "file_gcs_uri": file_gcs_uri,
        "model_target": model_target,
        "voice_name": voice_name,
        "language_code": language_code
    }
    
    # Trigger Batch Agent by publishing to a dedicated topic
    broker.publish("topic-batch-ingest", payload)
    
    return {
        "actionResponse": {"type": "NEW_MESSAGE"},
        "cardsV2": [{
            "cardId": f"job-status-{batch_id}",
            "card": {
                "header": {"title": "🎬 Creative Studio", "subtitle": "Job Dispatched"},
                "sections": [{"widgets": [{"textParagraph": {"text": f"Your batch spreadsheet job for **{file_gcs_uri}** has been queued."}}]}]
            }
        }]
    }

@app.get("/api/config")
def get_project_config():
    """Returns basic GCP and environment configurations."""
    from backend.config import PROJECT_ID, DEFAULT_LOCATION, INGEST_BUCKET
    return {
        "project_id": PROJECT_ID,
        "location": DEFAULT_LOCATION,
        "ingest_bucket": INGEST_BUCKET
    }

@app.get("/api/jobs")
async def get_all_jobs():
    """Lists all tracked jobs."""
    return db.list_jobs()

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Retrieves status details for a specific job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/jobs/{job_id}/stream")
async def stream_job_status(job_id: str):
    """Streams job status and logs in real-time using Server-Sent Events (SSE)."""
    async def event_generator():
        while True:
            job = db.get_job(job_id)
            if not job:
                yield {"data": json.dumps({"status": "not_found"})}
                break
            
            yield {"data": json.dumps(job)}
            
            if job.get("status") in ["COMPLETED", "failed"]:
                break
                
            await asyncio.sleep(2)
            
    return EventSourceResponse(event_generator())

@app.get("/api/finops/pricing")
def get_live_pricing(location: str = "asia-south1"):
    """Fetches live pricing SKUs for GenAI models and infrastructure in the target region."""
    try:
        billing = GCPBillingService()
        rates = billing.get_live_pricing_skus(location)
        return {"location": location, "rates": rates}
    except Exception as e:
        logger.error(f"Failed to get pricing SKUs: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pricing SKUs")

@app.post("/api/finops/calculate-simulation")
def calculate_simulation(
    video_volume: int = Form(...),
    discount_percent: float = Form(...),
    custom_margin_percent: float = Form(...),
    model_text: str = Form(...),
    model_video: str = Form(...),
    model_tts: str = Form(...),
    model_bgm: str = Form(...),
    avg_duration_sec: int = Form(...),
    gcp_location: str = Form("asia-south1")
):
    """Computes total campaign investment, component breakdowns, and volume savings for campaign projections."""
    try:
        billing_service = GCPBillingService()
        # Simulated single job usage metadata based on standard metrics
        usage_metadata = {
            "text_input_tokens": 2500,
            "text_output_tokens": 750,
            "video_model": model_video,
            "video_duration_sec": avg_duration_sec,
            "tts_chars": 600,
            "bgm_duration_sec": avg_duration_sec,
            "worker_vcpu_sec": avg_duration_sec * 8, # 8 seconds of processing vCPU per output second
            "worker_ram_gib_sec": avg_duration_sec * 8 * 2.0 # 2 GiB allocation
        }
        
        single_cost_details = billing_service.calculate_job_cost(usage_metadata, gcp_location)
        single_video_cost = single_cost_details["total_cost"]
        
        gross_total = single_video_cost * video_volume
        
        # Volume Discount
        discount_amount = gross_total * (discount_percent / 100.0)
        net_after_discount = gross_total - discount_amount
        
        # Markup Margin
        margin_amount = net_after_discount * (custom_margin_percent / 100.0)
        final_investment = net_after_discount + margin_amount
        
        # Compute components total
        components = single_cost_details["component_costs"]
        total_components = {}
        for k, val in components.items():
            total_components[k] = round(val * video_volume, 4)

        return {
            "gcp_location": gcp_location,
            "single_unit_cost_usd": single_video_cost,
            "gross_campaign_cost_usd": round(gross_total, 4),
            "discount_savings_usd": round(discount_amount, 4),
            "custom_margin_earnings_usd": round(margin_amount, 4),
            "total_campaign_investment_usd": round(final_investment, 4),
            "component_total_breakdown": total_components,
            "rates_used": single_cost_details["rates"]
        }
    except Exception as e:
        logger.error(f"Failed to calculate pricing simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Simulation calculation failed: {str(e)}")

@app.get("/api/audit-trail")
async def get_audit_trail():
    """Lists historical job audit records from Firestore."""
    jobs = db.list_jobs()
    records = []
    for j in jobs:
        records.append({
            "job_id": j.get("job_id"),
            "psn": j.get("psn"),
            "category": j.get("category"),
            "model_target": j.get("model_target"),
            "created_at": j.get("created_at", ""),
            "status": j.get("status"),
            "segments": len(j.get("segments", [])),
            "final_video_uri": j.get("final_video_uri")
        })
    return {"audit_records": records}

@app.get("/api/audit-trail/{job_id}")
async def get_audit_detail(job_id: str):
    """Fetches detailed audit details for a specific job."""
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.get("/api/video/{job_id}")
async def get_final_video(job_id: str):
    """Serves the final completed video file."""
    job = db.get_job(job_id)
    if not job or job.get("status") != "COMPLETED":
        raise HTTPException(status_code=400, detail="Video is not ready or job failed")
        
    final_uri = job.get("final_video_uri")
    if final_uri.startswith("gs://"):
        # Download GCS file to local temp and serve
        temp_path = os.path.join(GCS_FUSE_MOUNT, f"stream_{job_id}.mp4")
        storage.download_file(final_uri, temp_path)
        return FileResponse(temp_path, media_type="video/mp4", filename=f"{job_id}_final.mp4")
    else:
        # Serve local storage file directly
        if os.path.exists(final_uri):
            return FileResponse(final_uri, media_type="video/mp4")
        else:
            raise HTTPException(status_code=404, detail="Local video file not found")

@app.get("/api/storage/clips/{filename}")
async def get_clip_file(filename: str):
    """Serves individual generated clip files."""
    # Clips bucket/folder name is 'clips'
    safe_filename = os.path.basename(filename)
    local_path = os.path.join(LOCAL_STORAGE_DIR, "clips", safe_filename)
    if os.path.exists(local_path):
        return FileResponse(local_path, media_type="video/mp4")
    else:
        raise HTTPException(status_code=404, detail="Clip not found")

# ----------------- Pub/Sub Webhooks -----------------

@app.post("/pubsub/topic-batch-ingest")
async def handle_batch_pubsub(envelope: dict, background_tasks: BackgroundTasks):
    payload = unpack_pubsub_message(envelope)
    background_tasks.add_task(batch_agent.run, payload)
    return {"status": "enqueued"}

@app.post("/pubsub/topic-context-agent")
async def handle_context_pubsub(envelope: dict, background_tasks: BackgroundTasks):
    payload = unpack_pubsub_message(envelope)
    job_id = payload.get("job_id")
    if check_duplicate_trigger(job_id, 2):
        logger.warning(f"Pub/Sub ContextAgent trigger bypassed: Job {job_id} already processing or completed.")
        return {"status": "skipped_duplicate"}
    background_tasks.add_task(context_agent.run, payload)
    return {"status": "enqueued"}

@app.post("/pubsub/topic-scripting")
async def handle_scripting_pubsub(envelope: dict, background_tasks: BackgroundTasks):
    payload = unpack_pubsub_message(envelope)
    job_id = payload.get("job_id")
    if check_duplicate_trigger(job_id, 4):
        logger.warning(f"Pub/Sub Scripting trigger bypassed: Job {job_id} already processing or completed.")
        return {"status": "skipped_duplicate"}
    background_tasks.add_task(scripting_agent.run, payload)
    return {"status": "enqueued"}

@app.post("/pubsub/topic-segmentation")
async def handle_segmentation_pubsub(envelope: dict, background_tasks: BackgroundTasks):
    payload = unpack_pubsub_message(envelope)
    job_id = payload.get("job_id")
    if check_duplicate_trigger(job_id, 6):
        logger.warning(f"Pub/Sub Segmentation trigger bypassed: Job {job_id} already processing or completed.")
        return {"status": "skipped_duplicate"}
    background_tasks.add_task(segmentation_agent.run, payload)
    return {"status": "enqueued"}

@app.post("/pubsub/topic-generation")
async def handle_generation_pubsub(envelope: dict, background_tasks: BackgroundTasks):
    payload = unpack_pubsub_message(envelope)
    job_id = payload.get("job_id")
    if check_duplicate_trigger(job_id, 8):
        logger.warning(f"Pub/Sub Generation trigger bypassed: Job {job_id} already processing or completed.")
        return {"status": "skipped_duplicate"}
    background_tasks.add_task(trigger_batch_worker, job_id, "generation")
    return {"status": "enqueued"}

@app.post("/pubsub/topic-verification")
async def handle_verification_pubsub(envelope: dict, background_tasks: BackgroundTasks):
    payload = unpack_pubsub_message(envelope)
    job_id = payload.get("job_id")
    if check_duplicate_trigger(job_id, 10):
        logger.warning(f"Pub/Sub Verification trigger bypassed: Job {job_id} already processing or completed.")
        return {"status": "skipped_duplicate"}
    background_tasks.add_task(verification_agent.run, payload)
    return {"status": "enqueued"}

@app.post("/pubsub/topic-stitch")
async def handle_stitch_pubsub(envelope: dict, background_tasks: BackgroundTasks):
    payload = unpack_pubsub_message(envelope)
    job_id = payload.get("job_id")
    if check_duplicate_trigger(job_id, 12):
        logger.warning(f"Pub/Sub Stitch trigger bypassed: Job {job_id} already processing or completed.")
        return {"status": "skipped_duplicate"}
    background_tasks.add_task(trigger_batch_worker, job_id, "stitch")
    return {"status": "enqueued"}

# ----------------- Serve Frontend -----------------

# Fallback serving of frontend index
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

@app.get("/")
async def read_index():
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse(status_code=404, content={"message": "Frontend index.html not found"})

# Serve static files for app.js/styles
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir), name="frontend")
