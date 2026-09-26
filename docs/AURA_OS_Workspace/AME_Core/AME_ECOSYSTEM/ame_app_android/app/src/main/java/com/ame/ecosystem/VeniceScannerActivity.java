package com.ame.ecosystem;

import android.animation.ValueAnimator;
import android.graphics.Color;
import android.graphics.Typeface;
import android.os.Bundle;
import android.os.Handler;
import androidx.appcompat.app.AppCompatActivity;
import android.view.Gravity;
import android.view.View;
import android.view.animation.LinearInterpolator;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

public class VeniceScannerActivity extends AppCompatActivity {

    private EditText etTargetIp;
    private Spinner spinnerScanType;
    private EditText etThreads;
    private Button btnStartScan;
    private ProgressBar progressScan;
    private TextView tvScanProgress;
    private TextView tvConsole;
    private ScrollView scrollConsole;

    private boolean scanning = false;
    private Handler handler = new Handler();

    private final String[] scanTypes = {"stealth", "intense", "ports"};

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_venice_scanner);

        etTargetIp = findViewById(R.id.etTargetIp);
        spinnerScanType = findViewById(R.id.spinnerScanType);
        etThreads = findViewById(R.id.etThreads);
        btnStartScan = findViewById(R.id.btnStartScan);
        progressScan = findViewById(R.id.progressScan);
        tvScanProgress = findViewById(R.id.tvScanProgress);
        tvConsole = findViewById(R.id.tvConsole);
        scrollConsole = findViewById(R.id.scrollConsole);

        ArrayAdapter<String> adapter = new ArrayAdapter<>(this,
            android.R.layout.simple_spinner_item, scanTypes);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerScanType.setAdapter(adapter);

        btnStartScan.setOnClickListener(v -> { if (!scanning) startScan(); });

        appendConsole("╔══════════════════════════════════════╗");
        appendConsole("║   AURA SCANNER TERMINAL v2.0         ║");
        appendConsole("║   Motor: VENICE-MOCK                 ║");
        appendConsole("║   Tipos: stealth | intense | ports   ║");
        appendConsole("╚══════════════════════════════════════╝");
    }

    private void startScan() {
        String targetIp = etTargetIp.getText().toString().trim();
        if (targetIp.isEmpty()) { etTargetIp.setError("TARGET IP REQUIRED"); return; }

        String scanType = spinnerScanType.getSelectedItem().toString();
        String threadsStr = etThreads.getText().toString().trim();
        int threads = threadsStr.isEmpty() ? 1 : Integer.parseInt(threadsStr);

        scanning = true;
        btnStartScan.setText("⏳ SCANNING...");
        btnStartScan.setEnabled(false);
        progressScan.setProgress(0);
        progressScan.setVisibility(View.VISIBLE);
        tvScanProgress.setText("INITIALIZING...");
        tvScanProgress.setTextColor(Color.parseColor("#FFD700"));
        tvConsole.setText("");

        animateProgressBar();

        appendConsole("┌─────────────────────────────────────┐");
        appendConsole("│ TARGET: " + targetIp);
        appendConsole("│ TYPE:   " + scanType);
        appendConsole("│ THREADS:" + threads);
        appendConsole("│ TIME:   " + System.currentTimeMillis());
        appendConsole("└─────────────────────────────────────┘");
        appendConsole("");

        simulateProgress(targetIp, scanType, 0);
    }

    private void simulateProgress(final String targetIp, final String scanType, final int step) {
        final String[][] steps = {
            {"INIT",     "████░░░░░░░░░░░░░░░░ 0%  Booting scan engine..."},
            {"DNS",      "████████░░░░░░░░░░░░ 20% Resolving DNS: " + targetIp},
            {"PING",     "██████████░░░░░░░░░░ 30% Host alive check..."},
            {"RECON",    "████████████░░░░░░░░ 50% Passive recon sweep"},
            {"PORTS",    "██████████████░░░░░░ 60% Port scanning..."},
            {"SERVICES", "████████████████░░░░ 80% Service fingerprinting"},
            {"OS",       "██████████████████░░ 90% OS detection..."},
            {"COMPLETE", "████████████████████ 100% ✓ SCAN COMPLETE"},
        };

        if (step >= steps.length) {
            scanning = false;
            btnStartScan.setText("⚡ INITIATE SCAN");
            btnStartScan.setEnabled(true);
            tvScanProgress.setText("COMPLETED — 100%");
            tvScanProgress.setTextColor(Color.parseColor("#00FF41"));

            appendConsole("");
            appendConsole("╔══════════════════════════════════════╗");
            appendConsole("║ # TODO: VENICE_IMPLEMENTATION         ║");
            appendConsole("║ Reemplazar mock con motor real        ║");
            appendConsole("║ de escaneo de Venice Framework.       ║");
            appendConsole("╚══════════════════════════════════════╝");
            return;
        }

        final int progress = (step + 1) * 100 / steps.length;
        final int delay = 500 + (int) (Math.random() * 800);

        handler.postDelayed(() -> {
            progressScan.setProgress(progress);
            tvScanProgress.setText(steps[step][0] + " — " + progress + "%");
            appendConsole("[" + steps[step][0] + "] " + steps[step][1]);

            if (steps[step][0].equals("PORTS")) {
                appendConsole("  ├─ 22/tcp   OPEN  SSH");
                appendConsole("  ├─ 80/tcp   OPEN  HTTP");
                appendConsole("  └─ 443/tcp  OPEN  HTTPS");
            }
            if (steps[step][0].equals("SERVICES")) {
                appendConsole("  ├─ ssh:  OpenSSH 8.9p1");
                appendConsole("  ├─ http: nginx/1.24.0");
                appendConsole("  └─ tls:  TLS 1.3 (ECDHE)");
            }
            if (steps[step][0].equals("OS")) {
                appendConsole("  └─ OS: Linux 5.15 x86_64 (99%)");
            }
            scrollConsole.fullScroll(View.FOCUS_DOWN);
            simulateProgress(targetIp, scanType, step + 1);
        }, delay);
    }

    private void animateProgressBar() {
        if (!scanning) return;
        progressScan.animate().cancel();
    }

    private void appendConsole(String text) {
        tvConsole.append(text + "\n");
    }
}
