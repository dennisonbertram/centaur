# ------------------------------------------------------------------------------
# Customer deployment variables
# ------------------------------------------------------------------------------

variable "hcloud_token" {
  description = "Hetzner Cloud API token for the customer's project"
  type        = string
  sensitive   = true
}

variable "customer_id" {
  description = "Short identifier for the customer (used in resource names)"
  type        = string
  validation {
    condition     = can(regex("^[a-z0-9-]{2,20}$", var.customer_id))
    error_message = "customer_id must be 2-20 lowercase alphanumeric characters or hyphens"
  }
}

variable "location" {
  description = "Hetzner datacenter location"
  type        = string
  default     = "nbg1"
  validation {
    condition     = contains(["nbg1", "fsn1", "hel1", "ash", "hil"], var.location)
    error_message = "Must be one of: nbg1, fsn1, hel1, ash, hil"
  }
}

# --- Cluster sizing ---

variable "tier" {
  description = "Deployment tier: dev (1 node), small (3-node HA), prod (3-node HA + autoscaler)"
  type        = string
  default     = "small"
  validation {
    condition     = contains(["dev", "small", "prod"], var.tier)
    error_message = "Must be one of: dev, small, prod"
  }
}

variable "control_plane_type" {
  description = "Server type for control plane / combined nodes. Override to customize beyond tier defaults."
  type        = string
  default     = ""
}

variable "worker_type" {
  description = "Server type for worker nodes (small/prod tiers). Override to customize."
  type        = string
  default     = ""
}

variable "postgres_type" {
  description = "Server type for the dedicated Postgres node (small/prod tiers only)."
  type        = string
  default     = ""
}

# --- Centaur configuration ---

variable "centaur_image_registry" {
  description = "Container registry for Centaur images (e.g. ghcr.io/paradigmxyz)"
  type        = string
  default     = "ghcr.io/paradigmxyz"
}

variable "centaur_image_tag" {
  description = "Image tag for all Centaur services"
  type        = string
  default     = "latest"
}

variable "slackbot_enabled" {
  description = "Enable the Slack bot adapter"
  type        = bool
  default     = true
}

variable "ssh_public_keys" {
  description = "SSH public keys for node access (for debugging)"
  type        = list(string)
  default     = []
}

# --- Secrets (injected at deploy time, never stored in state) ---

variable "slack_bot_token" {
  description = "Slack bot token (xoxb-...)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "slack_signing_secret" {
  description = "Slack signing secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key for the Codex harness"
  type        = string
  default     = ""
  sensitive   = true
}

variable "anthropic_api_key" {
  description = "Anthropic API key for the Claude harness"
  type        = string
  default     = ""
  sensitive   = true
}

variable "extra_secrets" {
  description = "Additional key=value secrets to inject (tool credentials, etc.)"
  type        = map(string)
  default     = {}
  sensitive   = true
}
