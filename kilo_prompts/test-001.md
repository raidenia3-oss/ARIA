
╔════════════════════════════════════════════════════════════════════════╗
║                    AURA TASK DELEGATION TO KILO                       ║
╚════════════════════════════════════════════════════════════════════════╝

TASK ID: test-001
OBJECTIVE: Validar integración Kilo bridge
TIMEOUT: 300s
CALLBACK: http://localhost:8000/api/agents/kilo/callback

CONTEXT:
{
  "repo": "AURA"
}

REQUIRED TOOLS:
- Standard CLI tools

INSTRUCTIONS:
1. Analiza el objetivo
2. Ejecuta los pasos necesarios
3. Documenta el resultado
4. Envía callback POST a http://localhost:8000/api/agents/kilo/callback

Callback payload debe ser:
{
  "task_id": "test-001",
  "status": "completed|failed",
  "result": {},
  "error": "si aplica",
  "duration": segundos
}

COMIENZA AHORA.
