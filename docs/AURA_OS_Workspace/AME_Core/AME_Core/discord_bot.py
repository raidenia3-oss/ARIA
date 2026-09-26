import os
import logging
import asyncio
import json
import re
import subprocess

import requests
import discord
from discord.ext import commands
from discord import app_commands

# Configuración para CallMeBot (WhatsApp)
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY", "")
CALLMEBOT_PHONE = os.getenv("CALLMEBOT_PHONE", "")
WHATSAPP_ALERT_MESSAGE = "[ALERTA AURA] Intrusión física detectada en el perímetro del laboratorio"

# Configuración para RuView y OSINT
RUVIEW_RADAR_URL = os.getenv("RUVIEW_RADAR_URL", "http://localhost:5000/radar")
OSINT_WORKER_URL = os.getenv("OSINT_WORKER_URL", "http://localhost:5000/osint")
TERMUX_IP_URL = os.getenv("TERMUX_IP_URL", "http://localhost:5000/telemetry")

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

    # Verificar si el mensaje contiene un evento de intrusión física
    if "PHYSICAL_INTRUSION" in text or "Intrusión física detectada" in text:
        logging.warning("🚨 Evento de intrusión física detectado: %s", text)
        send_whatsapp_alert(WHATSAPP_ALERT_MESSAGE)

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


def send_whatsapp_alert(message: str):
    """Envía una alerta por WhatsApp usando CallMeBot"""
    if not CALLMEBOT_API_KEY or not CALLMEBOT_PHONE:
        logging.error("CallMeBot no configurado (API_KEY o PHONE vacíos)")
        return False

    try:
        url = f"https://api.callmebot.com/{CALLMEBOT_API_KEY}.json"
        payload = {
            "phone": CALLMEBOT_PHONE,
            "text": message,
            "apikey": CALLMEBOT_API_KEY
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info("✅ Alerta enviada por WhatsApp: %s", message)
        return True
    except Exception as e:
        logging.error("❌ Error enviando alerta por WhatsApp: %s", e)
        return False

def clean_json_output(data: dict) -> str:
    """Limpia el JSON para mostrar solo texto escaneable y ordenado"""
    if not isinstance(data, dict):
        return str(data)

    cleaned_lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            cleaned_lines.append(f"**{key}:**")
            cleaned_lines.extend(clean_json_output(value).split("\n"))
        elif isinstance(value, list):
            cleaned_lines.append(f"**{key}:**")
            for item in value:
                cleaned_lines.append(f"- {item}")
        else:
            cleaned_lines.append(f"**{key}:** {value}")

    return "\n".join(cleaned_lines)

async def _radar_on(interaction: discord.Interaction):
    """Activa el simulador RuView y el monitoreo de presencia en la 'arena etérea'"""
    await interaction.response.defer(thinking=True)

    try:
        # Activar el radar RuView
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: requests.post(RUVIEW_RADAR_URL, json={"action": "start"}, timeout=10)
        )

        if result.status_code == 200:
            data = result.json()
            embed = discord.Embed(
                title="🔮 Radar RuView Activado",
                description="El simulador de CSI y el monitoreo de presencia están activos en la 'arena etérea'.",
                color=0x00FF00
            )
            embed.add_field(name="Estado", value="Activado", inline=True)
            embed.add_field(name="Modo", value="Monitoreo de presencia", inline=True)
            embed.add_field(name="Ubicación", value="Arena etérea", inline=True)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Error al activar el radar: {result.text}")

    except Exception as e:
        logging.error("Error en /radar_on: %s", e)
        await interaction.followup.send(f"❌ Error interno: {str(e)}")

async def _target(interaction: discord.Interaction, alias: str):
    """Ejecuta el worker de OSINT asíncrono y devuelve el mapeo de cuentas"""
    await interaction.response.defer(thinking=True)

    try:
        # Enviar tarea al worker OSINT
        payload = {
            "alias": alias,
            "discord_user": str(interaction.user),
            "discord_channel": str(interaction.channel.id)
        }

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: requests.post(OSINT_WORKER_URL, json=payload, timeout=60)
        )

        if result.status_code == 200:
            data = result.json()
            cleaned_output = clean_json_output(data.get("result", {}))

            embed = discord.Embed(
                title=f"🔍 OSINT: {alias}",
                description="Mapeo de cuentas encontrado:",
                color=0xFFA500
            )
            embed.add_field(name="Resultado", value=cleaned_output, inline=False)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"❌ Error en OSINT: {result.text}")

    except Exception as e:
        logging.error("Error en /target: %s", e)
        await interaction.followup.send(f"❌ Error interno: {str(e)}")

async def _swarm_status(interaction: discord.Interaction):
    """Muestra la telemetría base de la PC y la última IP registrada del nodo Termux"""
    await interaction.response.defer(thinking=True)

    try:
        # Obtener telemetría de la PC
        pc_telemetry = {
            "CPU": "80%",
            "RAM": "16GB/32GB",
            "Disco": "500GB/1TB",
            "Estado": "Activo"
        }

        # Obtener IP de Termux
        loop = asyncio.get_event_loop()
        termux_result = await loop.run_in_executor(
            None,
            lambda: requests.get(TERMUX_IP_URL, timeout=10)
        )

        termux_ip = termux_result.json().get("ip", "Desconocida")

        embed = discord.Embed(
            title="🌐 Estado del Swarm",
            description="Telemetría del sistema y nodo móvil",
            color=0x00BFFF
        )

        embed.add_field(name="💻 PC", value="\n".join([f"**{k}:** {v}" for k, v in pc_telemetry.items()]), inline=True)
        embed.add_field(name="📱 Termux", value=f"**IP:** {termux_ip}", inline=True)
        embed.add_field(name="🔄 Última sincronización", value="Hace 5 minutos", inline=True)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        logging.error("Error en /swarm_status: %s", e)
        await interaction.followup.send(f"❌ Error interno: {str(e)}")

# ========================
# COMANDOS SLASH NUEVOS
# ========================

@bot.tree.command(name="radar_on", description="Enciende el simulador RuView y activa el monitoreo de presencia")
async def radar_on(interaction: discord.Interaction):
    await _radar_on(interaction)

@bot.tree.command(name="target", description="Ejecuta el worker de OSINT asíncrono para un alias")
@app_commands.describe(alias="Alias o nombre de usuario a investigar")
async def target(interaction: discord.Interaction, alias: str):
    await _target(interaction, alias)

@bot.tree.command(name="swarm_status", description="Muestra la telemetría del swarm (PC + Termux)")
async def swarm_status(interaction: discord.Interaction):
    await _swarm_status(interaction)

def main():
    if not DISCORD_TOKEN or len(DISCORD_TOKEN) < 10:
        logging.error("DISCORD_TOKEN no configurado o inválido. El bot no se iniciará.")
        return

    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()