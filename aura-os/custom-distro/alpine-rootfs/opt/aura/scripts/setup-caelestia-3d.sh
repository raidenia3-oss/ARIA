# AURA OS - Theme Setup (Caelestia 3D)
# Handles: custom photos, photo enhancement, 3D effects, animations

#!/bin/bash

THEME_DIR="/usr/share/themes/Caelestia"
WALLPAPER_DIR="/usr/share/pixmaps"
CONFIG_DIR="/etc/skel/.config/hypr"

# ============================================
# FOTO MEJORADA CON IMAGEMAGICK
# ============================================
enhance_photo() {
    local input="$1"
    local output="$2"
    
    if command -v convert &> /dev/null; then
        # Mejorar foto: sharpening, color correction, denoise
        convert "$input" \
            -resize 1920x1080^ \
            -gravity center \
            -extent 1920x1080 \
            -auto-level \
            -auto-gamma \
            -unsharp 0x1.0 \
            -denoise 0.5 \
            -brightness-contrast -5x10 \
            "$output" 2>/dev/null && return 0
    fi
    
    # Fallback: copiar original
    cp "$input" "$output"
    return 1
}

# ============================================
# GENERAR WALLPAPER 3D CON PROFUNDIDAD
# ============================================
generate_3d_wallpaper() {
    local output="$1"
    local photo="$2"
    
    if command -v convert &> /dev/null; then
        # Fondo base
        convert -size 1920x1080 \
            gradient:'#0a0e27'-'#1a1a3e' \
            "$output"
        
        # Si hay foto, superponer con efectos 3D
        if [ -f "$photo" ]; then
            convert "$output" \
                "$photo" -resize 1920x1080^ -gravity center -extent 1920x1080 \
                -blend 80 \
                -background '#0a0e27' \
                -layers merge \
                "$output"
        fi
        
        # Efecto de profundidad (vignette + blur selectivo)
        convert "$output" \
            -fill '#8a2be2' -colorize 10% \
            -blur 0x1 \
            -brightness-contrast -3x5 \
            -crop 1920x1080+0+0 \
            "$output" 2>/dev/null
    fi
}

# ============================================
# APLICAR THEME 3D A VENTANAS
# ============================================
apply_3d_window_rules() {
    cat > "$CONFIG_DIR/window-rules-3d.conf" << 'EOF'
# AURA OS - 3D Window Effects

# Efecto de profundidad en ventanas activas
windowrule = blur, class:.*
windowrule = shadow, class:.*
windowrule = rounding, class:.*

# Ventanas flotantes con más efecto 3D
windowrule = float, class:^(pavucontrol|nm-connection-editor|file-roller|kitty)$
windowrule = size 900x600, class:^(pavucontrol|nm-connection-editor)$
windowrule = move 0.5 0.5, class:^(pavucontrol|nm-connection-editor)$

# Efecto glass para terminales
windowrule = opacity 0.95 0.9, class:^(alacritty|kitty|foot)$
windowrule = rounding 12, class:^(alacritty|kitty|foot)$

# Navegador con efecto especial
windowrule = opacity 1.0 1.0, class:^(firefox|chromium|google-chrome)$

# AURA apps con glow
windowrule = shadow_color #8a2be2, class:^(AURA|aura)$
windowrule = shadow_size 20, class:^(AURA|aura)$
EOF
}

# ============================================
# ANIMACIONES 3D AVANZADAS
# ============================================
apply_3d_animations() {
    cat > "$CONFIG_DIR/animations-3d.conf" << 'EOF'
# AURA OS - 3D Animations

animations {
    enabled = yes
    
    # Curvas de animación 3D
    bezier = easeOutCubic, 0.33, 1, 0.68, 1
    bezier = easeInCubic, 0.32, 0, 0.67, 0
    bezier = easeOutBack, 0.34, 1.56, 0.64, 1
    bezier = smoothOut, 0.36, 0, 0.66, -0.56
    
    # Ventanas con efecto 3D de profundidad
    animation = windows, 1, 8, easeOutCubic, slide
    animation = windowsOut, 1, 6, easeInCubic, popin 80%
    
    # Bordes con glow animado
    animation = border, 1, 12, easeOutCubic
    animation = borderLength, 1, 12, easeOutCubic
    
    # Fade con profundidad
    animation = fade, 1, 8, easeOutCubic
    animation = fadeDim, 1, 8, easeOutCubic
    
    # Workspaces con zoom 3D
    animation = workspaces, 1, 8, easeOutBack, slide
    animation = workspacesIn, 1, 8, smoothOut, slide
    animation = workspacesOut, 1, 6, smoothIn, slide
    
    # Minimizar con efecto 3D
    animation = minimize, 1, 8, easeOutCubic
    animation = maximize, 1, 8, easeOutCubic
    
    # Mouse con tracking suave
    animation = mouseMove, 1, 15, easeOutCubic
    
    # Layout con transición 3D
    animation = layout, 1, 8, easeOutCubic
}
EOF
}

