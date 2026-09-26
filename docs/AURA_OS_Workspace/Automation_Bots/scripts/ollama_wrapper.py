import subprocess
import sys
import json

def run_ollama_directly(prompt):
    try:
        # Ejecutar Ollama directamente sin argumentos adicionales
        process = subprocess.Popen(
            ["ollama", "run", "dolphin-llama3"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Enviar el prompt en el formato correcto
        stdout, stderr = process.communicate(input=f"[INST] {prompt} [/INST]")

        if process.returncode != 0:
            return f"Error: {stderr.strip() if stderr else 'Desconocido'}"
        else:
            return stdout
    except Exception as e:
        return f"Error inesperado: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python ollama_wrapper.py \"prompt\"")
        sys.exit(1)

    prompt = sys.argv[1]
    response = run_ollama_directly(prompt)
    print(response)