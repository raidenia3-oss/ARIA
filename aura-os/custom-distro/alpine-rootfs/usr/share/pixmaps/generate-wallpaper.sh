# AURA OS - Caelestia Theme
# Wallpaper: gradient aurora borealis style
# Generated procedurally with ImageMagick

cat > /usr/share/pixmaps/aura-wallpaper.png << 'WALLPAPER_EOF'
WALLPAPER_EOF

# Better: generate with gradients
cat > /usr/share/pixmaps/aura-wallpaper-gradient.sh << 'GEN'
#!/bin/bash
# Generar wallpaper Caelestia con gradientes
# Requiere: ImageMagick (convert)

WALLPAPER="/usr/share/pixmaps/aura-wallpaper.png"
WIDTH=1920
HEIGHT=1080

convert -size ${WIDTH}x${HEIGHT} \
  gradient:'#0a0e27'-'#1a1a3e' \
  -fill '#8a2be2' -draw 'rectangle 0,0 1920,200' \
  -fill '#38bdf8' -draw 'rectangle 0,200 1920,400' \
  -fill '#8a2be2' -draw 'rectangle 0,400 1920,600' \
  -fill '#38bdf8' -draw 'rectangle 0,600 1920,800' \
  -fill '#8a2be2' -draw 'rectangle 0,800 1920,1000' \
  -fill '#0a0e27' -draw 'rectangle 0,1000 1920,1080' \
  -blur 0x20 \
  "$WALLPAPER" 2>/dev/null || true

echo "Wallpaper generado: $WALLPAPER"
GEN

chmod +x /usr/share/pixmaps/aura-wallpaper-gradient.sh