# ============================================
# MAIN SETUP
# ============================================
setup_3d_theme() {
    local photo="${1:-}"
    
    echo "╔════════════════════════════════════════════╗"
    echo "║     Caelestia 3D Theme Setup               ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    
    # Directorios
    mkdir -p "$THEME_DIR"
    mkdir -p "$WALLPAPER_DIR"
    mkdir -p "$CONFIG_DIR"
    
    # Wallpaper
    echo "[1/4] Setting up wallpaper..."
    if [ -n "$photo" ] && [ -f "$photo" ]; then
        echo "  Using photo: $photo"
        enhance_photo "$photo" "$WALLPAPER_DIR/aura-wallpaper.png"
        generate_3d_wallpaper "$WALLPAPER_DIR/aura-wallpaper-enhanced.png" "$photo"
    else
        echo "  No photo provided, using generated gradient"
        generate_3d_wallpaper "$WALLPAPER_DIR/aura-wallpaper.png" ""
    fi
    echo "✓ Wallpaper ready"
    
    # Window rules 3D
    echo "[2/4] Applying 3D window rules..."
    apply_3d_window_rules
    echo "✓ Window rules configured"
    
    # Animaciones 3D
    echo "[3/4] Applying 3D animations..."
    apply_3d_animations
    echo "✓ Animations configured"
    
    # Hyprland main config
    echo "[4/4] Configuring Hyprland..."
    cat > "$CONFIG_DIR/hyprland.conf" << 'HYPRCONF'
# AURA OS - Hyprland Configuration (Caelestia 3D Theme)
# Incluye: wallpaper 3D, animaciones, glass effects, blur

monitor=,preferred,auto,1

# Input
input {
    kb_layout = us,es
    kb_options = grp:alt_shift_toggle
    follow_mouse = 1
    touchpad {
        natural_scroll = false
        tap_to_click = true
    }
}

# General
general {
    gaps_in = 8
    gaps_out = 20
    border_size = 2
    col.active_border = rgba(8a2be2ff) rgba(38bdf8ff) 45deg
    col.inactive_border = rgba(0a0e27ff)
    layout = master
    allow_tearing = false
}

# Decoration con efectos 3D
decoration {
    rounding = 12
    drop_shadow = yes
    shadow_range = 8
    shadow_render_power = 4
    col.shadow = rgba(1a1a2eff)
    
    blur {
        enabled = yes
        size = 12
        passes = 4
        ignore_opacity = true
    }
    
    vignette {
        enabled = true
        size = 0.5
    }
}

# Animaciones 3D
animations {
    enabled = yes
    bezier = easeOutCubic, 0.33, 1, 0.68, 1
    bezier = easeInCubic, 0.32, 0, 0.67, 0
    bezier = easeOutBack, 0.34, 1.56, 0.64, 1
    
    animation = windows, 1, 8, easeOutCubic, slide
    animation = windowsOut, 1, 6, easeInCubic, popin 80%
    animation = border, 1, 12, easeOutCubic
    animation = fade, 1, 8, easeOutCubic
    animation = workspaces, 1, 8, easeOutBack, slide
    animation = minimize, 1, 8, easeOutCubic
    animation = mouseMove, 1, 15, easeOutCubic
}

# Dwindle
dwindle {
    pseudotile = yes
    preserve_split = yes
}

# Master
master {
    new_status = master
    new_on_top = true
    mfact = 0.55
}

# Keybinds
$mainMod = SUPER

bind = $mainMod, Return, exec, alacritty
bind = $mainMod, Q, killactive,
bind = $mainMod, D, exec, wofi --show drun
bind = $mainMod, E, exec, pcmanfm
bind = $mainMod, V, togglefloating,
bind = $mainMod, L, exec, hyprlock
bind = $mainMod, A, exec, /opt/aura/scripts/aura-cli.sh
bind = $mainMod, O, exec, /opt/aura/scripts/aura-voice.sh
bind = $mainMod, G, exec, ruby /opt/aura/scripts/custom_tools.rb

# Workspaces
bind = $mainMod, 1, workspace, 1
bind = $mainMod, 2, workspace, 2
bind = $mainMod, 3, workspace, 3
bind = $mainMod, 4, workspace, 4
bind = $mainMod, 5, workspace, 5
bind = $mainMod SHIFT, 1, movetoworkspace, 1
bind = $mainMod SHIFT, 2, movetoworkspace, 2
bind = $mainMod SHIFT, 3, movetoworkspace, 3

# Media
bind = , XF86AudioRaiseVolume, exec, pactl set-sink-volume @DEFAULT_SINK@ +5%
bind = , XF86AudioLowerVolume, exec, pactl set-sink-volume @DEFAULT_SINK@ -5%
bind = , XF86AudioMute, exec, pactl set-sink-mute @DEFAULT_SINK@ toggle

# Autostart
exec-once = hyprpaper -f /usr/share/pixmaps/aura-wallpaper.png
exec-once = waybar
exec-once = dunst
exec-once = /opt/aura/scripts/panel.sh

# Incluir reglas 3D adicionales
source = /etc/skel/.config/hypr/window-rules-3d.conf
source = /etc/skel/.config/hypr/animations-3d.conf
HYPRCONF

    echo "✓ Hyprland configured"
    
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║   Caelestia 3D Theme Installed            ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    echo "Features:"
    echo "  ✓ 3D window effects (blur, shadow, rounding)"
    echo "  ✓ 3D animations (easeOutBack, slide, popin)"
    echo "  ✓ Glass/vignette effects"
    echo "  ✓ Custom photo support"
    echo "  ✓ Photo enhancement (sharpening, denoise)"
    echo ""
}

# Ejecutar setup
setup_3d_theme "$1"
