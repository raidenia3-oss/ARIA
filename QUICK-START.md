# AURA OS v2.1 — 5-Minute Quick Start

Pick your platform. You'll be sending messages to AI in 5 minutes.

---

## 📱 Android (2 Minutes)

```bash
# 1. Install app
Play Store → Search "AURA Launcher" → Install

# 2. Open app → Grant permissions → Wait 10s

# 3. Open browser
http://localhost:8000/api/docs

# 4. Send message
curl -X POST http://localhost:8000/api/chat \
  -d '{"message": "Hello AURA"}'

# Done! ✅
```

---

## 🐳 Docker (3 Minutes)

```bash
# 1. Start
docker-compose up -d

# 2. Wait for startup
sleep 5

# 3. Verify
curl http://localhost:8000/api/health

# 4. Open dashboard
open http://localhost:8000/api/docs

# 5. Chat
curl -X POST http://localhost:8000/api/chat \
  -d '{"message": "What is AURA?"}'

# Done! ✅
```

---

## 🖥️ Local (5 Minutes)

```bash
# 1. Install
cd backend/
pip install -r requirements.txt

# 2. Start
python -m uvicorn main:app --reload

# 3. Verify (in another terminal)
curl http://localhost:8000/api/health

# 4. Open dashboard
open http://localhost:8000/api/docs

# 5. Chat
curl -X POST http://localhost:8000/api/chat \
  -d '{"message": "Hello!"}'

# Done! ✅
```

---

## 💬 First Chat Command

```bash
# Simple
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is AI?"}'

# Advanced (specify provider)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Explain quantum computing",
    "provider": "claude",
    "temperature": 0.7,
    "max_tokens": 500
  }'
```

---

## 🔗 Key URLs

| What | URL |
|------|-----|
| **API Docs** | http://localhost:8000/api/docs |
| **Health** | http://localhost:8000/api/health |
| **Providers** | http://localhost:8000/api/providers |
| **Dashboard** | http://localhost:8000 |

---

## ✨ Next: Try These Commands

```bash
# 1. List all providers
curl http://localhost:8000/api/providers

# 2. Get best provider
curl http://localhost:8000/api/providers/best

# 3. Check provider stats
curl http://localhost:8000/api/providers/stats

# 4. Execute a skill
curl -X POST http://localhost:8000/api/skills/translate/exec \
  -d '{"text": "Hello", "target_language": "Spanish"}'

# 5. Get chat history
curl http://localhost:8000/api/chat/history

# 6. Create new user
curl -X POST http://localhost:8000/api/auth/register \
  -d '{"username": "myuser", "password": "mypass"}'
```

---

## 📚 Learn More

- [Full Installation Guide](INSTALLATION.md)
- [API Documentation](docs/API.md)
- [Architecture Guide](docs/ARCHITECTURE.md)
- [Mobile Architecture](docs/MOBILE-ARCHITECTURE.md)

---

**Ready?** Start with your platform above! 🚀
