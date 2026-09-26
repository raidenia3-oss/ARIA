import requests
import sys
import json

def run_ollama_api(prompt):
    try:
        # Usar la API de Ollama directamente
        url = "http://localhost:11434/api/generate"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": "dolphin-llama3",
            "prompt": f"{prompt}",
            "stream": False
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        # Procesar la respuesta JSON
        response_data = response.json()
        if "response" in response_data:
            return response_data["response"]
        else:
            return f"No se recibió respuesta del modelo. Respuesta: {json.dumps(response_data)}"
    except requests.exceptions.RequestException as e:
        return f"Error en la API de Ollama: {str(e)}"
    except Exception as e:
        return f"Error inesperado: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python ollama_api_wrapper.py \"prompt\"")
        sys.exit(1)

    prompt = sys.argv[1]
    response = run_ollama_api(prompt)
    print(response)