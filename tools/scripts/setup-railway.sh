#!/bin/bash

# Script para configurar Railway y desplegar el backend

# Variables
PROJECT_NAME="aura-backend"
RAILWAY_TOKEN="tu_token_railway"  # Reemplazar con token real
BACKEND_DIR="backend"

# Crear servicio de PostgreSQL en Railway
echo "Creando servicio de PostgreSQL en Railway..."
railway add --database postgres --json

# Obtener la URL de la base de datos (el addon expone DATABASE_URL como variable del proyecto)
echo "Obteniendo DATABASE_URL..."
DATABASE_URL=$(railway variable list --json | jq -r '.[] | select(.name=="DATABASE_URL") | .value')

# Actualizar .env con la URL de la base de datos
echo "Actualizando DATABASE_URL en .env..."
echo "DATABASE_URL=$DATABASE_URL" > $BACKEND_DIR/.env
echo "QWEN_URL=https://raiden456-slut.hf.space/v1/chat/completions" >> $BACKEND_DIR/.env
echo "HF_TOKEN=tu_token_hf" >> $BACKEND_DIR/.env

# Inicializar el proyecto (build/start se definen en railway.toml)
echo "Desplegando backend a Railway..."
railway init --name "$PROJECT_NAME"

# Obtener la URL del backend
BACKEND_URL=$(railway domain)

# Actualizar el workflow N8N con la URL del backend
echo "Actualizando workflow N8N con la URL del backend..."
sed -i "s|https://app-xxx.railway.app|$BACKEND_URL|g" n8n/aura_news_workflow.json

echo "Configuración de Railway completada."
echo "Backend URL: $BACKEND_URL"
echo "PostgreSQL URL: $DATABASE_URL"