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

import argparse
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_single_test(category_tab: str, psn: str, file_uri: str, model_target: str):
    url = "http://localhost:8000/api/jobs"
    
    payload = {
        "category_tab": category_tab,
        "psn": psn,
        "file_gcs_uri": file_uri,
        "model_target": model_target
    }

    logger.info(f"Triggering single test job...")
    logger.info(f" -> Category: {category_tab}")
    logger.info(f" -> PSN: {psn}")
    logger.info(f" -> File: {file_uri}")
    
    try:
        response = requests.post(url, data=payload)
        
        if response.status_code == 200:
            logger.info("✅ Successfully triggered job!")
            logger.info(f"Response: {response.json()}")
            logger.info("Check your FastAPI server logs to watch the ContextAgent fetch the dynamic Firestore rules!")
        else:
            logger.error(f"❌ Failed to trigger job. Status: {response.status_code}")
            logger.error(f"Error details: {response.text}")
            
    except requests.exceptions.ConnectionError:
        logger.error("❌ Connection refused. Is your FastAPI server (uvicorn backend.main:app --reload) running on port 8000?")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger a single GenAI Video job.")
    parser.add_argument("--category", type=str, required=True, help="Category tab name (e.g., tv, ac)")
    parser.add_argument("--psn", type=str, required=True, help="Product Serial Number (e.g., TVSHATFHDPHR7Z7T)")
    parser.add_argument("--file", type=str, required=True, help="GCS URI to the Excel/CSV file (e.g., gs://my-bucket/sheet.xlsx)")
    parser.add_argument("--model", type=str, default="gemini-omni-flash-preview", help="Target model to use")
    
    args = parser.parse_args()
    run_single_test(args.category, args.psn, args.file, args.model)
