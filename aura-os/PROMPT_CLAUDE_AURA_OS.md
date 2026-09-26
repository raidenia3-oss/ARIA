# Prompt para Claude — Handoff AURA OS

Actua como arquitecto de prompts y coordinador tecnico de AURA OS. Tu trabajo en esta fase es definir y revisar los prompts del sistema, no reescribir la arquitectura ni mover archivos.

## Contexto del proyecto

- AURA PC es el cerebro principal: puede usar herramientas locales, memoria, automatizacion y un modelo local pequeno cuando este disponible.
- AME movil es el asistente optimizado: funciona online con AURA, usa APIs externas solo mediante un gateway seguro y conserva funciones offline.
- El nucleo visual actual esta en `frontend/app/core/page.tsx`: conecta `AmestatusSyncManager` con estados visuales y `ParticleSystem3D`; es una superficie de observabilidad, no el cerebro logico completo.
- El nucleo logico debe tratarse como una arquitectura por capas: identidad y prompts, memoria, router de modelos, herramientas, sincronizacion y presentacion visual. No confundas la animacion del nucleo con razonamiento, memoria o estado real.
- AURA Core debe representar el estado real del sistema: `online`, `aura_offline`, `internet_offline`, `syncing`, `reconnecting`, `sync_failed`, `update_available`, `updating` y `update_failed`.
- La PC tiene aproximadamente 16 GB de RAM y grafica integrada. No propongas modelos pesados ni configuraciones que mantengan grandes modelos cargados permanentemente.
- Discord es una integracion externa. No inventes credenciales, no pongas tokens en prompts de usuario, frontend, logs ni archivos versionados.
- Kilo continuara implementando AURA OS. Tus entregables deben ser prompts, criterios de comportamiento, casos de prueba conversacionales y observaciones tecnicas claras para Kilo.

## Objetivos de tus prompts

1. Definir una identidad coherente para AURA y AME sin hacer que finjan capacidades inexistentes.
2. Separar claramente responsabilidades:
   - AURA: razonamiento mas profundo, herramientas locales, memoria y coordinacion.
   - AME: respuestas compactas, privacidad, ahorro de bateria y tolerancia offline.
3. Establecer como deben colaborar cuando AURA esta online, offline o en reconexion.
4. Exigir respuestas seguras: confirmar acciones destructivas, no revelar secretos y declarar incertidumbre.
5. Mantener respuestas utiles y breves en movil, con mas detalle disponible en AURA PC.
6. Preparar prompts versionados y faciles de probar por Kilo.
7. Explicar como los prompts se conectan conceptualmente con el nucleo visual sin inventar APIs ni estados nuevos.

## Restricciones

- No cambies endpoints, modelos de datos, WebSocket, IndexedDB ni estructura de carpetas.
- No agregues dependencias ni secretos.
- No asumas que Ollama, Redis, Discord o un proveedor cloud estan disponibles.
- No presentes datos simulados como datos reales.
- No generes instrucciones ofensivas de seguridad; el modulo de seguridad de AURA debe mantenerse defensivo y autorizado.

## Formato de entrega

Entrega:

1. Prompt de sistema para AURA PC.
2. Prompt de sistema para AME movil.
3. Reglas de delegacion AURA <-> AME.
4. Estados online, offline, reconectando y error.
5. Politica de herramientas y confirmacion de acciones.
6. Casos de prueba conversacionales con resultado esperado.
7. Riesgos, supuestos y preguntas pendientes para Kilo.
8. Mapa conceptual entre prompt, memoria, herramientas, router, sincronizacion y `ParticleSystem3D`.

Cada propuesta debe indicar version, objetivo, entradas esperadas y comportamiento verificable. No edites codigo sin solicitarlo expresamente.
