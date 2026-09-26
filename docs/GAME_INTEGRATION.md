# AURA/AME - Integración con Mini-Juegos (Godot)

## Introducción

Este documento describe cómo integrar mini-juegos desarrollados en Godot con el ecosistema AURA/AME. La integración permitirá a los usuarios ganar experiencia (EXP) y recompensas al completar juegos, mejorando la experiencia de usuario y fomentando la interacción con la plataforma.

---

## Arquitectura de Integración

### 1. Componentes Principales

- **AURA/AME Frontend**: Interfaz de usuario principal.
- **Godot Engine**: Motor de juegos para crear mini-juegos.
- **Backend AURA**: Sistema de recompensas y gestión de EXP.
- **WebSocket**: Comunicación en tiempo real entre el frontend y el backend.

### 2. Flujo de Datos

```
[Usuario] → (Frontend AURA) → [WebSocket] → (Backend AURA) ↔ [Godot Game]
```

---

## Configuración Inicial

### 1. Requisitos Previos

- Godot Engine 4.x instalado.
- Proyecto Godot configurado para exportar a HTML5.
- Cuenta de desarrollador en Vercel/Netlify para desplegar juegos.
- Acceso a la API de AURA/AME para gestionar recompensas.

### 2. Configuración del Proyecto Godot

```gdscript
# Ejemplo de configuración en Godot para exportar a HTML5
export(ExportPreset) preset = "HTML5"

func _ready():
    # Conectar con el backend de AURA/AME
    var ws_url = "wss://aura-backend.example.com/ws/game"
    var websocket = WebSocket.new()
    websocket.connect_to_host(ws_url)
    websocket.connect("connected", self, "_on_websocket_connected")
    websocket.connect("data_received", self, "_on_websocket_data_received")
    add_child(websocket)
```

---

## Sistema de Recompensas

### 1. Tipos de Recompensas

| Tipo        | Descripción                                      | Valor Base |
| ----------- | ------------------------------------------------ | ---------- |
| EXP         | Puntos de experiencia para subir de nivel.       | 10-100     |
| Monedas     | Monedas virtuales para compras dentro de la app. | 5-50       |
| Badges      | Insignias por logros específicos.                | -          |
| Desbloqueos | Acceso a contenido exclusivo.                    | -          |

### 2. Estructura de Datos para Recompensas

```json
{
  "game_id": "platformer_level_1",
  "user_id": "user_12345",
  "event": "level_complete",
  "reward": {
    "exp": 50,
    "coins": 20,
    "badge": "speedrunner"
  },
  "metadata": {
    "time_taken": 45.2,
    "score": 9800
  }
}
```

---

## Integración Técnica

### 1. Conexión entre Godot y AURA/AME

#### a. WebSocket en Godot

```gdscript
func _on_websocket_connected():
    print("Conectado al servidor de AURA/AME")

func _on_websocket_data_received(data):
    var json_data = JSON.parse_string(data.get_string_from_utf8())
    if json_data["type"] == "reward":
        _handle_reward(json_data["reward"])

func _handle_reward(reward):
    # Mostrar notificación al usuario
    var notification = Notification.new()
    notification.text = "¡Felicidades! Has ganado: " + str(reward["exp"]) + " EXP y " + str(reward["coins"]) + " monedas."
    add_child(notification)
```

#### b. Envío de Eventos desde Godot

```gdscript
func _on_level_complete():
    var event_data = {
        "game_id": "platformer_level_1",
        "user_id": "user_12345",
        "event": "level_complete",
        "metadata": {
            "time_taken": get_tree().get_time_since_start(),
            "score": calculate_score()
        }
    }
    websocket.put_data(JSON.stringify(event_data).get_utf8())
```

---

### 2. Backend de AURA/AME

#### a. Endpoint para Recompensas

```python
# Ejemplo en FastAPI (backend de AURA)
@app.websocket("/ws/game")
async def websocket_game(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        event_data = json.loads(data)

        # Procesar evento y calcular recompensas
        reward = calculate_reward(event_data)

        # Enviar respuesta al cliente
        await websocket.send_text(json.dumps({
            "type": "reward",
            "reward": reward
        }))
```

#### b. Función para Calcular Recompensas

