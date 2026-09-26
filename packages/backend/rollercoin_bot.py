"""
Rollercoin Bot - Automatización autónoma de juegos y recolección de rewards
Juega todos los minijuegos, scrappea página, recolecta automáticamente
"""

import time
import asyncio
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RollercoinBot:
    def __init__(self, email: str, password: str):
        """Inicializar bot con credenciales de Rollercoin"""
        self.email = email
        self.password = password
        self.driver = None
        self.is_running = False
        self.balance = 0
        self.earnings_per_min = 0
        self.games_played = 0
        self.current_goal = None
        self.start_balance = 0
        
        # Stats para notificaciones
        self.stats = {
            "balance": 0,
            "earnings_per_min": 0,
            "games_played": 0,
            "goal_reached": False,
            "uptime_minutes": 0,
            "last_updated": None
        }

    def _init_driver(self):
        """Inicializar webdriver de Chrome headless"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Sin interfaz gráfica
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        logger.info("Chrome driver inicializado")

    def _login(self) -> bool:
        """Login a Rollercoin"""
        try:
            logger.info(f"Intentando login como {self.email}")
            self.driver.get("https://rollercoin.com/login")
            
            wait = WebDriverWait(self.driver, 10)
            
            # Llenar email
            email_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']")))
            email_input.send_keys(self.email)
            
            # Llenar password
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_input.send_keys(self.password)
            
            # Click login
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_btn.click()
            
            # Esperar a que cargue dashboard
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "user-balance")))
            logger.info("Login exitoso")
            return True
            
        except Exception as e:
            logger.error(f"Error en login: {e}")
            return False

    def _parse_page(self) -> dict:
        """Scrapear página para obtener información de juegos y estado"""
        try:
            info = {
                "balance": 0,
                "games_available": [],
                "rewards_available": [],
                "timestamp": datetime.now().isoformat()
            }
            
            # Obtener balance
            try:
                balance_elem = self.driver.find_element(By.CLASS_NAME, "user-balance")
                balance_text = balance_elem.text.replace("$", "").replace(",", "")
                info["balance"] = float(balance_text)
                self.balance = info["balance"]
            except:
                pass
            
            # Obtener lista de juegos disponibles
            try:
                game_elements = self.driver.find_elements(By.CLASS_NAME, "game-card")
                for game_elem in game_elements:
                    try:
                        game_name = game_elem.find_element(By.CLASS_NAME, "game-name").text
                        game_reward = game_elem.find_element(By.CLASS_NAME, "game-reward").text
                        is_playable = "play-btn" in game_elem.get_attribute("class")
                        
                        info["games_available"].append({
                            "name": game_name,
                            "reward": game_reward,
                            "playable": is_playable,
                            "element": game_elem
                        })
                    except:
                        pass
            except:
                pass
            
            # Obtener rewards disponibles para reclamar
            try:
                reward_elements = self.driver.find_elements(By.CLASS_NAME, "claim-reward-btn")
                info["rewards_available"] = [{"type": "daily_bonus"} for _ in reward_elements]
            except:
                pass
            
            logger.info(f"Página parseada: {len(info['games_available'])} juegos, {len(info['rewards_available'])} rewards")
            return info
            
        except Exception as e:
            logger.error(f"Error parseando página: {e}")
            return {"balance": 0, "games_available": [], "rewards_available": []}

    def _claim_rewards(self):
        """Reclamar todos los rewards disponibles"""
        try:
            reward_btns = self.driver.find_elements(By.CLASS_NAME, "claim-reward-btn")
            
            for btn in reward_btns:
                try:
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    logger.info("Reward reclamado")
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error reclamando rewards: {e}")

    def _play_game(self, game_elem) -> bool:
        """Jugar un minijuego específico"""
        try:
            # Click en juego
            self.driver.execute_script("arguments[0].click();", game_elem)
            
            # Esperar a que cargue
            time.sleep(2)
            
            # Buscar botones de juego (varían según juego)
            clickable_elements = self.driver.find_elements(By.CSS_SELECTOR, "button, [role='button']")
            
            # Auto-click en elementos del juego (estrategia: click en todo)
            for elem in clickable_elements[:5]:  # Limitar a 5 clicks por seguridad
                try:
                    if elem.is_displayed() and elem.is_enabled():
                        self.driver.execute_script("arguments[0].click();", elem)
                        time.sleep(0.5)
                except:
                    pass
            
            # Esperar resultado
            time.sleep(1)
            
            # Cerrar juego
            try:
                close_btn = self.driver.find_element(By.CLASS_NAME, "game-close-btn")
                close_btn.click()
            except:
                pass
            
            self.games_played += 1
            logger.info(f"Juego jugado. Total: {self.games_played}")
            return True
            
        except Exception as e:
            logger.error(f"Error jugando: {e}")
            return False

    def _update_stats(self):
        """Actualizar estadísticas del bot"""
        page_info = self._parse_page()
        
        self.stats["balance"] = page_info.get("balance", 0)
        self.stats["games_played"] = self.games_played
        self.stats["last_updated"] = datetime.now().isoformat()
        
        # Calcular earnings por minuto
        if hasattr(self, 'start_time'):
            elapsed_minutes = (time.time() - self.start_time) / 60
            if elapsed_minutes > 0:
                earnings = self.stats["balance"] - self.start_balance
                self.stats["earnings_per_min"] = earnings / elapsed_minutes
        
        # Checkear si alcanzó meta
        if self.current_goal and self.stats["balance"] >= self.current_goal:
            self.stats["goal_reached"] = True
            logger.info(f"🎉 META ALCANZADA: ${self.stats['balance']} >= ${self.current_goal}")

    def start(self, goal: float = None):
        """Iniciar bot"""
        try:
            if self.is_running:
                logger.warning("Bot ya está corriendo")
                return False
            
            self._init_driver()
            
            # Login
            if not self._login():
                return False
            
            self.is_running = True
            self.current_goal = goal
            self.start_balance = self.balance
            self.start_time = time.time()
            
            logger.info(f"Bot iniciado. Meta: ${goal if goal else 'sin límite'}")
            return True
            
        except Exception as e:
            logger.error(f"Error iniciando bot: {e}")
            return False

    async def run_loop(self, play_interval: int = 30, claim_interval: int = 60):
        """Loop principal del bot (async para no bloquear FastAPI)"""
        last_claim = time.time()
        
        while self.is_running:
            try:
                # Reclamar rewards cada claim_interval segundos
                if time.time() - last_claim > claim_interval:
                    self._claim_rewards()
                    last_claim = time.time()
                
                # Parsear página y jugar
                page_info = self._parse_page()
                
                # Jugar todos los juegos disponibles y jugables
                for game in page_info.get("games_available", []):
                    if game.get("playable"):
                        self._play_game(game.get("element"))
                        time.sleep(play_interval)
                        
                        # Actualizar stats
                        self._update_stats()
                        
                        # Checkear meta
                        if self.stats.get("goal_reached"):
                            logger.info("Meta alcanzada. Deteniendo...")
                            self.stop()
                            break
                
                await asyncio.sleep(5)  # Pequeña pausa antes de siguiente ciclo
                
            except Exception as e:
                logger.error(f"Error en loop: {e}")
                await asyncio.sleep(10)

    def stop(self):
        """Detener bot"""
        self.is_running = False
        if self.driver:
            self.driver.quit()
        logger.info("Bot detenido")

    def get_status(self) -> dict:
        """Obtener estado actual del bot"""
        self._update_stats()
        return {
            "running": self.is_running,
            "stats": self.stats,
            "goal": self.current_goal,
            "goal_reached": self.stats.get("goal_reached", False)
        }

    def set_goal(self, amount: float):
        """Establecer meta de dinero"""
        self.current_goal = amount
        logger.info(f"Meta establecida a ${amount}")

    def get_daily_earnings(self) -> float:
        """Obtener ganancias diarias estimadas basadas en earnings por minuto"""
        if hasattr(self, 'start_time') and self.start_time:
            elapsed_minutes = max((time.time() - self.start_time) / 60.0, 1.0)
            earnings_per_min = self.stats.get("earnings_per_min", 0.0)
            if earnings_per_min > 0:
                return earnings_per_min * elapsed_minutes
        return self.stats.get("earnings_per_min", 0.0) * 60.0
