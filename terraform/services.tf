# ==============================================================================
# ZiWan Ad Studio — GCP Service APIs Activation
# ==============================================================================
# Automatically enables all required Google Cloud APIs for Cloud Run,
# Vertex AI (Gemini & Veo), Cloud Pub/Sub, GCS, and Artifact Registry.
# ==============================================================================

locals {
  gcp_services = [
    "run.googleapis.com",             # Google Cloud Run Service API
    "aiplatform.googleapis.com",      # Vertex AI API (Gemini 3.5 Flash, Veo Video)
    "pubsub.googleapis.com",          # Cloud Pub/Sub Messaging Engine
    "storage.googleapis.com",         # Google Cloud Storage API
    "artifactregistry.googleapis.com",# Artifact Registry Docker Container Store
    "cloudbuild.googleapis.com",      # Cloud Build API
    "iam.googleapis.com",             # Identity and Access Management API
    "logging.googleapis.com",         # Cloud Logging API
    "monitoring.googleapis.com"       # Cloud Monitoring API
  ]
}

resource "google_project_service" "enabled_apis" {
  for_each = var.enable_gcp_apis ? toset(local.gcp_services) : toset([])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false

  # Prevents race conditions during initial deployment
  disable_dependent_services = false
}
