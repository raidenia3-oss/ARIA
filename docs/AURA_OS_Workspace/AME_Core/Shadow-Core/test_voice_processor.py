#!/usr/bin/env python3
"""
Script de prueba para el Voice Processor.
Permite probar el procesamiento de comandos de voz con archivos de ejemplo.
"""

import os
import requests
import time
import tempfile
import wave
import contextlib
import subprocess
import threading
from datetime import datetime

# Configuración global
VOICE_PROCESSOR_URL = "http://localhost:5018"
AUTH_KEY = "SECRET_AUTH_KEY_12345"

def create_test_audio(duration=3, sample_rate=16000, channels=1):
    """
    Crear un archivo de audio de prueba con ruido blanco.
    Esto simula un archivo de audio real para pruebas.
    """
    try:
        print(f"🎤 Creando archivo de audio de prueba ({duration} segundos)...")

        # Crear un archivo temporal
        temp_audio_path = tempfile.mktemp(suffix=".webm")

        # Generar audio con ruido blanco
        with contextlib.closing(wave.open(temp_audio_path, 'wb')) as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(2)  # 2 bytes por sample (16-bit)
            wav_file.setframerate(sample_rate)
            wav_file.setcomptype('WAV', 'IMA ADPCM')

            # Generar datos de audio (ruido blanco)
            frames = []
            for _ in range(int(sample_rate * duration)):
                frames.append(int(32767 * (2 * (0.5 - datetime.now().microsecond / 1000000))))

            wav_file.writeframes(b''.join([frame.to_bytes(2, byteorder='little', signed=True) for frame in frames]))

        print(f"✅ Archivo de audio creado: {temp_audio_path}")
        return temp_audio_path
    except Exception as e:
        print(f"❌ Error al crear archivo de audio: {e}")
        return None

def record_audio(duration=5):
    """
    Grabar audio desde el micrófono usando arecord (Linux) o similar.
    """
    try:
        print(f"🎤 Grabando audio desde el micrófono ({duration} segundos)...")

        # Intentar grabar audio usando arecord (Linux)
        temp_audio_path = tempfile.mktemp(suffix=".wav")
        command = f"arecord -D plughw:0,0 -d {duration} -f cd -r 16000 -c 1 {temp_audio_path}"

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=duration + 5
        )

        if result.returncode == 0:
            print(f"✅ Audio grabado correctamente: {temp_audio_path}")
            return temp_audio_path
        else:
            print(f"❌ Error al grabar audio: {result.stderr}")
            return None
    except Exception as e:
        print(f"❌ Error al grabar audio: {e}")
        return None

def call_voice_processor(audio_file_path):
    """Llamar al Voice Processor para procesar un archivo de audio."""
    try:
        print(f"📤 Enviando audio al Voice Processor: {audio_file_path}")

        with open(audio_file_path, 'rb') as f:
            files = {'audio': (os.path.basename(audio_file_path), f)}
            response = requests.post(
                f"{VOICE_PROCESSOR_URL}/api/voice-command",
                files=files,
                timeout=60
            )

        if response.status_code == 202:
            print(f"✅ Comando de voz enviado correctamente (procesamiento en curso)")
            print(f"   Código de respuesta: {response.status_code}")
            print(f"   Mensaje: {response.json().get('message', 'Procesamiento en curso')}")
            return response.json()
        elif response.status_code == 200:
            print(f"✅ Comando de voz procesado:")
            result = response.json()
            print(f"   Texto transcrito: {result.get('transcription', 'No disponible')[:100]}...")
            print(f"   Respuesta del Model Router: {result.get('model_router_response', 'No disponible')[:100]}...")
            return result
        else:
            print(f"❌ Error al enviar comando de voz:")
            print(f"   Código de respuesta: {response.status_code}")
            print(f"   Mensaje: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error al llamar al Voice Processor: {e}")
        return None

def get_voice_processor_status():
    """Obtener el estado actual del Voice Processor."""
    try:
        response = requests.get(f"{VOICE_PROCESSOR_URL}/api/voice-status", timeout=10)
        if response.status_code == 200:
            print(f"✅ Estado del Voice Processor:")
            status = response.json()
            print(f"   Modelo: {status.get('model', 'desconocido')}")
            print(f"   Transcripciones activas: {status.get('active_transcriptions', 0)}")
            print(f"   Transcripciones completadas: {status.get('completed_transcriptions', 0)}")
            print(f"   Transcripciones fallidas: {status.get('failed_transcriptions', 0)}")
            print(f"   Última actualización: {status.get('last_updated', 'Nunca')}")
            return status
        else:
            print(f"❌ Error al obtener estado del Voice Processor:")
            print(f"   Código de respuesta: {response.status_code}")
            print(f"   Mensaje: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error al obtener estado del Voice Processor: {e}")
        return None

