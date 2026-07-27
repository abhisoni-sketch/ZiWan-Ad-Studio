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
import logging
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from backend.config import PROJECT_ID, BASE_DIR

def main():
    project_id = PROJECT_ID
    model_target = os.getenv("DEFAULT_VIDEO_MODEL", "veo-3.1-fast-generate-001")
    
    print("--- Test Real Video Generation ---")
    print(f"Initializing GenAI client for project: {project_id}")
    
    try:
        client = genai.Client(vertexai=True, project=project_id, location="us-central1")
        
        prompt = "A close up cinematic shot of a modern smartphone on a marble table, slow pan right."
        print(f"Calling generate_videos with model: {model_target}")
        print(f"Prompt: {prompt}")
        
        # Start the video generation operation
        operation = client.models.generate_videos(
            model=model_target,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                duration_seconds=5,
                aspect_ratio="16:9",
                number_of_videos=1
            )
        )
        
        print("Operation started. Polling status in a loop...")
        
        while not operation.done:
            print("Operation is in progress... waiting 10 seconds.")
            time.sleep(10)
            operation = client.operations.get(operation)
            
        print("\nOperation completed! Processing result...")
        print("Operation details:")
        import json
        print(json.dumps(operation.model_dump(), indent=2))
        
        result = operation.result
        if result and getattr(result, "generated_videos", None):
            output_path = os.path.join(BASE_DIR, "storage", "test_gen_video.mp4")
            video_bytes = result.generated_videos[0].video.video_bytes
            with open(output_path, "wb") as f:
                f.write(video_bytes)
            print(f"Success! Video generated and saved to: {output_path}")
        else:
            print("No videos returned in the operation result.")
            
    except Exception as e:
        print(f"\nGeneration failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
