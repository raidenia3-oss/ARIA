
package com.ame.ecosystem;

import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ImageButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import com.ame.ecosystem.api.GbrainApiClient;
import com.ame.ecosystem.api.GbrainService;

import java.util.Map;
import java.util.UUID;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * GBrain Tactical Chat Activity.
 * Panel de chat de inteligencia IA local (sin censura).
 * Se conecta a AURA Core -> Ollama local via /api/v1/gbrain/tactical-chat.
 *
 * Caracteristicas:
 * - Modos: Tactical / OSINT / Creative / Strict
 * - ProgressBar visual durante generacion (evita ANR)
 * - Sesion con historial (session_id)
 * - Tema oscuro tactico (GitHub Dark)
 * - Llamadas asincronas con Retrofit (no bloquea UI)
 */
public class GbrainChatActivity extends AppCompatActivity {

    private LinearLayout layoutMessages;
    private ScrollView scrollMessages;
    private EditText etMessage;
    private ImageButton btnSend;
    private LinearLayout layoutLoading;
    private TextView tvLoadingText;
    private TextView tvConnectionStatus;
    private TextView tvModelInfo;
    private Spinner spinnerMode;

    private GbrainService gbrainService;
    private String sessionId;
    private boolean isLoading = false;
    private final Handler handler = new Handler(Looper.getMainLooper());

