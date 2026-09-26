# Prompt para Kilo — Continuar BLOQUE 8 de AURA/AME

Continua el desarrollo de AURA OS dentro de `C:\Users\User\Downloads\AURA` sin mover archivos fuera del repositorio ni romper el trabajo existente.

## Estado confirmado

- El backend FastAPI importa correctamente y `/health` responde.
- Existen las rutas AME para listado, historial, mensajes y WebSocket.
- Pruebas backend AME + Omniroute: 15 pasan y 1 queda omitida.
- Pruebas frontend: 7 pasan y 3 quedan omitidas.
- El WebSocket usa autenticacion en el primer mensaje y deduplicacion por `eventId`.
- AME conserva mensajes pendientes en IndexedDB cuando AURA esta offline.
- El router local esta preparado para Ollama, pero Ollama no esta instalado y no debes instalarlo en esta fase.
- Redis, Docker y Discord quedan fuera del alcance inmediato.

## Objetivo de esta fase

Cerrar el BLOQUE 8 con validacion E2E reproducible de AME, sin introducir secretos ni dependencias innecesarias.

## Tareas obligatorias

1. Ejecutar el backend real en `localhost:8000` usando la configuracion existente, sin mostrar valores de `.env`.
2. Comprobar `/health`, `/api/mobile/ames`, historial y envio de mensajes usando una API key de prueba o la configuracion segura ya existente.
3. Validar el flujo online desde el proxy Next.js hasta FastAPI.
4. Validar WebSocket:
   - primer mensaje de autenticacion;
   - rechazo de token invalido;
   - rechazo de eventos antes de autenticar;
   - reconexion sin duplicar `eventId`.
5. Validar el flujo offline con las pruebas existentes o pruebas dirigidas:
   - guardar mensaje;
   - mantenerlo en `pending_events`;
   - reconectar;
   - confirmar solo despues de respuesta exitosa;
   - conservarlo si falla la sincronizacion.
6. Revisar la configuracion Capacitor existente. No agregues dependencias Android si no estan declaradas; informa exactamente que falta para un build reproducible.
7. Corregir solo errores TypeScript directamente relacionados con AME. No mezcles en este bloque los errores antiguos de Discord, Telegram, Teams, webhooks o multimodal.
8. Actualizar `PROJECT_STATUS.md` con resultados, comandos, bloqueos y archivos modificados.

## Reglas de seguridad y calidad

- Nunca leas, imprimas, copies o commits tokens de `.env`, `.env.local`, Discord o proveedores cloud.
- No uses `NEXT_PUBLIC_*` para secretos.
- No presentes fallback o datos demo como datos reales.
- No cambies contratos de eventos, IndexedDB o WebSocket sin justificar compatibilidad.
- No instales Ollama, Docker, Redis ni paquetes nuevos en este bloque.
- Usa cambios quirurgicos y conserva cambios previos de otros agentes.
- Ejecuta validaciones despues de editar y reporta cualquier bloqueo real.

## Entrega requerida

Devuelve un reporte con:

1. Archivos modificados.
2. Flujo online validado.
3. Flujo offline y reconexion validados.
4. Resultado de TypeScript, ESLint y pruebas.
5. Limitaciones de Capacitor.
6. Riesgos pendientes para el BLOQUE 9.
