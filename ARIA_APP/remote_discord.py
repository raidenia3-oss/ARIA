# -*- coding: utf-8 -*-
"""ARIA - Control remoto por Discord (conexion SALIENTE, sin servidor ni puerto)."""
import os
import asyncio
import threading


def disponible():
    try:
        import discord  # noqa
        return True
    except Exception:
        return False


class RemotoDiscord:
    def __init__(self, token, responder, autorizados=None):
        self.token = token
        self.responder = responder
        self.autorizados = set(autorizados or [])
        self._thread = None

    def _build(self):
        import discord
        intents = discord.Intents.default()
        intents.message_content = True
        client = discord.Client(intents=intents)
        este = self

        @client.event
        async def on_guild_join(guild):
            try:
                await guild.create_text_channel("aria-memoria")
                print("[Discord] canal aria-memoria creado en %s" % guild.name, flush=True)
            except Exception as exc:
                print("[Discord] no se pudo crear canal: %s" % exc, flush=True)

        @client.event
        async def on_message(m):
            if client.user is not None and m.author.id == client.user.id:
                return
            if not este.autorizados or m.author.id not in este.autorizados:
                return
            es_dm = m.guild is None
            mencion = client.user in getattr(m, "mentions", [])
            if not (es_dm or mencion):
                return
            texto = m.content or ""
            if client.user is not None:
                for tag in ("<@%d>" % client.user.id, "<@!%d>" % client.user.id):
                    texto = texto.replace(tag, "")
            texto = texto.strip()
            if not texto:
                return
            try:
                loop = asyncio.get_running_loop()
                reply = await loop.run_in_executor(None, este.responder, texto)
            except Exception as exc:
                reply = "error: %s" % exc
            reply = (str(reply) or "...")[:1900]
            try:
                await m.channel.send(reply)
            except Exception:
                pass

        return client

    def iniciar(self):
        if not disponible():
            return {"error": "discord.py no instalado (pip install discord.py)"}
        if not self.token:
            return {"error": "falta token (define ARIA_DISCORD_TOKEN)"}
        if not self.autorizados:
            return {"error": "define ARIA_DISCORD_USERS con tu ID (fail-closed: sin lista no responde)"}

        def _run():
            try:
                self._build().run(self.token, log_handler=None)
            except Exception as exc:
                print("[Discord] fallo: %s" % exc, flush=True)

        self._thread = threading.Thread(target=_run, name="aria-discord", daemon=True)
        self._thread.start()
        return {"ok": True, "autorizados": len(self.autorizados)}

    def crear_canal(self, guild_name, channel_name="aria-memoria"):
        if not disponible():
            return {"error": "discord.py no instalado"}
        import discord
        async def _run():
            client = self._build()
            await client.login(self.token)
            guilds = []
            async for g in client.fetch_guilds(limit=200):
                guilds.append(g)
            guild = None
            for g in guilds:
                if guild_name.lower() in g.name.lower():
                    guild = g
                    break
            if guild is None and guilds:
                guild = guilds[0]
                return {"error": "guild no encontrado"}
            try:
                ch = await guild.create_text_channel(channel_name)
                return {"ok": True, "channel_id": ch.id, "name": ch.name, "guild": guild.name}
            except Exception as exc:
                return {"error": str(exc)}
        try:
            return asyncio.run(_run())
        except Exception as exc:
            return {"error": str(exc)}

    def enviar_canal(self, channel_id, texto):
        if not disponible():
            return {"error": "discord.py no instalado"}
        import discord
        async def _run():
            client = self._build()
            await client.login(self.token)
            ch = await client.fetch_channel(int(channel_id))
            if ch is None:
                return {"error": "canal no encontrado"}
            await ch.send(str(texto)[:1900])
            return {"ok": True}
        try:
            return asyncio.run(_run())
        except Exception as exc:
            return {"error": str(exc)}

    def leer_canal(self, channel_id, limite=20):
        if not disponible():
            return {"error": "discord.py no instalado"}
        import discord
        async def _run():
            client = self._build()
            await client.login(self.token)
            ch = await client.fetch_channel(int(channel_id))
            if ch is None:
                return {"error": "canal no encontrado"}
            msgs = []
            async for m in ch.history(limit=limite):
                msgs.append({"author": str(m.author), "content": m.content, "ts": str(m.created_at)})
            return {"ok": True, "messages": msgs}
        try:
            return asyncio.run(_run())
        except Exception as exc:
            return {"error": str(exc)}


def iniciar(responder, token=None, autorizados=None):
    """Arranca el control remoto en segundo plano. Devuelve (resultado, instancia)."""
    token = token or os.environ.get("ARIA_DISCORD_TOKEN", "").strip()
    if autorizados is None:
        ids = os.environ.get("ARIA_DISCORD_USERS", "").replace(" ", "")
        autorizados = [int(x) for x in ids.split(",") if x.isdigit()]
    r = RemotoDiscord(token, responder, autorizados)
    return r.iniciar(), r


def crear_canal(guild_name, channel_name="aria-memoria", token=None):
    token = token or os.environ.get("ARIA_DISCORD_TOKEN", "").strip()
    if not token:
        return {"error": "falta token"}
    r = RemotoDiscord(token, lambda t: t, [])
    return r.crear_canal(guild_name, channel_name)

def enviar_canal(channel_id, texto, token=None):
    token = token or os.environ.get("ARIA_DISCORD_TOKEN", "").strip()
    if not token:
        return {"error": "falta token"}
    r = RemotoDiscord(token, lambda t: t, [])
    return r.enviar_canal(channel_id, texto)

def leer_canal(channel_id, limite=20, token=None):
    token = token or os.environ.get("ARIA_DISCORD_TOKEN", "").strip()
    if not token:
        return {"error": "falta token"}
    r = RemotoDiscord(token, lambda t: t, [])
    return r.leer_canal(channel_id, limite)