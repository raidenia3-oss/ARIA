"""
N8N en Render.com (gratis) para automatizaciones AURA.
Genera instrucciones y exporta workflows JSON listos para importar.
"""

import os, json

RENDER_INSTRUCTIONS = """
PASOS PARA INSTALAR N8N EN RENDER.COM (GRATIS):

1. Ve a render.com y crea cuenta gratis
2. New -> Web Service
3. Usa la imagen Docker: n8nio/n8n
4. Configurar:
   Name: aura-n8n
   Region: Oregon (gratis)
   Instance Type: Free
5. Environment Variables:
   N8N_BASIC_AUTH_ACTIVE=true
   N8N_BASIC_AUTH_USER=admin
   N8N_BASIC_AUTH_PASSWORD=aura2026
   WEBHOOK_URL=https://aura-n8n.onrender.com
   N8N_HOST=0.0.0.0
   N8N_PORT=10000
   N8N_PROTOCOL=https
6. Deploy (3-5 min)
7. URL: https://aura-n8n.onrender.com
   Login: admin / aura2026
"""

AURA_WORKFLOWS = {
    "rollercoin_monitor": {
        "name": "RollerCoin Monitor",
        "description": "Monitorea RollerCoin cada hora y alerta si el bot se cae",
        "trigger": "cron",
        "schedule": "0 * * * *",
        "actions": [
            "HTTP Request -> GET https://raiden456-slut.hf.space/health",
            "IF -> status != ok -> Send alert",
            "Email/Discord -> notificar",
        ],
    },
    "gmail_rollercoin_code": {
        "name": "Gmail -> RollerCoin Login Code",
        "description": "Detecta codigo de login de RollerCoin en Gmail",
        "trigger": "gmail_new_email",
        "filter": "from:rollercoin.com",
        "actions": [
            "Extract code from email body",
            "HTTP Request -> POST a AURA EventBus",
            "AURA completa el login automaticamente",
        ],
    },
    "hf_space_monitor": {
        "name": "HF Space Health Monitor",
        "description": "Verifica cada 30min que el servidor de IA esta activo",
        "trigger": "cron",
        "schedule": "*/30 * * * *",
        "actions": [
            "HTTP GET -> https://raiden456-slut.hf.space/health",
            "IF -> no responde -> notificar por Discord/Email",
        ],
    },
    "ame_update_notify": {
        "name": "AME Auto Update",
        "description": "Cuando hay nuevo commit en GitHub, notifica para actualizar AME",
        "trigger": "github_webhook",
        "repo": "tu-usuario/aura-ame",
        "actions": [
            "Detectar nuevo commit en main",
            "HTTP POST -> AURA EventBus -> AME_UPDATE",
            "Notificar por Discord",
        ],
    },
}


def ensure_workflows_dir():
    os.makedirs("n8n_workflows", exist_ok=True)


def save_workflows():
    ensure_workflows_dir()
    with open("n8n_workflows/aura_workflows.json", "w", encoding="utf-8") as f:
        json.dump(AURA_WORKFLOWS, f, indent=2, ensure_ascii=False)


def print_instructions():
    print(RENDER_INSTRUCTIONS)
    print("Workflows guardados en n8n_workflows/aura_workflows.json")
    print("Importar en N8N desde Settings -> Import Workflow")


if __name__ == "__main__":
    save_workflows()
    print_instructions()
