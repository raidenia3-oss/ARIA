#!/usr/bin/env python3
"""Conectores sociales de ARIA: la audiencia entra al backend.

Este script es el "puente" entre las redes donde habla la gente y el runtime
autónomo de ARIA (backend Axum). Cada conector:

1. escucha mensajes de una plataforma (Twitch, YouTube, Discord),
2. los empuja a ``POST /api/social/messages``,
3. recoge lo que ARIA responde en ``GET /api/social/channels/<id>/outbox``
   y lo publica en la plataforma.

No es un Bot de Discord ni un script de streaming: es un lector y un
escritor tonto. La inteligencia (qué contestar, cuándo callarse, cómo
sonar) vive en el backend, igual que en Neuro-sama o Airi, donde el
conector sólo transporta.

Uso::

    python scripts/aria_social.py --kind twitch --target vedal987
    python scripts/aria_social.py --kind youtube --target <id-video>
    python scripts/aria_social.py --kind discord --target <channel-id>
    python scripts/aria_social.py --kind simulator --target demo

Variables de entorno:
    ARIA_BACKEND   dirección del backend (por defecto http://127.0.0.1:8002)
    ARIA_TOKEN     token de acceso (Bearer)
    DISCORD_BOT_TOKEN  token del bot de Discord (sólo para el conector de Discord)
"""

from __future__ import annotations

import argparse
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BACKEND = os.environ.get("ARIA_BACKEND", "http://127.0.0.1:8002").rstrip("/")
TOKEN = os.environ.get("ARIA_TOKEN", "")
USER_AGENT = "ARIA-Social/1.0 (+autonomous presence)"

# Cliente anónimo de Twitch: el protocolo IRC no necesita cuenta para leer
# el chat de un canal público.
TWITCH_HOST = "irc.chat.twitch.tv"
TWITCH_PORT = 6697

# API pública de YouTube (la de innertube). Se usa para leer el chat en
# directo de una emisión.
YOUTUBE_API_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"
YOUTUBE_LIVE_CHAT = "https://www.youtube.com/youtubei/v1/live_chat/get_live_chat"

DISCORD_API = "https://discord.com/api/v10"


def log(message: str) -> None:
    """Estado para el backend: una línea por stdout,Flush para que el
    supervisor del backend la vea enseguida."""
    print(f"ARIA-SOCIAL: {message}", flush=True)


