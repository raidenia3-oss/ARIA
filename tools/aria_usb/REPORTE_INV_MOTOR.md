=== REPORTE-KILO ===
FASE: Investigación (motor unificado)

ESTADO:
- Diseño motor unificado: HECHO (tools/aria-usb/docs/DESIGN-MOTOR-UNIFICADO-DETALLADO.md)
- Investigación sin código: HECHO
- Integridad repo: OK (solo tools/aria-usb)

EVIDENCIA:
- Commit: 6f6a449cda856895bd625de1959dbc8834cc6e4e
- Archivos: DESIGN-MOTOR-UNIFICADO.md, DESIGN-MOTOR-UNIFICADO-DETALLADO.md

CONCLUSIÓN:
Viable: ModelManager + router extendido, multi-modal base (Qwen2.5-VL) + módulos (Whisper), SFT+LoRA automatizable en Kaggle/Colab (gratis), no manual, fail-closed. CPU-first Ryzen 5700G viable con modelo Q4 3–4B one-at-a-time.

DUDAS (3):
1. ¿Todo-en-uno (Qwen2.5-VL) vs módulos separados?
2. Login Kaggle/Colab (semi-manual) aceptable para "no manual"?
3. Priorizar uncensor ligero vs mejora funcional?

=== FIN ===
