import os
import requests
import time

JUDGE0_URL = os.environ.get("JUDGE0_URL", "https://ce.judge0.com")

# IDs de lenguajes en Judge0
LANGUAGES = {
    "python": 71,
    "cpp": 54,
    "c": 50,
    "javascript": 63,
    "java": 62,
    "bash": 46,
}

def execute_code(code: str, language: str = "python", stdin: str = "") -> dict:
    lang_id = LANGUAGES.get(language.lower(), 71)
    try:
        # Enviar código
        res = requests.post(
            f"{JUDGE0_URL}/submissions",
            json={
                "source_code": code,
                "language_id": lang_id,
                "stdin": stdin,
                "wait": False
            },
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if res.status_code not in [200, 201]:
            return {"error": f"Error enviando código: {res.status_code}"}

        token = res.json().get("token")
        if not token:
            return {"error": "No se obtuvo token de ejecución"}

        # Esperar resultado
        for _ in range(10):
            time.sleep(2)
            result = requests.get(
                f"{JUDGE0_URL}/submissions/{token}",
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            data = result.json()
            status_id = data.get("status", {}).get("id", 0)

            # Status 1=En cola, 2=Procesando, 3+=Listo
            if status_id >= 3:
                stdout = data.get("stdout") or ""
                stderr = data.get("stderr") or ""
                compile_err = data.get("compile_output") or ""
                status = data.get("status", {}).get("description", "")
                time_taken = data.get("time") or "?"
                memory = data.get("memory") or "?"

                return {
                    "stdout": stdout.strip(),
                    "stderr": stderr.strip(),
                    "compile_error": compile_err.strip(),
                    "status": status,
                    "time": time_taken,
                    "memory": memory,
                    "success": status_id == 3
                }

        return {"error": "Timeout — el código tardó demasiado"}

    except Exception as e:
        return {"error": f"Error: {str(e)}"}

def format_result(result: dict) -> str:
    if "error" in result:
        return f"❌ {result['error']}"

    out = f"⚡ Estado: {result['status']}\n"
    out += f"⏱ Tiempo: {result['time']}s | 💾 Memoria: {result['memory']} KB\n\n"

    if result.get("compile_error"):
        out += f"🔴 Error de compilación:\n{result['compile_error']}\n"
    elif result.get("stderr"):
        out += f"⚠️ Error:\n{result['stderr']}\n"
    elif result.get("stdout"):
        out += f"✅ Salida:\n{result['stdout']}"
    else:
        out += "✅ Ejecutado sin salida"

    return out

def detect_language(code: str) -> str:
    if "#include" in code or "int main" in code:
        return "cpp"
    if "console.log" in code or "const " in code or "let " in code:
        return "javascript"
    if "public class" in code or "System.out" in code:
        return "java"
    if "#!/bin/bash" in code:
        return "bash"
    return "python"
