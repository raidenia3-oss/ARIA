# Fase 8B: Cloud Deployment

Infraestructura como código para desplegar AURA en Kubernetes (AWS EKS o DigitalOcean Kubernetes).

## Componentes

- **Terraform**: provisioning de cluster, red, Redis y storage
- **Helm**: empaquetado y despliegue del backend de AURA
- **Kubernetes**: orquestación de contenedores con HPA, ingress y TLS

## Proveedores Soportados

- AWS EKS + ElastiCache + S3
- DigitalOcean Kubernetes + Managed Redis + Spaces

## Próximos Pasos

1. Configurar credenciales en `terraform.tfvars`
2. Ejecutar `terraform init && terraform plan`
3. Desplegar con `terraform apply`
4. Instalar chart Helm: `helm upgrade --install aura-backend ./helm/aura-backend -n aura --create-namespace`

## Estado

Infraestructura base creada. Pendiente: CI/CD pipeline y secrets management.
