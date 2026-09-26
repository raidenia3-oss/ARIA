package com.ame.ecosystem;

import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.appcompat.app.AppCompatActivity;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;

public class AuraHudActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_aura_hud);

        WebView webView = findViewById(R.id.webViewHud);

        // Configuración del WebView para renderizado optimizado
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setAllowUniversalAccessFromFileURLs(true);
        settings.setAllowFileAccessFromFileURLs(true);
        settings.setRenderPriority(WebSettings.RenderPriority.HIGH);
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setSupportZoom(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);

        // Cargar el HUD móvil desde el archivo HTML
        try {
            // Ruta al archivo HTML del HUD móvil
            File htmlFile = new File(getFilesDir(), "aura_mobile_hud.html");

            // Si el archivo no existe, copiarlo desde assets
            if (!htmlFile.exists()) {
                copyFromAssets("aura_mobile_hud.html", htmlFile);
            }

            // Cargar el contenido del archivo
            String htmlContent = readFile(htmlFile);
            webView.loadDataWithBaseURL("file:///android_asset/", htmlContent, "text/html", "UTF-8", null);

        } catch (IOException e) {
            e.printStackTrace();
            // Si no se puede cargar el archivo, mostrar un mensaje de error
            webView.loadData("<html><body><h1>Error al cargar HUD</h1><p>No se pudo cargar el HUD móvil</p></body></html>", "text/html", "UTF-8");
        }

        // Manejar eventos de navegación
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                // Bloquear navegación externa
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                // Inyectar JavaScript para manejar eventos de botón
                view.evaluateJavascript("""
                    document.addEventListener('auraAction', function(e) {
                        const action = e.detail.action;
                        console.log('Action triggered: ' + action);
                        // Enviar evento al Android
                        AndroidBridge.sendActionToAndroid(action);
                    });
                """, null);
            }
        });
    }

    // Método para copiar archivos desde assets
    private void copyFromAssets(String assetName, File destFile) throws IOException {
        try (FileReader reader = new FileReader(new File(getFilesDir(), assetName))) {
            // Si el archivo ya existe, no hacer nada
            if (destFile.exists()) return;
        } catch (IOException e) {
            // Si no existe, copiar desde assets
            try {
                java.io.InputStream in = getAssets().open(assetName);
                java.io.FileOutputStream out = new java.io.FileOutputStream(destFile);
                byte[] buffer = new byte[1024];
                int read;
                while ((read = in.read(buffer)) != -1) {
                    out.write(buffer, 0, read);
                }
                in.close();
                out.close();
            } catch (IOException ex) {
                throw new IOException("Error al copiar archivo desde assets: " + assetName, ex);
            }
        }
    }

    // Método para leer contenido de archivo
    private String readFile(File file) throws IOException {
        StringBuilder content = new StringBuilder();
        try (java.io.BufferedReader reader = new java.io.BufferedReader(new java.io.FileReader(file))) {
            String line;
            while ((line = reader.readLine()) != null) {
                content.append(line).append("\n");
            }
        }
        return content.toString();
    }

    // Método para manejar eventos desde JavaScript
    public void sendActionToAndroid(String action) {
        // Manejar acciones desde el HUD
        switch (action) {
            case "osint":
                // Navegar a la pantalla de OSINT
                finish();
                overridePendingTransition(0, 0);
                startActivity(new android.content.Intent(this, OsintReconActivity.class));
                overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
                break;
            case "target":
                // Navegar a la pantalla de Target Analysis
                finish();
                overridePendingTransition(0, 0);
                startActivity(new android.content.Intent(this, OsintReconActivity.class));
                overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
                break;
            case "network":
                // Navegar a la pantalla de Network Scan
                finish();
                overridePendingTransition(0, 0);
                startActivity(new android.content.Intent(this, GlobalMapActivity.class));
                overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
                break;
            case "chat":
                // Navegar a la pantalla de Chat
                finish();
                overridePendingTransition(0, 0);
                startActivity(new android.content.Intent(this, GbrainChatActivity.class));
                overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
                break;
            case "console":
                // Navegar a la pantalla de Tactical Console
                finish();
                overridePendingTransition(0, 0);
                startActivity(new android.content.Intent(this, TacticalConsoleActivity.class));
                overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
                break;
            default:
                // Acciones no implementadas
                break;
        }
    }

    // Método para manejar el botón atrás
    @Override
    public void onBackPressed() {
        WebView webView = findViewById(R.id.webViewHud);
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
