import os
import logging
import asyncio
import json

import requests
import discord
from discord.ext import commands
from discord import app_commands

TARGET_CHAT_URL = os.getenv("AURA_CHAT_URL", "https://aura-server-01.vercel.app/chat")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


def build_payload(message: discord.Message) -> dict:
    channel_name = getattr(message.channel, "name", str(message.channel))
    return {
        "message": message.content,
        "user": str(message.author),
        "channel": f"{message.guild.name if message.guild else 'DM'} / {channel_name}",
        "channel_id": str(message.channel.id),
        "guild_id": str(message.guild.id) if message.guild else None,
    }


@bot.event
async def on_ready():
    logging.info("✅ AURA Discord bot conectado como %s", bot.user)
    logging.info("🌐 Enviando mensajes a %s", TARGET_CHAT_URL)
    
    # Sincronizar comandos slash
    try:
        synced = await bot.tree.sync()
        logging.info("✅ Comandos slash sincronizados: %d", len(synced))
    except Exception as e:
        logging.error("❌ Error sincronizando comandos slash: %s", e)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    text = message.content.strip()
    if not text:
        return

    payload = build_payload(message)
    logging.info("📨 Enviando mensaje de Discord a AURA: %s", payload)

    try:
        response = requests.post(TARGET_CHAT_URL, json=payload, timeout=30)
        response.raise_for_status()

        reply = None
        try:
            data = response.json()
            reply = data.get("reply") or data.get("response") or data.get("message")
        except ValueError:
            reply = response.text.strip()

        if reply:
            await message.channel.send(reply)
            logging.info("✅ Respuesta enviada a Discord")
        else:
            logging.info("⚠️ La API devolvió respuesta vacía")

    except requests.exceptions.RequestException as e:
        logging.error("❌ Error enviando mensaje a AURA: %s", e)
        await message.channel.send("❌ No pude conectar con AURA. Revisa la configuración del bot.")

    await bot.process_commands(message)


@bot.command(name="ping", description="Comprueba que el bot de Discord está activo")
async def ping(ctx: commands.Context):
    await ctx.send("Pong! El bot está conectado.")


# ========================
# COMANDO /osint (Slash)
# ========================
@bot.tree.command(name="osint", description="Escaneo OSINT Shodan: IP, puertos, vulns críticos, geo")
@app_commands.describe(
    target="IP o dominio a escanear (ej: 8.8.8.8 o example.com)",
    mode="Modo de escaneo: host (completo), vulns (solo CVEs), search (búsqueda)"
)
@app_commands.choices(mode=[
    app_commands.Choice(name="Host Completo", value="host"),
    app_commands.Choice(name="Solo Vulnerabilidades", value="vulns"),
    app_commands.Choice(name="Búsqueda", value="search"),
])
async def osint_slash(
    interaction: discord.Interaction,
    target: str,
    mode: app_commands.Choice[str] = None
):
    await interaction.response.defer(thinking=True)
    
    scan_mode = mode.value if mode else "host"
    
    try:
        # Llamar al endpoint de AURA que ejecuta el módulo Venice
        aura_osint_url = os.getenv("AURA_OSINT_URL", "http://localhost:5000/osint")
        
        payload = {
            "target": target,
            "mode": scan_mode,
            "discord_user": str(interaction.user),
            "discord_channel": str(interaction.channel.id)
        }
        
        # Ejecutar en hilo para no bloquear
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: requests.post(aura_osint_url, json=payload, timeout=60)
        )
        
        if result.status_code != 200:
            await interaction.followup.send(f"❌ Error {result.status_code}: {result.text}")
            return
        
        data = result.json()
        
        # Formatear como embed de Discord
        embed_data = data.get("embed", data)
        
        embed = discord.Embed(
            title=embed_data.get("title", "🔍 Perfil de Inteligencia Shodan"),
            description=embed_data.get("description", ""),
            color=embed_data.get("color", 0xFFA500)
        )
        
        for field in embed_data.get("fields", []):
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", "N/A"),
                inline=field.get("inline", False)
            )
        
        if "footer" in embed_data:
            embed.set_footer(text=embed_data["footer"].get("text", "AURA Venice OSINT"))
        
        embed.timestamp = discord.utils.utcnow()
        
        await interaction.followup.send(embed=embed)
        
    except requests.exceptions.Timeout:
        await interaction.followup.send("⏱️ Timeout: El escaneo tardó demasiado")
    except requests.exceptions.RequestException as e:
        # Fallback: intentar ejecutar directamente via task_dispatcher
        logging.warning("Fallo endpoint OSINT, intentando fallback: %s", e)
        await _osint_fallback(interaction, target, scan_mode)
    except Exception as e:
        logging.error("Error en /osint: %s", e)
        await interaction.followup.send(f"❌ Error interno: {str(e)}")


