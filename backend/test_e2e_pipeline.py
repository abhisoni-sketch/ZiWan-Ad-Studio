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
import time
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    server_url = os.getenv("SERVER_URL", "http://127.0.0.1:8000")
    csv_file_path = os.path.join(BASE_DIR, "ProductData", "MasterCSV_PRODUCTDETAILS_MLE.xlsx")
    psn = "MOBHH69N2XATECZZ"
    
    print("--- E2E Pipeline Integration Test ---")
    
    # 1. Upload CSV file
    print(f"\n1. Uploading product details sheet: {csv_file_path}")
    upload_url = f"{server_url}/api/upload"
    try:
        with open(csv_file_path, "rb") as f:
            response = requests.post(upload_url, files={"file": f})
        
        if response.status_code != 200:
            print(f"Failed to upload file. Server returned {response.status_code}: {response.text}")
            sys.exit(1)
            
        res_data = response.json()
        file_gcs_uri = res_data["file_gcs_uri"]
        print(f"Upload Succeeded! File GCS URI: {file_gcs_uri}")
    except Exception as e:
        print(f"Connection error uploading file: {e}")
        sys.exit(1)

    # 2. Dispatch Agent Fleet
    print(f"\n2. Dispatching Agent Fleet for PSN {psn}...")
    jobs_url = f"{server_url}/api/jobs"
    payload = {
        "category_tab": "mobile v2",
        "model_target": "gemini-omni-flash-preview",
        "psn": psn,
        "file_gcs_uri": file_gcs_uri
    }
    
    try:
        response = requests.post(jobs_url, data=payload)
        if response.status_code != 200:
            print(f"Failed to create job. Server returned {response.status_code}: {response.text}")
            sys.exit(1)
            
        job_data = response.json()
        job_id = job_data["job_id"]
        print(f"Job dispatched successfully! Job ID: {job_id}")
    except Exception as e:
        print(f"Connection error starting job: {e}")
        sys.exit(1)

    # 3. Poll job status until complete or failed
    print(f"\n3. Polling Job {job_id} status...")
    status_url = f"{server_url}/api/jobs/{job_id}"
    
    max_retries = 90  # 3 minutes max
    retry_count = 0
    last_status = None
    
    while retry_count < max_retries:
        try:
            status_response = requests.get(status_url)
            if status_response.status_code == 200:
                job_status = status_response.json()
                current_status = job_status.get("status")
                
                if current_status != last_status:
                    print(f"[{time.strftime('%H:%M:%S')}] Job status changed to: {current_status}")
                    last_status = current_status
                
                if current_status == "COMPLETED":
                    print("\n--- Pipeline Completed Successfully! ---")
                    print(f"Final Video location: {job_status.get('final_video_uri')}")
                    sys.exit(0)
                    
                if current_status == "failed":
                    print(f"\n--- Pipeline Failed! ---")
                    print(f"Error Message: {job_status.get('error')}")
                    sys.exit(1)
            else:
                print(f"Failed to get job status. Status code: {status_response.status_code}")
                
        except Exception as e:
            print(f"Error fetching status: {e}")
            
        time.sleep(2)
        retry_count += 1
        
    print("\nTimeout: Pipeline did not complete within 3 minutes.")
    sys.exit(1)

if __name__ == "__main__":
    main()
