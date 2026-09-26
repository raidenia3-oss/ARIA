#!/usr/bin/env bash
# ============================================================================
# INSTALL SECURITY TOOLS — Laboratorio de Hacking Ético Android
# ============================================================================
# Este script instala y configura:
#   1. Frida & Frida-Tools — Instrumentación dinámica de apps Android
#   2. JADX — Descompilador gráfico de APK
#   3. Drozer — Consola de explotación de componentes expuestos
# ============================================================================
# Requisitos:
#   - Python 3.8+ (para pip)
#   - Java 11+ (para JADX y Drozer)
#   - ADB (Android Debug Bridge) conectado a emulador/dispositivo
# ============================================================================

BLUE='\033[0;94m'
GREEN='\033[0;92m'
YELLOW='\033[0;93m'
RED='\033[0;91m'
CYAN='\033[0;96m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "\n${BOLD}${CYAN}==============================================${RESET}"
echo -e "${BOLD}${CYAN}  🛡️  AURA — LABORATORIO DE SEGURIDAD ANDROID  ${RESET}"
echo -e "${BOLD}${CYAN}==============================================${RESET}"

# ─── Detectar SO ───
OS="unknown"
case "$(uname -s)" in
    Linux*)  OS=linux;;
    Darwin*) OS=macos;;
    MINGW*|MSYS*) OS=windows;;
esac
echo -e "${BLUE}[INFO]${RESET} Sistema: ${BOLD}$OS${RESET}"

# ─── Directorio de trabajo ───
TOOLS_DIR="$(dirname "$0")/../security-tools"
mkdir -p "$TOOLS_DIR"
cd "$TOOLS_DIR" || exit 1

# ─── 1. FRIDA & FRIDA-TOOLS ───
echo -e "\n${BOLD}FASE 1: Instalar Frida & Frida-Tools${RESET}"

# Intentar instalar con el entorno virtual primero, si no pip global
if [ -f "../.venv/Scripts/pip.exe" ]; then
    PIP="../.venv/Scripts/pip.exe"
elif [ -f "../.venv/bin/pip" ]; then
    PIP="../.venv/bin/pip"
else
    PIP="pip"
fi

echo -e "  ${BLUE}[INFO]${RESET} Usando: ${BOLD}$PIP${RESET}"

# Instalar frida-tools
$PIP install frida-tools 2>&1 | tail -3
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓${RESET} Frida-Tools instalado correctamente"
else
    echo -e "  ${YELLOW}⚠ Error instalando Frida-Tools. Intentando con pip global...${RESET}"
    pip install frida-tools 2>&1 | tail -3
fi

# Verificar versión
if command -v frida &> /dev/null; then
    FRIDA_VER=$(frida --version 2>&1)
    echo -e "  ${GREEN}✓${RESET} Frida versión: ${BOLD}$FRIDA_VER${RESET}"
else
    echo -e "  ${YELLOW}⚠ Frida no está en PATH. Usa: python -m frida${RESET}"
fi

# ─── 2. JADX — Descompilador Gráfico ───
echo -e "\n${BOLD}FASE 2: Instalar JADX (Descompilador APK)${RESET}"

JADX_DIR="$TOOLS_DIR/jadx"
if [ -f "$JADX_DIR/bin/jadx-gui" ] || [ -f "$JADX_DIR/bin/jadx-gui.bat" ]; then
    echo -e "  ${GREEN}✓${RESET} JADX ya está instalado en: ${BOLD}$JADX_DIR${RESET}"
