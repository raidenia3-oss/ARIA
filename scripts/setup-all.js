#!/usr/bin/env node

// AURA/AME - Setup Automatico Completo
// Uso: npm run setup:all

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

console.log("🚀 AURA/AME - Setup Automatico Completo\n");

async function main() {
  // 1. Verificar Node.js
  console.log("1️⃣ Verificando Node.js...");
  try {
    const nodeVersion = execSync("node --version").toString().trim();
    console.log(`   ✅ Node.js ${nodeVersion}`);
  } catch {
    console.error(
      "❌ Node.js no encontrado. Instala Node.js 18+ desde https://nodejs.org",
    );
    process.exit(1);
  }

  // 2. Instalar dependencias globales
  console.log("\n2️⃣ Instalando herramientas globales...");
  try {
    execSync("npm install -g firebase-tools vercel", { stdio: "inherit" });
    console.log("   ✅ firebase-tools instalado");
    console.log("   ✅ vercel instalado");
  } catch {
    console.log("   ⚠️  Algunas herramientas ya existen o requieren permisos");
  }

  // 3. Crear carpetas necesarias
  console.log("\n3️⃣ Creando estructura de carpetas...");
  const folders = [
    "chrome-extension-aura/styles",
    "chrome-extension-aura/assets",
    "scripts",
    "frontend/lib",
    "frontend/pages/api/avatar",
    "frontend/pages/api/auth",
    "frontend/components",
    "frontend/styles",
  ];

  folders.forEach((folder) => {
    const fullPath = path.join(__dirname, "..", folder);
    if (!fs.existsSync(fullPath)) {
      fs.mkdirSync(fullPath, { recursive: true });
      console.log(`   ✅ ${folder}`);
    }
  });

  // 4. Crear .env.local template
  console.log("\n4️⃣ Creando .env.local...");
  const envPath = path.join(__dirname, "..", "frontend", ".env.local");
  if (!fs.existsSync(envPath)) {
    const envContent = `# Firebase (reemplazar con credenciales reales)
NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyDummyKeyReplaceWithReal
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=aura-ame-ecosystem.firebaseapp.com
NEXT_PUBLIC_FIREBASE_PROJECT_ID=aura-ame-ecosystem
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=aura-ame-ecosystem.appspot.com
NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=123456789012
NEXT_PUBLIC_FIREBASE_APP_ID=1:123456789012:web:abcdef123456

# Google OAuth (reemplazar con credenciales reales)
NEXT_PUBLIC_GOOGLE_CLIENT_ID=123456789012-abcdef.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-abcdefghijklmnop

# Google Apps Script (reemplazar con URL real)
GOOGLE_APPS_SCRIPT_URL=https://script.google.com/macros/s/123456789/exec

# URLs
AURA_URL=https://aura-web-chi-seven.vercel.app
AME_URL=https://aura-web-chi-seven.vercel.app/ame

# Vercel
VERCEL_TOKEN=your_vercel_token_here
`;

    fs.writeFileSync(envPath, envContent);
    console.log("   ✅ .env.local creado");
  } else {
    console.log("   ⚠️  .env.local ya existe, no se sobrescribe");
  }

  // 5. Instalar dependencias del proyecto
  console.log("\n5️⃣ Instalando dependencias del proyecto...");
  try {
    execSync("cd frontend && npm install", { stdio: "inherit" });
    console.log("   ✅ Dependencias instaladas");
  } catch (error) {
    console.error("   ❌ Error instalando dependencias:", error.message);
  }

  // 6. Inicializar Firestore
  console.log("\n6️⃣ Inicializando Firestore...");
  console.log("   📋 Sigue estos pasos:");
  console.log("   1. Ve a: https://console.firebase.google.com");
  console.log("   2. Crea proyecto: aura-ame-ecosystem");
  console.log("   3. Habilita Firestore, Auth y Storage");
  console.log("   4. Descarga service-account.json");
  console.log("   5. Guárdalo en: frontend/firebase-service-account.json");
  console.log("   6. Ejecuta: node scripts/firestore-init.js\n");

  // 7. Google OAuth setup
  console.log("7️⃣ Configurando Google OAuth...");
  console.log("   📋 Sigue estos pasos:");
  console.log("   1. Ve a: https://console.cloud.google.com");
  console.log("   2. Proyecto: aura-ame-ecosystem");
  console.log("   3. Habilita APIs: Gmail, Drive, Sheets");
  console.log("   4. Crea OAuth 2.0 Client ID");
  console.log("   5. Agrega URIs:");
  console.log("      - http://localhost:3000/api/auth/callback");
  console.log(
    "      - https://aura-web-chi-seven.vercel.app/api/auth/callback",
  );
  console.log("   6. Copia Client ID y Secret a .env.local\n");

  // 8. Google Apps Script setup
  console.log("8️⃣ Configurando Google Apps Script...");
  console.log("   📋 Sigue estos pasos:");
  console.log("   1. Ve a: https://script.google.com");
  console.log("   2. Nuevo proyecto");
  console.log("   3. Pega código de: scripts/google-apps-script.js");
  console.log("   4. Deploy → Web App → Execute as: Me → Anyone");
  console.log("   5. Copia URL a .env.local como GOOGLE_APPS_SCRIPT_URL\n");

  // 9. Vercel setup
  console.log("9️⃣ Configurando Vercel...");
  console.log("   📋 Sigue estos pasos:");
  console.log("   1. Ejecuta: vercel login");
  console.log("   2. Ejecuta: cd frontend && vercel link");
  console.log("   3. Ejecuta: vercel deploy --prod\n");

  console.log("\n✅ ============================================");
  console.log("✅ AURA/AME - Setup Completado");
  console.log("✅ ============================================\n");

  console.log("📍 Próximos pasos:");
  console.log("   1. Llena .env.local con credenciales (pasos 6, 7, 8)");
  console.log("   2. Ejecuta: node scripts/firestore-init.js");
  console.log("   3. Ejecuta: npm run dev (probar localmente)");
  console.log("   4. Ejecuta: vercel deploy --prod (deploy)");
  console.log("   5. Instala Chrome Extension: chrome://extensions\n");
}

main().catch((err) => {
  console.error("❌ Error:", err);
  process.exit(1);
});
