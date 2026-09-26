#!/usr/bin/env python3
"""
NOD_ROLLERCOIN_BOT.py — Bot automatizado para Rollercoin
Maximiza puntos jugando minijuegos 24/7 usando Playwright.
"""

import asyncio
import time
import json
import random
from datetime import datetime, timedelta
from flask import Flask, jsonify
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Configuración
ROLLERCOIN_URL = "https://rollercoin.com"
LOGIN_URL = f"{ROLLERCOIN_URL}/login"
GAMES_URL = f"{ROLLERCOIN_URL}/games"
API_PORT = 5003
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
MAX_RETRIES = 3
RETRY_DELAY = 10  # segundos

# Inicializar Flask
app = Flask(__name__)

# Estado global
state = {
    "status": "stopped",
    "current_game": None,
    "points_earned_last_hour": 0,
    "uptime": "00:00:00",
    "last_restart": None,
    "games_played": 0,
    "errors": 0
}

async def initialize_browser():
    """Inicializa el navegador con configuración optimizada"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--window-size=1280,720",
                f"--user-agent={USER_AGENT}"
            ],
            ignore_default_args=["--enable-automation"]
        )
        return browser

async def login(browser, username, password):
    """Autenticación en Rollercoin con manejo de CAPTCHA/2FA"""
    page = await browser.new_page()
    try:
        # Navegar a login
        await page.goto(LOGIN_URL, timeout=30000)

        # Esperar elementos
        await page.wait_for_selector("#email", timeout=10000)
        await page.wait_for_selector("#password", timeout=10000)

        # Ingresar credenciales
        await page.fill("#email", username)
        await page.fill("#password", password)
        await page.click('button[type="submit"]')  # Botón de login

        # --- NUEVA LÓGICA PARA MANEJO DE CAPTCHA/2FA ---
        # Esperamos a que aparezca el contenedor de Captcha o 2FA
        captcha_detected = False
        twofa_detected = False

        # Esperar hasta 30 segundos para detectar CAPTCHA/2FA
        try:
            # Verificar si hay CAPTCHA (iframe)
            captcha_frame = await page.query_selector("iframe[src*='captcha']")
            if captcha_frame:
                captcha_detected = True
                print("⚠️  CAPTCHA detectado. Por favor resuélvelo manualmente...")
                print("   Abre una pestaña en tu navegador y completa el CAPTCHA.")
                print("   Presiona ENTER cuando hayas completado el CAPTCHA...")

                # Esperar a que el usuario presione ENTER
                input("   Esperando confirmación de CAPTCHA completado...")

            # Verificar si hay 2FA (código de verificación)
            twofa_element = await page.query_selector("#twofa-code")
            if twofa_element:
                twofa_detected = True
                print("⚠️  2FA detectado. Por favor ingresa el código manualmente...")
                print("   Abre una pestaña en tu navegador y completa el código 2FA.")
                print("   Presiona ENTER cuando hayas ingresado el código...")

                # Esperar a que el usuario presione ENTER
                input("   Esperando confirmación de 2FA completado...")

        except Exception as e:
            print(f"⚠️  Error detectando CAPTCHA/2FA: {e}")

        # Verificar si el login fue exitoso
        if await page.url() != LOGIN_URL and "login" not in await page.title():
            print("✅ Login exitoso")
            return page
        else:
            print("❌ Login fallido. Reintentando...")
            return await login(browser, username, password)

    except Exception as e:
        print(f"❌ Error en login: {e}")
        await page.close()
        raise

async def discover_games(page):
    """Descubre todos los juegos disponibles en Rollercoin"""
    try:
        # Navegar a sección de juegos
        await page.goto(GAMES_URL, timeout=30000)

        # Esperar carga de juegos
        await page.wait_for_selector(".game-card", timeout=20000)

        # Extraer juegos
        games = []
        game_elements = await page.query_selector_all(".game-card")
        for element in game_elements:
            name = await element.inner_text()
            href = await element.get_attribute("href")
            if href and "game/" in href:
                games.append({
                    "name": name.strip(),
                    "url": f"{ROLLERCOIN_URL}{href}",
                    "selector": f"a[href*='{href}']"
                })

        print(f"🎮 Descubiertos {len(games)} juegos:")
        for game in games:
            print(f"   - {game['name']} ({game['url']})")

        return games

    except Exception as e:
        print(f"❌ Error descubriendo juegos: {e}")
        raise

async def play_coin_flip_game(page):
    """Juega el juego de la moneda (Coin Flip)"""
    try:
        print(f"💰 Jugando Coin Flip...")
        await page.goto(f"{ROLLERCOIN_URL}/game/coin-flip", timeout=30000)

        # Esperar elementos del juego
        await page.wait_for_selector(".coin-flip-container", timeout=15000)

        # Obtener opciones
        heads_btn = await page.query_selector(".heads")
        tails_btn = await page.query_selector(".tails")

        if not heads_btn or not tails_btn:
            print("⚠️  Elementos del juego no encontrados. Reiniciando...")
            raise Exception("Juego no disponible")

        # Elegir opción aleatoria
        choice = random.choice([heads_btn, tails_btn])
        await choice.click()

        # Esperar resultado (2-5 segundos)
        await asyncio.sleep(random.uniform(2, 5))

        # Verificar si ganó puntos
        points_gained = await page.query_selector(".points-gained")
        if points_gained:
            points = await points_gained.inner_text()
            print(f"🎉 +{points} puntos en Coin Flip")
            return int(points.replace("+", "").strip())

        return 0

    except Exception as e:
        print(f"❌ Error en Coin Flip: {e}")
        raise

async def play_crypto_drop_game(page):
    """Juega el juego de la criptomoneda que cae (Crypto Drop)"""
    try:
        print(f"💎 Jugando Crypto Drop...")
        await page.goto(f"{ROLLERCOIN_URL}/game/crypto-drop", timeout=30000)

        # Esperar elementos del juego
        await page.wait_for_selector(".crypto-drop-container", timeout=15000)

        # Esperar a que aparezca la criptomoneda
        await page.wait_for_selector(".crypto-item", timeout=10000)

        # Hacer clic en la primera criptomoneda visible
        crypto_items = await page.query_selector_all(".crypto-item")
        if crypto_items:
            await crypto_items[0].click()

            # Esperar resultado (1-3 segundos)
            await asyncio.sleep(random.uniform(1, 3))

            # Verificar puntos
            points_gained = await page.query_selector(".points-gained")
            if points_gained:
                points = await points_gained.inner_text()
                print(f"💰 +{points} puntos en Crypto Drop")
                return int(points.replace("+", "").strip())

        return 0

    except Exception as e:
        print(f"❌ Error en Crypto Drop: {e}")
        raise

async def play_rocket_game(page):
    """Juega el juego del cohete (Rocket Launch)"""
    try:
        print(f"🚀 Jugando Rocket Launch...")
        await page.goto(f"{ROLLERCOIN_URL}/game/rocket", timeout=30000)

        # Esperar elementos del juego
        await page.wait_for_selector(".rocket-container", timeout=15000)

        # Esperar a que aparezca el botón de lanzamiento
        launch_btn = await page.query_selector(".launch-btn")
        if not launch_btn:
            print("⚠️  Botón de lanzamiento no encontrado. Reiniciando...")
            raise Exception("Juego no disponible")

        # Hacer clic en lanzar
        await launch_btn.click()

        # Esperar resultado (3-6 segundos)
        await asyncio.sleep(random.uniform(3, 6))

        # Verificar puntos
        points_gained = await page.query_selector(".points-gained")
        if points_gained:
            points = await points_gained.inner_text()
            print(f"🌌 +{points} puntos en Rocket Launch")
            return int(points.replace("+", "").strip())

        return 0

    except Exception as e:
        print(f"❌ Error en Rocket Launch: {e}")
        raise

async def play_clicker_game(page):
    """Juega el juego de clic (Clicker)"""
    try:
        print(f"🖱️ Jugando Clicker...")
        await page.goto(f"{ROLLERCOIN_URL}/game/clicker", timeout=30000)

        # Esperar elementos del juego
        await page.wait_for_selector(".clicker-container", timeout=15000)

        # Obtener el elemento clickeable
        click_target = await page.query_selector(".click-target")
        if not click_target:
            print("⚠️  Objetivo no encontrado. Reiniciando...")
            raise Exception("Juego no disponible")

        # Hacer clics rápidos (10 clics por segundo)
        for _ in range(10):
            await click_target.click()
            await asyncio.sleep(0.1)

        # Esperar resultado (2 segundos)
        await asyncio.sleep(2)

        # Verificar puntos
        points_gained = await page.query_selector(".points-gained")
        if points_gained:
            points = await points_gained.inner_text()
            print(f"💥 +{points} puntos en Clicker")
            return int(points.replace("+", "").strip())

        return 0

    except Exception as e:
        print(f"❌ Error en Clicker: {e}")
        raise

async def play_game(page, game):
    """Juega un juego específico"""
    try:
        # Navegar al juego
        await page.goto(game["url"], timeout=30000)

        # Seleccionar función de juego según el nombre
        game_name = game["name"].lower()

        if "coin flip" in game_name or "moneda" in game_name:
            return await play_coin_flip_game(page)
        elif "crypto drop" in game_name or "criptomoneda" in game_name:
            return await play_crypto_drop_game(page)
        elif "rocket" in game_name or "cohete" in game_name:
            return await play_rocket_game(page)
        elif "clicker" in game_name or "clic" in game_name:
            return await play_clicker_game(page)
        else:
            print(f"⚠️  Juego desconocido: {game['name']}. Saltando...")
            return 0

    except Exception as e:
        print(f"❌ Error jugando {game['name']}: {e}")
        return 0

async def main_loop(browser, username, password, games):
    """Bucle principal del bot"""
    global state
    state["status"] = "running"
    state["last_restart"] = datetime.now().isoformat()
    points_last_hour = 0
    start_time = time.time()

    try:
        # Iniciar sesión
        page = await login(browser, username, password)

        while True:
            try:
                # Seleccionar juego aleatorio
                game = random.choice(games)
                state["current_game"] = game["name"]

                # Jugar el juego
                points = await play_game(page, game)
                points_last_hour += points
                state["games_played"] += 1

                # Actualizar estado cada 5 juegos
                if state["games_played"] % 5 == 0:
                    state["points_earned_last_hour"] = points_last_hour
                    uptime = str(timedelta(seconds=int(time.time() - start_time)))
                    state["uptime"] = uptime

                # Esperar antes de cambiar de juego (1-3 segundos)
                await asyncio.sleep(random.uniform(1, 3))

            except Exception as e:
                print(f"⚠️  Error en juego: {e}. Reiniciando navegador...")
                state["errors"] += 1
                await page.close()
                browser = await initialize_browser()
                page = await login(browser, username, password)
                await asyncio.sleep(RETRY_DELAY)

    except KeyboardInterrupt:
        print("🛑 Deteniendo bot...")
    finally:
        await page.close()
        await browser.close()
        state["status"] = "stopped"

@app.route('/status')
def get_status():
    """Endpoint para consultar el estado del bot"""
    return jsonify(state)

def start_bot(username, password):
    """Inicia el bot en un hilo separado"""
    async def run():
        browser = await initialize_browser()
        games = await discover_games(await login(browser, username, password))
        await main_loop(browser, username, password, games)

    asyncio.run(run())

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Rollercoin Bot")
    parser.add_argument("--username", required=True, help="Usuario de Rollercoin")
    parser.add_argument("--password", required=True, help="Contraseña de Rollercoin")
    args = parser.parse_args()

    print("🚀 Iniciando Rollercoin Bot...")
    print(f"👤 Usuario: {args.username}")
    print(f"🔑 API disponible en http://localhost:{API_PORT}/status")

    # Iniciar bot en segundo plano
    import threading
    bot_thread = threading.Thread(target=start_bot, args=(args.username, args.password))
    bot_thread.daemon = True
    bot_thread.start()

    # Iniciar servidor Flask
    app.run(port=API_PORT, threaded=True)