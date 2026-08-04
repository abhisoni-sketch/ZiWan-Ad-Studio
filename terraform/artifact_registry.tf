# ==============================================================================
# ZiWan Ad Studio — Artifact Registry Docker Store
# ==============================================================================
# Provisions a private Docker repository for storing built application images
# deployed to Google Cloud Run container instances.
# ==============================================================================

resource "google_artifact_registry_repository" "docker_repo" {
  provider = google-beta

  location      = var.region
  repository_id = "ziwan-ad-studio-repo"
  description   = "Docker container registry for ZiWan Ad Studio FastAPI & worker services"
  format        = "DOCKER"

  docker_config {
    immutable_tags = false
  }

  labels = {
    application = "ziwan-ad-studio"
  }

  depends_on = [google_project_service.enabled_apis]
}
