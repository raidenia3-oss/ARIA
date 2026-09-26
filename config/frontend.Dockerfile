# =============================================
# AURA Frontend - Producción Docker (Multi-stage)
# =============================================
# Etapa 1: Construir con Node.js
FROM node:20-alpine AS builder

WORKDIR /app

# Copiar package files primero para cache
COPY aura-ui/package*.json ./
RUN npm ci --legacy-peer-deps

# Copiar código fuente y construir
COPY aura-ui/ ./
RUN npm run build

# Etapa 2: Servir con Nginx (imagen ultra-liviana)
FROM nginx:alpine

# Copiar archivos estáticos compilados
COPY --from=builder /app/dist /usr/share/nginx/html

# Configuración personalizada de nginx para SPA (React Router)
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exponer puerto 80
EXPOSE 80

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

# Iniciar nginx
CMD ["nginx", "-g", "daemon off;"]
