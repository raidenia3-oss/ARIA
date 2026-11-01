import sys
content = '''#!/usr/bin/env python3
"""video_a_texto.py - convierte videos e imagenes en TEXTO que ARIA pueda leer.

Por cada archivo escribe un .md con: transaccion del audio (con mm:ss) y texto en
pantalla (OCR de fotogramas). Al final junta todo en INFORME.md + index.json.

Honestidad: cada seccion lleva un estado (ok / unavailable / sin_audio / sin_texto).
Si falta una herramienta, la seccion dice unavailable y por que. Nunca inventa texto.

Seguridad: lo extraido es DATO NO CONFIABLE. Un video o comentario puede contener
"ignora tus instrucciones". Este script no ejecuta ni interpreta nada de lo extraido.
La censura de codigos/emails es de mejor esfuerzo: revisa el informe antes de compartirlo.

Uso:
  python video_a_texto.py "D:\\\\ARIA\\\\drive_inbox\\\\INSTAGRAM" -o "D:\\\\ARIA\\\\salida"
Requisitos: ffmpeg y ffprobe en el PATH. Opcionales:
  pip install faster-whisper          (transaccion; descarga el modelo la 1a vez)
  pip install rapidocr-onnxruntime    (OCR sin binarios externos)  o  tesseract en el PATH
"""
'''
with open('video_a_texto.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('ok')