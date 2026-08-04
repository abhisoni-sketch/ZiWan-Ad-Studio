# ==============================================================================
# ZiWan Ad Studio — Identity & Access Management (IAM)
# ==============================================================================
# Creates a dedicated Service Account for Cloud Run worker processes and grants
# least-privilege permissions for Vertex AI, GCS, Pub/Sub, Logging, and Monitoring.
# ==============================================================================

# Dedicated Service Account for ZiWan Ad Studio Execution
resource "google_service_account" "ziwan_sa" {
  account_id   = "ziwan-ad-studio-sa"
  display_name = "ZiWan Ad Studio Execution Service Account"
  description  = "Service Account used by Cloud Run container instances to call Vertex AI (Gemini/Veo), read/write GCS vaults, and publish Pub/Sub events."
  project      = var.project_id
}

# ------------------------------------------------------------------------------
# IAM Role Bindings (Least-Privilege Principles)
# ------------------------------------------------------------------------------

locals {
  service_account_roles = [
    "roles/aiplatform.user",            # Call Vertex AI APIs (Gemini 3.5 Flash, Veo 3.1 Fast)
    "roles/pubsub.publisher",           # Publish async execution messages to Pub/Sub topics
    "roles/pubsub.subscriber",          # Subscribe to agent message topics
    "roles/logging.logWriter",          # Write structured logs to Cloud Logging
    "roles/monitoring.metricWriter",    # Emit latency & rendering metrics to Cloud Monitoring
    "roles/eventarc.eventReceiver"      # Receive Eventarc trigger events
  ]
}

resource "google_project_iam_member" "sa_role_bindings" {
  for_each = toset(local.service_account_roles)

  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.ziwan_sa.email}"
}

# Object-Level Access to Asset & Output GCS Buckets
resource "google_storage_bucket_iam_member" "asset_bucket_access" {
  bucket = google_storage_bucket.assets_vault.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.ziwan_sa.email}"
}

resource "google_storage_bucket_iam_member" "output_bucket_access" {
  bucket = google_storage_bucket.outputs_vault.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.ziwan_sa.email}"
}

resource "google_storage_bucket_iam_member" "staging_bucket_access" {
  bucket = google_storage_bucket.staging_vault.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.ziwan_sa.email}"
}
