@echo off
:: Script para iniciar todos los servicios de AURA
:: Incluye MCP, LangGraph, ChromaDB, Telemetría, Self Evolution, Vision Engine, Swarm Orchestrator, Model Orchestrator, Deep Knowledge RAG, DNS Blocker, Offline Mode Controller, LLM Analyzer, Shared Context Bus, Agent Swarm Visualizer, Voice Processor, Mobile Voice UI, Proactive Mobile Alerts y Dynamic Resource Optimizer

echo ===================================================
echo 🚀 Iniciando todos los servicios de AURA
echo ===================================================

:: Verificar si Ollama está en ejecución
echo 🔍 Verificando si Ollama está en ejecución...
tasklist | find "ollama" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo ✅ Ollama ya está en ejecución
) else (
    echo 🔧 Iniciando Ollama...
    start "Ollama" cmd /c ollama serve
    timeout /t 10 >nul
)

:: Configurar modelos automáticamente
echo 🛠️ Configurando modelos especializados...
python Shadow-Core\setup_models.py
if %ERRORLEVEL% neq 0 (
    echo ⚠️  Advertencia: Algunos modelos pueden no estar instalados correctamente.
    echo    Puedes ejecutar manualmente: python Shadow-Core\setup_models.py
)

:: Esperar a que los modelos estén listos
timeout /t 10 >nul

:: Descargar modelos de Ollama (solo si no están instalados)
echo 🔧 Verificando modelos instalados...
ollama list | find "deepseek-coder-v2" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 📥 Descargando deepseek-coder-v2...
    ollama pull deepseek-coder-v2
)

ollama list | find "dolphin-llama3" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 📥 Descargando dolphin-llama3...
    ollama pull dolphin-llama3
)

ollama list | find "mistral-nemo-uncensored" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo 📥 Descargando mistral-nemo-uncensored...
    ollama pull mistral-nemo-uncensored
)

:: Iniciar Dynamic Resource Optimizer
echo 🔧 Iniciando Dynamic Resource Optimizer...
start "Resource Optimizer" cmd /c python Shadow-Core\resource_guardian.py

:: Esperar a que el Resource Optimizer esté listo
timeout /t 5 >nul

:: Iniciar Model Orchestrator Router
echo 🔧 Iniciando Model Orchestrator Router...
start "Model Router" cmd /c python Shadow-Core\model_router.py

:: Esperar a que el Model Router esté listo
timeout /t 5 >nul

:: Iniciar Deep Knowledge RAG
echo 🔧 Iniciando Deep Knowledge RAG...
start "Knowledge RAG" cmd /c python Shadow-Core\knowledge_rag.py

:: Esperar a que el Knowledge RAG esté listo
timeout /t 5 >nul

:: Iniciar DNS Blocker para operaciones air-gapped
echo 🔧 Iniciando DNS Blocker para operaciones air-gapped...
start "DNS Blocker" cmd /c python Shadow-Core\dns_blocker.py

:: Esperar a que el DNS Blocker esté listo
timeout /t 5 >nul

:: Iniciar Offline Mode Controller
echo 🔧 Iniciando Offline Mode Controller...
start "Offline Mode Controller" cmd /c python AURA_Core\offline_mode.py

:: Esperar a que el Offline Mode Controller esté listo
timeout /t 5 >nul

:: Iniciar LLM Analyzer
echo 🔧 Iniciando LLM Analyzer...
start "LLM Analyzer" cmd /c python Shadow-Core\llm_analyzer.py

:: Esperar a que el LLM Analyzer esté listo
timeout /t 5 >nul

:: Iniciar Shared Context Bus
echo 🔧 Iniciando Shared Context Bus...
start "Shared Context Bus" cmd /c python Shadow-Core\context_bus.py

:: Esperar a que el Shared Context Bus esté listo
timeout /t 5 >nul

:: Iniciar Swarm Orchestrator
echo 🔧 Iniciando Swarm Orchestrator...
start "Swarm Orchestrator" cmd /c python Shadow-Core\swarm_orchestrator.py

:: Esperar a que el Swarm Orchestrator esté listo
timeout /t 5 >nul

:: Iniciar Agent Swarm Visualizer
echo 🔧 Iniciando Agent Swarm Visualizer...
start "Agent Swarm Visualizer" cmd /c python Shadow-Core\agent_swarm_visualizer.py

:: Esperar a que el Agent Swarm Visualizer esté listo
timeout /t 5 >nul

:: Iniciar Voice Processor
echo 🔧 Iniciando Voice Processor...
start "Voice Processor" cmd /c python Shadow-Core\voice_processor.py

:: Esperar a que el Voice Processor esté listo
timeout /t 5 >nul

:: Iniciar servicios MCP
echo 🔧 Configurando MCP (Model Context Protocol)...
python AURA_Core\mcp_setup.py

