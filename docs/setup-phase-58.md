# Setup Guide for Phase 58 — Cline Implementation

> Prepara el entorno para la Fase 58 (React Native + Fine-tuning + Analytics
> Engine). La app web v3.0 ya está completa y verificada; esto es lo que Cline
> necesita para las piezas de backend/móvil que requieren servicios externos y
> toolchains nativas no disponibles en el entorno de Kilo.

## Prerequisites

- Git + acceso a GitHub
- Node.js 18+
- Python 3.10+ (para fine-tuning / analytics engine)
- GPU recomendada para fine-tuning
- Firebase project + credenciales (React Native auth)
- HuggingFace account + token (fine-tuning)
- ElevenLabs API key (TTS)
- PostgreSQL / Redis (analytics engine)

## 🚀 Quick Start (para Cline)

### 1. Clonar e instalar el frontend

```bash
git clone https://github.com/raidenia3-oss/AURA-server.01.git
cd AURA-server.01/frontend
npm install
npm run typecheck
npm run lint:local
npm test
```

### 2. Variables de entorno

```bash
cp .env.example .env.local
# Edita .env.local con tus credenciales (ver .env.example)
```

### 3. Verificar que v3.0 funciona

```bash
npm run dev
# Visita http://localhost:3000 → /integrations y /analytics
```

---

## 📦 Fase 58 — Setup por opción

### Opción A: React Native

```bash
npm install -g expo-cli
expo init ame-mobile
cd ame-mobile
npm install @react-native-firebase/app @react-native-firebase/auth
npm install @react-native-async-storage/async-storage zustand
```

Configurar Firebase (console → project → iOS/Android apps → descarga
`GoogleService-Info.plist` / `google-services.json`). Luego:

```bash
cd ame-mobile && expo start   # escanea el QR con Expo Go
```

### Opción D: Fine-tuning + Multimodal

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
huggingface-cli login            # pega tu HF token
```

Recolectar datos y entrenar (estos scripts los crea Cline en la Fase 58; no
existen aún en el repo):

```bash
python scripts/collect-training-data.py   # → training-data.jsonl
python scripts/finetune-model.py           # → ./fine-tuned-model
```

### Opción F: Analytics Engine

```bash
pip install -r requirements.txt
# PostgreSQL:
createdb aura_analytics
# o SQLite para dev: DATABASE_URL=sqlite:///aura_analytics.db
python scripts/analytics-engine.py         # agrega stats cada hora
```

---

## 🔗 Integration Points (endpoints que Cline creará)

### Mobile APIs (Opción A)
- `GET /api/mobile/ames` — lista los AMEs del usuario
- `POST /api/mobile/chat` — envía mensaje a un AME
- `PUT /api/mobile/sync` — sync offline
- `GET|POST /api/mobile/analytics` — datos de analytics

### Fine-tuning APIs (Opción D)
- `POST /api/ai/multimodal` — texto + imagen + audio
- `GET /api/ai/model-info` — info del modelo actual

### Analytics APIs (Opción F)
- `GET /api/analytics` — datos del dashboard
- `GET /api/analytics/predictions` — forecast 7 días
- `GET /api/analytics/anomalies` — anomalías detectadas

---

## 📋 Deployment Checklist (antes de prod)

- [ ] Tests pasando (`npm test`)
- [ ] Lighthouse ≥ 90 (ver `PERFORMANCE.md`)
- [ ] TypeScript errors: 0 (`npm run typecheck`)
- [ ] ESLint errors: 0 (`npm run lint:local`)
- [ ] Variables de entorno configuradas
- [ ] Migraciones de DB ejecutadas
- [ ] Reglas de Firebase actualizadas

---

## 🆘 Troubleshooting

- **Module not found:** `npm install` / `pip install -r requirements.txt`
- **Port in use:** `npm run dev -- -p 3001`
- **Firebase connection error:** verifica credenciales en `.env.local`
- **No GPU:** fine-tuning corre en CPU (más lento); usa Colab/Lambda Labs

---

## 📞 Soporte

- `README.md`, `CONTRIBUTING.md`, `TROUBLESHOOTING.md`, `README-ROADMAP.md`
- Issues: https://github.com/raidenia3-oss/AURA-server.01/issues
