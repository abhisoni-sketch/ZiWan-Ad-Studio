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
import argparse
import logging
from backend.db_provider import DatabaseProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("batch_worker")

def main():
    parser = argparse.ArgumentParser(description="Google Cloud Batch worker entrypoint for ZiWan - Ad Studio.")
    parser.add_argument("--job_id", required=True, help="Unique Job ID to process.")
    parser.add_argument("--task", required=True, choices=["generation", "stitch"], help="Task to execute ('generation' or 'stitch').")
    args = parser.parse_args()

    job_id = args.job_id
    task = args.task

    logger.info(f"Batch Worker: Starting Task '{task}' for Job ID '{job_id}'")

    db = DatabaseProvider()
    job_data = db.get_job(job_id)
    if not job_data:
        logger.error(f"Batch Worker: Job {job_id} not found in database.")
        sys.exit(1)

    if task == "generation":
        from backend.agents.generation_agent import GenerationAgent
        payload = {
            "job_id": job_id,
            "psn": job_data.get("psn"),
            "category_tab": job_data.get("category"),
            "model_target": job_data.get("model_target"),
            "voice_name": job_data.get("voice_name"),
            "language_code": job_data.get("language_code"),
            "product_metadata": job_data.get("product_metadata"),
            "visual_metadata": job_data.get("visual_metadata"),
            "image_analyses": job_data.get("image_analyses"),
            "best_front_image": job_data.get("best_front_image"),
            "segments": job_data.get("segments")
        }
        agent = GenerationAgent()
        agent.run(payload)

    elif task == "stitch":
        from backend.stitching.stitcher import Stitcher
        payload = {
            "job_id": job_id,
            "clips": job_data.get("clips", [])
        }
        agent = Stitcher()
        agent.run(payload)

    logger.info(f"Batch Worker: Task '{task}' completed successfully for Job ID '{job_id}'")

if __name__ == "__main__":
    main()