:: Esperar a que MCP esté listo
timeout /t 5 >nul

:: Iniciar LangGraph Manager
echo 🔧 Iniciando LangGraph Manager...
start "LangGraph" cmd /c python AURA_Core\langgraph_manager.py

:: Iniciar Telemetry Manager
echo 🔧 Iniciando Telemetry Manager...
start "Telemetry" cmd /c python AURA_Core\telemetry_manager.py

:: Iniciar Self Evolution Core (Code Auditor)
echo 🔧 Iniciando Self Evolution Core (Code Auditor)...
start "Self Evolution" cmd /c python AURA_Core\code_auditor.py

:: Iniciar Vision Engine
echo 🔧 Iniciando Vision Engine...
start "Vision Engine" cmd /c python Shadow-Core\vision_engine.py

:: Iniciar servidor principal de AURA
echo 🔧 Iniciando servidor principal de AURA...
start "AURA Server" cmd /c python AME_Core\servidor_ame.py

:: Configurar tarea programada para analizar logs cada 30 minutos
echo 🔧 Configurando tarea programada para Self Evolution...
schtasks /create /tn "AURA Self Evolution" /tr "python AURA_Core\code_auditor.py" /sc minute /mo 30 /ru "%username%" /st 00:00

:: Iniciar Redis para comunicación entre agentes
echo 🔧 Iniciando Redis para comunicación entre agentes...
start "Redis Server" cmd /c redis-server --port 6379

echo ===================================================
echo ✅ Todos los servicios de AURA están en ejecución.
echo ===================================================
echo 🔒 Para activar el modo offline (air-gapped), ejecuta:
echo   python AURA_Core\offline_mode.py --activate
echo 🌐 Para desactivar el modo offline, ejecuta:
echo   python AURA_Core\offline_mode.py --deactivate
echo ===================================================
echo 📊 Para probar el nuevo sistema de rutado de modelos:
echo   curl -X POST http://localhost:5014/api/llm/analyze ^
echo   -H "Content-Type: application/json" ^
echo   -d "{\"auth_key\": \"SECRET_AUTH_KEY_12345\", \"prompt\": \"Escribe un script en Python para analizar datos de tráfico de red.\"}"
echo   curl -X POST http://localhost:5014/api/llm/analyze ^
echo   -H "Content-Type: application/json" ^
echo   -d "{\"auth_key\": \"SECRET_AUTH_KEY_12345\", \"prompt\": \"Investiga las mejores prácticas para optimizar el rendimiento de un servidor.\"}"
echo ===================================================
echo 🔄 Para probar el Shared Context Bus (ejecuta en otra terminal):
echo   python Shadow-Core\test_context_bus.py
echo ===================================================
echo 🧬 Para probar el Parallel Agent Swarm (ejecuta en otra terminal):
echo   python Shadow-Core\test_swarm.py
echo ===================================================
echo 💡 Para probar directamente el Swarm Orchestrator:
echo   curl -X POST http://localhost:5016/api/swarm/test ^
echo   -H "Content-Type: application/json" ^
echo   -d "{\"auth_key\": \"SECRET_AUTH_KEY_12345\"}"
echo ===================================================
echo 🖥️ Para acceder al Agent Swarm Visualizer:
echo   Abre tu navegador en: http://localhost:5017
echo ===================================================
echo 🎤 Para probar el Voice Processor:
echo   1. Graba un archivo de audio en formato .webm o .wav
echo   2. Usa curl para enviar el audio:
echo      curl -X POST -F "audio=@tu_archivo.webm" http://localhost:5018/api/voice-command
echo   3. Verifica el estado del procesador:
echo      curl http://localhost:5018/api/voice-status
echo ===================================================
echo 📱 Para probar el Mobile Voice UI:
echo   Abre el dashboard en tu navegador móvil y usa el botón de voz táctico.
echo   Presiona y habla para enviar comandos de voz.
echo ===================================================
echo 🔔 Para probar las Notificaciones Proactivas:
echo   python Shadow-Core\test_proactive_alerts.py
echo ===================================================
echo 🔧 Para configurar manualmente los modelos (si es necesario):
echo   python Shadow-Core\setup_models.py
echo ===================================================
echo 💻 Para probar el Dynamic Resource Optimizer:
echo   1. Verifica los logs en: Shadow-Core/resource_guardian.log
echo   2. Observa cómo los modelos inactivos son descargados después de 5 minutos
echo   3. Prueba el modo de bajo consumo con batería baja o red móvil
echo   4. Verifica las alertas cuando el uso de memoria supera el 85%
echo ===================================================
echo 📊 Para ver la telemetría del sistema en tiempo real:
echo   tail -f Shadow-Core/resource_guardian.log
echo ===================================================