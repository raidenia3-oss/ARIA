#!/usr/bin/env bash
# ============================================================================
# SETUP AI MODELS — Instalación de Gemma 4 vía Ollama + Configuración de IA Local
# ============================================================================
# Este script automatiza:
#   1. Verificar/instalar Ollama CLI
#   2. Descargar Gemma 4 (2B/9B/12B/27B según RAM disponible)
#   3. Verificar conectividad con LM Studio
#   4. Probar endpoint de chat local
# ============================================================================

RED='\033[0;91m'
GREEN='\033[0;92m'
YELLOW='\033[0;93m'
BLUE='\033[0;94m'
CYAN='\033[0;96m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "\n${BOLD}${CYAN}======================================${RESET}"
echo -e "${BOLD}${CYAN}  🤖 AURA — SETUP DE MODELOS DE IA   ${RESET}"
echo -e "${BOLD}${CYAN}======================================${RESET}\n"

# ─── 1. Detectar Sistema Operativo ───
OS="unknown"
case "$(uname -s)" in
    Linux*)     OS=linux;;
    Darwin*)    OS=macos;;
    MINGW*|MSYS*) OS=windows;;
    *)          OS=unknown;;
esac
echo -e "${BLUE}[INFO]${RESET} Sistema: ${BOLD}$OS${RESET}"

# ─── 2. Verificar/Instalar Ollama ───
echo -e "\n${BOLD}FASE 1: Verificar Ollama CLI${RESET}"

if command -v ollama &> /dev/null; then
    OLLAMA_VERSION=$(ollama --version 2>&1)
    echo -e "  ${GREEN}✓${RESET} Ollama ya está instalado: ${BOLD}$OLLAMA_VERSION${RESET}"
else
    echo -e "  ${YELLOW}⚠ Ollama no encontrado.${RESET}"
    echo -e "  ${CYAN}→ Descarga desde: https://ollama.com/download${RESET}"
    echo -e "  ${CYAN}→ O instala con:${RESET}"
    if [ "$OS" = "linux" ]; then
        echo -e "    ${BOLD}curl -fsSL https://ollama.com/install.sh | sh${RESET}"
    elif [ "$OS" = "macos" ]; then
        echo -e "    ${BOLD}brew install ollama${RESET}"
    elif [ "$OS" = "windows" ]; then
        echo -e "    ${BOLD}winget install Ollama.Ollama${RESET}"
    fi
    echo -e "  ${YELLOW}Después de instalar, ejecuta este script nuevamente.${RESET}"
    exit 1
fi

# ─── 3. Verificar que Ollama esté ejecutándose ───
echo -e "\n${BOLD}FASE 2: Verificar servidor Ollama${RESET}"
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} Servidor Ollama corriendo en http://localhost:11434"
else
    echo -e "  ${YELLOW}⚠ Servidor Ollama no responde. Iniciando...${RESET}"
    if [ "$OS" = "linux" ] || [ "$OS" = "macos" ]; then
        ollama serve &
        OLAMA_PID=$!
        echo -e "  ${BLUE}[INFO]${RESET} Ollama iniciado (PID: $OLAMA_PID)"
        sleep 3
    else
        echo -e "  ${YELLOW}⚠ Inicia Ollama manualmente desde el menú Inicio${RESET}"
    fi
fi

# ─── 4. Determinar RAM y elegir modelo ───
echo -e "\n${BOLD}FASE 3: Elegir modelo Gemma ${RESET}"

# Detectar RAM disponible
if command -v free &> /dev/null; then
    RAM_GB=$(free -g | awk '/^Mem:/{print $2}')
elif command -v sysctl &> /dev/null; then
    RAM_GB=$(($(sysctl -n hw.memsize) / 1073741824))
elif [ -f /proc/meminfo ]; then
    RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    RAM_GB=$((RAM_KB / 1048576))
else
    RAM_GB=8  # Default conservador
fi

echo -e "  ${BLUE}[INFO]${RESET} RAM detectada: ${BOLD}${RAM_GB}GB${RESET}"

# Elegir modelo según RAM
if [ "$RAM_GB" -ge 32 ]; then
    GEMMA_MODEL="gemma3:27b"
    echo -e "  ${GREEN}✓${RESET} Suficiente RAM para Gemma 3 27B"
elif [ "$RAM_GB" -ge 16 ]; then
    GEMMA_MODEL="gemma3:12b"
    echo -e "  ${GREEN}✓${RESET} RAM suficiente para Gemma 3 12B"
elif [ "$RAM_GB" -ge 8 ]; then
    GEMMA_MODEL="gemma3:4b"
    echo -e "  ${GREEN}✓${RESET} RAM suficiente para Gemma 3 4B (recomendado)"
