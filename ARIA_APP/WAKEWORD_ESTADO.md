# Wake-word local — estado (regla v2: sin dependencias nuevas)

Fecha: 2026-11-09
Rama: feat/aria-unified

## Veredicto: NO viable con stdlib solo

La detección de wake-word ("hey aria", etc.) requiere:
1. Captura de micrófono en tiempo real -> `pyaudio` o `sounddevice` (no stdlib).
2. Modelo de detección de palabra de activación -> `vosk` / `openWakeWord` / Porcupine (no stdlib).

Ninguna de estas está en la biblioteca estándar de Python. La regla v2 prohíbe dependencias nuevas sin aprobación, por tanto el wake-word local **no se puede activar hoy**.

## Estado en el código
- `aria_va_core.py` declara `self.wake_words = ["hey aria","hola aria","ok aria","oye aria","aria"]` y `self._wake_available = False`.
- Los imports `import pyaudio` / `import sounddevice` / `import vosk` van envueltos en `try/except` y `self._wake_available` queda `False` cuando no están instalados (estado actual en este entorno: `pyaudio` y `vosk` no instalados).
- No hay escucha de micrófono activa; ARIA responde por texto/chat y por habilidades invocadas explícitamente.

## Qué se necesita para activarlo (pendiente de aprobación)
- Dependencia propuesta: `pyaudio` (captura) + `vosk` (wake-word offline) o `openWakeWord`.
- Una vez aprobadas e instaladas, se activa el hilo de wake-word ya esbozado en `aria_va_core.py` (`_wake_available`, `_on_wake`).

## Prueba
- `python -c "import pyaudio"` -> ModuloNotFoundError (no instalado).
- `python -c "import vosk"` -> ModuloNotFoundError (no instalado).
- `aria_va_core.LocalAIBrain()._wake_available` -> `False`.
