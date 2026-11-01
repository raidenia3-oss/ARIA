Ambxst mejorado: fondo personalizado desde galería, con animaciones cortas.

- Seleccionar imagen (local/galería): ackground pick o g pick
- Usar URL/gradiente: ackground set url("...") o ackground set linear-gradient(...) 
- Animaciones: ackground anim kenburns|zoom|fade|none
- Limpiar: ackground clear
- Temas: 	heme ambxst dark / 	heme ambxst light
- Mejorar/autoaplicar: g enhance (ARIA puede sugerir/optimizar brillo/contraste)

Frontend:
- ambxst.css (glass, blur, overlay, animaciones)
- ambxst-bg.js (gestión + API global)
- ambxst-gallery.js (file picker + enhance)
- ambxst-init.js

Nota: las imágenes se guardan en localStorage (dataURL). ARIA puede analizar la imagen al cargarla para sugerir animación óptima.
