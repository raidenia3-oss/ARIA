#!/bin/bash
# Caelestia Theme Setup
# Aplica iconos, wallpaper y configuraciones de tema

set -e

THEME_DIR="/usr/share/icons/Caelestia"
CONFIG_DIR="/etc/skel/.config"
WALLPAPER_DIR="/usr/share/pixmaps"

echo "╔════════════════════════════════════════════╗"
echo "║     Caelestia Theme Setup                  ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Crear directorios
mkdir -p "$THEME_DIR"
mkdir -p "$WALLPAPER_DIR"

# Copiar iconos
echo "[1/4] Installing icons..."
cp -r "$CONFIG_DIR/icons/Caelestia/apps" "$THEME_DIR/"
cp -r "$CONFIG_DIR/icons/Caelestia/devices" "$THEME_DIR/"
cp -r "$CONFIG_DIR/icons/Caelestia/places" "$THEME_DIR/"
cp -r "$CONFIG_DIR/icons/Caelestia/mimetypes" "$THEME_DIR/"

# Crear index.theme
cat > "$THEME_DIR/index.theme" << 'ICONTHEME'
[Icon Theme]
Name=Caelestia
Comment=AURA OS Caelestia Theme
Inherits=Papirus,hicolor

[Desktop Entry]
Name=Caelestia
Comment=AURA OS Theme
IconTheme=Caelestia
ICONTHEME

echo "✓ Icons installed"

# Generar wallpaper
echo "[2/4] Generating wallpaper..."
if command -v convert &> /dev/null; then
    convert -size 1920x1080 \
      gradient:'#0a0e27'-'#1a1a3e' \
      -fill '#8a2be2' -draw 'rectangle 0,0 1920,200' \
      -fill '#38bdf8' -draw 'rectangle 0,200 1920,400' \
      -fill '#8a2be2' -draw 'rectangle 0,400 1920,600' \
      -fill '#38bdf8' -draw 'rectangle 0,600 1920,800' \
      -fill '#8a2be2' -draw 'rectangle 0,800 1920,1000' \
      -fill '#0a0e27' -draw 'rectangle 0,1000 1920,1080' \
      -blur 0x20 \
      "$WALLPAPER_DIR/aura-wallpaper.png"
    echo "✓ Wallpaper generated"
else
    echo "⚠ ImageMagick not found, skipping wallpaper generation"
fi

# Configurar GTK/Qt theme
echo "[3/4] Configuring GTK/Qt..."
mkdir -p /etc/skel/.config/gtk-3.0
mkdir -p /etc/skel/.config/qt5ct
mkdir -p /etc/skel/.config/qt6ct

cat > /etc/skel/.config/gtk-3.0/settings.ini << 'GTKCONF'
[Settings]
gtk-theme-name=Caelestia
gtk-icon-theme-name=Caelestia
gtk-font-name=Noto Sans 11
gtk-cursor-theme-name=Adwaita
gtk-toolbar-style=GTK_TOOLBAR_ICONS
gtk-button-images=1
gtk-menu-images=1
gtk-enable-animations=1
gtk-application-prefer-dark-theme=1
GTKCONF

echo "✓ GTK theme configured"

# Configurar Waybar
echo "[4/4] Configuring Waybar..."
mkdir -p /etc/skel/.config/waybar

cat > /etc/skel/.config/waybar/config << 'WAYBAR'
{
  "layer": "top",
  "position": "top",
  "height": 32,
  "spacing": 8,
  "margin-top": 8,
  "margin-left": 16,
  "margin-right": 16,
  
  "modules-left": ["hyprland/workspaces", "hyprland/window"],
  "modules-center": ["clock"],
  "modules-right": ["cpu", "memory", "battery", "pulseaudio", "tray"],
  
  "hyprland/workspaces": {
    "format": "{name}",
    "on-click": "activate",
    "active-only": false,
    "all-outputs": true
  },
  
  "hyprland/window": {
    "format": "{}",
    "max-length": 40
  },
  
  "clock": {
    "format": "{:%H:%M}",
    "tooltip-format": "{:%Y-%m-%d %H:%M:%S}"
  },
  
  "cpu": {
    "format": "CPU {}%",
    "interval": 5
  },
  
  "memory": {
    "format": "RAM {}%",
    "interval": 5
  },
  
  "battery": {
    "format": "BAT {}%",
    "interval": 10
  },
  
  "pulseaudio": {
    "format": "VOL {volume}%",
    "on-click": "pavucontrol"
  },
  
  "tray": {
    "icon-size": 16,
    "spacing": 8
  }
}
WAYBAR

cat > /etc/skel/.config/waybar/style.css << 'WAYBARSTYLE'
* {
  border: none;
  border-radius: 8px;
  background: rgba(10, 14, 39, 0.9);
  color: #38bdf8;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}

window#waybar {
  background: rgba(10, 14, 39, 0.95);
  border-bottom: 2px solid #8a2be2;
  backdrop-filter: blur(10px);
}

#workspaces button {
  background: transparent;
  color: #38bdf8;
  padding: 0 12px;
  margin: 4px 2px;
  border-radius: 8px;
  transition: all 0.2s;
}

#workspaces button.active {
  background: linear-gradient(90deg, #8a2be2, #38bdf8);
  color: white;
}

#workspaces button.urgent {
  background: #ff4444;
  color: white;
}

#cpu, #memory, #battery, #pulseaudio, #clock, #tray {
  background: rgba(138, 43, 226, 0.2);
  border: 1px solid rgba(138, 43, 226, 0.4);
  padding: 0 12px;
  margin: 4px 2px;
  border-radius: 8px;
}
WAYBARSTYLE

echo "✓ Waybar configured"

echo ""
echo "╔════════════════════════════════════════════╗"
echo "║   Caelestia Theme Installed Successfully  ║"
echo "╚════════════════════════════════════════════╝"
echo ""
echo "Theme: Caelestia"
echo "Icons: $THEME_DIR"
echo "Wallpaper: $WALLPAPER_DIR/aura-wallpaper.png"
echo "Config: $CONFIG_DIR"
echo ""
