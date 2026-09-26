import tkinter as tk
from tkinter import messagebox
import requests
import os
import threading

# =========================
# CONFIGURACIÓN
# =========================
SERVER_URL = os.getenv("TRAIN_SERVER_URL", "http://127.0.0.1:5000/train")  # Flask de TRAIN
TRAIN_TOKEN = os.getenv("TRAIN_TOKEN")
TRAIN_COLOR = "#FFD700"  # Dorado
TRAIN_NAME = "TRAIN"

# =========================
# FUNCIÓN PARA ENVIAR MENSAJE
# =========================
def enviar_mensaje():
    texto = entrada.get()
    if not texto.strip():
        return
    mostrar_mensaje("Tú", texto)
    entrada.delete(0, tk.END)

    def hilo_post():
        try:
            headers = {"Content-Type": "application/json"}
            if TRAIN_TOKEN:
                headers["X-Train-Token"] = TRAIN_TOKEN
            respuesta = requests.post(SERVER_URL, json={"msg": texto}, headers=headers).json()
            mostrar_mensaje(TRAIN_NAME, respuesta.get("respuesta", str(respuesta)))
            burbuja_alerta()  # Muestra alerta de burbuja
        except Exception as e:
            mostrar_mensaje("Error", str(e))

    threading.Thread(target=hilo_post, daemon=True).start()

# =========================
# FUNCIÓN PARA MOSTRAR MENSAJE
# =========================
def mostrar_mensaje(remitente, texto):
    chat.config(state="normal")
    chat.insert(tk.END, f"{remitente}: {texto}\n")
    chat.config(state="disabled")
    chat.see(tk.END)

# =========================
# BURBUJA MÓVIL DE NOTIFICACIÓN
# =========================
def burbuja_alerta():
    # Crea la burbuja si no existe
    if not hasattr(burbuja_alerta, "widget"):
        burbuja_alerta.widget = tk.Toplevel(root)
        burbuja_alerta.widget.overrideredirect(True)
        burbuja_alerta.widget.geometry("50x50+500+200")
        burbuja_alerta.widget.config(bg=TRAIN_COLOR)

        # Permite mover la burbuja
        def mover(event):
            burbuja_alerta.widget.geometry(f"+{event.x_root}+{event.y_root}")
        burbuja_alerta.widget.bind("<B1-Motion>", mover)

    # Parpadeo de alerta
    def parpadear():
        for _ in range(3):
            burbuja_alerta.widget.config(bg="white")
            burbuja_alerta.widget.update()
            burbuja_alerta.widget.after(200)
            burbuja_alerta.widget.config(bg=TRAIN_COLOR)
            burbuja_alerta.widget.update()
            burbuja_alerta.widget.after(200)
    threading.Thread(target=parpadear, daemon=True).start()

# =========================
# INTERFAZ PRINCIPAL
# =========================
root = tk.Tk()
root.title("Chat TRAIN")
root.geometry("400x500")

chat = tk.Text(root, state="disabled", wrap="word")
chat.pack(expand=True, fill="both")

entrada = tk.Entry(root)
entrada.pack(fill="x")
entrada.bind("<Return>", lambda e: enviar_mensaje())

enviar_btn = tk.Button(root, text="Enviar", command=enviar_mensaje)
enviar_btn.pack()

root.mainloop()