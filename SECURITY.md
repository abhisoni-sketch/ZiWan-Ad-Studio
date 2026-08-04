# 🔒 Security & Compliance Policy

The **ZiWan Ad Studio** team takes data privacy, secret management, and cloud security seriously. This document outlines our security architecture, data handling practices, and vulnerability disclosure policies.

---

## 🛡️ Data Privacy & Foundation Model Policies

1. **Zero Model Training on Customer Data:**
   All generative requests processed via Google Cloud Vertex AI (Gemini 3.5 Flash, Gemini Pro Vision, Veo 3.1 Fast, and Gemini Flash TTS) adhere to strict enterprise data protection agreements. **No customer assets, prompt payloads, or output media are used to train base foundation models.**

2. **Data Isolation & Encryption:**
   * **In Transit:** All communications between micro-agents, client applications, and GCP APIs are encrypted using TLS 1.3.
   * **At Rest:** Storage vaults in Google Cloud Storage (GCS) and Artifact Registry images are encrypted by default using Google-managed encryption keys (KMEK) or customer-managed encryption keys (CMEK).

---

## 🔑 Secret Management & Credentials

* **Zero Hardcoded Secrets:** No API keys, passwords, or service account keys are stored in source code.
* **Environment Variables & Secret Manager:** Secret parameters (e.g. database credentials or custom tokens) must be injected via runtime environment variables or Google Secret Manager.
* **IAM Least-Privilege Access:** Service accounts used for Cloud Run instances (`ziwan-ad-studio-sa`) are granted only minimum required scopes (`roles/aiplatform.user`, `roles/storage.objectAdmin`, `roles/pubsub.publisher`).

---

## 🚫 Pub/Sub Infinite Loop & Cost Safeguards

To prevent runaway Pub/Sub execution queues and cost leakage:
1. **Dead-Letter Queue (DLQ):** Subscriptions automatically redirect failing messages to a Dead-Letter Topic after 5 failed delivery attempts.
2. **Auto-Purge Staging Vaults:** Temporary audio/video rendering files stored in `ziwan-staging-bucket` feature an automated 7-day GCS lifecycle purge rule.
3. **Cloud Run Autoscaling Bounds:** Container scaling is bounded by `min_instances = 0` (scale-to-zero) and `max_instances = 10` to prevent budget runaway.

---

## 📩 Reporting a Security Vulnerability

If you discover a security vulnerability within this repository, please do **NOT** open a public GitHub issue.

Please report the issue directly to the maintainers:
* **Security Contact:** `abhisoni@google.com`
* **Response Time:** We aim to acknowledge reports within 24–48 hours and provide remediation updates.
