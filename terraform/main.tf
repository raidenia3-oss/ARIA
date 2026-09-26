terraform {
  required_version = ">= 1.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  token = var.do_token
}

# Kubernetes Cluster
resource "digitalocean_kubernetes_cluster" "aura" {
  name    = var.cluster_name
  region  = var.region
  version = "latest"

  node_pool {
    name       = "primary"
    size       = var.node_size
    node_count = var.node_count
    auto_scale = true
    min_nodes  = 3
    max_nodes  = 10

    labels = {
      tier = "primary"
    }
  }

  tags = ["aura", "production"]
}

# PostgreSQL Database Cluster
resource "digitalocean_database_cluster" "aura_db" {
  name       = "${var.cluster_name}-db"
  engine     = "pg"
  version    = "14"
  region     = var.region
  size       = "db-s-1vcpu-1gb"
  node_count = 3

  firewall {
    type  = "kubernetes"
    value = digitalocean_kubernetes_cluster.aura.id
  }

  tags = ["aura", "database"]
}

# Database user
resource "digitalocean_database_user" "aura_user" {
  cluster_id = digitalocean_database_cluster.aura_db.id
  name       = "aura_admin"
  password   = var.database_password
}

# Database
resource "digitalocean_database_db" "aura_db" {
  cluster_id = digitalocean_database_cluster.aura_db.id
  name       = "aura_db"
}

# Redis Cluster
resource "digitalocean_database_cluster" "aura_redis" {
  name       = "${var.cluster_name}-redis"
  engine     = "redis"
  version    = "7"
  region     = var.region
  size       = "db-s-1vcpu-1gb"
  node_count = 3

  firewall {
    type  = "kubernetes"
    value = digitalocean_kubernetes_cluster.aura.id
  }

  tags = ["aura", "cache"]
}

# Spaces (Object Storage) for backups
resource "digitalocean_spaces_bucket" "aura_backups" {
  name   = "${var.cluster_name}-backups"
  region = var.region
  acl    = "private"
}

# Outputs
output "kubernetes_cluster_name" {
  value = digitalocean_kubernetes_cluster.aura.name
}

output "kubernetes_cluster_host" {
  value     = digitalocean_kubernetes_cluster.aura.endpoint
  sensitive = true
}

output "kubernetes_ca_cert" {
  value     = digitalocean_kubernetes_cluster.aura.kube_config[0].cluster[0].certificate_authority_data
  sensitive = true
}

output "kube_config" {
  value     = digitalocean_kubernetes_cluster.aura.kube_config[0].raw_config
  sensitive = true
}

output "database_host" {
  value = digitalocean_database_cluster.aura_db.host
}

output "database_port" {
  value = digitalocean_database_cluster.aura_db.port
}

output "database_user" {
  value = digitalocean_database_user.aura_user.name
}

output "database_password" {
  value     = digitalocean_database_user.aura_user.password
  sensitive = true
}

output "database_name" {
  value = digitalocean_database_db.aura_db.name
}

output "redis_host" {
  value = digitalocean_database_cluster.aura_redis.host
}

output "redis_port" {
  value = digitalocean_database_cluster.aura_redis.port
}

output "database_uri" {
  value = "postgresql://aura_admin:${var.database_password}@${digitalocean_database_cluster.aura_db.host}:${digitalocean_database_cluster.aura_db.port}/${digitalocean_database_db.aura_db.name}?sslmode=require"
  sensitive = true
}

output "redis_uri" {
  value = "redis://:${digitalocean_database_cluster.aura_redis.password}@${digitalocean_database_cluster.aura_redis.host}:${digitalocean_database_cluster.aura_redis.port}"
  sensitive = true
}