    // Modos disponibles
    private final String[] modeLabels = {"Tactical", "OSINT", "Creative", "Strict"};
    private final String[] modeKeys = {"tactical", "osint", "creative", "strict"};

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_gbrain_chat);

        // Generar sesion unica
        sessionId = "mobile_" + UUID.randomUUID().toString().substring(0, 8);

        // Inicializar vistas
        initViews();

        // Inicializar servicio Retrofit usando GbrainApiClient
        gbrainService = GbrainApiClient.getInstance().getService();

        // Configurar spinner de modos
        ArrayAdapter<String> modeAdapter = new ArrayAdapter<>(this,
            android.R.layout.simple_spinner_item, modeLabels);
        modeAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerMode.setAdapter(modeAdapter);

        // Mensajes de bienvenida
        addSystemMessage("\uD83E\uDDE0 GBrain Tactical Chat v1.0");
        addSystemMessage("IA local sin censura via AURA Core + Ollama");
        addSystemMessage("Sesion: " + sessionId);
        addSystemMessage("Modos: Tactical | OSINT | Creative | Strict");
        addSystemMessage("─────────────────────────");

        // Verificar salud del backend
        checkHealth();

        // Evento enviar mensaje
        btnSend.setOnClickListener(v -> sendMessage());
    }

    private void initViews() {
        layoutMessages = findViewById(R.id.layoutMessages);
        scrollMessages = findViewById(R.id.scrollMessages);
        etMessage = findViewById(R.id.etMessage);
        btnSend = findViewById(R.id.btnSend);
        layoutLoading = findViewById(R.id.layoutLoading);
        tvLoadingText = findViewById(R.id.tvLoadingText);
        tvConnectionStatus = findViewById(R.id.tvConnectionStatus);
        tvModelInfo = findViewById(R.id.tvModelInfo);
        spinnerMode = findViewById(R.id.spinnerMode);
    }

    private void sendMessage() {
        String message = etMessage.getText().toString().trim();
        if (message.isEmpty() || isLoading) return;

        // Mostrar mensaje del usuario
        addUserMessage(message);
        etMessage.setText("");

        // Obtener modo seleccionado
        int idx = spinnerMode.getSelectedItemPosition();
        String mode = modeKeys[idx];

        // Mostrar loading
        setLoading(true);

        // Construir request con session_id para mantener contexto
        GbrainService.TacticalChatRequest request =
            new GbrainService.TacticalChatRequest(message, mode)
                .withSession(sessionId);

        // Llamada asincrona con Retrofit -> sin ANR
        gbrainService.tacticalChat(request).enqueue(new Callback<Map<String, Object>>() {
            @Override
            public void onResponse(Call<Map<String, Object>> call,
                                   Response<Map<String, Object>> response) {
                handler.post(() -> {
                    setLoading(false);
                    if (response.isSuccessful() && response.body() != null) {
                        Map<String, Object> body = response.body();
                        String responseText = (String) body.get("response");
                        double duration = ((Number) body.get("duration_ms")).doubleValue();
                        int tokens = ((Number) body.get("tokens_eval")).intValue();

                        addBotMessage(responseText);
                        addSystemMessage("\u23F1 " + (int)duration + "ms | \uD83D\uDD22 "
                            + tokens + " tokens | Modo: " + body.get("mode"));
                    } else {
                        addErrorMessage("Error HTTP " + response.code());
                    }
                });
            }

            @Override
            public void onFailure(Call<Map<String, Object>> call, Throwable t) {
                handler.post(() -> {
                    setLoading(false);
                    addErrorMessage("Error de conexion: " + t.getMessage());
                    addSystemMessage("\uD83D\uDCA1 Verifica que AURA Core este corriendo en la PC");
                    tvConnectionStatus.setText("\u25CF OFFLINE");
                    tvConnectionStatus.setTextColor(0xFFFF7B72);
                });
            }
        });
    }

    private void checkHealth() {
        gbrainService.healthCheck().enqueue(new Callback<Map<String, Object>>() {
            @Override
            public void onResponse(Call<Map<String, Object>> call,
                                   Response<Map<String, Object>> response) {
                handler.post(() -> {
                    if (response.isSuccessful() && response.body() != null) {
                        Map<String, Object> body = response.body();
                        String status = (String) body.get("status");
                        if ("online".equals(status)) {
                            tvConnectionStatus.setText("\u25CF ONLINE");
                            tvConnectionStatus.setTextColor(0xFF3FB950);
                            addSystemMessage("Ollama activo | Latencia: "
                                + body.get("latency_ms") + "ms");
                            // Cargar modelos
                            loadModels();
                        } else {
                            tvConnectionStatus.setText("\u25CF DEGRADED");
                            tvConnectionStatus.setTextColor(0xFFD29922);
                        }
                    }
                });
            }

            @Override
            public void onFailure(Call<Map<String, Object>> call, Throwable t) {
                handler.post(() -> {
                    tvConnectionStatus.setText("\u25CF OFFLINE");
                    tvConnectionStatus.setTextColor(0xFFFF7B72);
                    addSystemMessage("No se puede conectar a AURA Core");
                    addSystemMessage("\uD83D\uDCA1 Inicia AURA Core y Ollama en la PC");
                });
            }
        });
    }

    private void loadModels() {
        gbrainService.listModels().enqueue(new Callback<Map<String, Object>>() {
            @Override
            public void onResponse(Call<Map<String, Object>> call,
                                   Response<Map<String, Object>> response) {
                if (response.isSuccessful() && response.body() != null) {
                    Map<String, Object> body = response.body();
                    String defaultModel = (String) body.get("default");
                    if (defaultModel != null) {
                        tvModelInfo.setText(defaultModel);
                    }
                }
            }

            @Override
            public void onFailure(Call<Map<String, Object>> call, Throwable t) {
                // Silencioso: los modelos son solo informativos
            }
        });
    }

    private void setLoading(boolean show) {
        isLoading = show;
        layoutLoading.setVisibility(show ? View.VISIBLE : View.GONE);
        etMessage.setEnabled(!show);
        btnSend.setEnabled(!show);
        if (show) {
            tvLoadingText.setText("GBrain procesando en la PC...");
        }
    }

    private void addUserMessage(String msg) {
        TextView tv = createMessageView(msg, 0xFF1F6FEB,
            Gravity.END, "\uD83D\uDC64");
        layoutMessages.addView(tv);
        scrollToBottom();
    }

    private void addBotMessage(String msg) {
        TextView tv = createMessageView(msg, 0xFF21262D,
            Gravity.START, "\uD83E\uDDE0");
        layoutMessages.addView(tv);
        scrollToBottom();
    }

    private void addSystemMessage(String msg) {
        TextView tv = new TextView(this);
        tv.setText(msg);
        tv.setTextColor(0xFF8B949E);
        tv.setTextSize(11);
        tv.setPadding(8, 4, 8, 4);
        tv.setGravity(Gravity.CENTER);
        layoutMessages.addView(tv);
        scrollToBottom();
    }

    private void addErrorMessage(String msg) {
        TextView tv = new TextView(this);
        tv.setText("\u274C " + msg);
        tv.setTextColor(0xFFFF7B72);
        tv.setTextSize(13);
        tv.setPadding(16, 8, 16, 8);
        tv.setBackgroundColor(0x33FF7B72);
        // Margen
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 4, 0, 4);
        tv.setLayoutParams(params);
        tv.setGravity(Gravity.CENTER);
        layoutMessages.addView(tv);
        scrollToBottom();
    }

    private TextView createMessageView(String msg, int bgColor,
                                        int gravity, String prefix) {
        TextView tv = new TextView(this);
        tv.setText(prefix + " " + msg);
        tv.setTextColor(0xFFC9D1D9);
        tv.setTextSize(14);
        tv.setPadding(16, 12, 16, 12);
        tv.setBackgroundColor(bgColor);
        tv.setGravity(Gravity.START | Gravity.CENTER_VERTICAL);

        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            LinearLayout.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, 4, 0, 4);
        tv.setLayoutParams(params);
        return tv;
    }

    private void scrollToBottom() {
        scrollMessages.post(() ->
            scrollMessages.fullScroll(ScrollView.FOCUS_DOWN));
    }
}
