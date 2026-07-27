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
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.context_agent import ContextAgent

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    csv_path = os.path.join(BASE_DIR, "ProductData", "MasterCSV_PRODUCTDETAILS_MLE.xlsx")
    psn = "MOBHH69N2XATECZZ"
    
    print(f"Testing ContextAgent parsing on {csv_path} with PSN {psn}...")
    agent = ContextAgent()
    try:
        metadata = agent.parse_product_xlsx(csv_path, "Mobile", psn)
        print("\n--- Parsing Succeeded! ---")
        print(json.dumps(metadata, indent=2))
    except Exception as e:
        print(f"\n--- Parsing Failed! ---")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
