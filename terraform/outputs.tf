output "cluster_endpoint" {
  description = "Kubernetes cluster endpoint"
  value       = module.kubernetes.cluster_endpoint
}

output "cluster_ca_certificate" {
  description = "Kubernetes cluster CA certificate"
  value       = module.kubernetes.cluster_ca_certificate
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis endpoint"
  value       = module.redis.redis_endpoint
}

output "redis_password" {
  description = "Redis password"
  value       = module.redis.redis_password
  sensitive   = true
}

output "storage_bucket_name" {
  description = "S3/Spaces bucket name"
  value       = module.storage.bucket_name
}

output "ingress_controller_ip" {
  description = "Ingress controller IP"
  value       = module.kubernetes.ingress_controller_ip
}