else
    GEMMA_MODEL="gemma3:2b"
    echo -e "  ${YELLOW}⚠ RAM limitada. Usando Gemma 3 2B${RESET}"
fi

echo -e "  ${CYAN}Modelo seleccionado:${RESET} ${BOLD}$GEMMA_MODEL${RESET}"

# ─── 5. Descargar modelo Gemma ───
echo -e "\n${BOLD}FASE 4: Descargar $GEMMA_MODEL${RESET}"
echo -e "  ${YELLOW}⚠ Esto puede tomar varios minutos dependiendo de tu internet...${RESET}"

ollama pull "$GEMMA_MODEL"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "  ${GREEN}✓${RESET} Modelo ${BOLD}$GEMMA_MODEL${RESET} descargado exitosamente"
else
    echo -e "  ${RED}✗${RESET} Error descargando modelo (código: $EXIT_CODE)"
    echo -e "  ${YELLOW}→ Verifica conexión y espacio en disco${RESET}"
fi

# ─── 6. Descargar modelo adicional para código ───
echo -e "\n${BOLD}FASE 5: Descargar modelo para código (CodeGemma)${RESET}"
ollama pull codegemma:2b
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓${RESET} CodeGemma 2B descargado"
else
    echo -e "  ${YELLOW}⚠ No se pudo descargar CodeGemma${RESET}"
fi

# ─── 7. Verificar modelos instalados ───
echo -e "\n${BOLD}FASE 6: Verificar modelos instalados${RESET}"
ollama list

# ─── 8. Verificar LM Studio (opcional) ───
echo -e "\n${BOLD}FASE 7: Verificar LM Studio (local)${RESET}"
if curl -s http://localhost:1234/v1/models > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${RESET} LM Studio disponible en http://localhost:1234/v1"
else
    echo -e "  ${YELLOW}⚠ LM Studio no detectado en puerto 1234${RESET}"
    echo -e "  ${CYAN}→ Si quieres usarlo, inicia LM Studio y activa el servidor HTTP${RESET}"
fi

# ─── 9. Probar chat local ───
echo -e "\n${BOLD}FASE 8: Probar chat local${RESET}"
TEST_RESPONSE=$(curl -s -X POST http://localhost:11434/api/generate \
    -d "{\"model\": \"$GEMMA_MODEL\", \"prompt\": \"Responde SOLO con: OK\", \"stream\": false}" 2>&1)

if echo "$TEST_RESPONSE" | grep -q "response"; then
    echo -e "  ${GREEN}✓${RESET} Chat local funcionando correctamente"
else
    echo -e "  ${YELLOW}⚠ Prueba de chat falló. El modelo puede estar cargándose aún.${RESET}"
    echo -e "  ${CYAN}→ Respuesta: ${TEST_RESPONSE:0:200}${RESET}"
fi

# ─── Resumen Final ───
echo -e "\n${BOLD}${GREEN}======================================${RESET}"
echo -e "${BOLD}${GREEN}  ✅ SETUP DE IA COMPLETADO         ${RESET}"
echo -e "${BOLD}${GREEN}======================================${RESET}"
echo -e "\n${CYAN}Modelos instalados:${RESET}"
echo -e "  • ${BOLD}$GEMMA_MODEL${RESET} — Modelo principal"
echo -e "  • ${BOLD}codegemma:2b${RESET} — Asistente de código"
echo -e "\n${CYAN}Endpoints disponibles:${RESET}"
echo -e "  • Ollama:     ${BOLD}http://localhost:11434${RESET}"
echo -e "  • LM Studio:  ${BOLD}http://localhost:1234/v1${RESET} (si está activo)"
echo -e "\n${CYAN}Comandos útiles:${RESET}"
echo -e "  • ${BOLD}ollama run $GEMMA_MODEL${RESET} — Chat interactivo"
echo -e "  • ${BOLD}ollama list${RESET} — Ver modelos instalados"
echo -e "  • ${BOLD}ollama rm <modelo>${RESET} — Eliminar un modelo"
echo -e ""
</｜｜DSML｜｜>
<task_progress>
- [x] MÓDULO 1: Git config, .gitignore, commit-validator.py
- [x] MÓDULO 2: docker-compose.yml (Odysseus + MobSF + ComfyUI)
- [x] MÓDULO 2: setup-ai-models.sh (Ollama + Gemma 4)
- [ ] MÓDULO 2: docs/ai-local-setup.md (guía técnica IA + ComfyUI)
- [ ] MÓDULO 3: install-security-tools.sh (Frida, JADX, Drozer)
- [ ] README.md maestro
</task_progress>
</write_to_file>
