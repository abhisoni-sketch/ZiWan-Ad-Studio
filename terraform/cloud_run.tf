# ==============================================================================
# ZiWan Ad Studio — Google Cloud Run Container Deployment
# ==============================================================================
# Deploys the main ZiWan Ad Studio FastAPI web service & video processing engine
# onto Google Cloud Run v2 with configured autoscaling, memory, and vCPU.
# ==============================================================================

resource "google_cloud_run_v2_service" "app_service" {
  name     = var.service_name
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.ziwan_sa.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    max_instance_request_concurrency = var.container_concurrency
    timeout                          = "${var.request_timeout_seconds}s"

    containers {
      image = var.container_image

      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
        cpu_idle = var.min_instances > 0 ? false : true
      }

      ports {
        container_port = 8080
      }

      # Environment Variables injected into the running container instance
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "VERTEX_LOCATION"
        value = var.region
      }
      env {
        name  = "GCS_ASSETS_BUCKET"
        value = google_storage_bucket.assets_vault.name
      }
      env {
        name  = "GCS_OUTPUTS_BUCKET"
        value = google_storage_bucket.outputs_vault.name
      }
      env {
        name  = "GCS_STAGING_BUCKET"
        value = google_storage_bucket.staging_vault.name
      }
      env {
        name  = "PUBSUB_TOPIC_CONTEXT"
        value = google_pubsub_topic.agent_topics["ziwan-context-analysis-topic"].name
      }

      # Health & Startup Probes
      startup_probe {
        failure_threshold = 3
        period_seconds    = 10
        timeout_seconds   = 5
        tcp_socket {
          port = 8080
        }
      }

      liveness_probe {
        http_get {
          path = "/api/health"
          port = 8080
        }
        period_seconds = 30
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.enabled_apis,
    google_service_account.ziwan_sa,
    google_storage_bucket.assets_vault,
    google_storage_bucket.outputs_vault
  ]
}

# ------------------------------------------------------------------------------
# IAM Policy for Cloud Run Service (Public Access Control)
# ------------------------------------------------------------------------------

resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count    = var.allow_unauthenticated ? 1 : 0
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app_service.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
