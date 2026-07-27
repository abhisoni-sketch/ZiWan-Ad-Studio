import os

target_dir = '/Users/abhisoni/Documents/Ad_Creator/forPublicgit'
files_to_update = ['ARCHITECTURE.md', 'TECHNICAL_DOSSIER.md']

disclaimer = """

---

## ⚠️ Prototype Disclaimer & Production Readiness

**ZiWan - Ad Studio** is provided as an open-source architectural blueprint and Proof-of-Concept (PoC). While the underlying Gemini Enterprise Agent Platform (including **Gemini Omni Flash and Veo**) offers enterprise-grade capabilities, the orchestration layer in this repository has been designed for demonstration and foundational prototyping purposes. 

**Important considerations before production deployment:**
This solution should **not** be deployed into a production environment without undergoing rigorous, enterprise-standard validations. If adapting this architecture for a live project, organizations must implement and validate proper Non-Functional Requirements (NFRs) and functional test suites, including but not limited to:
* **Functional & Integration Testing:** Ensuring end-to-end multi-agent workflows gracefully handle data anomalies, API timeouts, and edge cases.
* **Comprehensive Load Testing:** Validating system stability and throughput under massive, concurrent asynchronous job volumes.
* **Quota & Throttling Management:** Implementing strict API rate-limiting, robust Dead Letter Queues (DLQs), and enforcing quota limits to prevent runaway billing or throttling errors.
* **Security & Auditing:** Conducting thorough security reviews prior to handling live customer data. 

This repository is strictly for educational, prototyping, and foundational architectural design.
"""

for filename in files_to_update:
    filepath = os.path.join(target_dir, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "Prototype Disclaimer" not in content:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(disclaimer)
            print(f"Appended disclaimer to {filename}")
        else:
            print(f"Disclaimer already exists in {filename}")
    except Exception as e:
        print(f"Error updating {filename}: {e}")
