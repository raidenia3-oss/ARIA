package com.aura.mobile;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.util.Log;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.util.Base64;

/**
 * ShareTargetHandler — intercepta archivos compartidos vía Android Share Intent
 * y los expone al frontend JavaScript para enviarlos al Cortex.
 */
public class ShareTargetHandler {

    private static final String TAG = "ShareTargetHandler";
    private final Activity activity;
    private final WebView webView;
    private String pendingFileContent = null;
    private String pendingFileName = null;
    private String pendingMimeType = null;

    public ShareTargetHandler(Activity activity, WebView webView) {
        this.activity = activity;
        this.webView = webView;
        setupWebView();
    }

    private void setupWebView() {
        webView.getSettings().setJavaScriptEnabled(true);
        webView.addJavascriptInterface(this, "AndroidShareHandler");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                // Si hay un archivo pendiente por procesar, lo inyectamos al frontend
                if (pendingFileContent != null) {
                    injectFileToJavaScript(pendingFileContent, pendingFileName, pendingMimeType);
                    pendingFileContent = null;
                    pendingFileName = null;
                    pendingMimeType = null;
                }
            }
        });
    }

    /**
     * Procesa el Intent cuando la app es abierta desde "Compartir" en Android.
     */
    public void handleShareIntent(Intent intent) {
        if (intent == null) return;

        String action = intent.getAction();
        String type = intent.getType();

        if (Intent.ACTION_SEND.equals(action) && type != null) {
            Uri fileUri = intent.getParcelableExtra(Intent.EXTRA_STREAM);
            String textExtra = intent.getStringExtra(Intent.EXTRA_TEXT);

            if (fileUri != null) {
                // Archivo compartido (PDF, imagen, TXT)
                processSharedFile(fileUri, type);
            } else if (textExtra != null) {
                // Texto plano compartido
                processSharedText(textExtra);
            }
        }
    }

    private void processSharedFile(Uri fileUri, String mimeType) {
        try {
            String fileName = getFileName(fileUri, mimeType);
            byte[] fileBytes = readBytesFromUri(fileUri);

            if (mimeType.startsWith("text/") || mimeType.equals("application/pdf")) {
                // Para PDF usamos base64, para texto usamos string
                if (mimeType.startsWith("text/")) {
                    String content = new String(fileBytes, "UTF-8");
                    pendingFileContent = content;
                    pendingFileName = fileName;
                    pendingMimeType = mimeType;
                    Log.d(TAG, "Text file loaded: " + fileName + " (" + content.length() + " chars)");
                } else {
                    // PDF en base64
                    String base64Content = Base64.getEncoder().encodeToString(fileBytes);
                    pendingFileContent = base64Content;
                    pendingFileName = fileName;
                    pendingMimeType = "application/pdf";
                    Log.d(TAG, "PDF file loaded: " + fileName + " (" + fileBytes.length + " bytes)");
                }
            } else if (mimeType.startsWith("image/")) {
                // Imagen en base64
                String base64Content = Base64.getEncoder().encodeToString(fileBytes);
                pendingFileContent = base64Content;
                pendingFileName = fileName;
                pendingMimeType = mimeType;
                Log.d(TAG, "Image loaded: " + fileName + " (" + fileBytes.length + " bytes)");
            }

            // Si WebView ya cargó, inyectamos directamente
            if (webView.getUrl() != null) {
                injectFileToJavaScript(pendingFileContent, pendingFileName, pendingMimeType);
                pendingFileContent = null;
                pendingFileName = null;
                pendingMimeType = null;
            }

        } catch (Exception e) {
            Log.e(TAG, "Error processing shared file: " + e.getMessage());
        }
    }

    private void processSharedText(String text) {
        pendingFileContent = text;
        pendingFileName = "shared_text.txt";
        pendingMimeType = "text/plain";
        Log.d(TAG, "Text shared: " + text.substring(0, Math.min(100, text.length())));

        if (webView.getUrl() != null) {
            injectFileToJavaScript(pendingFileContent, pendingFileName, pendingMimeType);
            pendingFileContent = null;
            pendingFileName = null;
            pendingMimeType = null;
        }
    }

    @JavascriptInterface
    public void injectFileToJavaScript(String content, String fileName, String mimeType) {
        activity.runOnUiThread(() -> {
            String escapedContent = content
                .replace("\\", "\\\\")
                .replace("'", "\\'")
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t");

            String js = String.format(
                "if (window.onFileReceived) { window.onFileReceived('%s', '%s', '%s'); }",
                escapedContent, fileName, mimeType
            );
            webView.evaluateJavascript(js, null);
            Log.d(TAG, "File injected to JavaScript: " + fileName);
        });
    }

    private String getFileName(Uri uri, String mimeType) {
        String displayName = "shared_file";
        String extension = getExtensionForMime(mimeType);

        try (android.database.Cursor cursor = activity.getContentResolver()
                .query(uri, null, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int nameIndex = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME);
                if (nameIndex >= 0) {
                    displayName = cursor.getString(nameIndex);
                }
            }
        } catch (Exception e) {
            Log.w(TAG, "Could not get file name, using default: " + e.getMessage());
        }

        // Asegurar extensión
        if (!displayName.contains(".")) {
            displayName += "." + extension;
        }
        return displayName;
    }

    private String getExtensionForMime(String mimeType) {
        switch (mimeType) {
            case "application/pdf": return "pdf";
            case "text/plain": return "txt";
            case "image/jpeg": return "jpg";
            case "image/png": return "png";
            default: return "bin";
        }
    }

    private byte[] readBytesFromUri(Uri uri) throws IOException {
        try (InputStream inputStream = activity.getContentResolver().openInputStream(uri);
             ByteArrayOutputStream byteBuffer = new ByteArrayOutputStream()) {

            if (inputStream == null) throw new IOException("Cannot open input stream");

            byte[] buffer = new byte[4096];
            int bytesRead;
            while ((bytesRead = inputStream.read(buffer)) != -1) {
                byteBuffer.write(buffer, 0, bytesRead);
            }
            return byteBuffer.toByteArray();
        }
    }
}