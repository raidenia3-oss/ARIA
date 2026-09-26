#!/bin/bash
# Deploy AURA to DigitalOcean Kubernetes

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║         AURA CLOUD DEPLOYMENT - DigitalOcean              ║"
echo "╚════════════════════════════════════════════════════════════╝"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check tools
check_tool() {
  if ! command -v $1 &> /dev/null; then
    echo -e "${RED}❌ $1 no está instalado${NC}"
    exit 1
  fi
  echo -e "${GREEN}✅ $1 disponible${NC}"
}

echo ""
echo -e "${YELLOW}Verificando herramientas...${NC}"
check_tool "terraform"
check_tool "kubectl"
check_tool "helm"
check_tool "doctl"

# 1. Terraform init
echo ""
echo -e "${YELLOW}1️⃣ Inicializando Terraform...${NC}"
cd terraform || exit 1
terraform init

# 2. Terraform validate
echo -e "${YELLOW}Validando Terraform...${NC}"
terraform validate

# 3. Terraform plan
echo -e "${YELLOW}Planificando infraestructura...${NC}"
terraform plan -out=tfplan

# 4. Terraform apply
echo ""
echo -e "${YELLOW}2️⃣ Creando infraestructura en DigitalOcean...${NC}"
echo -e "${RED}ADVERTENCIA: Esto creará recursos en DigitalOcean${NC}"
read -p "¿Continuar? (s/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
  terraform apply tfplan
else
  echo "Abortado."
  exit 0
fi

# 5. Save outputs
echo ""
echo -e "${YELLOW}3️⃣ Guardando credenciales...${NC}"
terraform output kube_config > kubeconfig.yaml
terraform output database_uri > /tmp/db_uri.txt
terraform output redis_uri > /tmp/redis_uri.txt

# 6. Setup kubeconfig
echo -e "${YELLOW}Configurando kubectl...${NC}"
export KUBECONFIG=$(pwd)/kubeconfig.yaml
kubectl cluster-info

# 7. Create namespace
echo ""
echo -e "${YELLOW}4️⃣ Creando namespace Kubernetes...${NC}"
kubectl create namespace aura --dry-run=client -o yaml | kubectl apply -f -

# 8. Create secrets
echo -e "${YELLOW}Creando secrets...${NC}"
DB_URI=$(terraform output -raw database_uri)
REDIS_URI=$(terraform output -raw redis_uri)

kubectl create secret generic aura-secrets \
  --from-literal=DATABASE_URL="$DB_URI" \
  --from-literal=REDIS_URL="$REDIS_URI" \
  -n aura --dry-run=client -o yaml | kubectl apply -f -

# 9. Install Helm chart
echo ""
echo -e "${YELLOW}5️⃣ Desplegando AURA con Helm...${NC}"
cd ../helm || exit 1
helm install aura . -n aura --values values.yaml

# 10. Wait for pods
echo ""
echo -e "${YELLOW}6️⃣ Esperando que los pods estén listos...${NC}"
kubectl rollout status deployment/aura -n aura --timeout=10m

# 11. Get service info
echo ""
echo -e "${YELLOW}7️⃣ Obteniendo información del servicio...${NC}"
echo ""
kubectl get service aura -n aura

SERVICE_IP=$(kubectl get svc aura -n aura -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pendiente")

if [ "$SERVICE_IP" != "pendiente" ]; then
  echo ""
  echo -e "${GREEN}✅ DEPLOYMENT COMPLETADO${NC}"
  echo ""
  echo "🌐 Acceso a AURA:"
  echo "   http://$SERVICE_IP/health"
  echo "   http://$SERVICE_IP/api/cluster/status"
  echo ""
  echo "📊 Dashboard:"
  echo "   http://$SERVICE_IP/dashboard"
  echo ""
  echo "Próximos pasos:"
  echo "1. Configurar dominio (DNS) apuntando a: $SERVICE_IP"
  echo "2. Verificar pods: kubectl get pods -n aura"
  echo "3. Ver logs: kubectl logs -n aura -l app=aura-backend -f"
else
  echo ""
  echo -e "${YELLOW}⏳ Load Balancer IP aún no asignada${NC}"
  echo "Verificar en 1-2 minutos con:"
  echo "  kubectl get svc aura -n aura"
fi

echo ""
echo -e "${GREEN}Script completado${NC}"
