#!/bin/bash

# Script para desplegar el frontend a Vercel

FRONTEND_DIR="frontend"
BACKEND_URL="https://app-xxx.railway.app"  # Reemplazar con la URL real del backend

# Configurar variables de entorno
echo "Configurando variables de entorno en frontend..."
echo "NEXT_PUBLIC_API_URL=$BACKEND_URL" > $FRONTEND_DIR/.env.local
echo "NEXT_PUBLIC_WS_URL=wss://$BACKEND_URL/ws" >> $FRONTEND_DIR/.env.local

# Desplegar a Vercel
echo "Desplegando frontend a Vercel..."
vercel --prod --scope raidenia3 --name aura-frontend

echo "Despliegue a Vercel completado."