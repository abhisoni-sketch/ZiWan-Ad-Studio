# ==============================================================================
# ZiWan Ad Studio — Terraform Provider Configuration
# ==============================================================================
# Defines required Terraform version, required provider plugins (Google & Google-Beta),
# and default provider configuration settings.
# ==============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.30"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.30"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Optional Remote Backend Configuration:
  # Uncomment and configure this block to store Terraform state in a GCS bucket.
  # backend "gcs" {
  #   bucket = "YOUR_TF_STATE_BUCKET_NAME"
  #   prefix = "ziwan-ad-studio/state"
  # }
}

# Standard Google Cloud Provider Configuration
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  default_labels = {
    application = "ziwan-ad-studio"
    managed_by  = "terraform"
    environment = var.environment
  }
}

# Beta Google Cloud Provider Configuration (for advanced Cloud Run & Vertex AI features)
provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone

  default_labels = {
    application = "ziwan-ad-studio"
    managed_by  = "terraform"
    environment = var.environment
  }
}
