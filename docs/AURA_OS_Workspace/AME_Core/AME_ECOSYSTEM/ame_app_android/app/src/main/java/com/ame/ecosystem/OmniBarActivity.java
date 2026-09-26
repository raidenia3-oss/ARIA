package com.ame.ecosystem;

import android.annotation.SuppressLint;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.inputmethod.EditorInfo;
import android.widget.*;
import androidx.appcompat.app.AppCompatActivity;
import okhttp3.*;
import org.json.JSONObject;
import java.io.IOException;
import java.util.concurrent.TimeUnit;

public class OmniBarActivity extends AppCompatActivity {

    private static final String TAG = "AURA-OmniBar";
    private EditText omniInput;
    private ScrollView scrollResults;
    private LinearLayout resultsContainer;
    private TextView statusBar;
    private OkHttpClient httpClient;

    private String getServerUrl() {
        SharedPreferences prefs = getSharedPreferences("aura_config", MODE_PRIVATE);
        return prefs.getString("aura_server_url", "http://10.0.2.2:5000");
    }

    @SuppressLint("SetTextI18n")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_omnibar);

        omniInput = findViewById(R.id.omni_input);
        scrollResults = findViewById(R.id.scroll_results);
        resultsContainer = findViewById(R.id.results_container);
        statusBar = findViewById(R.id.status_bar);

        httpClient = new OkHttpClient.Builder()
                .connectTimeout(5, TimeUnit.SECONDS)
                .readTimeout(10, TimeUnit.SECONDS)
                .build();

        omniInput.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                String cmd = omniInput.getText().toString().trim();
                if (!cmd.isEmpty()) {
                    executeCommand(cmd);
                    omniInput.setText("");
                }
                return true;
            }
            return false;
        });

        findViewById(R.id.btn_quick_bot_start).setOnClickListener(v -> executeCommand("/bot start"));
        findViewById(R.id.btn_quick_bot_stop).setOnClickListener(v -> executeCommand("/bot stop"));
        findViewById(R.id.btn_quick_stats).setOnClickListener(v -> executeCommand("/sys stats"));
        findViewById(R.id.btn_quick_daemon).setOnClickListener(v -> executeCommand("/daemon status"));

        appendResult("AURA OmniBar v1.0 listo. Escribe un comando o usa los botones rápidos.", "#00ff88");
        statusBar.setText("Estado: Conectado a " + getServerUrl());
    }

    @SuppressLint("SetTextI18n")
    private void executeCommand(String command) {
        appendResult("> " + command, "#00ffaa");
        statusBar.setText("Ejecutando: " + command + "...");

        JSONObject body = new JSONObject();
        try {
            body.put("command", command);
        } catch (Exception e) {
            Log.e(TAG, "JSON error", e);
        }

        RequestBody rBody = RequestBody.create(body.toString(), MediaType.parse("application/json"));
        Request req = new Request.Builder()
                .url(getServerUrl() + "/api/v1/omnibar/command")
                .post(rBody)
                .build();

        httpClient.newCall(req).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                runOnUiThread(() -> {
                    appendResult("Error: " + e.getMessage(), "#ff4444");
                    statusBar.setText("Estado: Error de conexión");
                });
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                String respBody = response.body() != null ? response.body().string() : "{}";
                runOnUiThread(() -> {
                    try {
                        JSONObject json = new JSONObject(respBody);
                        boolean ok = json.optBoolean("ok", false);
                        String msg = json.optString("msg", json.toString());
                        String color = ok ? "#00ff88" : "#ffaa00";

                        StringBuilder sb = new StringBuilder();
                        sb.append(ok ? "✓ " : "✗ ").append(msg);

                        if (json.has("cpu")) {
                            sb.append("\n  CPU: ").append(json.getDouble("cpu")).append("%");
                            sb.append(" | RAM: ").append(json.getDouble("ram")).append("%");
                            sb.append(" | Disk: ").append(json.getDouble("disk")).append("%");
                        }
                        if (json.has("url")) {
                            sb.append("\n  URL: ").append(json.getString("url"));
                            sb.append("\n  Slug: ").append(json.getString("slug"));
                        }
                        appendResult(sb.toString(), color);
                        statusBar.setText("OK — " + command);
                    } catch (Exception e) {
                        appendResult("Respuesta: " + respBody, "#888888");
                        statusBar.setText("Respuesta recibida");
                    }
                });
            }
        });
    }

    @SuppressLint("SetTextI18n")
    private void appendResult(String text, String color) {
        TextView tv = new TextView(this);
        tv.setText(text);
        tv.setTextSize(13);
        tv.setTextColor(Color.parseColor(color));
        tv.setPadding(12, 4, 12, 4);
        tv.setGravity(Gravity.START);
        tv.setBackgroundColor(Color.parseColor("#0d0d1a"));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
        );
        params.setMargins(0, 2, 0, 2);
        tv.setLayoutParams(params);
        resultsContainer.addView(tv);
        scrollResults.post(() -> scrollResults.fullScroll(ScrollView.FOCUS_DOWN));
    }
}
