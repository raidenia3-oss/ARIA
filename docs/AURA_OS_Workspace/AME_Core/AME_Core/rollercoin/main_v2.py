import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import warnings

warnings.filterwarnings("ignore")

import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from browser_connector import BrowserConnector
from game_analyzer import GameAnalyzer
from game_player import GamePlayer
from knowledge_base import KnowledgeBase
from rollercoin_knowledge import RollerCoinKnowledge
from actions import RollerCoinActions


class RollerCoinModuleV2:

    def __init__(self):
        self.connector = BrowserConnector()
        self.kb = KnowledgeBase()
        self.rc_knowledge = RollerCoinKnowledge()
        self.analyzer = None
        self.player = None
        self.actions = None
        self.running = False

    async def start(self):
        """Inicio automatico total: Chrome, sesion, bot."""
        print("ROLLERCOIN BOT - INICIO AUTOMATICO TOTAL")

        # Paso 1: Lanzar Chrome automaticamente SIN pedir nada
        await self._launch_chrome_auto()

        # Paso 2: Esperar que Chrome cargue completamente
        print("Esperando que Chrome cargue...")
        await asyncio.sleep(10)

        # Paso 3: Conectar al Chrome que acabamos de abrir
        connected = False
        for intento in range(8):
            print(f"Conectando a Chrome... intento {intento+1}/8")
            connected = await self.connector.connect_to_existing_browser()
            if connected:
                break
            await asyncio.sleep(5)

        if not connected:
            print("ERROR: No se pudo conectar a Chrome")
            print("Verifica que Chrome este instalado")
            return

        page = await self.connector.get_page()

        # Paso 4: Manejar sesion automaticamente
        await self._handle_session(page)

        # Paso 5: Iniciar el bot
        self.analyzer = GameAnalyzer(page, self.kb)
        self.player = GamePlayer(page)
        self.actions = RollerCoinActions(page)

        print("Bot activo - jugando automaticamente...")
        self.running = True
        await self._main_loop()

    async def _launch_chrome_auto(self) -> bool:
        """Busca Chrome instalado y lo lanza con debug port."""
        import subprocess

        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]

        chrome = None
        for path in chrome_paths:
            if os.path.exists(path):
                chrome = path
                break

        if not chrome:
            print("ERROR: Chrome no encontrado en el sistema")
            return False

        user_data = os.path.expandvars(r"%TEMP%\rollercoin_bot_profile")

        # Matar cualquier Chrome con debug port activo primero
        try:
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
            await asyncio.sleep(2)
        except Exception:
            pass

        # Lanzar Chrome nuevo con debug port
        subprocess.Popen(
            [
                chrome,
                "--remote-debugging-port=9222",
                f"--user-data-dir={user_data}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-notifications",
                "--disable-popup-blocking",
                "--start-maximized",
                "https://rollercoin.com/game/games",
            ]
        )

        print(f"Chrome iniciado: {chrome}")
        return True

    async def _handle_session(self, page):
        """Maneja la sesion: carga cookies o hace login con Gmail."""
        import json
        from pathlib import Path

        cookies_file = Path("AME_Core/rollercoin/rc_session.json")

        # Cargar cookies si existen
        if cookies_file.exists():
            try:
                cookies = json.loads(cookies_file.read_text())
                await self.connector.context.add_cookies(cookies)
                await page.reload()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(3)
                print("Sesion restaurada automaticamente")
            except Exception as e:
                print(f"Cookies expiradas: {e}")
                cookies_file.unlink(missing_ok=True)

        # Verificar si hay login
        await page.goto("https://rollercoin.com/game")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

        if "login" in page.url or "sign" in page.url:
            # Intentar login automatico con email
            print("Iniciando sesion automaticamente...")
            await self._auto_login(page, cookies_file)
        else:
            # Ya hay sesion - guardar cookies actualizadas
            cookies = await self.connector.context.cookies()
            cookies_file.write_text(json.dumps(cookies, indent=2))
            print("Sesion activa - cookies guardadas")

        # Ir a juegos
        await page.goto("https://rollercoin.com/game/games")
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)

    async def _auto_login(self, page, cookies_file):
        """Login automatico usando email + codigo desde Gmail."""
        import os, json
        from pathlib import Path

        email = os.environ.get("ROLLERCOIN_EMAIL", "danielhiga2003@gmail.com")

        try:
            # Esperar y escribir email con timeout adecuado para carga dinamica
            email_input = await page.wait_for_selector(
                "input[type='email'], input[name='email'], "
                "input[placeholder*='email'], input[placeholder*='Email']",
                timeout=15000,
                state="visible",
            )
            if email_input:
                await email_input.fill(email)
                await asyncio.sleep(2)

            # Esperar y click en verificar/continuar con reintentos
            for btn_text in ["Click to verify", "CONTINUE WITH EMAIL", "Continue", "Continuar"]:
                try:
                    btn = await page.wait_for_selector(
                        f"button:has-text('{btn_text}')", timeout=5000, state="visible"
                    )
                    if btn:
                        await btn.scroll_into_view_if_needed()
                        await asyncio.sleep(1)
                        await btn.click()
                        await asyncio.sleep(4)
                        break
                except Exception:
                    continue

            # Leer codigo via N8N + Gmail, con fallback directo
            print("Esperando codigo de Gmail...")
            code = await self._get_login_code()

            if code:
                print(f"Codigo recibido: {code}")
                code_input = await page.wait_for_selector(
                    "input[name='code'], "
                    "input[placeholder*='code'], "
                    "input[placeholder*='Code'], "
                    "input[type='number'], "
                    "input[maxlength='6']",
                    timeout=15000,
                    state="visible",
                )
                if code_input:
                    await code_input.fill(code)
                    await asyncio.sleep(1)

                    submit = await page.query_selector(
                        "button:has-text('CONTINUE'), "
                        "button[type='submit'], "
                        "button:has-text('Verify')"
                    )
                    if submit:
                        await submit.click()
                        await asyncio.sleep(4)

                        # Guardar cookies despues del login
                        cookies = await self.connector.context.cookies()
                        cookies_file.write_text(json.dumps(cookies, indent=2))
                        print("Login completado - sesion guardada")
            else:
                print("No se pudo obtener codigo de Gmail automaticamente")
                print("Ingresa el codigo manualmente en el Chrome abierto")
                # Esperar hasta 2 minutos para login manual
                for i in range(24):
                    await asyncio.sleep(5)
                    if "game" in page.url:
                        cookies = await self.connector.context.cookies()
                        cookies_file.write_text(json.dumps(cookies, indent=2))
                        print("Login manual detectado - sesion guardada")
                        break
        except Exception as e:
            print(f"Error en login automatico: {e}")

    async def _get_login_code(self) -> str | None:
        """
        Obtiene el codigo de 6 digitos de RollerCoin.
        Primero intenta via N8N (webhook + EventBus),
        si falla usa Gmail directo como fallback.
        """
        from n8n_login_bridge import (
            notify_n8n_session_expired,
            wait_for_code_from_aura,
        )

        # 1. Notificar a N8N para que lea el codigo via Gmail
        print("[Login] Notificando a N8N...")
        ok = await notify_n8n_session_expired()
        if ok:
            print("[Login] N8N notificado, esperando codigo...")
            codigo = await wait_for_code_from_aura(timeout=120)
            if codigo:
                return codigo
            print("[Login] Timeout esperando codigo de N8N, usando fallback...")
        else:
            print("[Login] N8N no disponible, usando fallback directo...")

        # 3. Fallback: leer Gmail directamente
        return await self._get_gmail_code()

    async def _get_gmail_code(self) -> str | None:
        """Lee el codigo de 6 digitos desde el correo de RollerCoin en Gmail."""
        import os, imaplib, email as email_lib, re

        gmail_email = os.environ.get("ROLLERCOIN_EMAIL", "danielhiga2003@gmail.com")
        gmail_pass = os.environ.get("GMAIL_APP_PASSWORD", "")

        if not gmail_pass:
            print("GMAIL_APP_PASSWORD no configurado en .env")
            print("Para login 100% automatico, anade al .env:")
            print("GMAIL_APP_PASSWORD=tu_contraseña_de_app_gmail")
            print("Obtenerla en: myaccount.google.com/apppasswords")
            return None

        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com")
            mail.login(gmail_email, gmail_pass)

            # Esperar hasta 2 minutos por el email
            for intento in range(24):
                mail.select("INBOX")
                _, msgs = mail.search(None, '(FROM "rollercoin" UNSEEN)')
                if msgs[0]:
                    msg_ids = msgs[0].split()
                    _, data = mail.fetch(msg_ids[-1], "(RFC822)")
                    msg = email_lib.message_from_bytes(data[0][1])

                    # Extraer body
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body += part.get_payload(decode=True).decode(
                                    "utf-8", errors="ignore"
                                )
                    else:
                        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

                    # Buscar codigo de 6 digitos
                    match = re.search(r"\b(\d{6})\b", body)
                    if match:
                        mail.logout()
                        return match.group(1)

                print(f"Esperando email... {intento+1}/24")
                await asyncio.sleep(5)

            mail.logout()
            return None
        except Exception as e:
            print(f"Error Gmail: {e}")
            return None

    async def _main_loop(self):
        """Bucle principal del bot."""
        session_games = 0
        start_time = datetime.now()

        while self.running:
            try:
                state = await self.analyzer.analyze_full_state()
                action = self.rc_knowledge.get_priority_action(state)

                print(f"\n[P{action['priority']}] {action['reason']}")

                if action["action"] == "reload_battery":
                    await self.actions.reload_battery()

                elif action["action"] == "claim_quests":
                    n = await self.actions.claim_quests(action.get("quests", []))
                    print(f"  {n} quests reclamadas")

                elif action["action"] == "play_game":
                    game = action["game"]
                    strategy = action.get("strategy", {})
                    tips = strategy.get("tips", [])
                    if tips:
                        print(f"  Tip: {tips[0]}")
                    result = await self.player.play_game(game)
                    session_games += 1
                    self.kb.record_game_result(
                        game_name=game["name"],
                        strategy=strategy.get("strategy", "generic"),
                        success=result.get("success", False),
                        hashrate_gained=result.get("hashrate_gained", "?"),
                        cooldown_after=0,
                    )

                elif action["action"] == "wait":
                    secs = min(action.get("seconds", 60), 300)
                    elapsed = (datetime.now() - start_time).seconds
                    if elapsed > 0 and elapsed % 1800 < 10:
                        print(f"\n RESUMEN ({elapsed//60}min):")
                        print(f"   Juegos: {session_games}")
                    print(f"  Esperando {secs}s...")
                    await asyncio.sleep(secs)

                await asyncio.sleep(2)

            except KeyboardInterrupt:
                print("\n Detenido por el usuario")
                self.running = False
            except Exception as e:
                print(f" Error: {e}")
                await asyncio.sleep(30)

        await self.connector.close()
        print(f"\n Sesion terminada. Juegos: {session_games}")


async def main():
    """Punto de entrada del RollerCoin bot."""
    if sys.platform == "win32":
        import io

        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, errors="replace")
    module = RollerCoinModuleV2()
    await module.start()


if __name__ == "__main__":
    asyncio.run(main())
