variable "cloud_provider" {
  description = "Cloud provider"
  type        = string
  default     = "digitalocean"
}

variable "region" {
  description = "Cloud region"
  type        = string
  default     = "nyc3"
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
  default     = "aura-prod"
}

variable "node_count" {
  description = "Number of K8s nodes"
  type        = number
  default     = 3
}

variable "node_size" {
  description = "Machine size"
  type        = string
  default     = "s-2vcpu-4gb"
}

variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "database_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Domain name for AURA"
  type        = string
}
