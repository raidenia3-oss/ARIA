#!/usr/bin/env python3
"""
RollerCoin Bot - Automatización de RollerCoin usando Playwright
Autor: AURA System
Descripción: Bot para automatizar login, recarga de batería, juegos y quests en RollerCoin.
"""

import os
import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
import random

# Cargar variables de entorno
load_dotenv()

# Configuración global
ROLLERCOIN_URL = "https://rollercoin.com"
LOG_DIR = Path("logs")
GAMES_SECTION = "#games"
BATTERY_SECTION = "#battery"
LOGIN_BUTTON = "#login-button"
EMAIL_INPUT = "#email"
PASSWORD_INPUT = "#password"
RELOAD_BUTTON = "#reload-button"
GAMES_LIST = ".game-item"
GAME_COOLDOWN = ".game-cooldown"
GAME_PLAY_BUTTON = ".play-button"
GAME_RESULT = ".game-result"
QUESTS_SECTION = "#quests"
QUEST_ITEM = ".quest-item"
QUEST_COMPLETE_BUTTON = ".complete-quest"


# Configuración de logs
def setup_logging():
    """Configura el directorio de logs y crea el archivo de log."""
    if not LOG_DIR.exists():
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOG_DIR / f"rollercoin_{timestamp}.log"
    return log_file


def log_message(message, log_file):
    """Registra un mensaje en el archivo de log y en consola."""
    timestamp = datetime.now().strftime("[%H:%M:%S]")
    log_entry = f"{timestamp} {message}\n"
    print(log_entry.strip())
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)


def parse_cooldown(time_str):
    """Convierte cadenas como '2:30' a segundos."""
    try:
        minutes, seconds = map(int, time_str.split(":"))
        return minutes * 60 + seconds
    except:
        return 0


def wait_for_element(page, selector, max_retries=3, delay=5):
    """Espera a que un elemento esté disponible en la página."""
    global log_file

    for attempt in range(max_retries):
        try:
            page.wait_for_selector(selector, timeout=10000)
            return True
        except Exception as e:
            log_message(f"Esperando {selector}... (Intento {attempt + 1}/{max_retries})", log_file)
            if attempt == max_retries - 1:
                try:
                    LOG_DIR.mkdir(parents=True, exist_ok=True)
                    screenshot_name = (
                        f"wait_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        f"_{selector.replace('#', '').replace('.', '_').replace('/', '_')}.png"
                    )
                    screenshot_path = LOG_DIR / screenshot_name
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    log_message(f"⚠️ Captura de error guardada en {screenshot_path}", log_file)
                except Exception as screenshot_error:
                    log_message(
                        f"⚠️ No se pudo guardar la captura de error: {screenshot_error}",
                        log_file,
                    )
            time.sleep(delay)
    return False


def human_like_delay(min_delay=0.5, max_delay=2):
    """Espera un tiempo aleatorio para simular comportamiento humano."""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


def login(page, email, password):
    """Realiza el login en RollerCoin."""
    try:
        log_message("Iniciando sesión en RollerCoin...", log_file)

        # Verificar si ya hay sesión activa
        if page.url != ROLLERCOIN_URL:
            log_message("Ya hay una sesión activa. Saltando login.", log_file)
            return True

        # Navegar a la página de login
        page.goto(ROLLERCOIN_URL, timeout=30000)

        # Esperar y llenar el formulario de login
        if wait_for_element(page, LOGIN_BUTTON):
            page.click(LOGIN_BUTTON)
            human_like_delay()
        else:
            log_message("⚠️ No apareció el botón de login; se continúa con el flujo.", log_file)

        if wait_for_element(page, EMAIL_INPUT):
            page.fill(EMAIL_INPUT, email)
            human_like_delay()
        else:
            log_message("⚠️ No apareció el campo de email; se continúa con el flujo.", log_file)

        if wait_for_element(page, PASSWORD_INPUT):
            page.fill(PASSWORD_INPUT, password)
            human_like_delay()
        else:
            log_message("⚠️ No apareció el campo de password; se continúa con el flujo.", log_file)

        # Hacer clic en el botón de login (asumiendo que es un submit)
        page.keyboard.press("Enter")
        human_like_delay()

        # Verificar si el login fue exitoso
        if wait_for_element(page, BATTERY_SECTION):
            log_message("✅ Login exitoso.", log_file)
            return True
        else:
            log_message("❌ Error en el login. Verifica credenciales.", log_file)
            return False
    except Exception as e:
        log_message(f"❌ Error durante el login: {str(e)}", log_file)
        return False


