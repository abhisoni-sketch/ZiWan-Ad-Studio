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
import base64
import logging
import threading
import requests
from backend.config import RUNNING_ON_GCP, PROJECT_ID

logger = logging.getLogger(__name__)

class EventBroker:
    def __init__(self):
        self.running_on_gcp = RUNNING_ON_GCP
        if self.running_on_gcp:
            from google.cloud import pubsub_v1
            self.publisher = pubsub_v1.PublisherClient()
        else:
            self.publisher = None
            self.local_url_template = "http://127.0.0.1:8000/pubsub/{topic}"

    def publish(self, topic_name: str, payload: dict):
        """Publishes a message to a topic."""
        message_bytes = json.dumps(payload).encode("utf-8")
        
        if self.running_on_gcp:
            topic_path = f"projects/{PROJECT_ID}/topics/{topic_name}"
            try:
                future = self.publisher.publish(topic_path, message_bytes)
                message_id = future.result()
                logger.info(f"Published message {message_id} to GCP topic: {topic_name}")
                return message_id
            except Exception as e:
                logger.error(f"Failed to publish to GCP topic {topic_name}: {e}")
                raise e
        else:
            logger.info(f"Simulating Pub/Sub publish to topic: {topic_name}")
            # Spawn a background thread to handle local HTTP delivery
            t = threading.Thread(
                target=self._deliver_local_message_sync,
                args=(topic_name, message_bytes),
                daemon=False
            )
            t.start()
            return "local-msg-id"

    def _deliver_local_message_sync(self, topic: str, data_bytes: bytes):
        """Delivers the message synchronously in a background thread to simulate Pub/Sub push."""
        import time
        # Short sleep to let the active HTTP request complete before next step starts
        time.sleep(0.5)
        
        url = self.local_url_template.format(topic=topic)
        base64_data = base64.b64encode(data_bytes).decode("utf-8")
        
        envelope = {
            "message": {
                "data": base64_data,
                "messageId": "local-sim-id-12345"
            },
            "subscription": f"projects/{PROJECT_ID}/subscriptions/sub-local-{topic}"
        }
        
        try:
            logger.info(f"Background thread dispatching simulated Pub/Sub to: {url}")
            response = requests.post(url, json=envelope, timeout=30.0)
            if response.status_code >= 400:
                logger.error(f"Local Pub/Sub dispatch to {url} failed with status {response.status_code}: {response.text}")
            else:
                logger.info(f"Local Pub/Sub dispatch to {url} succeeded: {response.status_code}")
        except Exception as e:
            logger.error(f"Error executing local Pub/Sub dispatch to {url}: {e}")
