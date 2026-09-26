# AURA/AME - Setup Guide

## Credenciales Necesarias

### 1. Firebase

1. Ve a https://console.firebase.google.com
2. Crear proyecto: `aura-ame-ecosystem`
3. Habilitar: Firestore + Authentication + Storage
4. Descargar service-account.json
5. Copiar credenciales a `.env.local`

### 2. Google OAuth

1. Ve a https://console.cloud.google.com
2. Crear proyecto: `aura-ame-ecosystem`
3. Habilitar APIs: Gmail, Drive, Sheets
4. Crear OAuth 2.0 Client ID (Web Application)
5. Authorized redirect URIs:
   - `https://aura-web-chi-seven.vercel.app/api/auth/callback`
   - `http://localhost:3000/api/auth/callback`
6. Copiar Client ID y Secret a `.env.local`

### 3. Google Apps Script

1. Ve a https://script.google.com
2. Nuevo proyecto
3. Pegar código de `google-apps-script.js`
4. Deploy → Web app → Execute as: Me → Who has access: Anyone
5. Copiar URL de deployment a `.env.local` como `GOOGLE_APPS_SCRIPT_URL`

### 4. Vercel

1. `vercel login`
2. `vercel link`
3. Deploy automático al pushear a GitHub

## Instalación

```bash
# Setup automático completo (recomendado)
npm run setup:all

# O manual:
cd frontend
npm install
node scripts/firestore-init.js
npm run dev
vercel deploy --prod
```

## Chrome Extension

1. Abrir `chrome://extensions/`
2. Modo desarrollador: ON
3. Cargar extensión sin empaquetar: `chrome-extension-aura/`
4. Listo

## Estructura

```
frontend/
├── .env.local          # Credenciales (NO commithear)
├── .env.example         # Template de variables
├── package.json         # Dependencias + script setup:all
├── lib/
│   ├── firebase-config.js
│   └── api.js
├── components/
│   ├── Avatar3D.jsx
│   ├── NewsCard.jsx
│   └── ...
├── pages/
│   ├── index.js         # AURA Dashboard (PC)
│   ├── ame.js           # AME Mobile
│   └── api/
│       ├── auth/[...nextauth].js
│       ├── avatar/emotion.js
│       └── sync.js
└── styles/globals.css

chrome-extension-aura/
├── manifest.json
├── background.js
├── content.js
├── popup.html
├── popup.js
└── styles/popup.css

scripts/
├── setup-all.js         # Setup automático completo
├── firestore-init.js    # Inicializar Firestore
└── google-apps-script.js # Automatización Google
```