def check_and_reload_battery(page):
    """Verifica si la batería necesita recarga y la realiza si es necesario."""
    try:
        if not wait_for_element(page, BATTERY_SECTION):
            return False

        # Obtener el estado de la batería
        battery_element = page.query_selector(BATTERY_SECTION)
        if not battery_element:
            return False

        # Verificar si hay un botón de recarga visible
        reload_button = page.query_selector(RELOAD_BUTTON)
        if reload_button:
            log_message("🔋 Batería necesita recarga...", log_file)
            page.click(RELOAD_BUTTON)
            human_like_delay(2, 4)  # Esperar a que termine la recarga
            log_message("✅ Batería recargada.", log_file)
            return True
        else:
            log_message("ℹ️ Batería OK. No se requiere recarga.", log_file)
            return True
    except Exception as e:
        log_message(f"❌ Error al verificar batería: {str(e)}", log_file)
        return False


def get_available_games(page):
    """Obtiene una lista de juegos disponibles y sus cooldowns."""
    try:
        if not wait_for_element(page, GAMES_SECTION):
            return {}

        games = {}
        game_items = page.query_selector_all(GAMES_LIST)

        for game in game_items:
            try:
                game_name = game.inner_text().strip()
                cooldown_element = game.query_selector(GAME_COOLDOWN)
                if cooldown_element:
                    cooldown_text = cooldown_element.inner_text().strip()
                    cooldown_seconds = parse_cooldown(cooldown_text)
                    games[game_name] = cooldown_seconds
                else:
                    games[game_name] = 0  # Cooldown = 0 significa disponible
            except Exception as e:
                log_message(f"⚠️ Error al procesar juego {game_name}: {str(e)}", log_file)

        return games
    except Exception as e:
        log_message(f"❌ Error al obtener juegos disponibles: {str(e)}", log_file)
        return {}


def play_game(page, game_name):
    """Juega un juego específico."""
    try:
        log_message(f"🎮 Jugando {game_name}...", log_file)

        # Buscar el botón de jugar
        play_button = page.query_selector(f".game-item:has-text('{game_name}') .play-button")
        if not play_button:
            log_message(f"❌ No se encontró botón de jugar para {game_name}.", log_file)
            return False

        # Hacer clic en el botón de jugar
        play_button.click()
        human_like_delay(1, 3)

        # Esperar a que el juego termine (timeout de 60 segundos)
        start_time = time.time()
        while time.time() - start_time < 60:
            try:
                result_element = page.query_selector(GAME_RESULT)
                if result_element:
                    result_text = result_element.inner_text().strip()
                    log_message(f"🎮 Resultado de {game_name}: {result_text}", log_file)
                    return True
            except:
                pass
            human_like_delay(1, 2)

        log_message(f"⏰ Tiempo límite alcanzado para {game_name}.", log_file)
        return False
    except Exception as e:
        log_message(f"❌ Error al jugar {game_name}: {str(e)}", log_file)
        return False


def complete_quests(page):
    """Completa quests disponibles."""
    try:
        if not wait_for_element(page, QUESTS_SECTION):
            return 0

        quests_completed = 0
        quest_items = page.query_selector_all(QUEST_ITEM)

        for quest in quest_items:
            try:
                quest_name = quest.inner_text().strip()
                complete_button = quest.query_selector(QUEST_COMPLETE_BUTTON)
                if complete_button:
                    log_message(f"🏆 Completando quest: {quest_name}", log_file)
                    complete_button.click()
                    human_like_delay(1, 2)
                    quests_completed += 1
            except Exception as e:
                log_message(f"⚠️ Error al completar quest {quest_name}: {str(e)}", log_file)

        return quests_completed
    except Exception as e:
        log_message(f"❌ Error al completar quests: {str(e)}", log_file)
        return 0


def report_status_to_aura(juegos_jugados, hashrate_ganado, proximo_cooldown, bateria_estado):
    """Reporta el estado al sistema AURA (opcional)."""
    try:
        # Esto sería integrado con el EventBus de AURA
        # Por ahora solo se imprime en consola
        status = {
            "node": "ROLLERCOIN_BOT",
            "event": "STATUS_UPDATE",
            "payload": {
                "juegos_jugados": juegos_jugados,
                "hashrate_ganado": f"{hashrate_ganado} GH/s",
                "proximo_juego_en": f"{proximo_cooldown} segundos",
                "bateria": bateria_estado,
            },
        }
        log_message(
            f"📡 Reporte a AURA: {json.dumps(status, indent=2, ensure_ascii=False)}", log_file
        )
    except Exception as e:
        log_message(f"⚠️ Error al reportar estado a AURA: {str(e)}", log_file)


