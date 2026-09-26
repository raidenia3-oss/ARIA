# Cloud Deployment Guide - AURA v1.0

## Quick Start

### Prerequisites

1. DigitalOcean account: https://cloud.digitalocean.com
2. Generate API token:
   - Go to: Account → API → Tokens
   - Click "Generate New Token"
   - Grant read + write permissions
   - Copy token

3. Install tools:
```bash
   # macOS
   brew install terraform kubectl helm doctl
   
   # Linux (Ubuntu)
   sudo apt-get install -y terraform kubectl helm
   
   # Windows (Chocolatey)
   choco install terraform kubectl helm doctl
```

### Deploy

1. Update terraform vars:
```bash
   cd terraform
   # Edit terraform.auto.tfvars with your token & password
```

2. Run deployment script:
```bash
   bash scripts/deploy-cloud.sh
```

3. Wait 5-10 minutes for infrastructure to be created

4. Access AURA:
```bash
   # Get service IP
   kubectl get svc aura -n aura
   
   # Test
   curl http://<EXTERNAL-IP>/health
```

## Scaling

```bash
# Scale to 5 replicas
kubectl scale deployment aura -n aura --replicas=5

# Check autoscaling
kubectl get hpa -n aura
```

## Monitoring

```bash
# View logs
kubectl logs -n aura -l app=aura-backend -f

# Port forward Prometheus
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# http://localhost:9090

# Pod info
kubectl describe pod <pod-name> -n aura
```

## Troubleshooting

```bash
# Check cluster
kubectl cluster-info

# Check nodes
kubectl get nodes

# Check pods
kubectl get pods -n aura

# Pod events
kubectl describe pod <pod-name> -n aura

# Logs
kubectl logs <pod-name> -n aura
```
