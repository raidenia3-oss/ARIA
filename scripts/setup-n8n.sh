#!/bin/bash

# Script para configurar el workflow en N8N

N8N_WORKFLOW="n8n/aura_news_workflow.json"
N8N_URL="https://n8n-onme.onrender.com"
N8N_API_KEY="tu_api_key_n8n"  # Reemplazar con la clave API real

# Importar el workflow a N8N
echo "Importando workflow a N8N..."
curl -X POST "$N8N_URL/rest/workflows" \
  -H "Authorization: Bearer $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary "@$N8N_WORKFLOW"

# Configurar credenciales de PostgreSQL
echo "Configurando credenciales de PostgreSQL en N8N..."
POSTGRES_CREDENTIALS=$(jq -n \
  --arg url "$DATABASE_URL" \
  '{
    "name": "AURA PostgreSQL",
    "type": "postgres",
    "username": (.url | split("://")[1] | split(":")[0]),
    "password": (.url | split("://")[1] | split(":")[1] | split("@")[0]),
    "host":    (.url | split("@")[1] | split("/")[0] | split(":")[0]),
    "port":    (.url | split("@")[1] | split("/")[0] | split(":")[1]),
    "databaseName": (.url | split("/")[1])
  }')

curl -X POST "$N8N_URL/rest/credentials" \
  -H "Authorization: Bearer $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$POSTGRES_CREDENTIALS"

# Activar el workflow
echo "Activando el workflow en N8N..."
WORKFLOW_ID=$(curl -s -X GET "$N8N_URL/rest/workflows" \
  -H "Authorization: Bearer $N8N_API_KEY" | jq -r '.[] | select(.name == "AURA News Workflow") | .id')

curl -X PATCH "$N8N_URL/rest/workflows/$WORKFLOW_ID" \
  -H "Authorization: Bearer $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": true}'

echo "Configuración de N8N completada."