def _request(
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict | None = None,
    timeout: int = 15,
) -> tuple[int, str]:
    """Petición HTTP mínima. Devuelve (código, cuerpo)."""
    data = None
    all_headers = {"User-Agent": USER_AGENT}
    if headers:
        all_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        all_headers["Content-Type"] = "application/json"
    if TOKEN:
        all_headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(url, data=data, headers=all_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")
    except Exception as error:  # red caída, DNS, timeout...
        return 0, str(error)


def channel_id_for(kind: str, target: str) -> str:
    """Identificador de canal en el backend: `twitch:vedal987`."""
    clean = "".join(
        c.lower() if c.isalnum() or c in "-_" else "-" for c in target.strip()
    ).strip("-")
    return f"{kind}:{clean}"


def push_message(channel: str, author: str, text: str) -> bool:
    """Manda un mensaje al backend."""
    status, body = _request(
        "POST",
        f"{BACKEND}/api/social/messages",
        {"channel": channel, "author": author, "text": text},
    )
    if status != 200:
        log(f"error al enviar mensaje ({status}): {body[:160]}")
        return False
    return True


def take_outbox(channel: str) -> list[dict]:
    """Recoge lo que ARIA quiere decir en ese canal."""
    status, body = _request("GET", f"{BACKEND}/api/social/channels/{urllib.parse.quote(channel)}/outbox")
    if status != 200:
        return []
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return []
    return payload.get("messages", [])


def channel_enabled(channel: str) -> bool:
    """¿Sigue el canal encendido? Si el usuario lo apaga, el conector se
    va solo."""
    status, body = _request("GET", f"{BACKEND}/api/social/channels/{urllib.parse.quote(channel)}")
    if status != 200:
        return True  # backend caído: el conector espera, no se muere
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return True
    channel_data = payload.get("channel") or {}
    return bool(channel_data.get("enabled", True))


def report_state(channel: str, connected: bool, status: str) -> None:
    """Informa al backend del estado del conector."""
    _request(
        "POST",
        f"{BACKEND}/api/social/channels/{urllib.parse.quote(channel)}/state",
        {"connected": connected, "status": status},
    )


# --------------------------------------------------------------------------
# Twitch: IRC en claro sobre TLS
# --------------------------------------------------------------------------


def run_twitch(target: str, channel: str) -> None:
    """Lee el chat de un canal de Twitch.

    El protocolo IRC es de texto plano sobre TLS: se conecta, se anuncia
    como anónimo, se entra al canal y se leen los PRIVMSG. Es el mismo
    camino que usan los bots de chat de Twitch, sin dependencias.
    """
    import socket

    nickname = f"aria_{random.randint(1000, 9999)}"
    context = ssl.create_default_context()
    report_state(channel, False, "conectando")
    while channel_enabled(channel):
        try:
            raw = socket.create_connection((TWITCH_HOST, TWITCH_PORT), timeout=30)
        except OSError as error:
            log(f"twitch: no se pudo conectar ({error})")
            time.sleep(10)
            continue
        secure = context.wrap_socket(raw, server_hostname=TWITCH_HOST)
        secure.settimeout(60)
        file = secure.makefile("r", encoding="utf-8", errors="replace", newline="\n")

        def send(line: str) -> None:
            secure.sendall((line + "\r\n").encode("utf-8"))

        send("CAP REQ :twitch.tv/tags twitch.tv/commands")
        send(f"NICK {nickname}")
        send("JOIN #" + target.lower())
        report_state(channel, True, "conectado")
        log(f"twitch: conectado a #{target.lower()}")

        try:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("PING"):
                    send("PONG :twitch.tv")
                    continue
                if "PRIVMSG" not in line:
                    continue
                parts = line.split(" ", 3)
                if len(parts) < 4:
                    continue
                author = parts[0].split("!")[0].split("@")[0]
                text = parts[3]
                # El prefijo de estado (":uptime, :emote-only, ..") no
                # interesa; lo que llega en el segundo campo es el mensaje.
                if text.startswith(":"):
                    text = text[1:]
                push_message(channel, author or "anon", text)
        except (OSError, ssl.SSLError) as error:
            log(f"twitch: conexión perdida ({error})")
        finally:
            try:
                secure.close()
            except OSError:
                pass
        report_state(channel, False, "reconectando")
        time.sleep(5)


# --------------------------------------------------------------------------
# YouTube: chat en directo por la API de innertube
# --------------------------------------------------------------------------


def _youtube_continuation(video_id: str) -> str:
    """Saca el token de continuación del chat en vivo de un vídeo."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    status, body = _request("GET", url, headers={"Accept-Language": "es"})
    if status != 200:
        raise RuntimeError(f"no se pudo abrir el vídeo ({status})")
    marker = '"liveChatRenderer":{"continuation"'
    index = body.find(marker)
    if index < 0:
        raise RuntimeError("el vídeo no tiene chat en vivo")
    start = index + len(marker)
    end = body.find('"', start)
    raw = body[start:end]
    return raw.encode("utf-8").decode("unicode_escape")


def run_youtube(target: str, channel: str) -> None:
    """Lee el chat en directo de un vídeo de YouTube.

    La API de innertube devuelve el chat en "continuaciones": cada respuesta
    trae las acciones y el siguiente token. Se repite hasta que el directo
    se acaba.
    """
    video_id = target
    if "v=" in target:
        query = urllib.parse.urlparse(target).query
        video_id = urllib.parse.parse_qs(query).get("v", [""])[0]
    video_id = video_id.split("/")[-1] if "/" in video_id else video_id
    if not video_id:
        log("youtube: hace falta el id del vídeo")
        return

    report_state(channel, False, "conectando")
    while channel_enabled(channel):
        try:
            continuation = _youtube_continuation(video_id)
        except RuntimeError as error:
            log(f"youtube: {error}")
            report_state(channel, False, "error")
            time.sleep(20)
            continue

        report_state(channel, True, "conectado")
        log(f"youtube: leyendo el chat de {video_id}")
        while channel_enabled(channel):
            payload = {
                "context": {
                    "client": {"clientName": "WEB", "clientVersion": "2.20240101.00.00"}
                },
                "videoId": video_id,
                "continuation": continuation,
            }
            status, body = _request(
                "POST",
                f"{YOUTUBE_LIVE_CHAT}?key={YOUTUBE_API_KEY}",
                payload,
            )
            if status != 200:
                log(f"youtube: error del chat ({status})")
                time.sleep(10)
                break
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                time.sleep(10)
                break
            actions = (
                data.get("actions")
                or data.get("continuationContents", {})
                .get("liveChatContinuation", {})
                .get("continuations", [])
            )
            texts = []
            next_continuation = None
            for action in actions:
                if not isinstance(action, dict):
                    continue
                if "reloadContinuationData" in action:
                    next_continuation = action["reloadContinuationData"].get("continuation")
                renderer = action.get("addChatItemAction", {}).get("item", {})
                message = renderer.get("liveChatTextMessageRenderer", {})
                author = (
                    message.get("authorName", {}).get("simpleText")
                    or message.get("authorName", {}).get("runs", [{}])[0].get("text", "anon")
                )
                parts = message.get("message", {}).get("runs", [])
                text = "".join(part.get("text", "") for part in parts)
                if text:
                    texts.append((author, text))
            for author, text in texts:
                push_message(channel, author, text)
            if next_continuation:
                continuation = next_continuation
                time.sleep(3)
            else:
                time.sleep(8)
        report_state(channel, False, "reconectando")
        time.sleep(5)


# --------------------------------------------------------------------------
# Discord: API REST de bot
# --------------------------------------------------------------------------


def run_discord(target: str, channel: str) -> None:
    """Lee y escribe en un canal de Discord.

    Se usa la API REST (no el gateway): basta con pedir los últimos
    mensajes del canal cada pocos segundos y, cuando hay algo nuevo,
    publicarlo en el backend. Para escribir, se usa el mismo endpoint con
    el token del bot.
    """
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    channel_key = target.strip()
    if not token:
        log("discord: falta DISCORD_BOT_TOKEN")
        report_state(channel, False, "sin token")
        return

    headers = {"Authorization": f"Bot {token}"}
    last_id = None
    report_state(channel, False, "conectando")
    while channel_enabled(channel):
        status, body = _request(
            "GET",
            f"{DISCORD_API}/channels/{channel_key}/messages?limit=20",
            headers=headers,
        )
        if status != 200:
            log(f"discord: error leyendo ({status})")
            report_state(channel, False, "reconectando")
            time.sleep(10)
            continue
        try:
            messages = json.loads(body)
        except json.JSONDecodeError:
            time.sleep(5)
            continue
        if not isinstance(messages, list):
            time.sleep(5)
            continue
        report_state(channel, True, "conectado")
        for message in reversed(messages):
            message_id = message.get("id")
            if last_id and message_id and message_id <= last_id:
                continue
            author = (message.get("author") or {}).get("username", "anon")
            content = (message.get("content") or "").strip()
            if content:
                push_message(channel, author, content)
            if message_id:
                last_id = message_id

        # Lo que ARIA responde se publica aquí.
        for reply in take_outbox(channel):
            text = reply.get("text", "").strip()
            if not text:
                continue
            _request(
                "POST",
                f"{DISCORD_API}/channels/{channel_key}/messages",
                {"content": text},
                headers=headers,
            )
        time.sleep(4)


# --------------------------------------------------------------------------
# Simulador: la audiencia de prueba
# --------------------------------------------------------------------------

SIMULATED = [
    ("ana", "hola ARIA, ¿qué tal?"),
    ("bruno", "estoy mirando esto desde el móvil"),
    ("carla", "aria ¿puedes revisar la red local?"),
    ("diego", "qué pasada lo que hicisteis la semana pasada"),
    ("eva", "ARIA cuenta algo interesante"),
    ("fede", "luego me lo explicas"),
    ("gaby", "¿qué herramientas de red tienes?"),
]


def run_simulator(target: str, channel: str) -> None:
    """Audiencia de mentira para probar el circuito entero sin cuentas.

    Genera mensajes con la forma de los reales (algunos dirigidos a ARIA,
    otros no) y deja que ARIA conteste sola.
    """
    report_state(channel, True, "conectado")
    log(f"simulador: audiencia de prueba en {channel}")
    index = 0
    while channel_enabled(channel):
        author, text = SIMULATED[index % len(SIMULATED)]
        index += 1
        push_message(channel, author, text)
        # Se entrega lo que ARIA haya contestado durante este ciclo.
        for reply in take_outbox(channel):
            log(f"respuesta: {reply.get('text', '')}")
        time.sleep(float(os.environ.get("ARIA_SIMULATOR_INTERVAL", "12")))


# --------------------------------------------------------------------------
# Arranque
# --------------------------------------------------------------------------

KIND_RUNNERS = {
    "twitch": run_twitch,
    "youtube": run_youtube,
    "discord": run_discord,
    "simulator": run_simulator,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Conectores sociales de ARIA")
    parser.add_argument(
        "--kind",
        required=True,
        choices=sorted(KIND_RUNNERS.keys()),
        help="de dónde viene el chat",
    )
    parser.add_argument("--target", required=True, help="canal, vídeo o id de Discord")
    parser.add_argument("--channel", default=None, help="id del canal en el backend")
    args = parser.parse_args()

    channel = args.channel or channel_id_for(args.kind, args.target)
    log(f"conector {args.kind} -> {channel}")

    try:
        KIND_RUNNERS[args.kind](args.target, channel)
    except KeyboardInterrupt:
        log("parado")
    except Exception as error:  # noqa: BLE001 - un conector no tumba ARIA
        log(f"error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