else
    echo -e "  ${BLUE}[INFO]${RESET} Descargando JADX desde GitHub..."

    # Detectar arquitectura
    if [ "$OS" = "windows" ]; then
        JADX_URL="https://github.com/skylot/jadx/releases/latest/download/jadx-gui-1.5.0.zip"
        JADX_ZIP="jadx.zip"
    else
        JADX_URL="https://github.com/skylot/jadx/releases/latest/download/jadx-1.5.0.zip"
        JADX_ZIP="jadx.zip"
    fi

    # Descargar
    if command -v curl &> /dev/null; then
        curl -L -o "$JADX_ZIP" "$JADX_URL" --progress-bar
    elif command -v wget &> /dev/null; then
        wget -O "$JADX_ZIP" "$JADX_URL"
    else
        echo -e "  ${RED}✗ No se encontró curl ni wget. Descarga manual:${RESET}"
        echo -e "  ${CYAN}  $JADX_URL${RESET}"
        echo -e "  ${CYAN}  Extrae en: $JADX_DIR${RESET}"
    fi

    if [ -f "$JADX_ZIP" ]; then
        unzip -o "$JADX_ZIP" -d "$JADX_DIR" 2>&1 | tail -3
        rm -f "$JADX_ZIP"

        # Agregar al PATH si es posible
        if [ -f "$JADX_DIR/bin/jadx" ] || [ -f "$JADX_DIR/bin/jadx.bat" ]; then
            echo -e "  ${GREEN}✓${RESET} JADX instalado en: ${BOLD}$JADX_DIR${RESET}"
            echo -e "  ${CYAN}  Para usar: $JADX_DIR/bin/jadx-gui (o jadx-gui.bat en Windows)${RESET}"
        fi
    fi
fi

# ─── 3. DROZER — Consola de Explotación ───
echo -e "\n${BOLD}FASE 3: Instalar Drozer${RESET}"

# Drozer se instala mejor desde pip para la consola
$PIP install drozer 2>&1 | tail -3
if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓${RESET} Drozer (consola) instalado via pip"
else
    echo -e "  ${YELLOW}⚠ Instalación via pip falló. Método alternativo:${RESET}"
    echo -e "  ${CYAN}  git clone https://github.com/f-secure-labs/drozer.git${RESET}"
    echo -e "  ${CYAN}  cd drozer && python setup.py install${RESET}"
fi

# Verificar Drozer
if command -v drozer &> /dev/null; then
    echo -e "  ${GREEN}✓${RESET} Drozer disponible en CLI"
else
    echo -e "  ${YELLOW}⚠ Drozer no está en PATH${RESET}"
fi

# ─── 4. VERIFICAR ADB ───
echo -e "\n${BOLD}FASE 4: Verificar ADB (Android Debug Bridge)${RESET}"

ADB=""
if command -v adb &> /dev/null; then
    ADB="adb"
elif [ -f "$HOME/AppData/Local/Android/Sdk/platform-tools/adb.exe" ]; then
    ADB="$HOME/AppData/Local/Android/Sdk/platform-tools/adb.exe"
fi

if [ -n "$ADB" ]; then
    echo -e "  ${GREEN}✓${RESET} ADB encontrado: ${BOLD}$ADB${RESET}"
    DEVICES=$("$ADB" devices 2>/dev/null | grep -v "List of devices" | grep -v "^$" | wc -l)
    if [ "$DEVICES" -gt 0 ]; then
        echo -e "  ${GREEN}✓${RESET} Dispositivos/Emuladores conectados: ${BOLD}$DEVICES${RESET}"
        "$ADB" devices
    else
        echo -e "  ${YELLOW}⚠ No hay dispositivos/emuladores conectados${RESET}"
        echo -e "  ${CYAN}  Abre un emulador de Android Studio o conecta un dispositivo${RESET}"
    fi
else
    echo -e "  ${YELLOW}⚠ ADB no encontrado${RESET}"
    echo -e "  ${CYAN}  Instala Android SDK Platform-Tools:${RESET}"
    echo -e "  ${CYAN}  https://developer.android.com/studio/releases/platform-tools${RESET}"
fi

# ─── 5. GUÍA DROZER ───
echo -e "\n${BOLD}FASE 5: Guía de uso de Drozer${RESET}"
echo -e "${CYAN}"
echo -e "  ┌─────────────────────────────────────────────────────────┐"
echo -e "  │  GUÍA RÁPIDA DROZER                                    │"
echo -e "  ├─────────────────────────────────────────────────────────┤"
echo -e "  │  1. Instalar agente en el emulador:                    │"
echo -e "  │     adb install drozer-agent.apk                       │"
echo -e "  │                                                         │"
echo -e "  │  2. Abrir la app Drozer Agent en el emulador           │"
echo -e "  │     y tocar "Enable"                                   │"
echo -e "  │                                                         │"
echo -e "  │  3. Redirigir puerto:                                  │"
echo -e "  │     adb forward tcp:31415 tcp:31415                    │"
echo -e "  │                                                         │"
echo -e "  │  4. Conectar consola:                                  │"
echo -e "  │     drozer console connect                             │"
echo -e "  │                                                         │"
echo -e "  │  5. Comandos básicos:                                  │"
echo -e "  │     list (paquetes)                                    │"
echo -e "  │     run app.activity.info (actividades)                │"
echo -e "  │     run app.provider.info (content providers)          │"
echo -e "  │     run app.service.info (servicios)                  │"
echo -e "  │     run scanner.provider.finduri (inyección SQL)       │"
echo -e "  └─────────────────────────────────────────────────────────┘"
echo -e "${RESET}"

