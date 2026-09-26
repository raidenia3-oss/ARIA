package com.ame.ecosystem;

import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.TextView;
import android.widget.ViewFlipper;
import android.widget.Toast;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.appcompat.app.AppCompatActivity;

import com.ame.ecosystem.api.OsintApiClient;
import com.ame.ecosystem.plugins.AuraPlugin;

import java.util.Map;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class MainActivity extends AppCompatActivity {

    private ViewFlipper viewFlipper;
    private Button btnHome, btnOSINT, btnTarget, btnNetwork, btnChat, btnCheckStatus, btnConsole;
    private TextView tvStatus;
    private EditText etOSINTQuery, etTargetUsername, etNetworkTarget, etChatMessage;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        viewFlipper = findViewById(R.id.viewFlipper);
        btnHome = findViewById(R.id.btnHome);
        btnOSINT = findViewById(R.id.btnOSINT);
        btnTarget = findViewById(R.id.btnTarget);
        btnNetwork = findViewById(R.id.btnNetwork);
        btnChat = findViewById(R.id.btnChat);
        btnCheckStatus = findViewById(R.id.btnCheckStatus);
        tvStatus = findViewById(R.id.tvStatus);

        etOSINTQuery = findViewById(R.id.etOSINTQuery);
        etTargetUsername = findViewById(R.id.etTargetUsername);
        etNetworkTarget = findViewById(R.id.etNetworkTarget);
        etChatMessage = findViewById(R.id.etChatMessage);

        btnOSINT.setOnClickListener(v -> viewFlipper.setDisplayedChild(1));
        // btnTarget → Mapa Geopolítico Global
        btnTarget.setOnClickListener(v -> {
            startActivity(new Intent(MainActivity.this, GlobalMapActivity.class));
        });
        // btnNetwork → Venice Scanner (External Recon)
        btnNetwork.setOnClickListener(v -> {
            startActivity(new Intent(MainActivity.this, VeniceScannerActivity.class));
        });
        // btnChat → GBrain Chat (Hugging Face)
        btnChat.setOnClickListener(v -> {
            startActivity(new Intent(MainActivity.this, GbrainChatActivity.class));
        });
        btnConsole = findViewById(R.id.btnConsole);
        if (btnConsole != null) {
            btnConsole.setOnClickListener(v -> {
                startActivity(new Intent(MainActivity.this, TacticalConsoleActivity.class));
            });
        }
        btnHome.setOnClickListener(v -> viewFlipper.setDisplayedChild(0));
        btnCheckStatus.setOnClickListener(v -> checkStatus());

        // Inicializar plugin AURA para servicios de fondo
        AuraPlugin.init(getApplicationContext());

        checkStatus();
    }

    private void startAuraService() {
        if (!AuraPlugin.hasOverlayPermission()) {
            AuraPlugin.requestOverlayPermission(this);
            Toast.makeText(this, "Otorga permiso de overlay", Toast.LENGTH_LONG).show();
            return;
        }
        AuraPlugin.startPassiveService("ws://192.168.0.100:8765");
        Toast.makeText(this, "Servicio AURA activado", Toast.LENGTH_SHORT).show();
    }

    private void startBubble() {
        if (!AuraPlugin.hasOverlayPermission()) {
            AuraPlugin.requestOverlayPermission(this);
            Toast.makeText(this, "Otorga permiso de overlay", Toast.LENGTH_LONG).show();
            return;
        }
        AuraPlugin.startBubbleService();
        Toast.makeText(this, "Burbuja flotante activada", Toast.LENGTH_SHORT).show();
    }

    private void checkStatus() {
        tvStatus.setText("Verificando conexión con AURA Core...");
        OsintApiClient.getInstance().getService().health().enqueue(new Callback<Map<String, Object>>() {
            @Override
            public void onResponse(Call<Map<String, Object>> call, Response<Map<String, Object>> response) {
                if (response.isSuccessful() && response.body() != null) {
                    tvStatus.setText("✅ AURA Core activo\nVersión: " + response.body().getOrDefault("version", "?"));
                    tvStatus.setTextColor(getResources().getColor(R.color.accentGreen));
                } else {
                    tvStatus.setText("❌ Error: " + response.message());
                    tvStatus.setTextColor(getResources().getColor(R.color.accentRed));
                }
            }

            @Override
            public void onFailure(Call<Map<String, Object>> call, Throwable t) {
                tvStatus.setText("❌ Sin conexión: " + t.getMessage());
                tvStatus.setTextColor(getResources().getColor(R.color.accentRed));
            }
        });
    }

    public void navigateToOsintRecon() {
        OsintReconActivity.startActivity(this);
    }
}
