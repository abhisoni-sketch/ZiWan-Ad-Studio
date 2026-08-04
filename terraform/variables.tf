# ==============================================================================
# ZiWan Ad Studio — Terraform Input Variables
# ==============================================================================
# Exhaustive variable declarations for project settings, region selection,
# container configurations, storage rules, and messaging infrastructure.
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. Core GCP Project Configuration
# ------------------------------------------------------------------------------

variable "project_id" {
  type        = string
  description = "The Google Cloud Project ID where ZiWan Ad Studio infrastructure will be deployed."
  validation {
    condition     = length(var.project_id) > 0
    error_message = "The project_id variable must not be empty."
  }
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "The primary GCP region for Cloud Run, GCS, Pub/Sub, and Vertex AI resources (e.g. us-central1, asia-south1)."
}

variable "zone" {
  type        = string
  default     = "us-central1-a"
  description = "The primary GCP zone for compute resources."
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Deployment environment tag (e.g., development, staging, production)."
}

# ------------------------------------------------------------------------------
# 2. Cloud Run Service Configuration
# ------------------------------------------------------------------------------

variable "service_name" {
  type        = string
  default     = "ziwan-ad-studio"
  description = "The name of the main Cloud Run container service."
}

variable "container_image" {
  type        = string
  default     = "gcr.io/cloudrun/hello"
  description = "The full Docker container image path in Artifact Registry / GCR to deploy on Cloud Run."
}

variable "cpu_limit" {
  type        = string
  default     = "2000m"
  description = "vCPU allocation limit for the Cloud Run container (e.g. 1000m = 1 vCPU, 2000m = 2 vCPU, 4000m = 4 vCPU)."
}

variable "memory_limit" {
  type        = string
  default     = "4Gi"
  description = "RAM allocation limit for the Cloud Run container (e.g. 2Gi, 4Gi, 8Gi)."
}

variable "min_instances" {
  type        = number
  default     = 0
  description = "Minimum number of warm container instances (0 for cost savings, 1+ for zero cold-start latency)."
}

variable "max_instances" {
  type        = number
  default     = 10
  description = "Maximum number of autoscaling container instances to prevent budget runaway."
}

variable "container_concurrency" {
  type        = number
  default     = 80
  description = "Maximum number of concurrent requests per container instance."
}

variable "request_timeout_seconds" {
  type        = number
  default     = 3600
  description = "Maximum request processing timeout in seconds (default 3600s / 60 minutes for long video rendering)."
}

variable "allow_unauthenticated" {
  type        = bool
  default     = true
  description = "If true, permits unauthenticated HTTPS requests to the Cloud Run service URL."
}

# ------------------------------------------------------------------------------
# 3. Google Cloud Storage (GCS) Configuration
# ------------------------------------------------------------------------------

variable "gcs_location" {
  type        = string
  default     = "US"
  description = "Multi-region or regional location for GCS buckets (e.g., US, ASIA, EU, US-CENTRAL1)."
}

variable "storage_class" {
  type        = string
  default     = "STANDARD"
  description = "Default storage class for GCS asset and output vaults (STANDARD, NEARLINE, COLDLINE)."
}

variable "staging_retention_days" {
  type        = number
  default     = 7
  description = "Number of days after which temporary video/audio rendering staging files in GCS are automatically purged."
}

# ------------------------------------------------------------------------------
# 4. Cloud Pub/Sub Messaging Configuration
# ------------------------------------------------------------------------------

variable "enable_dead_letter_queue" {
  type        = bool
  default     = true
  description = "Enables Dead-Letter Queue (DLQ) topics on Pub/Sub subscriptions to prevent runaway infinite retries."
}

variable "max_delivery_attempts" {
  type        = number
  default     = 5
  description = "Maximum delivery retry attempts before a failed event is forwarded to the Dead Letter Queue."
}

# ------------------------------------------------------------------------------
# 5. Enable API Services Toggle
# ------------------------------------------------------------------------------

variable "enable_gcp_apis" {
  type        = bool
  default     = true
  description = "If true, automatically enables required GCP APIs (Cloud Run, Vertex AI, Pub/Sub, Artifact Registry, Cloud Logging)."
}