# ─── 6. GUÍA FRIDA ───
echo -e "${BOLD}FASE 6: Guía rápida de Frida${RESET}"
echo -e "${CYAN}"
echo -e "  ┌─────────────────────────────────────────────────────────┐"
echo -e "  │  GUÍA RÁPIDA FRIDA                                     │"
echo -e "  ├─────────────────────────────────────────────────────────┤"
echo -e "  │  1. Verificar versión del servidor Frida en dispositivo:│"
echo -e "  │     adb shell getprop ro.build.version.sdk             │"
echo -e "  │                                                         │"
echo -e "  │  2. Descargar frida-server para esa versión:           │"
echo -e "  │     https://github.com/frida/frida/releases            │"
echo -e "  │                                                         │"
echo -e "  │  3. Instalar frida-server:                             │"
echo -e "  │     adb root                                           │"
echo -e "  │     adb push frida-server /data/local/tmp/             │"
echo -e "  │     adb shell chmod 755 /data/local/tmp/frida-server   │"
echo -e "  │     adb shell /data/local/tmp/frida-server &          │"
echo -e "  │                                                         │"
echo -e "  │  4. Probar conexión:                                   │"
echo -e "  │     frida-ps -U                                        │"
echo -e "  │                                                         │"
echo -e "  │  5. Ejemplo de hook:                                   │"
echo -e "  │     frida -U com.android.systemui -l hook.js          │"
echo -e "  └─────────────────────────────────────────────────────────┘"
echo -e "${RESET}"

# ─── 7. INSTALAR DROZER AGENT APK ───
echo -e "\n${BOLD}FASE 7: Instalar Drozer Agent en emulador (opcional)${RESET}"
echo -e "  ${CYAN}  El APK del agente Drozer se puede descargar de:${RESET}"
echo -e "  ${CYAN}  https://github.com/f-secure-labs/drozer/releases${RESET}"
echo -e "  ${CYAN}  Busca 'drozer-agent-2.4.4.apk' o similar${RESET}"
echo -e "  ${CYAN}  Luego: adb install drozer-agent.apk${RESET}"

# ─── Resumen Final ───
echo -e "\n${BOLD}${GREEN}==============================================${RESET}"
echo -e "${BOLD}${GREEN}  ✅ LABORATORIO DE SEGURIDAD CONFIGURADO  ${RESET}"
echo -e "${BOLD}${GREEN}==============================================${RESET}"
echo -e ""
echo -e "${CYAN}Frida:${RESET}"
echo -e "  • ${BOLD}frida --version${RESET} — Verificar instalación"
echo -e "  • ${BOLD}frida-ps -U${RESET} — Listar procesos en dispositivo"
echo -e "  • ${BOLD}frida -U com.app -l script.js${RESET} — Hooking"
echo -e ""
echo -e "${CYAN}JADX:${RESET}"
echo -e "  • ${BOLD}$JADX_DIR/bin/jadx-gui${RESET} — Interfaz gráfica"
echo -e "  • ${BOLD}$JADX_DIR/bin/jadx app.apk${RESET} — CLI"
echo -e ""
echo -e "${CYAN}Drozer:${RESET}"
echo -e "  • ${BOLD}drozer console connect${RESET} — Conectar al agente"
echo -e "  • ${BOLD}run app.activity.info${RESET} — Listar actividades"
echo -e "  • ${BOLD}run scanner.provider.finduri${RESET} — Buscar SQLi"
echo -e ""
echo -e "${CYAN}MobSF (Docker):${RESET}"
echo -e "  • ${BOLD}docker compose up -d mobsf${RESET} — Iniciar MobSF"
echo -e "  • ${BOLD}http://localhost:8000${RESET} — Interfaz web"
echo -e ""
