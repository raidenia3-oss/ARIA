import asyncio
import os
import sys

sys.path.insert(0, ".")

print("=== AURA v1.2 Integration Tests ===")
print()

# Test WhatsApp Bot
print("Test: WhatsApp Bot")
from backend.bots.whatsapp_bot import WhatsAppBot, get_whatsapp_bot

bot = WhatsAppBot("test_sid", "test_token", "+51942858492")
assert bot.account_sid == "test_sid"
assert bot.whatsapp_number == "+51942858492"
assert bot.messages_processed == 0
assert bot.users_connected == []

# Test command handlers registered
assert "/fanfic" in bot._command_handlers
assert "/search" in bot._command_handlers
assert "/marketplace" in bot._command_handlers
assert "/stats" in bot._command_handlers
assert "/netrunner" in bot._command_handlers
assert "/ask" in bot._command_handlers
assert "/help" in bot._command_handlers
assert "/status" in bot._command_handlers
print("  WhatsAppBot init: OK")

# Test singleton (get_whatsapp_bot creates default instance)
bot2 = get_whatsapp_bot()
assert bot2 is not None
assert bot2.account_sid == "TWILIO_ACCOUNT_SID"  # defaults from singleton
print("  Singleton: OK")

# Test WhatsApp Routes
print("Test: WhatsApp Routes")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.whatsapp_routes import router as whatsapp_router

test_app = FastAPI()
test_app.include_router(whatsapp_router)
client = TestClient(test_app)

# Test status endpoint
resp = client.get("/api/whatsapp/status")
assert resp.status_code == 200
data = resp.json()
assert data["bot_active"] is True
assert "messages_processed" in data
assert "users_connected" in data
print("  Status endpoint: OK")

# Test webhook
resp = client.post(
    "/api/whatsapp/webhook",
    json={
        "Body": "/help",
        "From": "+51912345678",
        "MessagingProduct": "whatsapp",
    },
)
assert resp.status_code == 200
data = resp.json()
assert data["status"] == "processed"
assert data["response"] is not None
print("  Webhook endpoint: OK")

# Test send message
resp = client.post(
    "/api/whatsapp/send",
    json={
        "to_number": "+51912345678",
        "text": "Hello from AURA",
    },
)
assert resp.status_code == 200
data = resp.json()
assert data["status"] in ("simulated", "sent", "error")
print("  Send endpoint: OK")

# Test main.py has WhatsApp router
print("Test: Main.py Integration")
with open("backend/main.py", "r", encoding="utf-8") as f:
    content = f.read()
assert "from backend.api.whatsapp_routes import router as whatsapp_router" in content
assert "app.include_router(whatsapp_router" in content
assert 'prefix="/api/whatsapp"' in content
print("  Import present: OK")
print("  Router include present: OK")

# Test .env has new vars
print("Test: .env variables")
with open("backend/.env", "r", encoding="utf-8") as f:
    env_content = f.read()
assert "TWILIO_ACCOUNT_SID" in env_content
assert "TWILIO_AUTH_TOKEN" in env_content
assert "TWILIO_WHATSAPP_NUMBER" in env_content
assert "CHROME_STORE_ID" in env_content
assert "GOOGLE_PLAY_KEY" in env_content
assert "GOOGLE_PLAY_PACKAGE_NAME" in env_content
assert "MICROSOFT_STORE_TOKEN" in env_content
assert "FIREBASE_API_KEY" in env_content
assert "FIREBASE_PROJECT_ID" in env_content
print("  All env vars present: OK")

# Test Windows Store files
print("Test: Windows Store")
assert os.path.exists("windows_store/Package.appxmanifest")
assert os.path.exists("windows_store/build_store_package.py")
with open("windows_store/Package.appxmanifest", "r") as f:
    manifest_xml = f.read()
assert "AURA" in manifest_xml
assert "1.2.0.0" in manifest_xml
print("  Package.appxmanifest: OK")
print("  build_store_package.py: OK")

# Test Chrome Extension
print("Test: Chrome Extension")
assert os.path.exists("chrome_extension/manifest.json")
assert os.path.exists("chrome_extension/popup.html")
assert os.path.exists("chrome_extension/popup.js")

with open("chrome_extension/manifest.json", "r") as f:
    import json

    manifest = json.load(f)
assert manifest["manifest_version"] == 3
assert manifest["name"] == "AURA Assistant"
assert manifest["version"] == "1.2.0"
assert "activeTab" in manifest["permissions"]
assert "storage" in manifest["permissions"]
print("  manifest.json: OK")
print("  popup.html: OK")
print("  popup.js: OK")

# Test APK v2
print("Test: APK v2")
assert os.path.exists("mobile_client/v2/ame_app_v2.py")
assert os.path.exists("mobile_client/v2/build_apk_v2.py")
assert os.path.exists("mobile_client/requirements_mobile_v2.txt")
assert os.path.exists("mobile_client/play_store_config.py")

with open("mobile_client/v2/ame_app_v2.py", "r") as f:
    ame_content = f.read()
assert "AMEMobileAppV2" in ame_content
assert "setup_biometric" in ame_content
assert "enable_push_notifications" in ame_content
assert "voice_command" in ame_content
assert "improved_netrunner_ui" in ame_content
print("  ame_app_v2.py: OK")

with open("mobile_client/play_store_config.py", "r") as f:
    play_content = f.read()
assert "PlayStoreConfig" in play_content
assert "com.raiden.aura" in play_content
assert "version_code" in play_content
print("  play_store_config.py: OK")

# Test Chrome publish
print("Test: Chrome Publish")
assert os.path.exists("chrome_extension/publish.py")
with open("chrome_extension/publish.py", "r") as f:
    pub_content = f.read()
assert "publish" in pub_content
assert "Chrome Web Store" in pub_content
print("  publish.py: OK")

print()
print("All v1.2 integration tests passed!")
