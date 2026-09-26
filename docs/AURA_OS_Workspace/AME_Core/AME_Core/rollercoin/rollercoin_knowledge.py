"""
Módulo RollerCoin para AURA
Todo lo que el módulo sabe sobre RollerCoin.
Base de conocimiento estática + dinámica.
"""


class RollerCoinKnowledge:
    """
    Conocimiento completo de RollerCoin.
    El módulo usa esto para tomar decisiones inteligentes.
    """

    # ── JUEGOS CONOCIDOS Y SUS CARACTERÍSTICAS ──────────
    KNOWN_GAMES = {
        "Token Blaster": {
            "type": "shooter",
            "strategy": "clicker",
            "difficulty": "easy",
            "description": "Dispara tokens cayendo",
            "tips": [
                "Hacer click rápido en los tokens",
                "Priorizar tokens de colores especiales",
                "Moverse con flechas izquierda/derecha",
            ],
        },
        "Coin-Match": {
            "type": "puzzle",
            "strategy": "memory",
            "difficulty": "medium",
            "description": "Combinar monedas iguales",
            "tips": [
                "Recordar posiciones de cartas reveladas",
                "Hacer pares lo más rápido posible",
            ],
        },
        "Dr. Hamster": {
            "type": "runner",
            "strategy": "runner",
            "difficulty": "medium",
            "description": "Hamster corriendo, evitar obstáculos",
            "tips": ["Saltar con Space o ArrowUp", "Ritmo constante de saltos"],
        },
        "Mining Fever": {
            "type": "clicker",
            "strategy": "clicker",
            "difficulty": "easy",
            "description": "Click para minar bloques",
            "tips": ["Click continuo en bloques", "Priorizar bloques dorados"],
        },
        "CryptoStar": {
            "type": "arcade",
            "strategy": "clicker",
            "difficulty": "medium",
            "description": "Recolectar estrellas crypto",
            "tips": ["Moverse con flechas", "Evitar obstáculos rojos"],
        },
    }

    # ── SISTEMA DE COOLDOWNS ─────────────────────────────
    COOLDOWN_SYSTEM = {
        "description": (
            "El cooldown aumenta con cada juego jugado en 24h. "
            "Rotar entre juegos minimiza el tiempo de espera."
        ),
        "approximate_cooldowns": {
            1: "30 segundos",
            2: "1 minuto",
            3: "2 minutos",
            5: "5 minutos",
            10: "10 minutos",
            20: "20 minutos",
        },
        "strategy": (
            "Jugar todos los juegos disponibles en rotación " "para maximizar juegos por hora"
        ),
    }

    # ── SISTEMA DE HASHRATE ──────────────────────────────
    HASHRATE_SYSTEM = {
        "description": (
            "El hashrate determina cuánta crypto minas. "
            "Los juegos dan hashrate temporal (12h), "
            "los miners dan hashrate permanente."
        ),
        "progression": {
            "level_1": "Hashrate básico de juegos",
            "level_2": "Comprar miners con RLT",
            "level_3": "Mejorar PC level para más duración",
            "level_4": "Crafting de miners avanzados",
        },
        "pc_levels": {
            1: "Hashrate de juegos dura 1 hora",
            2: "Hashrate de juegos dura 3 horas",
            3: "Hashrate de juegos dura 6 horas",
            4: "Hashrate de juegos dura 12 horas",
        },
    }

    # ── PRIORIDADES ESTRATÉGICAS ─────────────────────────
    PRIORITIES = [
        {
            "orden": 1,
            "accion": "Recargar batería diaria",
            "razon": "Sin batería los miners no generan hashrate",
            "cuando": "Una vez al día, al iniciar sesión",
        },
        {
            "orden": 2,
            "accion": "Reclamar quests completadas",
            "razon": "RLT gratis sin hacer nada extra",
            "cuando": "Siempre que estén disponibles",
        },
        {
            "orden": 3,
            "accion": "Jugar todos los juegos disponibles",
            "razon": "Cada juego da hashrate temporal",
            "cuando": "Cuando el cooldown llegue a 0",
        },
        {
            "orden": 4,
            "accion": "Rotar entre juegos en cooldown",
            "razon": "Minimizar tiempo de espera total",
            "cuando": "Mientras esperamos cooldowns",
        },
        {
            "orden": 5,
            "accion": "Revisar eventos activos",
            "razon": "Eventos dan recompensas extra",
            "cuando": "Al iniciar sesión",
        },
        {
            "orden": 6,
            "accion": "Comprar miners con RLT acumulado",
            "razon": "Hashrate pasivo permanente",
            "cuando": "Cuando haya suficiente RLT",
        },
    ]

    # ── SELECTORES CSS DE ROLLERCOIN ─────────────────────
    # Selectores conocidos de la UI (actualizar si cambian)
    SELECTORS = {
        "battery_reload": [
            "button:has-text('Reload')",
            "button:has-text('Recharge')",
            "[class*='battery'] button",
            "[data-testid='reload-battery']",
        ],
        "game_cards": [
            "[class*='game-card']",
            "[class*='mini-game']",
            "[class*='game-item']",
            ".games-list > div",
        ],
        "play_button": ["button:has-text('Play')", "a:has-text('Play')", "button:has-text('PLAY')"],
        "cooldown_timer": [
            "[class*='timer']",
            "[class*='cooldown']",
            "[class*='countdown']",
            "span:has-text(':')",
        ],
        "hashrate_display": [
            "[class*='hashrate']",
            "[class*='mining-power']",
            "[class*='power-value']",
        ],
        "rlt_balance": [
            "[class*='rlt-balance']",
            "[class*='token-balance']",
            "[class*='balance']:has-text('RLT')",
        ],
        "quest_claim": [
            "button:has-text('Claim')",
            "button:has-text('Collect')",
            "button:has-text('Complete')",
        ],
    }

    def get_strategy_for_game(self, game_name: str) -> dict:
        """Retorna la estrategia conocida para un juego"""
        # Buscar coincidencia parcial
        for known, info in self.KNOWN_GAMES.items():
            if known.lower() in game_name.lower() or game_name.lower() in known.lower():
                return info
        # Juego desconocido — estrategia genérica
        return {
            "type": "unknown",
            "strategy": "generic",
            "tips": ["Explorar clicks en el canvas", "Probar teclas Space y flechas"],
        }

    def get_priority_action(self, state: dict) -> dict:
        """
        Decide la accion de mayor prioridad segun el estado.
        Bateria: solo recargar si hay boton visible Y habilitado.
        Si el boton no existe o esta disabled = bateria llena.
        """
        # Prioridad 1: bateria
        battery = state.get("battery", {})
        # El analizador devuelve dict con needs_reload + button_enabled
        needs_reload = (
            isinstance(battery, dict)
            and battery.get("needs_reload", False)
            and battery.get("button_enabled", False)
        )
        if needs_reload:
            return {
                "action": "reload_battery",
                "priority": 1,
                "reason": "Bateria baja — boton de recarga disponible",
            }

        # Prioridad 2: quests
        claimable_quests = [q for q in state.get("quests", []) if q.get("claimable")]
        if claimable_quests:
            return {
                "action": "claim_quests",
                "priority": 2,
                "reason": f"{len(claimable_quests)} quests con recompensa",
                "quests": claimable_quests,
            }

        # Prioridad 3: jugar juego disponible
        available = [
            g for g in state.get("games", []) if g.get("playable") and g["cooldown_sec"] == 0
        ]
        if available:
            # Elegir el juego con estrategia conocida primero
            for game in available:
                info = self.get_strategy_for_game(game["name"])
                if info["strategy"] != "generic":
                    return {
                        "action": "play_game",
                        "priority": 3,
                        "game": game,
                        "strategy": info,
                        "reason": f"Jugar {game['name']} " f"({info['strategy']})",
                    }
            # Si todos son genéricos, jugar el primero
            return {
                "action": "play_game",
                "priority": 3,
                "game": available[0],
                "strategy": self.get_strategy_for_game(available[0]["name"]),
                "reason": f"Jugar {available[0]['name']}",
            }

        # Prioridad 4: esperar
        all_games = state.get("games", [])
        if all_games:
            next_ready = min(
                (g["cooldown_sec"] for g in all_games if g["cooldown_sec"] > 0), default=300
            )
            return {
                "action": "wait",
                "priority": 4,
                "seconds": next_ready + 3,
                "reason": f"Próximo juego en {next_ready}s",
            }

        return {"action": "wait", "priority": 4, "seconds": 60, "reason": "Analizando estado..."}
