// AURA - Google Apps Script (Automatización)
// Deploy como Web App en script.google.com

// Trigger cada 6 horas (configurar en Google Cloud)
function autoSyncNews() {
  const url = "https://aura-web-chi-seven.vercel.app/api/news/recommend";
  const options = {
    method: "get",
    headers: {
      "Content-Type": "application/json",
    },
    muteHttpExceptions: true,
  };

  try {
    const response = UrlFetchApp.fetch(url, options);
    const data = JSON.parse(response.getContentText());

    // Guardar en Google Drive
    saveToGoogleDrive(data);

    // Log
    Logger.log(
      "[AURA] Noticias sincronizadas: " +
        (data.articles ? data.articles.length : 0),
    );
  } catch (e) {
    Logger.log("Error: " + e.toString());
  }
}

function saveToGoogleDrive(data) {
  // Crear carpeta si no existe
  const folders = DriveApp.getFoldersByName("AURA_Noticias");
  const folder = folders.hasNext()
    ? folders.next()
    : DriveApp.createFolder("AURA_Noticias");

  const fileName =
    "noticias-" + new Date().toISOString().slice(0, 10) + ".json";

  const file = folder.createFile(
    fileName,
    JSON.stringify(data, null, 2),
    MimeType.PLAIN_TEXT,
  );

  Logger.log("Guardado: " + file.getUrl());
}

// Webhook endpoint (recibir notificaciones de Vercel)
function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);

    // Procesar datos
    Logger.log("Webhook recibido: " + JSON.stringify(data));

    // Guardar automáticamente
    if (data.articles) {
      saveToGoogleDrive(data);
    }

    return ContentService.createTextOutput(
      JSON.stringify({ success: true, timestamp: new Date() }),
    ).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(
      JSON.stringify({ error: err.toString() }),
    ).setMimeType(ContentService.MimeType.JSON);
  }
}

// Test manual
function testSync() {
  autoSyncNews();
}
