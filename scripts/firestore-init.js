// AURA - Firestore Initialization
// Run: node scripts/firestore-init.js

const admin = require("firebase-admin");

// Service account key (download from Firebase Console)
let serviceAccount;
try {
  serviceAccount = require("../frontend/firebase-service-account.json");
} catch {
  console.error("❌ Coloca firebase-service-account.json en frontend/ (descárgalo de Firebase Console).");
  process.exit(1);
}

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});

const db = admin.firestore();

async function initializeFirestore() {
  console.log("📊 Inicializando Firestore...");

  // Colección: users
  await db
    .collection("users")
    .doc("template")
    .set({
      avatar: {
        emotion: "idle",
        position: { x: 0, y: 0 },
        platform: "web",
        lastUpdate: admin.firestore.FieldValue.serverTimestamp(),
      },
      news: {},
      stats: {
        level: 1,
        exp: 0,
        title: "🏆 Iniciador",
        lastUpdate: admin.firestore.FieldValue.serverTimestamp(),
      },
      sync: {
        extension: null,
        web: null,
        mobile: null,
        lastSync: admin.firestore.FieldValue.serverTimestamp(),
      },
    });

  // Colección: settings
  await db.collection("settings").doc("global").set({
    cronInterval: 6, // horas
    maxNewsPerDay: 20,
    defaultEmotion: "idle",
    autoSync: true,
  });

  console.log("✅ Firestore inicializado correctamente");
}

initializeFirestore()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ Error:", err);
    process.exit(1);
  });
