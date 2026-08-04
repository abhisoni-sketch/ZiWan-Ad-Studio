# 🏗️ ZiWan Ad Studio — Infrastructure as Code (Terraform)

This directory contains the production-ready **Terraform (HCL)** module to provision and manage the complete Google Cloud Platform (GCP) infrastructure for **ZiWan Ad Studio**.

---

## 📐 Architecture & Resource Overview

The Terraform configuration provisions the following GCP resources:

```
                  ┌───────────────────────────────────────────────────────────┐
                  │                 Google Cloud Platform                     │
                  │                                                           │
                  │  ┌─────────────────────────────────────────────────────┐  │
                  │  │ Cloud Run v2 (ziwan-ad-studio)                      │  │
                  │  │  - 2 vCPU / 4 GB RAM                                │  │
                  │  │  - Autoscaling (0 to 10 instances)                  │  │
                  │  │  - Health Probes & 3600s Timeout                    │  │
                  │  └──────────────────┬──────────────────────────────────┘  │
                  │                     │                                     │
       ┌──────────┴───────────────┬─────┴──────────────────┬──────────────────┴──────────────┐
       │                          │                        │                                 │
       ▼                          ▼                        ▼                                 ▼
┌───────────────┐        ┌──────────────────┐    ┌──────────────────┐               ┌──────────────────┐
│ Vertex AI API │        │ GCS Buckets (x3) │    │ Pub/Sub Topics   │               │ Artifact         │
│ - Gemini Flash│        │ - Assets Vault   │    │ - Context        │               │ Registry Repo    │
│ - Veo 3.1 Fast│        │ - Outputs Vault  │    │ - Scripting      │               │ - ziwan-ad-studio│
│ - Gemini TTS  │        │ - Auto-purge     │    │ - Generation     │               │   -repo          │
└───────────────┘        │   Staging Vault  │    │ - DLQ Safeguard  │               └──────────────────┘
                         └──────────────────┘    └──────────────────┘
```

---

## 📁 Module Structure

```
terraform/
├── providers.tf            # Provider definitions & backend state settings
├── variables.tf            # Input variables with validation & default values
├── services.tf             # Automated GCP Service API enabler
├── storage.tf               # GCS Buckets (Assets, Outputs, Auto-purging Staging)
├── iam.tf                  # Service Account & least-privilege IAM roles
├── pubsub.tf               # Cloud Pub/Sub topics, subscriptions, & DLQ safeguards
├── artifact_registry.tf    # Docker container registry configuration
├── cloud_run.tf            # Cloud Run v2 container service & scaling policies
├── outputs.tf              # Exported deployment URLs, Bucket names, & SA email
├── terraform.tfvars.example# Example variable customization template
└── README.md               # Infrastructure documentation (this file)
```

---

## 🚀 Quickstart Deployment Guide

### Prerequisites
1. **Terraform CLI** (`>= 1.5.0` installed): Check with `terraform -v`.
2. **Google Cloud SDK (`gcloud` CLI)** installed and authenticated.
3. A GCP Project with Billing enabled.

### Step 1: Authenticate with Google Cloud
Ensure your local `gcloud` identity has Application Default Credentials (ADC) and Project Owner/Editor permissions:

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### Step 2: Configure Deployment Variables
Copy the example variables file to `terraform.tfvars`:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` to set your GCP Project ID:
```hcl
project_id  = "your-gcp-project-id"
region      = "us-central1"
environment = "production"
```

### Step 3: Initialize & Validate Terraform
Initialize provider plugins and validate the HCL syntax:

```bash
terraform init
terraform validate
```

### Step 4: Preview Infrastructure Plan
Generate and review the execution plan before creating real resources:

```bash
terraform plan
```

### Step 5: Apply Infrastructure Deployment
Provision all GCP resources:

```bash
terraform apply
```

*Confirm the execution plan by typing `yes` when prompted.*

---

## 🔒 Security & Best Practices Implemented

1. **Least-Privilege IAM:** The dedicated service account `ziwan-ad-studio-sa` is granted only required roles (`roles/aiplatform.user`, `roles/storage.objectAdmin`, `roles/pubsub.publisher`, `roles/logging.logWriter`).
2. **Storage Cost Governance:** The temporary rendering staging bucket (`ziwan-staging-bucket`) features an automated 7-day lifecycle purge rule to prevent storage cost leaks from raw audio/video clips.
3. **Pub/Sub Dead-Letter Queue (DLQ):** Prevents runaway billable retry loops by redirecting failing event payloads to a DLQ topic after 5 failed delivery attempts.
4. **Scale-to-Zero Cloud Run:** Default `min_instances = 0` ensures zero idle compute charges when the pipeline is inactive.

---

## 🧹 Destroying Infrastructure

To teardown all provisioned infrastructure and prevent ongoing charges:

```bash
terraform destroy
```
