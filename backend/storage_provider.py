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
import shutil
import logging
from urllib.parse import urlparse
from backend.config import USE_REAL_GCS_AND_MODELS, LOCAL_STORAGE_DIR, INGEST_BUCKET

logger = logging.getLogger(__name__)

class StorageProvider:
    def __init__(self):
        if USE_REAL_GCS_AND_MODELS:
            from google.cloud import storage
            self.client = storage.Client()
        else:
            self.client = None

    def upload_file(self, bucket_name: str, source_path: str, destination_blob_name: str) -> str:
        """Uploads a file and returns its URI (gs:// or local absolute path)."""
        if USE_REAL_GCS_AND_MODELS:
            try:
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(destination_blob_name)
                blob.upload_from_filename(source_path, timeout=60)
                return f"gs://{bucket_name}/{destination_blob_name}"
            except Exception as e:
                logger.warning(
                    f"GCS Upload failed for {destination_blob_name} to bucket {bucket_name}: {e}. "
                    f"Falling back to local storage copy."
                )
        
        # Local fallback: copy file to local storage directory
        target_dir = os.path.join(LOCAL_STORAGE_DIR, bucket_name)
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, destination_blob_name)
        
        # Ensure target parent dirs exist
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Avoid copying a file to itself (shutil.SameFileError)
        src_real = os.path.realpath(source_path)
        dst_real = os.path.realpath(target_path)
        if src_real != dst_real:
            shutil.copy2(source_path, target_path)
            
        return target_path

    def download_file(self, uri: str, local_destination_path: str) -> str:
        """Downloads a file from a URI (gs:// or local absolute path) to a local destination path."""
        # Ensure destination folder exists
        os.makedirs(os.path.dirname(local_destination_path), exist_ok=True)

        if uri.startswith("gs://"):
            if not USE_REAL_GCS_AND_MODELS:
                parsed = urlparse(uri)
                bucket_name = parsed.netloc
                blob_name = parsed.path.lstrip('/')
                local_src = os.path.join(LOCAL_STORAGE_DIR, bucket_name, blob_name)
                if os.path.exists(local_src):
                    src_real = os.path.realpath(local_src)
                    dst_real = os.path.realpath(local_destination_path)
                    if src_real != dst_real:
                        shutil.copy2(local_src, local_destination_path)
                    return local_destination_path
                else:
                    raise FileNotFoundError(f"Simulated GCS file not found locally: {local_src}")
            else:
                parsed = urlparse(uri)
                bucket_name = parsed.netloc
                blob_name = parsed.path.lstrip('/')
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                blob.download_to_filename(local_destination_path, timeout=60)
                return local_destination_path
        else:
            # It's already a local path
            if os.path.exists(uri):
                src_real = os.path.realpath(uri)
                dst_real = os.path.realpath(local_destination_path)
                if src_real != dst_real:
                    shutil.copy2(uri, local_destination_path)
                return local_destination_path
            else:
                raise FileNotFoundError(f"Local file not found at: {uri}")

    def read_bytes(self, uri: str) -> bytes:
        """Reads file content directly in memory as bytes."""
        if uri.startswith("gs://"):
            if not USE_REAL_GCS_AND_MODELS:
                parsed = urlparse(uri)
                bucket_name = parsed.netloc
                blob_name = parsed.path.lstrip('/')
                local_src = os.path.join(LOCAL_STORAGE_DIR, bucket_name, blob_name)
                with open(local_src, 'rb') as f:
                    return f.read()
            else:
                parsed = urlparse(uri)
                bucket_name = parsed.netloc
                blob_name = parsed.path.lstrip('/')
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                return blob.download_as_bytes()
        else:
            with open(uri, 'rb') as f:
                return f.read()

    def list_files(self, bucket_name: str, prefix: str = "") -> list:
        """Lists files in a GCS bucket, returning basic metadata."""
        if USE_REAL_GCS_AND_MODELS:
            bucket = self.client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            results = []
            for blob in blobs:
                results.append({
                    "filename": blob.name,
                    "size": blob.size,
                    "updated": blob.updated.isoformat() if blob.updated else None
                })
            return results
        else:
            target_dir = os.path.join(LOCAL_STORAGE_DIR, bucket_name, prefix)
            if not os.path.exists(target_dir):
                return []
            
            results = []
            for root, dirs, files in os.walk(target_dir):
                for f in files:
                    full_path = os.path.join(root, f)
                    stat = os.stat(full_path)
                    import datetime
                    results.append({
                        "filename": os.path.relpath(full_path, os.path.join(LOCAL_STORAGE_DIR, bucket_name)),
                        "size": stat.st_size,
                        "updated": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
            return results

    def delete_file(self, bucket_name: str, filename: str):
        """Deletes a file from a GCS bucket."""
        if USE_REAL_GCS_AND_MODELS:
            try:
                bucket = self.client.bucket(bucket_name)
                blob = bucket.blob(filename)
                blob.delete()
            except Exception as e:
                logger.error(f"Failed to delete {filename} from GCS: {e}")
        else:
            local_path = os.path.join(LOCAL_STORAGE_DIR, bucket_name, filename)
            if os.path.exists(local_path):
                os.remove(local_path)
