package com.ame.ecosystem;

import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.ame.ecosystem.api.OsintApiClient;
import com.ame.ecosystem.api.OSINTScanRequest;
import com.ame.ecosystem.api.GoogleDorkRequest;
import com.google.android.material.textfield.TextInputEditText;

import java.util.List;
import java.util.Map;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class OsintReconActivity extends AppCompatActivity {

    // UI Components
    private TextInputEditText etTarget, etDorkTerm, etDorkFileType, etDorkSite;
    private Spinner spinnerTargetType;
    private Button btnScan, btnDorks, btnFramework, btnGenerateDork;
    private TextView tvConnectionStatus, tvScanStatus, tvResultsMeta, tvDorkResult, tvFrameworkContent;
    private LinearLayout layoutResults, layoutDorks, layoutFramework;
    private ProgressBar progressBar;

    private final String[] targetTypes = {"Auto (detect)", "Email", "Username", "Domain/IP", "IP Address"};

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_osint_recon);

        initViews();
        setupSpinner();
        setupClickListeners();
        checkHealth();
    }

    public static void startActivity(Context context) {
        Intent intent = new Intent(context, OsintReconActivity.class);
        context.startActivity(intent);
    }

    private void initViews() {
        etTarget = findViewById(R.id.etTarget);
        etDorkTerm = findViewById(R.id.etDorkTerm);
        etDorkFileType = findViewById(R.id.etDorkFileType);
        etDorkSite = findViewById(R.id.etDorkSite);

        spinnerTargetType = findViewById(R.id.spinnerTargetType);

        btnScan = findViewById(R.id.btnScan);
        btnDorks = findViewById(R.id.btnDorks);
        btnFramework = findViewById(R.id.btnFramework);
        btnGenerateDork = findViewById(R.id.btnGenerateDork);

        tvConnectionStatus = findViewById(R.id.tvConnectionStatus);
        tvScanStatus = findViewById(R.id.tvScanStatus);
        tvResultsMeta = findViewById(R.id.tvResultsMeta);
        tvDorkResult = findViewById(R.id.tvDorkResult);
        tvFrameworkContent = findViewById(R.id.tvFrameworkContent);

        layoutResults = findViewById(R.id.layoutResults);
        layoutDorks = findViewById(R.id.layoutDorks);
        layoutFramework = findViewById(R.id.layoutFramework);

        progressBar = findViewById(R.id.progressBar);
    }

    private void setupSpinner() {
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
                android.R.layout.simple_spinner_dropdown_item, targetTypes);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerTargetType.setAdapter(adapter);
    }

    private void setupClickListeners() {
        btnScan.setOnClickListener(v -> executeScan());
        btnDorks.setOnClickListener(v -> toggleSection(layoutDorks, layoutFramework));
        btnFramework.setOnClickListener(v -> {
            toggleSection(layoutFramework, layoutDorks);
            loadFrameworkTree();
        });
        btnGenerateDork.setOnClickListener(v -> generateDork());
    }

    private void toggleSection(LinearLayout show, LinearLayout hide) {
        boolean isVisible = show.getVisibility() == View.VISIBLE;
        show.setVisibility(isVisible ? View.GONE : View.VISIBLE);
        hide.setVisibility(View.GONE);
    }

    // ─── Health Check ───────────────────────────────────
    private void checkHealth() {
        tvConnectionStatus.setText("● Conectando con AURA Core...");
        tvConnectionStatus.setTextColor(getResources().getColor(R.color.warning));

        OsintApiClient.getInstance().getService().health().enqueue(new Callback<Map<String, Object>>() {
            @Override
            public void onResponse(Call<Map<String, Object>> call, Response<Map<String, Object>> r) {
                if (r.isSuccessful() && r.body() != null) {
                    tvConnectionStatus.setText("● Conectado a AURA Core | v" + r.body().getOrDefault("version", "?"));
                    tvConnectionStatus.setTextColor(getResources().getColor(R.color.accentGreen));
                } else {
                    setConnectionError("Respuesta inválida del servidor");
                }
            }
            @Override
            public void onFailure(Call<Map<String, Object>> call, Throwable t) {
                setConnectionError(t.getMessage());
            }
        });
    }

    private void setConnectionError(String detail) {
        tvConnectionStatus.setText("✖ Sin conexión: " + detail);
        tvConnectionStatus.setTextColor(getResources().getColor(R.color.accentRed));
    }

    // ─── Scan Execution ─────────────────────────────────
    private void executeScan() {
        String target = etTarget.getText().toString().trim();
        if (target.isEmpty()) {
            Toast.makeText(this, "Introduce un objetivo primero", Toast.LENGTH_SHORT).show();
            return;
        }

        String targetType = convertTargetType(spinnerTargetType.getSelectedItemPosition());

        showProgress("Escaneando " + target + " (" + targetType + ")...");
        layoutResults.removeAllViews();

        OSINTScanRequest req = new OSINTScanRequest(target, targetType);
        OsintApiClient.getInstance().getService().scanTarget(req).enqueue(new Callback<Map<String, Object>>() {
            @Override
            public void onResponse(Call<Map<String, Object>> call, Response<Map<String, Object>> r) {
                hideProgress();
                if (r.isSuccessful() && r.body() != null) {
                    renderResults(r.body());
                } else {
                    appendResult("❌ Error: " + r.code() + " - " + r.message());
                }
            }
            @Override
            public void onFailure(Call<Map<String, Object>> call, Throwable t) {
                hideProgress();
                appendResult("❌ Error de conexión: " + t.getMessage());
            }
        });
    }

    private String convertTargetType(int position) {
        switch (position) {
            case 1: return "email";
            case 2: return "username";
            case 3: return "domain";
            case 4: return "ip";
            default: return "auto";
        }
    }

    // ─── Results Rendering ──────────────────────────────
    @SuppressWarnings("unchecked")
    private void renderResults(Map<String, Object> data) {
        String target = (String) data.getOrDefault("target", "?");
        String targetType = (String) data.getOrDefault("target_type", "?");
        double execTime = (double) data.getOrDefault("execution_time_seconds", 0.0);
        int toolsExec = ((Number) data.getOrDefault("tools_executed", 0)).intValue();
        int toolsWithResults = ((Number) data.getOrDefault("tools_with_results", 0)).intValue();

        tvResultsMeta.setVisibility(View.VISIBLE);
        tvResultsMeta.setText(String.format("Objetivo: %s (%s) | %d herramientas | %.1fs",
                target, targetType, toolsExec, execTime));

        Map<String, Object> sections = (Map<String, Object>) data.get("sections");
        if (sections == null || sections.isEmpty()) {
            appendResult("No se encontraron resultados");
            return;
        }

        for (Map.Entry<String, Object> entry : sections.entrySet()) {
            String toolName = entry.getKey();
            Map<String, Object> toolData = (Map<String, Object>) entry.getValue();
            String status = (String) toolData.getOrDefault("status", "unknown");

            TextView header = new TextView(this);
            String icon = status.equals("error") ? "❌" : "✅";
            header.setText(String.format("%s %s [%s]", icon, toolName, status));
            header.setTextColor(status.equals("error") ? getResources().getColor(R.color.accentRed) : getResources().getColor(R.color.accentGreen));
            header.setTextSize(14f);
            header.setPadding(8, 16, 8, 4);
            layoutResults.addView(header);

            if (status.equals("error")) {
                String errMsg = (String) toolData.getOrDefault("error", "Error desconocido");
                appendResult("  " + errMsg);
                continue;
            }

            Object dataResult = toolData.get("data");
            if (dataResult instanceof List) {
                List<Object> items = (List<Object>) dataResult;
                if (items.isEmpty()) {
                    appendResult("  Sin datos");
                } else {
                    for (Object item : items) {
                        appendResult("  • " + item.toString());
                    }
                }
            } else if (dataResult instanceof Map) {
                Map<String, Object> map = (Map<String, Object>) dataResult;
                for (Map.Entry<String, Object> e : map.entrySet()) {
                    appendResult("  " + e.getKey() + ": " + e.getValue());
                }
            } else if (dataResult != null) {
                appendResult("  " + dataResult.toString());
            } else {
                appendResult("  Sin datos");
            }
        }
    }

    private void appendResult(String text) {
        TextView tv = new TextView(this);
        tv.setText(text);
        tv.setTextColor(getResources().getColor(R.color.textPrimary));
        tv.setTextSize(12f);
        tv.setPadding(8, 4, 8, 4);
        tv.setEllipsize(TextUtils.TruncateAt.END);
        tv.setMaxLines(3);
        layoutResults.addView(tv);
    }

    // ─── Google Dorks ───────────────────────────────────
    private void generateDork() {
        String term = etDorkTerm.getText().toString().trim();
        String fileType = etDorkFileType.getText().toString().trim().isEmpty() ? "pdf" : etDorkFileType.getText().toString().trim();
        String site = etDorkSite.getText().toString().trim();

        if (term.isEmpty()) {
            Toast.makeText(this, "Introduce un término de búsqueda", Toast.LENGTH_SHORT).show();
            return;
        }

        tvDorkResult.setVisibility(View.VISIBLE);
        tvDorkResult.setText("Generando dork...");

        GoogleDorkRequest req = site.isEmpty() ? new GoogleDorkRequest(term, fileType) : new GoogleDorkRequest(term, fileType, site);
        OsintApiClient.getInstance().getService().generateDork(req).enqueue(new Callback<Map<String, Object>>() {
            @Override
            public void onResponse(Call<Map<String, Object>> call, Response<Map<String, Object>> r) {
                if (r.isSuccessful() && r.body() != null) {
                    String dorkQuery = (String) r.body().getOrDefault("dork_query", "");
                    String googleUrl = (String) r.body().getOrDefault("google_url", "");
                    tvDorkResult.setText("📌 Dork: " + dorkQuery + "\n\n🔗 " + googleUrl);
                    tvDorkResult.setTextColor(getResources().getColor(R.color.accentGreen));
                }
            }
            @Override
            public void onFailure(Call<Map<String, Object>> call, Throwable t) {
                tvDorkResult.setText("❌ Error: " + t.getMessage());
                tvDorkResult.setTextColor(getResources().getColor(R.color.accentRed));
            }
        });
    }

    // ─── OSINT Framework ────────────────────────────────
    @SuppressWarnings("unchecked")
    private void loadFrameworkTree() {
        tvFrameworkContent.setText("Cargando OSINT Framework...");

        OsintApiClient.getInstance().getService().getFrameworkTree().enqueue(new Callback<Map<String, Object>>() {
            @Override
            public void onResponse(Call<Map<String, Object>> call, Response<Map<String, Object>> r) {
                if (r.isSuccessful() && r.body() != null) {
                    StringBuilder sb = new StringBuilder();
                    List<Map<String, Object>> categories = (List<Map<String, Object>>) r.body().get("categories");

                    if (categories != null) {
                        for (Map<String, Object> cat : categories) {
                            String name = (String) cat.getOrDefault("name", "");
                            String icon = (String) cat.getOrDefault("icon", "");
                            sb.append("\n").append(icon).append(" ").append(name).append("\n");
                            sb.append("─────────────────\n");

                            List<Map<String, Object>> tools = (List<Map<String, Object>>) cat.get("tools");
                            if (tools != null) {
                                for (Map<String, Object> tool : tools) {
                                    String toolName = (String) tool.getOrDefault("name", "");
                                    String desc = (String) tool.getOrDefault("description", "");
                                    String url = (String) tool.getOrDefault("url", "");
                                    sb.append("  • ").append(toolName).append("\n");
                                    sb.append("    ").append(desc).append("\n");
                                }
                            }
                            sb.append("\n");
                        }
                    }
                    tvFrameworkContent.setText(sb.length() > 0 ? sb.toString() : "No hay datos del framework");
                }
            }
            @Override
            public void onFailure(Call<Map<String, Object>> call, Throwable t) {
                tvFrameworkContent.setText("❌ Error al cargar framework: " + t.getMessage());
            }
        });
    }

    // ─── Progress Helpers ───────────────────────────────
    private void showProgress(String status) {
        progressBar.setVisibility(View.VISIBLE);
        tvScanStatus.setVisibility(View.VISIBLE);
        tvScanStatus.setText(status);
    }

    private void hideProgress() {
        progressBar.setVisibility(View.GONE);
        tvScanStatus.setVisibility(View.GONE);
    }
}