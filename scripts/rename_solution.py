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

target_dir = '/Users/abhisoni/Documents/Ad_Creator/forPublicgit'

def replace_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        c1 = content.replace('ZiWan - Ad Studio', 'ZiWan - Ad Studio')
        c2 = c1.replace('ZiWan - Ad Studio', 'ZiWan - Ad Studio')
        c3 = c2.replace('ZiWan - Ad Studio', 'ZiWan - Ad Studio')
        
        if c3 != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(c3)
            print(f"Updated content in {filepath}")
    except Exception as e:
        print(f"Skipping {filepath}: {e}")

for root, _, files in os.walk(target_dir):
    for file in files:
        if file.endswith(('.md', '.yaml', '.html', '.py', '.txt', '.json', '.csv')):
            replace_in_file(os.path.join(root, file))

# Rename files that contain Ad_Creator
for root, _, files in os.walk(target_dir):
    for file in files:
        if 'Ad_Creator' in file:
            old_path = os.path.join(root, file)
            new_name = file.replace('Ad_Creator', 'ZiWan_Ad_Studio')
            new_path = os.path.join(root, new_name)
            os.rename(old_path, new_path)
            print(f"Renamed file to {new_name}")
