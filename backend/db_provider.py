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
from datetime import datetime
from backend.config import RUNNING_ON_GCP, LOCAL_DB_DIR, PROJECT_ID

class DatabaseProvider:
    def __init__(self):
        if RUNNING_ON_GCP:
            from google.cloud import firestore
            self.db = firestore.Client(project=PROJECT_ID)
            self.collection_name = "jobs"
        else:
            self.db = None
            self.json_path = os.path.join(LOCAL_DB_DIR, "jobs.json")
            if not os.path.exists(self.json_path):
                with open(self.json_path, 'w') as f:
                    json.dump({}, f)

    def _read_local_db(self) -> dict:
        with open(self.json_path, 'r') as f:
            return json.load(f)

    def _write_local_db(self, data: dict):
        with open(self.json_path, 'w') as f:
            json.dump(data, f, indent=2)

    def create_job(self, job_id: str, data: dict) -> dict:
        now = datetime.utcnow().isoformat()
        job_data = {
            **data,
            "job_id": job_id,
            "created_at": now,
            "updated_at": now
        }
        if RUNNING_ON_GCP:
            self.db.collection(self.collection_name).document(job_id).set(job_data)
        else:
            db_data = self._read_local_db()
            db_data[job_id] = job_data
            self._write_local_db(db_data)
        return job_data

    def update_job(self, job_id: str, updates: dict) -> dict:
        now = datetime.utcnow().isoformat()
        if RUNNING_ON_GCP:
            doc_ref = self.db.collection(self.collection_name).document(job_id)
            doc_ref.update({
                **updates,
                "updated_at": now
            })
            return doc_ref.get().to_dict()
        else:
            db_data = self._read_local_db()
            if job_id not in db_data:
                raise KeyError(f"Job {job_id} not found")
            db_data[job_id].update(updates)
            db_data[job_id]["updated_at"] = now
            self._write_local_db(db_data)
            return db_data[job_id]

    def get_job(self, job_id: str) -> dict:
        if RUNNING_ON_GCP:
            doc = self.db.collection(self.collection_name).document(job_id).get()
            if not doc.exists:
                return None
            return doc.to_dict()
        else:
            db_data = self._read_local_db()
            return db_data.get(job_id)

    def list_jobs(self) -> list:
        if RUNNING_ON_GCP:
            docs = self.db.collection(self.collection_name).order_by("created_at", direction="DESCENDING").stream()
            return [doc.to_dict() for doc in docs]
        else:
            db_data = self._read_local_db()
            jobs = list(db_data.values())
            # Sort by created_at descending
            jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return jobs