async def _osint_fallback(interaction: discord.Interaction, target: str, mode: str):
    """Fallback: ejecutar venice_shodan_scanner.py directamente vía task_dispatcher"""
    try:
        # Usar task_dispatcher para encolar la tarea
        dispatcher_url = os.getenv("AURA_DISPATCHER_URL", "http://localhost:8080/api/task")
        
        task_payload = {
            "task_type": "OSINT_SHODAN",
            "parameters": {
                "target": target,
                "mode": mode
            },
            "priority": "high",
            "requested_by": str(interaction.user),
            "reason": f"Comando /osint de Discord por {interaction.user}"
        }
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: requests.post(dispatcher_url, json=task_payload, timeout=10)
        )
        
        if result.status_code == 200:
            task_data = result.json()
            task_id = task_data.get("task_id")
            await interaction.followup.send(
                f"✅ Tarea OSINT encolada (ID: `{task_id}`). "
                f"Usa `/osint_status {task_id}` para ver resultados."
            )
        else:
            await interaction.followup.send(
                f"❌ No se pudo encolar la tarea. "
                f"AURA no responde. Verifica que el dispatcher esté corriendo."
            )
            
    except Exception as e:
        logging.error("Fallback OSINT falló: %s", e)
        await interaction.followup.send("❌ Error crítico: No se pudo procesar la solicitud OSINT")


@bot.tree.command(name="osint_status", description="Consulta el estado de una tarea OSINT encolada")
@app_commands.describe(task_id="ID de la tarea (ej: task_abc123)")
async def osint_status(interaction: discord.Interaction, task_id: str):
    await interaction.response.defer(thinking=True)
    
    try:
        dispatcher_url = os.getenv("AURA_DISPATCHER_URL", "http://localhost:8080/api/task")
        status_url = f"{dispatcher_url}/{task_id}"
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: requests.get(status_url, timeout=10)
        )
        
        if result.status_code == 200:
            data = result.json()
            status = data.get("status", "unknown")
            
            if status == "completed":
                result_data = data.get("result", {})
                embed_data = result_data.get("embed", result_data)
                
                embed = discord.Embed(
                    title=embed_data.get("title", "🔍 Resultado OSINT"),
                    description=embed_data.get("description", ""),
                    color=embed_data.get("color", 0x00FF00)
                )
                for field in embed_data.get("fields", []):
                    embed.add_field(
                        name=field.get("name", ""),
                        value=field.get("value", "N/A"),
                        inline=field.get("inline", False)
                    )
                if "footer" in embed_data:
                    embed.set_footer(text=embed_data["footer"].get("text", "AURA Venice OSINT"))
                embed.timestamp = discord.utils.utcnow()
                
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(
                    f"⏳ Tarea `{task_id}` - Estado: **{status}**\n"
                    f"Reintenta en unos segundos con `/osint_status {task_id}`"
                )
        else:
            await interaction.followup.send(f"❌ Tarea no encontrada: `{task_id}`")
            
    except Exception as e:
        logging.error("Error consultando estado OSINT: %s", e)
        await interaction.followup.send(f"❌ Error: {str(e)}")


def main():
    if not DISCORD_TOKEN or len(DISCORD_TOKEN) < 10:
        logging.error("DISCORD_TOKEN no configurado o inválido. El bot no se iniciará.")
        return

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()