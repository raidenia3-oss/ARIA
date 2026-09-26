# AURA OS - Caelestia Integration

Módulo de integración de Caelestia Shell en AURA OS.

## ¿Qué es Caelestia?
Shell de escritorio moderno para Hyprland/Arch Linux basado en QuickShell.
- Dashboard con controles de media, sistema y clima
- App launcher con comandos
- Panel lateral con widgets
- Temas Material You dinámicos
- Integración MPRIS para YouTube/Spotify

## Instalación en AURA OS

```bash
# En Arch Linux base
sudo pacman -S --noconfirm hyprland waybar rofi-wayland kitty pipewire python-pip git

# Instalar Caelestia CLI desde AUR
yay -S caelestia-shell-git

# Configurar Hyprland para usar Caelestia
mkdir -p ~/.config/hypr
cat > ~/.config/hypr/hyprland.conf << 'EOF'
exec-once = caelestia-shell
exec-once = waybar
EOF
```

## Integración con AURA Backend

Caelestia se conecta al backend de AURA via:
- REST API: `http://localhost:8000/api/*`
- WebSocket: `ws://localhost:8000/ws/telemetry`
- IPC: `caelestia shell mpris` para control de media

## Personalización AURA

El tema de Caelestia se adapta a la paleta de colores de AURA:
- Fondo: `#0a0e27`
- Acento: `#38bdf8` (cyan)
- Secundario: `#8a2be2` (purple)
- Tipografía: JetBrains Mono / Inter

## Comandos personalizados

```bash
# Control de AURA desde Caelestia
caelestia shell command aura-status    # Estado del sistema
caelestia shell command aura-chat      # Abrir chat con AURA
caelestia shell command aura-gesture   # Activar control por gestos
```
