"""
Endpoints FastAPI para Rollercoin Bot
Agregár estos endpoints al backend/main.py
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
from backend.rollercoin_bot import RollercoinBot

router = APIRouter(prefix="/api/rollercoin", tags=["rollercoin"])

# Instancia global del bot
rollercoin_bot = None
bot_task = None


class RollercoinLogin(BaseModel):
    email: str
    password: str


class RollercoinGoal(BaseModel):
    amount: float


@router.post("/login")
async def rollercoin_login(credentials: RollercoinLogin):
    """
    Iniciar sesión en Rollercoin
    
    ```json
    {
        "email": "tu_email@gmail.com",
        "password": "tu_password"
    }
    ```
    """
    global rollercoin_bot
    
    try:
        if rollercoin_bot and rollercoin_bot.is_running:
            raise HTTPException(status_code=400, detail="Bot ya está corriendo")
        
        rollercoin_bot = RollercoinBot(credentials.email, credentials.password)
        
        # Iniciar bot
        if not rollercoin_bot.start():
            raise HTTPException(status_code=401, detail="Login fallido")
        
        return {
            "status": "logged_in",
            "email": credentials.email,
            "bot_running": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def rollercoin_start(goal: RollercoinGoal = None):
    """
    Iniciar bot autónomo
    
    ```json
    {
        "amount": 100.50
    }
    ```
    
    El bot jugará minijuegos hasta alcanzar la meta
    """
    global rollercoin_bot, bot_task
    
    if not rollercoin_bot:
        raise HTTPException(status_code=400, detail="No hay sesión. Ejecuta /login primero")
    
    if rollercoin_bot.is_running:
        raise HTTPException(status_code=400, detail="Bot ya está corriendo")
    
    try:
        goal_amount = goal.amount if goal else None
        rollercoin_bot.start(goal=goal_amount)
        
        # Crear tarea async para el loop
        bot_task = asyncio.create_task(rollercoin_bot.run_loop())
        
        return {
            "status": "started",
            "goal": goal_amount,
            "message": f"Bot iniciado. Meta: ${goal_amount if goal_amount else 'sin límite'}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def rollercoin_stop():
    """Detener bot"""
    global rollercoin_bot, bot_task
    
    if not rollercoin_bot:
        raise HTTPException(status_code=400, detail="No hay bot corriendo")
    
    try:
        rollercoin_bot.stop()
        
        if bot_task:
            bot_task.cancel()
        
        return {
            "status": "stopped",
            "final_stats": rollercoin_bot.stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def rollercoin_status():
    """
    Obtener estado actual del bot
    Retorna: balance, earnings/min, juegos jugados, meta alcanzada
    """
    if not rollercoin_bot:
        return {
            "running": False,
            "message": "No hay bot activo"
        }
    
    try:
        status = rollercoin_bot.get_status()
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set_goal")
async def rollercoin_set_goal(goal: RollercoinGoal):
    """
    Cambiar meta durante la ejecución
    
    ```json
    {
        "amount": 250.75
    }
    ```
    """
    if not rollercoin_bot:
        raise HTTPException(status_code=400, detail="No hay bot corriendo")
    
    try:
        rollercoin_bot.set_goal(goal.amount)
        
        return {
            "status": "goal_updated",
            "new_goal": goal.amount,
            "current_balance": rollercoin_bot.balance
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def rollercoin_stats():
    """
    Obtener estadísticas detalladas
    Incluye: balance, earnings/min, juegos jugados, tiempo activo
    """
    if not rollercoin_bot:
        return {"error": "No hay bot activo"}
    
    try:
        return {
            "balance": rollercoin_bot.balance,
            "earnings_per_min": rollercoin_bot.stats.get("earnings_per_min", 0),
            "games_played": rollercoin_bot.games_played,
            "uptime": rollercoin_bot.stats.get("uptime_minutes", 0),
            "goal": rollercoin_bot.current_goal,
            "goal_reached": rollercoin_bot.stats.get("goal_reached", False),
            "last_updated": rollercoin_bot.stats.get("last_updated")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/claim_rewards")
async def rollercoin_claim_rewards():
    """Reclamar todos los rewards disponibles manualmente"""
    if not rollercoin_bot:
        raise HTTPException(status_code=400, detail="No hay bot corriendo")
    
    try:
        rollercoin_bot._claim_rewards()
        
        return {
            "status": "claimed",
            "message": "Rewards reclamados"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint de webhook para notificaciones
notifications_webhooks = []


@router.post("/webhook/goal_reached")
async def add_webhook(url: str):
    """
    Agregar webhook para recibir notificación cuando se alcance la meta
    Se enviará POST a la URL con los stats
    """
    notifications_webhooks.append(url)
    
    return {
        "status": "webhook_added",
        "url": url,
        "message": "Recibirás notificación POST cuando se alcance la meta"
    }
