# AURA OS × Omniroute Integration

Acceso a **300+ proveedores de IA gratuita** con rotación automática y fallback inteligente.

## ¿Qué es Omniroute?

Omniroute es una plataforma de código abierto que actúa como **puerta de entrada unificada** para múltiples proveedores de IA. Elimina los límites de uso rotando automáticamente entre proveedores según:

- **12-factor scoring** (latencia, costo, disponibilidad, etc)
- **Fallback automático** si un proveedor falla
- **Context relay** para mantener el contexto al cambiar proveedor
- **Monitoreo continuo** de salud

## Instalación

### Opción 1: Docker (Recomendado)

```bash
cd omniroute-docker
docker-compose up -d
```

### Opción 2: Local

```bash
cd omniroute-config
./start-omniroute.sh
```

### Opción 3: Manual

```bash
pip install omniroute
omniroute start --host 0.0.0.0 --port 8080
```

## Configuración AURA

1. **Editar .env:**

```bash
OMNIROUTE_URL=http://localhost:8080
OMNIROUTE_TIMEOUT=30
OMNIROUTE_FALLBACK_ENABLED=true
OMNIROUTE_CONTEXT_RELAY=true
```

2. **Reiniciar AURA:**

```bash
python backend/main.py
```

3. **Verificar:**

```bash
curl http://localhost:8000/api/omniroute/health
curl http://localhost:8000/api/providers
```

## Uso

### Chat con Omniroute

```bash
curl -X POST http://localhost:8000/api/chat/omniroute \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Cuál es la capital de Francia?"
  }'
```

Response automáticamente selecciona el mejor proveedor:

```json
{
  "response": "La capital de Francia es París...",
  "source": "omniroute",
  "provider_info": "Selected automatically by Omniroute scoring",
  "timestamp": "2024-08-31T12:34:56Z"
}
```

### Listar proveedores

```bash
curl http://localhost:8000/api/providers
```

Response:

```json
{
  "total": 312,
  "providers": [
    {
      "name": "groq",
      "model": "mixtral-8x7b",
      "status": "healthy",
      "latency_ms": 245,
      "score": 9.2
    }
  ]
}
```

### Obtener mejor proveedor

```bash
curl http://localhost:8000/api/providers/best
```

### Estadísticas

```bash
# Todas las estadísticas
curl http://localhost:8000/api/providers/stats

# Estadísticas específicas
curl http://localhost:8000/api/providers/groq/stats

# Recomendaciones
curl http://localhost:8000/api/providers/recommendations
```

## Proveedores Soportados

| Proveedor | Modelos | Status |
|-----------|---------|--------|
| Groq | Mixtral, Llama | ✅ |
| OpenRouter | 100+ | ✅ |
| OrcaRouter | Multi | ✅ |
| Ollama | Local | ❓ |
| HuggingFace | Inference API | ✅ |
| Together | Open Models | ✅ |
| Replicate | Modelos variados | ✅ |
| AWS Bedrock | Multi | ✅ |
| Azure OpenAI | GPT | ✅ |
| Y más... | | ✅ |

## Fallback Automático

Si todos los proveedores fallan, AURA usa **ReactLoop local** automáticamente:

```python
# Flujo:
1. Intenta Omniroute (mejor proveedor)
2. Si falla → Intenta siguiente mejor
3. Después de N reintentos → ReactLoop local
```

## Monitoreo

Omniroute monitorea automáticamente cada 5 minutos:

```bash
# Ver health
curl http://localhost:8000/api/omniroute/health

# Ver recomendaciones en tiempo real
curl http://localhost:8000/api/providers/recommendations
```

## Troubleshooting

### Omniroute no responde

```bash
# Verificar si está corriendo
curl http://localhost:8080/api/health

# Si Docker:
docker-compose logs omniroute

# Si local:
ps aux | grep omniroute
```

### Todos los proveedores degradados

```bash
# Ver estado actual
curl http://localhost:8000/api/providers

# Ver recomendaciones
curl http://localhost:8000/api/providers/recommendations

# AURA usará fallback local automáticamente
```

### Latencia alta

```bash
# Ver estadísticas de latencia
curl http://localhost:8000/api/providers/stats | jq '.[] | {name, avg_latency_ms}'

# Omniroute selecciona el más rápido automáticamente
```

## Performance Esperado

| Métrica | Valor |
|---------|-------|
| Latencia promedio | 200-500ms |
| Uptime de proveedores | 98%+ |
| Fallback time | <1s |
| Cambio de proveedor | Transparente |

## API Reference

### POST /api/chat/omniroute

Chat con Omniroute (multi-provider).

**Parámetros:**
- `message` (string) — Mensaje del usuario

**Response:**

```json
{
  "response": "...",
  "source": "omniroute",
  "provider_info": "...",
  "timestamp": "..."
}
```

### GET /api/providers

Listar proveedores disponibles.

### GET /api/providers/best

Obtener mejor proveedor actual.

### GET /api/providers/stats

Estadísticas agregadas de proveedores.

### GET /api/providers/{name}/stats

Estadísticas de proveedor específico.

### GET /api/providers/recommendations

Recomendaciones basadas en estado actual.

### GET /api/omniroute/health

Verificar health de Omniroute.

## Costos

| Aspecto | Costo |
|--------|-------|
| Omniroute | Gratuito (OSS) |
| Groq | Gratuito (con límites) |
| OpenRouter | Pago (pero barato) |
| Ollama | Local/Gratuito |
| **Total** | **Gratuito o muy barato** |

## Próximos Pasos

1. ✅ Instalar Omniroute
2. ✅ Configurar AURA
3. ⏭️ Agregar proveedores específicos
4. ⏭️ Tuning del scoring
5. ⏭️ Integración con plugins
