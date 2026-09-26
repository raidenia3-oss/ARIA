package com.ame.ecosystem;

import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import android.view.View;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.net.URLEncoder;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class WebFactoryActivity extends AppCompatActivity {

    private EditText etWebTitle, etWebNiche;
    private TextView tvWebLog;
    private ScrollView scrollWebLog;
    private Button btnGenerateWeb, btnOpenWebVault;
    private WebView webView;
    private final OkHttpClient client = new OkHttpClient.Builder().connectTimeout(5, java.util.concurrent.TimeUnit.SECONDS).readTimeout(10, java.util.concurrent.TimeUnit.SECONDS).build();
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");
    private static final String BASE = "http://10.0.2.2:5000";
    private String lastUrl = null;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_web_factory);

        etWebTitle = findViewById(R.id.etWebTitle);
        etWebNiche = findViewById(R.id.etWebNiche);
        tvWebLog = findViewById(R.id.tvWebLog);
        scrollWebLog = findViewById(R.id.scrollWebLog);
        btnGenerateWeb = findViewById(R.id.btnGenerateWeb);
        btnOpenWebVault = findViewById(R.id.btnOpenWebVault);

        webView = new WebView(this);
        webView.getSettings().setJavaScriptEnabled(true);
        webView.setWebViewClient(new WebViewClient());

        btnGenerateWeb.setOnClickListener(v -> generateWeb());
        btnOpenWebVault.setOnClickListener(v -> openLastUrl());

        appendLog("╔══════════════════════════════════════╗");
        appendLog("║  AURA WEB FACTORY v3.1               ║");
        appendLog("╚══════════════════════════════════════╝");
        appendLog("│ Backend: " + BASE + "/api/v1/webfactory/generate");
        appendLog("│ Hosting: " + BASE + "/webflux/{slug}/");
        appendLog("│ Listo para generar sitios web");
    }

    private void generateWeb() {
        String title = etWebTitle.getText().toString().trim();
        String niche = etWebNiche.getText().toString().trim();
        if (title.isEmpty()) { etWebTitle.setError("Título requerido"); return; }
        if (niche.isEmpty()) niche = "generico";

        appendLog("│");
        appendLog("│ [GENERANDO] Título: " + title);
        appendLog("│ [GENERANDO] Nicho: " + niche);

        String path = "/api/v1/webfactory/generate?title=" + urlEncode(title) + "&niche=" + urlEncode(niche) + "&style=cyberpunk&monetize=true";
        Request r = new Request.Builder().url(BASE + path).post(RequestBody.create(JSON, "")).build();
        client.newCall(r).enqueue(new Callback() {
            @Override public void onFailure(Call call, IOException e) { appendLog("│ ❌ [ERROR] " + e.getMessage()); }
            @Override public void onResponse(Call call, Response resp) throws IOException {
                if (!resp.isSuccessful()) { appendLog("│ ❌ [HTTP " + resp.code() + "] " + resp.body().string()); return; }
                try {
                    JSONObject j = new JSONObject(resp.body().string());
                    String slug = j.optString("slug", "");
                    String url = j.optString("url", "");
                    String ts = j.optString("timestamp", "");
                    lastUrl = BASE + "/webflux/" + slug + "/";
                    appendLog("│ ✅ [OK] Slug: " + slug);
                    appendLog("│ ✅ [OK] URL: " + lastUrl);
                    appendLog("│ ✅ [OK] Timestamp: " + ts);
                    appendLog("│");
                    appendLog("│ Abriendo en WebView...");
                    runOnUiThread(() -> {
                        webView.loadUrl(lastUrl);
                        setContentView(webView);
                    });
                } catch (JSONException e) { appendLog("│ ❌ [JSON] " + e.getMessage()); }
            }
        });
    }

    private void openLastUrl() {
        if (lastUrl != null) {
            Intent i = new Intent(Intent.ACTION_VIEW, Uri.parse(lastUrl));
            startActivity(i);
        } else {
            appendLog("│ ⚠️ Genera una página primero");
        }
    }

    private String urlEncode(String s) { try { return URLEncoder.encode(s, "UTF-8"); } catch (Exception e) { return s; } }

    private void appendLog(final String t) {
        runOnUiThread(() -> { tvWebLog.append(t + "\n"); scrollWebLog.fullScroll(View.FOCUS_DOWN); });
    }
}
