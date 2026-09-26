package com.ame.ecosystem;

import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import androidx.appcompat.app.AppCompatActivity;
import android.view.View;
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.Random;

public class TacticalConsoleActivity extends AppCompatActivity {

    private TextView tvCpuBar;
    private TextView tvRamBar;
    private TextView tvDiskBar;
    private TextView tvPortsStatus;
    private TextView tvAdbStatus;
    private TextView tvConsole;
    private ScrollView scrollConsole;
    private Button btnRefreshTelemetry;
    private Button btnStartMonitor;

    private boolean monitoring = false;
    private Handler handler = new Handler();
    private Random random = new Random();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_tactical_console);

        tvCpuBar = findViewById(R.id.tvCpuBar);
        tvRamBar = findViewById(R.id.tvRamBar);
        tvDiskBar = findViewById(R.id.tvDiskBar);
        tvPortsStatus = findViewById(R.id.tvPortsStatus);
        tvAdbStatus = findViewById(R.id.tvAdbStatus);
        tvConsole = findViewById(R.id.tvConsole);
        scrollConsole = findViewById(R.id.scrollConsole);
        btnRefreshTelemetry = findViewById(R.id.btnRefreshTelemetry);
        btnStartMonitor = findViewById(R.id.btnStartMonitor);

        btnRefreshTelemetry.setOnClickListener(v -> refreshTelemetry());
        btnStartMonitor.setOnClickListener(v -> {
            if (!monitoring) startMonitoring();
            else stopMonitoring();
        });

        appendConsole("╔══════════════════════════════════════╗");
        appendConsole("║  AURA TACTICAL CONSOLE v2.0          ║");
        appendConsole("║  Backend: /api/v1/telemetry          ║");
        appendConsole("║  PC Local → Android Emulator          ║");
        appendConsole("╚══════════════════════════════════════╝");
        appendConsole("");

        refreshTelemetry();
    }

    private void refreshTelemetry() {
        tvConsole.setText("");
        appendConsole("[" + System.currentTimeMillis() + "] Fetching telemetry...");

        simularTelemetria();
    }

    private void simularTelemetria() {
        int cpu = 15 + random.nextInt(50);
        int ram = 30 + random.nextInt(50);
        int disk = 40 + random.nextInt(40);

        tvCpuBar.setText(buildBar("CPU", cpu, "#00FF41"));
        tvRamBar.setText(buildBar("RAM", ram, "#3B82F6"));
        tvDiskBar.setText(buildBar("DISK", disk, "#FFD700"));

        boolean port5000 = random.nextBoolean();
        boolean port5555 = true;

        tvPortsStatus.setText(buildPortStatus(5000, "FastAPI", port5000));
        tvAdbStatus.setText(buildPortStatus(5555, "ADB", port5555));

        appendConsole("│ [SYSTEM] CPU: " + cpu + "% | RAM: " + ram + "% | DISK: " + disk + "%");
        appendConsole("│ [PORTS] :5000 " + (port5000 ? "ONLINE" : "OFFLINE")
                + " | :5555 ADB ONLINE");
        appendConsole("│ [ADB] emulator-5554 connected");

        if (cpu > 80) {
            appendConsole("│ ⚠️ [ALERT] CPU > 80% — High load detected");
        }
        if (ram > 80) {
            appendConsole("│ ⚠️ [ALERT] RAM > 80% — Memory pressure");
        }
        if (!port5000) {
            appendConsole("│ ❌ [ALERT] FastAPI :5000 DOWN — Backend needs restart");
        }

        appendConsole("│ [HF] HuggingFace inference: STANDBY");
        appendConsole("│ [GitHub] Sync: OK");
        appendConsole("│");
        appendConsole("└─── Snapshot: " + System.currentTimeMillis());
        appendConsole("");

        scrollConsole.fullScroll(View.FOCUS_DOWN);
    }

    private void startMonitoring() {
        monitoring = true;
        btnStartMonitor.setText("■ STOP MONITOR");
        btnStartMonitor.setTextColor(Color.RED);
        appendConsole("▶ [INFO] Continuous monitoring started (5s interval)");
        monitorLoop();
    }

    private void stopMonitoring() {
        monitoring = false;
        btnStartMonitor.setText("▶ MONITOR");
        btnStartMonitor.setTextColor(Color.parseColor("#3B82F6"));
        appendConsole("■ [INFO] Monitoring stopped");
        handler.removeCallbacksAndMessages(null);
    }

    private void monitorLoop() {
        if (!monitoring) return;
        simularTelemetria();
        handler.postDelayed(this::monitorLoop, 5000);
    }

    private String buildBar(String label, int percent, String color) {
        int filled = percent * 20 / 100;
        int empty = 20 - filled;
        StringBuilder bar = new StringBuilder();
        for (int i = 0; i < filled; i++) bar.append("█");
        for (int i = 0; i < empty; i++) bar.append("░");
        return label + "  " + bar + "  " + percent + "%";
    }

    private String buildPortStatus(int port, String name, boolean active) {
        String icon = active ? "●" : "○";
        String text = active ? "ONLINE" : "OFFLINE";
        String color = active ? "#00FF41" : "#FF6B6B";
        return String.format("Port %d (%-8s) %s %s", port, name, icon, text);
    }

    private void appendConsole(String text) {
        tvConsole.append(text + "\n");
    }
}