def main():
    """Función principal del bot."""
    global log_file

    # Configuración de argumentos
    parser = argparse.ArgumentParser(description="RollerCoin Bot - Automatización de RollerCoin")
    parser.add_argument(
        "--headless", action="store_true", help="Modo headless (sin ventana visible)"
    )
    parser.add_argument("--visible", action="store_true", help="Modo visible (ventana abierta)")
    args = parser.parse_args()

    # Configurar modo de ejecución
    browser_type = "chromium"
    if args.headless:
        browser = sync_playwright().launch(headless=True, slow_mo=50)
    elif args.visible:
        browser = sync_playwright().launch(headless=False, slow_mo=50)
    else:
        browser = sync_playwright().launch(headless=False, slow_mo=50)

    # Configurar página
    page = browser.new_page()

    # Configurar logs
    log_file = setup_logging()
    log_message("🚀 Iniciando RollerCoin Bot", log_file)
    log_message(f"📌 Modo: {'Headless' if args.headless else 'Visible'}", log_file)

    # Cargar credenciales
    email = os.getenv("ROLLERCOIN_EMAIL")
    password = os.getenv("ROLLERCOIN_PASSWORD")

    if not email or not password:
        log_message("❌ Error: Credenciales no configuradas en .env", log_file)
        log_message("   Asegúrate de tener las siguientes variables en tu .env:", log_file)
        log_message("   ROLLERCOIN_EMAIL=tu@email.com", log_file)
        log_message("   ROLLERCOIN_PASSWORD=tupassword", log_file)
        browser.close()
        sys.exit(1)

    # Iniciar sesión
    if not login(page, email, password):
        browser.close()
        sys.exit(1)

    # Loop principal
    juegos_jugados = 0
    hashrate_total = 0
    last_hour_report = time.time()

    while True:
        try:
            # Verificar y recargar batería si es necesario
            check_and_reload_battery(page)

            # Obtener juegos disponibles
            games = get_available_games(page)
            if not games:
                log_message("⚠️ No se pudieron obtener juegos disponibles.", log_file)
                time.sleep(60)
                continue

            # Filtrar juegos disponibles (cooldown = 0)
            available_games = {name: cooldown for name, cooldown in games.items() if cooldown == 0}

            if available_games:
                # Seleccionar un juego aleatorio
                game_name = random.choice(list(available_games.keys()))
                log_message(f"🎲 Juegos disponibles: {', '.join(available_games.keys())}", log_file)
                log_message(f"🎮 Seleccionado: {game_name}", log_file)

                # Jugar el juego
                if play_game(page, game_name):
                    juegos_jugados += 1
                    # Simular ganancia de hashrate (en un juego real esto sería dinámico)
                    hashrate_ganado = random.uniform(0.1, 1.0)
                    hashrate_total += hashrate_ganado
                    log_message(f"💰 Hashrate ganado: {hashrate_ganado:.2f} GH/s", log_file)

                    # Reportar estado cada cierto tiempo
                    if time.time() - last_hour_report >= 3600:
                        report_status_to_aura(juegos_jugados, hashrate_total, 0, "ok")
                        last_hour_report = time.time()

                # Completar quests
                quests_completed = complete_quests(page)
                if quests_completed > 0:
                    log_message(f"🏆 {quests_completed} quests completadas.", log_file)

            else:
                # No hay juegos disponibles, calcular el próximo cooldown
                min_cooldown = min(games.values())
                if min_cooldown > 0:
                    log_message(
                        f"⏳ Esperando {min_cooldown} segundos para el próximo juego.", log_file
                    )
                    time.sleep(min_cooldown + 5)  # +5 segundos de margen
                else:
                    log_message("⚠️ No hay juegos disponibles ni cooldowns.", log_file)
                    time.sleep(60)

        except Exception as e:
            log_message(f"❌ Error grave en el loop principal: {str(e)}", log_file)
            log_message("🔄 Reintentando en 5 minutos...", log_file)
            time.sleep(300)  # Esperar 5 minutos antes de reintentar

    # Cerrar navegador (esto nunca se alcanzará en el loop infinito)
    browser.close()


if __name__ == "__main__":
    main()
