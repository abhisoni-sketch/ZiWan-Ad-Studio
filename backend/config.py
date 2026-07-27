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

# Base Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_STORAGE_DIR = os.path.join(BASE_DIR, "storage")
GCS_FUSE_MOUNT = os.getenv("GCS_MOUNT_PATH", "/tmp/")
LOCAL_DB_DIR = os.path.join(BASE_DIR, "database")

# True if executing inside deployed Cloud Run service or job environment
RUNNING_ON_GCP = (
    os.getenv("K_SERVICE") is not None 
    or os.getenv("CLOUD_RUN_JOB") is not None 
    or os.getenv("K_JOB") is not None
)

# GCP Specific Configuration
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "dark-torch-384306")
INGEST_BUCKET = os.getenv("INGEST_BUCKET", f"{PROJECT_ID}-ingest-vault")
OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET", f"{PROJECT_ID}-production-vault")

# True if cloud credentials exist to run real GCS storage and Video APIs
USE_REAL_GCS_AND_MODELS = True

# Local Storage Folders Setup
os.makedirs(LOCAL_STORAGE_DIR, exist_ok=True)
os.makedirs(LOCAL_DB_DIR, exist_ok=True)

# Pub/Sub Mock Topics
TOPIC_CONTEXT_AGENT = "topic-context-agent"
TOPIC_SCRIPTING = "topic-scripting"
TOPIC_SEGMENTATION = "topic-segmentation"
TOPIC_GENERATION = "topic-generation"
TOPIC_VERIFICATION = "topic-verification"
TOPIC_STITCH = "topic-stitch"

# Vertex AI Default Model configurations
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gemini-3.1-pro-preview")
DEFAULT_LOCATION = os.getenv("DEFAULT_LOCATION", "asia-south1")

DEFAULT_TEXT_MODEL = os.getenv("DEFAULT_TEXT_MODEL", "gemini-3.1-pro-preview")
DEFAULT_VIDEO_MODEL = os.getenv("DEFAULT_VIDEO_MODEL", "gemini-omni-flash-preview")
DEFAULT_TTS_MODEL = os.getenv("DEFAULT_TTS_MODEL", "gemini-3.1-flash-tts-preview")
DEFAULT_BGM_MODEL = os.getenv("DEFAULT_BGM_MODEL", "lyria-3-pro-preview")

def get_model_location(model_name: str, requested_location: str = None) -> str:
    loc = requested_location or DEFAULT_LOCATION
    m_lower = str(model_name).lower()
    # Preview video, audio, text, and TTS endpoints requiring global scope
    if any(k in m_lower for k in ["lyria", "omni", "veo", "tts", "3.1", "preview"]):
        return "global"
    return loc

DEFAULT_FSN_DATASET = os.getenv("DEFAULT_FSN_DATASET", "")
FONT_DIR = os.getenv("FONT_DIR", os.path.join(BASE_DIR, "assets", "fonts"))
PRODUCT_ALIASES = json.loads(os.getenv('PRODUCT_ALIASES', '{"ACCG7YFMFQQTM93Z": "ACCGJYHMFUKZ2V5N", "RFRHJ4JJPA4UBHGZ": "WMNH2DJCJASPFZE2"}'))
