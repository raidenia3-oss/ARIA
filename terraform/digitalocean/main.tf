terraform {
  required_version = ">= 1.5.0"
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
}

variable "do_region" {
  description = "DigitalOcean region"
  type        = string
  default     = "nyc1"
}

variable "environment" {
  default = "prod"
}

locals {
  common_tags = {
    Project     = "AURA"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "digitalocean_kubernetes_cluster" "aura" {
  name         = "aura-${var.environment}"
  region       = var.do_region
  version      = "1.28"
  auto_upgrade = true

  node_pool {
    name       = "aura-workers"
    size       = "s-2vcpu-4gb"
    min_nodes  = 3
    max_nodes  = 10
    auto_scale = true
  }

  tags = [local.common_tags.Project, local.common_tags.Environment]
}

resource "digitalocean_database_cluster" "redis" {
  name       = "aura-redis"
  engine     = "redis"
  version    = "7"
  size       = "db-s-1vcpu-1gb"
  region     = var.do_region
  node_count = 2

  tags = [local.common_tags.Project, local.common_tags.Environment]
}

resource "digitalocean_spaces_bucket" "aura" {
  name   = "aura-${var.environment}-storage"
  region = var.do_region
}

provider "kubernetes" {
  host                   = digitalocean_kubernetes_cluster.aura.endpoint
  token                  = digitalocean_kubernetes_cluster.aura.kube_config[0].token
  cluster_ca_certificate = base64decode(digitalocean_kubernetes_cluster.aura.kube_config[0].cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = digitalocean_kubernetes_cluster.aura.endpoint
    token                  = digitalocean_kubernetes_cluster.aura.kube_config[0].token
    cluster_ca_certificate = base64decode(digitalocean_kubernetes_cluster.aura.kube_config[0].cluster_ca_certificate)
  }
}

resource "helm_release" "ingress_nginx" {
  name       = "ingress-nginx"
  repository = "https://kubernetes.github.io/ingress-nginx"
  chart      = "ingress-nginx"
  namespace  = "ingress-nginx"
  version    = "4.8.0"

  create_namespace = true

  values = [
    yamlencode({
      controller = {
        service = {
          type = "LoadBalancer"
        }
      }
    })
  ]
}

resource "helm_release" "cert_manager" {
  name       = "cert-manager"
  repository = "https://charts.jetstack.io"
  chart      = "cert-manager"
  namespace  = "cert-manager"
  version    = "v1.13.0"

  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }
}

output "kubernetes_endpoint" {
  description = "Kubernetes API endpoint"
  value       = digitalocean_kubernetes_cluster.aura.endpoint
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = digitalocean_database_cluster.redis.connection_host
}

output "redis_password" {
  description = "Redis password"
  value       = digitalocean_database_cluster.redis.password
  sensitive   = true
}

output "spaces_bucket" {
  description = "Spaces bucket name"
  value       = digitalocean_spaces_bucket.aura.name
}
