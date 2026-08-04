# ==============================================================================
# ZiWan Ad Studio — Terraform Output Values
# ==============================================================================
# Exposes generated resource URLs, GCS bucket URIs, Pub/Sub topics, and IAM service
# account emails for downstream integration and CI/CD pipelines.
# ==============================================================================

output "cloud_run_url" {
  value       = google_cloud_run_v2_service.app_service.uri
  description = "The public HTTPS URL of the deployed ZiWan Ad Studio Cloud Run service."
}

output "service_account_email" {
  value       = google_service_account.ziwan_sa.email
  description = "The email address of the dedicated ZiWan Ad Studio execution service account."
}

output "gcs_assets_bucket_name" {
  value       = google_storage_bucket.assets_vault.name
  description = "Name of the GCS bucket for raw product assets and image catalogs."
}

output "gcs_outputs_bucket_name" {
  value       = google_storage_bucket.outputs_vault.name
  description = "Name of the GCS bucket for generated 1080p video outputs."
}

output "gcs_staging_bucket_name" {
  value       = google_storage_bucket.staging_vault.name
  description = "Name of the GCS bucket for auto-purged temporary rendering files."
}

output "artifact_registry_repo" {
  value       = google_artifact_registry_repository.docker_repo.name
  description = "The Artifact Registry Docker repository name."
}

output "pubsub_topics" {
  value       = { for k, v in google_pubsub_topic.agent_topics : k => v.id }
  description = "Map of all created Cloud Pub/Sub topic IDs."
}
