import os
from flask import Flask, request, jsonify, send_from_directory
import speech_recognition as sr
from gtts import gTTS
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_cache")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/api/voice/interact", methods=["POST"])
def voice_interact():
    """
    Ruta para la comunicación bidireccional por voz.
    1. Recibe el archivo de audio.
    2. Lo transcribe a texto (STT).
    3. Genera una respuesta o interactúa con el sistema (aquí simulado o conectado a AURA).
    4. Convierte la respuesta a audio (TTS).
    5. Devuelve la URL del audio resultante.
    """
    if "audio" not in request.files:
        return jsonify({"error": "No se envió ningún archivo de audio"}), 400

    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    # Guardar audio de entrada
    input_filename = f"input_{uuid.uuid4().hex}.wav"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    audio_file.save(input_path)

    # 1. Speech-to-Text (STT)
    recognizer = sr.Recognizer()
    transcription = ""
    try:
        with sr.AudioFile(input_path) as source:
            audio_data = recognizer.record(source)
            transcription = recognizer.recognize_google(audio_data, language="es-ES")
    except sr.UnknownValueError:
        transcription = "[Audio no inteligible]"
    except sr.RequestError as e:
        transcription = f"[Error del servicio STT: {e}]"
    except Exception as e:
        transcription = f"[Error STT: {str(e)}]"

    # 2. Generar respuesta (simulada/inteligencia de AURA)
    response_text = f"He recibido tu mensaje por voz que dice: '{transcription}'. ¿En qué más puedo ayudarte hoy?"
    if "hola" in transcription.lower():
        response_text = "¡Hola! Estoy listo para recibir tus comandos de voz de forma segura en AURA."
    elif "estado" in transcription.lower():
        response_text = "Todos los sistemas de AURA se encuentran operativos y el escudo perimetral está al cien por cien."

    # 3. Text-to-Speech (TTS)
    output_filename = f"output_{uuid.uuid4().hex}.mp3"
    output_path = os.path.join(UPLOAD_FOLDER, output_filename)
    try:
        tts = gTTS(text=response_text, lang="es")
        tts.save(output_path)
    except Exception as e:
        return jsonify({"error": f"Error en generación TTS: {str(e)}", "transcription": transcription}), 500

    # Retornar URL de descarga para reproducción automática
    audio_url = f"http://localhost:5000/api/voice/cache/{output_filename}"

    return jsonify({
        "transcription": transcription,
        "response": response_text,
        "audio_url": audio_url
    }), 200

@app.route("/api/voice/cache/<filename>", methods=["GET"])
def get_cached_audio(filename):
    """Permite descargar/reproducir los audios generados por el servidor."""
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
