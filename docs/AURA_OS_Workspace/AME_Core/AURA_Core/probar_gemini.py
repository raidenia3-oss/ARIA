import os
from dotenv import load_dotenv
from google.genai import Client, types

# Cargar API Key desde .env
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

try:
    client = Client(api_key=GEMINI_API_KEY)
    chat = client.chats.create(model="models/gemini-2.5-flash")
    response = chat.send_message("Hola, confirma que la API Key funciona correctamente")
    print('--- DEBUG: response repr ---')
    try:
        print(repr(response))
    except Exception:
        print('No se pudo representar response')

    # Extraer texto de la respuesta de forma robusta
    text = ""
    try:
        candidates = getattr(response, "candidates", None)
        if candidates:
            content = getattr(candidates[0], "content", None)
            if content:
                parts = getattr(content, "parts", None)
                if parts:
                    for p in parts:
                        t = getattr(p, "text", None)
                        if t:
                            text += t
                        else:
                            text += str(p)
                else:
                    text = str(content)
            else:
                text = str(candidates[0])
        else:
            text = str(response)
    except Exception as e:
        text = f"Error extrayendo texto: {e}"

    print("✅ Resultado:", text)

except Exception as e:
    print("❌ Error al probar la API Key:", str(e))