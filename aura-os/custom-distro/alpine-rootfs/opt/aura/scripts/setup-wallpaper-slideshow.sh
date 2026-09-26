#!/bin/bash
# AURA OS - Slideshow de Wallpapers 3D
# Mejora fotos automáticamente y las rota con efectos 3D

set -e

WALLPAPER_DIR="/usr/share/pixmaps/aura-wallpapers"
CONFIG_DIR="/etc/skel/.config/hypr"
SLIDESHOW_CONFIG="$CONFIG_DIR/wallpaper-slideshow.conf"

echo "╔════════════════════════════════════════════╗"
echo "║   AURA OS - Wallpaper Slideshow 3D        ║"
echo "╚════════════════════════════════════════════╝"
echo ""

# Argumentos
PHOTO_DIR="${1:-/mnt/usb/wallpapers}"
INTERVAL="${2:-30}"  # segundos entre cambios
EFFECT="${3:-3d}"    # 3d, blur, glow, normal

# Crear directorios
mkdir -p "$WALLPAPER_DIR"

# ============================================
# MEJORAR FOTO INDIVIDUAL
# ============================================
enhance_photo() {
    local input="$1"
    local output="$2"
    local effect="$3"
    
    if ! command -v convert &> /dev/null; then
        cp "$input" "$output"
        return
    fi
    
    # Pipeline de mejora
    convert "$input" \
        -resize 1920x1080^ \
        -gravity center \
        -extent 1920x1080 \
        -auto-level \
        -auto-gamma \
        -unsharp 0x1.0 \
        -denoise 0.5 \
        -brightness-contrast -5x10 \
        "$output" 2>/dev/null || cp "$input" "$output"
    
    # Aplicar efecto 3D
    case "$effect" in
        3d)
            convert "$output" \
                -fill '#8a2be2' -colorize 8% \
                -blur 0x1.5 \
                -brightness-contrast -3x5 \
                -vignette 0x0+0+0 \
                "$output" 2>/dev/null
            ;;
        blur)
            convert "$output" \
                -blur 0x3 \
                -brightness-contrast -5x8 \
                "$output" 2>/dev/null
            ;;
        glow)
            convert "$output" \
                -fill '#38bdf8' -colorize 5% \
                -blur 0x2 \
                -brightness 105% \
                "$output" 2>/dev/null
            ;;
    esac
}

