#!/usr/bin/env bash
# ==============================================================================
# ZiWan Ad Studio — GCP One-Command Deployment Script
# ==============================================================================
# Automates:
# 1. Verification of gcloud CLI and authentication
# 2. Enabling GCP APIs (Cloud Run, Vertex AI, Pub/Sub, Artifact Registry)
# 3. Provisioning GCS buckets
# 4. Building and deploying container image to Google Cloud Run
# ==============================================================================

set -eo pipefail

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}==========================================================${NC}"
echo -e "${CYAN}   ZiWan Ad Studio — GCP Automated Cloud Deployment      ${NC}"
echo -e "${CYAN}==========================================================${NC}"

# Check for gcloud CLI
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}[Error] gcloud CLI is not installed. Please install Google Cloud SDK.${NC}"
    exit 1
fi

PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION=${REGION:-"us-central1"}
SERVICE_NAME=${SERVICE_NAME:-"ziwan-ad-studio"}

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}[Error] No active GCP project configured in gcloud.${NC}"
    echo "Set your project using: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo -e "${GREEN}Project ID:${NC} ${PROJECT_ID}"
echo -e "${GREEN}GCP Region:${NC} ${REGION}"
echo -e "${GREEN}Service Name:${NC} ${SERVICE_NAME}"
echo -e "${CYAN}----------------------------------------------------------${NC}"

# 1. Enable Required GCP APIs
echo -e "${CYAN}[1/4] Enabling required GCP APIs...${NC}"
gcloud services enable \
    run.googleapis.com \
    aiplatform.googleapis.com \
    pubsub.googleapis.com \
    storage.googleapis.com \
    artifactregistry.googleapis.com \
    --project="${PROJECT_ID}"

# 2. Provision GCS Storage Buckets
echo -e "${CYAN}[2/4] Provisioning GCS Storage Vaults...${NC}"
ASSETS_BUCKET="${PROJECT_ID}-ziwan-assets"
OUTPUTS_BUCKET="${PROJECT_ID}-ziwan-outputs"

gsutil mb -p "${PROJECT_ID}" -l "${REGION}" "gs://${ASSETS_BUCKET}" 2>/dev/null || true
gsutil mb -p "${PROJECT_ID}" -l "${REGION}" "gs://${OUTPUTS_BUCKET}" 2>/dev/null || true

# 3. Build & Deploy Container to Cloud Run
echo -e "${CYAN}[3/4] Deploying ZiWan Ad Studio to Cloud Run...${NC}"
gcloud run deploy "${SERVICE_NAME}" \
    --source . \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --set-env-vars="PROJECT_ID=${PROJECT_ID},GCP_REGION=${REGION},GCS_ASSETS_BUCKET=${ASSETS_BUCKET},GCS_OUTPUTS_BUCKET=${OUTPUTS_BUCKET}" \
    --cpu=2 \
    --memory=4Gi \
    --timeout=3600

# 4. Success Output
echo -e "${CYAN}----------------------------------------------------------${NC}"
echo -e "${GREEN}✅ Deployment Complete!${NC}"
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${REGION}" --format="value(status.url)")
echo -e "${GREEN}ZiWan Ad Studio URL:${NC} ${SERVICE_URL}"
echo -e "${CYAN}==========================================================${NC}"