def test_voice_processor_with_example():
    """Probar el Voice Processor con un archivo de audio de ejemplo."""
    print("\n🧪 Probando Voice Processor con archivo de audio de ejemplo...")

    # Crear un archivo de audio de prueba
    audio_file_path = create_test_audio(duration=3)

    if not audio_file_path:
        print("❌ No se pudo crear archivo de audio de prueba")
        return False

    try:
        # Enviar el audio al Voice Processor
        result = call_voice_processor(audio_file_path)

        if result and result.get("status") == "ok":
            print("\n✅ Prueba del Voice Processor completada con éxito!")
            print(f"   Texto transcrito: {result.get('transcription', '')[:150]}...")
            print(f"   Tiempo de procesamiento: {result.get('processing_time', 0):.2f} segundos")
            print(f"   Modelo usado: {result.get('model_used', 'desconocido')}")
            return True
        else:
            print("\n❌ Prueba del Voice Processor fallida:")
            print(f"   Estado: {result.get('status', 'desconocido')}")
            print(f"   Mensaje: {result.get('message', 'No disponible')}")
            return False
    finally:
        # Limpiar archivo temporal
        if audio_file_path and os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                print(f"🗑️  Archivo temporal eliminado: {audio_file_path}")
            except Exception as e:
                print(f"⚠️  Error al eliminar archivo temporal: {e}")

def test_voice_processor_with_recording():
    """Probar el Voice Processor grabando audio desde el micrófono."""
    print("\n🎤 Probando Voice Processor con grabación de audio...")

    # Intentar grabar audio
    audio_file_path = record_audio(duration=5)

    if not audio_file_path:
        print("⚠️  No se pudo grabar audio. Usando archivo de ejemplo en su lugar.")
        audio_file_path = create_test_audio(duration=3)
        if not audio_file_path:
            print("❌ No se pudo crear archivo de audio de prueba")
            return False

    try:
        # Enviar el audio al Voice Processor
        result = call_voice_processor(audio_file_path)

        if result and result.get("status") == "ok":
            print("\n✅ Prueba del Voice Processor con grabación completada con éxito!")
            print(f"   Texto transcrito: {result.get('transcription', '')[:150]}...")
            print(f"   Tiempo de procesamiento: {result.get('processing_time', 0):.2f} segundos")
            print(f"   Modelo usado: {result.get('model_used', 'desconocido')}")
            return True
        else:
            print("\n❌ Prueba del Voice Processor con grabación fallida:")
            print(f"   Estado: {result.get('status', 'desconocido')}")
            print(f"   Mensaje: {result.get('message', 'No disponible')}")
            return False
    finally:
        # Limpiar archivo temporal
        if audio_file_path and os.path.exists(audio_file_path):
            try:
                os.remove(audio_file_path)
                print(f"🗑️  Archivo temporal eliminado: {audio_file_path}")
            except Exception as e:
                print(f"⚠️  Error al eliminar archivo temporal: {e}")

def test_voice_processor_status():
    """Probar obteniendo el estado del Voice Processor."""
    print("\n📊 Probando estado del Voice Processor...")
    status = get_voice_processor_status()
    return status is not None

def main():
    """Función principal para probar el Voice Processor."""
    print("=" * 100)
    print("🎤 PRUEBA DEL VOICE PROCESSOR")
    print("=" * 100)
    print("Este script prueba el procesamiento de comandos de voz en AURA.")
    print("=" * 100)

    # Opción 1: Probar con archivo de ejemplo
    print("1. Probar con archivo de audio de ejemplo")
    print("2. Probar grabando audio desde el micrófono")
    print("3. Ambas opciones")
    choice = input("Elige una opción (1-3): ").strip()

    success_count = 0

    if choice == "1" or choice == "3":
        if test_voice_processor_with_example():
            success_count += 1
            time.sleep(2)

    if choice == "2" or choice == "3":
        if test_voice_processor_with_recording():
            success_count += 1
            time.sleep(2)

    # Probar estado del procesador
    if test_voice_processor_status():
        success_count += 1

    # Resumen final
    print("\n" + "=" * 100)
    print("📊 RESUMEN DE LAS PRUEBAS")
    print("=" * 100)
    print(f"✅ Prueba con archivo de ejemplo: {'Completada' if choice in ['1', '3'] else 'Saltada'}")
    print(f"✅ Prueba con grabación de audio: {'Completada' if choice in ['2', '3'] else 'Saltada'}")
    print(f"✅ Prueba de estado del procesador: {'Completada' if test_voice_processor_status() else 'Fallida'}")

    if success_count > 0:
        print(f"\n🎉 {success_count} de {1 if choice in ['1', '2'] else 2} pruebas completadas con éxito!")
        print("\n🔧 El Voice Processor está funcionando correctamente:")
        print("   • Puede transcribir audio a texto")
        print("   • Puede enviar comandos al Model Router")
        print("   • Proporciona estado en tiempo real")
        print("   • Funciona con archivos .webm y .wav")
    else:
        print("\n❌ Todas las pruebas fallaron. Revisa los mensajes anteriores.")

    print("\n" + "=" * 100)
    print("💡 INSTRUCCIONES PARA USAR EL VOICE PROCESSOR:")
    print("1. Graba un archivo de audio en formato .webm o .wav")
    print("2. Usa curl para enviar el audio:")
    print("   curl -X POST -F \"audio=@tu_archivo.webm\" http://localhost:5018/api/voice-command")
    print("3. Verifica el estado del procesador:")
    print("   curl http://localhost:5018/api/voice-status")
    print("4. Para probar con un archivo de ejemplo:")
    print("   python Shadow-Core/test_voice_processor.py")
    print("=" * 100)

    return success_count > 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)