# ============================================
# PROCESAR CARPETA DE FOTOS
# ============================================
process_photos() {
    local photo_dir="$1"
    local count=0
    
    echo "[1/4] Processing photos from: $photo_dir"
    
    if [ ! -d "$photo_dir" ]; then
        echo "  ERROR: Directory not found: $photo_dir"
        echo "  Create a folder with your photos and try again."
        exit 1
    fi
    
    # Limpiar wallpapers anteriores
    rm -f "$WALLPAPER_DIR"/aura-wallpaper-*.png
    rm -f "$WALLPAPER_DIR"/aura-wallpaper-enhanced.png
    
    # Procesar cada foto
    for photo in "$photo_dir"/*.jpg "$photo_dir"/*.jpeg "$photo_dir"/*.png "$photo_dir"/*.JPG "$photo_dir"/*.JPEG "$photo_dir"/*.PNG; do
        [ -f "$photo" ] || continue
        
        count=$((count + 1))
        output="$WALLPAPER_DIR/aura-wallpaper-$(printf "%03d" $count).png"
        
        echo "  Processing: $(basename "$photo") -> $output"
        enhance_photo "$photo" "$output" "$EFFECT"
    done
    
    echo "✓ Processed $count photos"
    
    if [ $count -eq 0 ]; then
        echo "  WARNING: No photos found in $photo_dir"
        echo "  Adding default gradient wallpaper..."
        generate_default_wallpaper
        count=1
    fi
    
    echo "$count"
}

# ============================================
# GENERAR WALLPAPER DEFAULT
# ============================================
generate_default_wallpaper() {
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
            "$WALLPAPER_DIR/aura-wallpaper-001.png" 2>/dev/null || true
    fi
}

# ============================================
# CREAR CONFIGURACIÓN DE SLIDESHOW
# ============================================
create_slideshow_config() {
    local count="$1"
    local interval="$2"
    
    echo "[2/4] Creating slideshow config..."
    
    cat > "$SLIDESHOW_CONFIG" << SLIDECONF
# AURA OS - Wallpaper Slideshow Configuration
# Auto-generated

# Configuración
SLIDESHOW_INTERVAL=$interval
SLIDESHOW_COUNT=$count
SLIDESHOW_CURRENT=1
SLIDESHOW_EFFECT=$EFFECT

# Wallpapers
SLIDESHOW_WALLPAPERS=()
for i in \$(ls "$WALLPAPER_DIR"/aura-wallpaper-*.png 2>/dev/null | sort); do
    SLIDESHOW_WALLPAPERS+=("\$i")
done

# Efectos por foto (opcional)
# SLIDESHOW_EFFECTS=(3d blur glow normal)
SLIDECONF

    echo "✓ Slideshow config created"
}

# ============================================
# CREAR SCRIPT DE ROTACIÓN
# ============================================
create_rotator_script() {
    echo "[3/4] Creating rotator script..."
    
    cat > "$CONFIG_DIR/wallpaper-rotator.sh" << 'ROTATOR'
#!/bin/bash
# AURA OS - Wallpaper Rotator
# Rota wallpapers automáticamente cada X segundos

CONFIG="/etc/skel/.config/hypr/wallpaper-slideshow.conf"
INTERVAL=30
CURRENT=1
COUNT=0
WALLPAPERS=()

# Cargar configuración
if [ -f "$CONFIG" ]; then
    source "$CONFIG"
fi

# Si no hay config, usar defaults
if [ $COUNT -eq 0 ]; then
    WALLPAPERS=($(ls /usr/share/pixmaps/aura-wallpapers/aura-wallpaper-*.png 2>/dev/null | sort))
    COUNT=${#WALLPAPERS[@]}
    INTERVAL=30
fi

if [ $COUNT -eq 0 ]; then
    echo "ERROR: No wallpapers found"
    exit 1
fi

echo "Starting wallpaper rotator..."
echo "  Wallpapers: $COUNT"
echo "  Interval: ${INTERVAL}s"
echo "  Press Ctrl+C to stop"
echo ""

# Función para cambiar wallpaper
change_wallpaper() {
    local wp="${WALLPAPERS[$((CURRENT - 1))]}"
    
    # Usar hyprpaper si está disponible
    if command -v hyprctl &> /dev/null; then
        hyprctl hyprpaper wallpaper "eDP-1,$wp" 2>/dev/null || \
        hyprctl hyprpaper preload "$wp" 2>/dev/null || true
    fi
    
    # Fallback: swww
    if command -v swww &> /dev/null; then
        swww img "$wp" --transition-type grow --transition-fps 60 2>/dev/null || true
    fi
    
    # Fallback: feh
    if command -v feh &> /dev/null; then
        feh --bg-scale "$wp" 2>/dev/null || true
    fi
    
    echo "[$(date '+%H:%M:%S')] Wallpaper: $(basename "$wp")"
    
    # Siguiente
    CURRENT=$((CURRENT + 1))
    if [ $CURRENT -gt $COUNT ]; then
        CURRENT=1
    fi
}

# Cambiar wallpaper inmediatamente
change_wallpaper

# Loop de rotación
while true; do
    sleep "$INTERVAL"
    change_wallpaper
done
ROTATOR

    chmod +x "$CONFIG_DIR/wallpaper-rotator.sh"
    echo "✓ Rotator script created"
}

# ============================================
# INTEGRAR CON HYPRLAND
# ============================================
integrate_hyprland() {
    echo "[4/4] Integrating with Hyprland..."
    
    # Agregar exec-once al hyprland.conf
    if [ -f "$CONFIG_DIR/hyprland.conf" ]; then
        # Verificar si ya está agregado
        if ! grep -q "wallpaper-rotator.sh" "$CONFIG_DIR/hyprland.conf"; then
            echo "" >> "$CONFIG_DIR/hyprland.conf"
            echo "# Wallpaper slideshow" >> "$CONFIG_DIR/hyprland.conf"
            echo "exec-once = $CONFIG_DIR/wallpaper-rotator.sh" >> "$CONFIG_DIR/hyprland.conf"
        fi
    fi
    
    echo "✓ Hyprland integration complete"
}

# ============================================
# MAIN
# ============================================
main() {
    local photo_dir="$1"
    local interval="$2"
    local effect="$3"
    
    # Validar intervalo
    if [ -z "$interval" ]; then
        interval=30
    fi
    
    # Validar efecto
    case "$effect" in
        3d|blur|glow|normal) ;;
        *) effect="3d" ;;
    esac
    
    echo "Configuration:"
    echo "  Photo directory: $photo_dir"
    echo "  Interval: ${interval}s"
    echo "  Effect: $effect"
    echo ""
    
    # Procesar fotos
    local count
    count=$(process_photos "$photo_dir")
    
    # Crear config
    create_slideshow_config "$count" "$interval"
    
    # Crear rotador
    create_rotator_script
    
    # Integrar
    integrate_hyprland
    
    echo ""
    echo "╔════════════════════════════════════════════╗"
    echo "║   Slideshow 3D Ready!                     ║"
    echo "╚════════════════════════════════════════════╝"
    echo ""
    echo "Wallpapers: $count"
    echo "Location: $WALLPAPER_DIR"
    echo "Interval: ${interval}s"
    echo "Effect: $effect"
    echo ""
    echo "To start slideshow:"
    echo "  $CONFIG_DIR/wallpaper-rotator.sh &"
    echo ""
    echo "To add more photos:"
    echo "  1. Copy photos to: $photo_dir"
    echo "  2. Run this script again"
    echo ""
    echo "Effects available: 3d, blur, glow, normal"
    echo ""
}

main "$@"
