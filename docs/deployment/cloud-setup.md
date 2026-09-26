# Fase 8B: Cloud Deployment

## Arquitectura

La infraestructura de AURA se despliega en Kubernetes con Terraform como IaC y Helm para empaquetar la aplicación.

- **Cluster**: EKS (AWS) o DO Kubernetes (DigitalOcean)
- **Redis**: ElastiCache (AWS) o Managed Redis (DO)
- **Storage**: S3 (AWS) o Spaces (DO)
- **Ingress**: NGINX Ingress Controller + cert-manager
- **Autoscaling**: HPA basado en CPU/Memory

## Estructura

```
terraform/
  main.tf
  variables.tf
  outputs.tf
  modules/
    networking/
    kubernetes/
    redis/
    storage/

helm/
  aura-backend/
    Chart.yaml
    values.yaml
    templates/
      namespace.yaml
      deployment.yaml
      service.yaml
      ingress.yaml
      hpa.yaml
```

## Uso

1. Configurar `terraform.tfvars` con credenciales y dominio.
2. `terraform init && terraform plan`
3. `terraform apply`
4. `helm upgrade --install aura-backend ./helm/aura-backend -n aura --create-namespace`

## Notas

- El backend de Terraform usa S3 + DynamoDB para state locking.
- Los secrets se inyectan vía Kubernetes Secrets, no hardcodeados.
- La arquitectura es provider-agnostic; cambiar de AWS a DO requiere solo ajustar variables.
