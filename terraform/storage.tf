# ==============================================================================
# ZiWan Ad Studio — Google Cloud Storage (GCS) Buckets
# ==============================================================================
# Provisions isolated storage vaults for raw product assets, generated 1080p
# video outputs, and auto-purging temporary rendering staging files.
# ==============================================================================

# Random suffix generator to ensure globally unique GCS bucket names
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# ------------------------------------------------------------------------------
# 1. Product Assets Storage Vault (Input product images, CSV catalogs, brand guidelines)
# ------------------------------------------------------------------------------

resource "google_storage_bucket" "assets_vault" {
  name          = "${var.project_id}-ziwan-assets-${random_id.bucket_suffix.hex}"
  location      = var.gcs_location
  storage_class = var.storage_class

  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  labels = {
    vault_type = "assets_input"
  }

  depends_on = [google_project_service.enabled_apis]
}

# ------------------------------------------------------------------------------
# 2. Rendered Video Outputs Vault (Master 1080p MP4 ads, thumbnail storyboards)
# ------------------------------------------------------------------------------

resource "google_storage_bucket" "outputs_vault" {
  name          = "${var.project_id}-ziwan-outputs-${random_id.bucket_suffix.hex}"
  location      = var.gcs_location
  storage_class = var.storage_class

  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST"]
    response_header = ["*"]
    max_age_seconds = 3600
  }

  labels = {
    vault_type = "video_outputs"
  }

  depends_on = [google_project_service.enabled_apis]
}

# ------------------------------------------------------------------------------
# 3. Temporary Staging Vault (FFmpeg video clips, TTS audio segments, intermediate frames)
# Includes automated lifecycle purge rules to eliminate storage cost leakage.
# ------------------------------------------------------------------------------

resource "google_storage_bucket" "staging_vault" {
  name          = "${var.project_id}-ziwan-staging-${random_id.bucket_suffix.hex}"
  location      = var.gcs_location
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
  force_destroy               = true

  # Automated Lifecycle Rule: Purge temporary rendering files older than var.staging_retention_days
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = var.staging_retention_days
    }
  }

  labels = {
    vault_type = "rendering_staging"
    auto_purge = "true"
  }

  depends_on = [google_project_service.enabled_apis]
}
