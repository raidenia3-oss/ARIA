# AURA Brain - Sistema de IA Mejorado

## Arquitectura del cerebro

### Capas de razonamiento
1. **Router de IA**: Decide qué proveedor usar según disponibilidad
   - Gemini (si hay API key)
   - Ollama local (si está corriendo)
   - HF Space (si está configurado)
   - Modo local (siempre disponible)

2. **Memoria conversacional**: Persiste historial en SQLite
   - Tablas: `conversations` y `messages`
   - Hasta 20 mensajes recientes por sesión
   - Session ID para mantener contexto entre requests

3. **Respuestas locales inteligentes**: Sin dependencias externas
   - 15+ intenciones reconocidas
   - Contexto de proyecto AURA
   - Ayuda contextual sobre servicios

### Endpoints del cerebro

#### Chat principal
```
POST /api/chat
Headers: X-API-Key: <key>
Body: {
  "prompt": "mensaje del usuario",
  "session_id": "uuid-opcional",
  "user_id": "user-opcional"
}
```

#### Gestión de memoria
```
GET  /api/conversations - Listar conversaciones
GET  /api/conversations/{session_id}/messages - Ver historial
DELETE /api/conversations/{session_id} - Borrar conversación
```

#### Otros endpoints
```
GET  /health - Estado del sistema
GET  /api/status - Estado de servicios
GET  /api/logs - Logs recientes
POST /api/restart - Reiniciar servicio
POST /api/deploy - Deploy servicio
POST /api/feedback - Enviar feedback
```

### Modos de operación

#### 1. Modo local (sin API keys)
- Funciona sin servicios externos
- Respuestas inteligentes hardcodeadas
- Memoria persistente en SQLite
- Ideal para desarrollo y testing

#### 2. Modo cloud (con API keys)
- Configurar `GEMINI_API_KEY` para Gemini
- Configurar `GROQ_API_KEY` para Groq
- Configurar `OPENROUTER_API_KEY` para OpenRouter
- Configurar `HF_TOKEN` para HF Space

#### 3. Modo híbrido
- Usa proveedores externos cuando están disponibles
- Fallback a modo local si fallan
- Memoria siempre persistente

### Deployment cloud

#### Railway
1. Conectar repo de GitHub
2. Variables de entorno:
   ```
   DATABASE_URL=postgresql://...
   AURA_API_KEY=tu-api-key
   REDIS_URL=redis://...
   ```
3. Deploy automático en cada push a main

#### Render
1. Nuevo Web Service
2. Build command: `pip install -r backend/requirements.txt`
3. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Variables de entorno igual que Railway

### Mejoras implementadas
- Memoria conversacional persistente en SQLite
- 15+ intenciones reconocidas en modo local
- Session IDs para contexto entre requests
- Endpoints de gestión de conversaciones
- Preparado para cloud deployment
- Respuestas más contextuales y útiles

### Próximas mejoras posibles
- RAG con documentos locales
- Tools execution (ejecutar comandos)
- Multi-usuario con autenticación real
- Streaming de respuestas
- Soporte multimodal (imágenes, audio)
- Integración con Godot para comandos de voz