```python
def calculate_reward(event_data):
    exp = 0
    coins = 0

    if event_data["event"] == "level_complete":
        exp = 50 + (100 - event_data["metadata"]["time_taken"])  # Más EXP por completar rápido
        coins = 20

    return {
        "exp": exp,
        "coins": coins,
        "badge": "speedrunner" if event_data["metadata"]["time_taken"] < 30 else None
    }
```

---

## Despliegue de Mini-Juegos

### 1. Exportar desde Godot

1. Ve a **Export** en Godot.
2. Selecciona **HTML5** como plataforma.
3. Configura el preset para exportar a una carpeta local.
4. Ejecuta la exportación.

### 2. Desplegar en Vercel/Netlify

1. Sube la carpeta exportada a un repositorio de GitHub.
2. Configura un proyecto en Vercel/Netlify que apunte a esa carpeta.
3. Despliega el juego y obtén la URL pública.

### 3. Integración con AURA/AME

1. Actualiza la configuración del juego en Godot para que apunte a la URL del WebSocket de AURA/AME.
2. Prueba la conexión y asegúrate de que los eventos se envíen correctamente.

---

## Ejemplo de Mini-Juego: "Plataformas de AURA"

### 1. Descripción

Un juego de plataformas simple donde el usuario debe recolectar monedas y llegar a la meta. Cada nivel completado otorga EXP y monedas.

### 2. Código de Ejemplo en Godot

```gdscript
extends Node2D

var exp_reward = 50
var coin_reward = 10
var websocket

func _ready():
    websocket = WebSocket.new()
    websocket.connect_to_host("wss://aura-backend.example.com/ws/game")
    websocket.connect("connected", self, "_on_websocket_connected")

func _on_player_win():
    var event_data = {
        "game_id": "platformer_level_1",
        "user_id": "user_12345",
        "event": "level_complete",
        "metadata": {
            "time_taken": get_tree().get_time_since_start(),
            "coins_collected": get_coins_collected()
        }
    }
    websocket.put_data(JSON.stringify(event_data).get_utf8())

    # Mostrar mensaje de felicitación
    push_notification("¡Nivel completado! EXP: " + str(exp_reward) + " | Monedas: " + str(coin_reward))
```

---

## Pruebas y Validación

### 1. Pruebas Locales

- Prueba la conexión WebSocket localmente usando un servidor de desarrollo.
- Verifica que los eventos se envíen correctamente y que las recompensas se calculen adecuadamente.

### 2. Pruebas de Integración

- Despliega una versión de prueba del juego en Vercel/Netlify.
- Conéctalo al backend de AURA/AME y valida que las recompensas se registren correctamente.

### 3. Pruebas de Usuario

- Realiza pruebas con usuarios reales para validar la experiencia de usuario.
- Recoge feedback y ajusta las recompensas según la dificultad percibida.

---

## Documentación Adicional

### 1. API de Recompensas

| Endpoint            | Método | Descripción                                    | Parámetros                                |
| ------------------- | ------ | ---------------------------------------------- | ----------------------------------------- |
| `/api/rewards`      | POST   | Registrar evento de juego y obtener recompensa | `game_id`, `user_id`, `event`, `metadata` |
| `/api/user/exp`     | GET    | Obtener EXP total del usuario                  | `user_id`                                 |
| `/api/user/rewards` | GET    | Obtener historial de recompensas               | `user_id`                                 |

### 2. Ejemplo de Respuesta de Recompensa

```json
{
  "success": true,
  "reward": {
    "exp": 75,
    "coins": 25,
    "badge": "explorer",
    "message": "¡Excelente trabajo! Has completado el nivel en tiempo récord."
  },
  "user_stats": {
    "total_exp": 1250,
    "total_coins": 450,
    "level": 12
  }
}
```

---

## Roadmap Futuro

1. **Primer Trimestre 2024**:
   - Implementar 3 mini-juegos básicos (plataformas, puzzles, arcade).
   - Sistema de niveles y progresión.

2. **Segundo Trimestre 2024**:
   - Integración con sistema de logros y badges.
   - Competencias entre usuarios (leaderboards).

3. **Tercer Trimestre 2024**:
   - Soporte para juegos multijugador en tiempo real.
   - Sistema de economía virtual dentro de los juegos.

---

## Soporte y Contacto

Para cualquier problema o pregunta sobre la integración de juegos, contacta al equipo de desarrollo de AURA/AME en:

- **Email**: support@aura-ame.com
- **Documentación Técnica**: [docs.aura-ame.com/game-integration](https://docs.aura-ame.com/game-integration)
