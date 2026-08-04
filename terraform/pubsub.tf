# ==============================================================================
# ZiWan Ad Studio — Cloud Pub/Sub Event Messaging Pipeline
# ==============================================================================
# Provisions topics and subscriptions for micro-agent async orchestration:
# Context Agent -> Scripting Agent -> Segmentation Agent -> Generation Agent -> Stitcher.
# Includes Dead-Letter Queue (DLQ) topics to prevent runaway infinite retry loops.
# ==============================================================================

locals {
  pipeline_topics = [
    "ziwan-context-analysis-topic",
    "ziwan-scripting-topic",
    "ziwan-segmentation-topic",
    "ziwan-generation-topic",
    "ziwan-stitcher-topic"
  ]
}

# ------------------------------------------------------------------------------
# 1. Primary Event Topics
# ------------------------------------------------------------------------------

resource "google_pubsub_topic" "agent_topics" {
  for_each = toset(local.pipeline_topics)

  name    = each.key
  project = var.project_id

  labels = {
    pipeline = "ziwan_ad_studio"
  }

  depends_on = [google_project_service.enabled_apis]
}

# ------------------------------------------------------------------------------
# 2. Dead-Letter Queue (DLQ) Safeguard Topics
# Catches unparseable or continuously failing events after var.max_delivery_attempts
# ------------------------------------------------------------------------------

resource "google_pubsub_topic" "dlq_topic" {
  count   = var.enable_dead_letter_queue ? 1 : 0
  name    = "ziwan-pipeline-dlq-topic"
  project = var.project_id

  labels = {
    pipeline = "ziwan_ad_studio"
    type     = "dead_letter_queue"
  }

  depends_on = [google_project_service.enabled_apis]
}

# ------------------------------------------------------------------------------
# 3. Agent Subscriptions with Retry Policies & DLQ Guardrails
# ------------------------------------------------------------------------------

resource "google_pubsub_subscription" "agent_subscriptions" {
  for_each = toset(local.pipeline_topics)

  name    = replace(each.key, "-topic", "-sub")
  topic   = google_pubsub_topic.agent_topics[each.key].name
  project = var.project_id

  ack_deadline_seconds = 600 # 10 minute ack deadline for long LLM/video processing turns

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  dynamic "dead_letter_policy" {
    for_each = var.enable_dead_letter_queue ? [1] : []
    content {
      dead_letter_topic     = google_pubsub_topic.dlq_topic[0].id
      max_delivery_attempts = var.max_delivery_attempts
    }
  }

  expiration_policy {
    ttl = "" # Never expire subscription
  }
}
