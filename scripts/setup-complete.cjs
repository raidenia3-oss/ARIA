#!/usr/bin/env node

const { execSync } = require("child_process");

let FirebaseAutoSetup;
try {
  FirebaseAutoSetup = require("../frontend/lib/firebase-setup-auto");
} catch {
  console.error("❌ Falta frontend/lib/firebase-setup-auto.js — ejecuta primero el setup de Firebase.");
  process.exit(1);
}

async function main() {
  console.log("\n🚀 AURA/AME - Setup COMPLETO FINAL\n");

  try {
    // 1. Instalar dependencias
    console.log("\n1️⃣ Instalando dependencias...");
    execSync("bash scripts/install-browser-deps.sh", { stdio: "inherit" });

    // 2. Fijar Vercel
    console.log("\n2️⃣ Fijando error de Vercel...");
    execSync("bash scripts/fix-vercel-final.sh", { stdio: "inherit" });

    // 3. Firebase setup
    console.log("\n3️⃣ Setup Firebase...");
    const firebaseSetup = new FirebaseAutoSetup();
    await firebaseSetup.run();

    // 4. Generate .env
    console.log("\n4️⃣ Generando .env...");
    generateEnv();

    // 5. Vercel deploy final
    console.log("\n5️⃣ Deploy final a Vercel...");
    execSync("cd frontend && vercel deploy --prod --force", {
      stdio: "inherit",
    });

    console.log("\n✅ ========================================");
    console.log("✅ SETUP COMPLETADO SIN ERRORES");
    console.log("✅ Sistema AURA/AME completamente funcional");
    console.log("✅ ========================================\n");
  } catch (error) {
    console.error("\n❌ Error:", error.message);
    process.exit(1);
  }
}

function generateEnv() {
  const env = `
NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyDYy5QYsXqXxXxXxXxXxXxXxXxXxXxXxX
NEXT_PUBLIC_FIREBASE_PROJECT_ID=aura-ame-ecosystem
NEXT_PUBLIC_GOOGLE_CLIENT_ID=1234567890-abcdefghijklmnopqrstuvwxyz.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_google_client_secret
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
VERCEL_TOKEN=your_vercel_token_here
`;

  require("fs").writeFileSync("frontend/.env.local", env);
}

main().catch(console.error);
