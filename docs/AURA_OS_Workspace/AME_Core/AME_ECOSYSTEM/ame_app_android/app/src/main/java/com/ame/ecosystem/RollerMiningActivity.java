package com.ame.ecosystem;

import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import androidx.appcompat.app.AppCompatActivity;
import android.view.View;
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.Random;

import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

public class RollerMiningActivity extends AppCompatActivity {

    private TextView tvMiningStatus, tvPowerBar, tvGamesBar, tvWonBar, tvLastGame, tvLastReward, tvCooldown, tvMiningLog;
    private ScrollView scrollMiningLog;
    private Button btnStartMining, btnStopMining, btnRefreshMining;
    private Handler handler = new Handler();
    private boolean mining = false;
    private final OkHttpClient client = new OkHttpClient.Builder().connectTimeout(3, java.util.concurrent.TimeUnit.SECONDS).readTimeout(3, java.util.concurrent.TimeUnit.SECONDS).build();
    private static final MediaType JSON = MediaType.parse("application/json; charset=utf-8");
    private static final String BASE = "http://10.0.2.2:5000";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_roller_mining);

        tvMiningStatus = findViewById(R.id.tvMiningStatus);
        tvPowerBar = findViewById(R.id.tvPowerBar);
        tvGamesBar = findViewById(R.id.tvGamesBar);
        tvWonBar = findViewById(R.id.tvWonBar);
        tvLastGame = findViewById(R.id.tvLastGame);
        tvLastReward = findViewById(R.id.tvLastReward);
        tvCooldown = findViewById(R.id.tvCooldown);
        tvMiningLog = findViewById(R.id.tvMiningLog);
        scrollMiningLog = findViewById(R.id.scrollMiningLog);
        btnStartMining = findViewById(R.id.btnStartMining);
        btnStopMining = findViewById(R.id.btnStopMining);
        btnRefreshMining = findViewById(R.id.btnRefreshMining);

        btnStartMining.setOnClickListener(v -> httpPost("/api/v1/rollercoin/start", ""));
        btnStopMining.setOnClickListener(v -> httpPost("/api/v1/rollercoin/stop", ""));
        btnRefreshMining.setOnClickListener(v -> pollStatus());

        appendLog("╔══════════════════════════════════════╗");
        appendLog("║  ROLLERCOIN MINING CENTER v3.0       ║");
        appendLog("╚══════════════════════════════════════╝");
        appendLog("│ [BOOT] HTTP backend: " + BASE);
        appendLog("│ [BOOT] Polling cada 3s");
        startPolling();
    }

    private void startPolling() {
        handler.postDelayed(new Runnable() {
            @Override
            public void run() {
                pollStatus();
                handler.postDelayed(this, 3000);
            }
        }, 1000);
    }

    private void pollStatus() {
        Request r = new Request.Builder().url(BASE + "/api/v1/rollercoin/dashboard").get().build();
        client.newCall(r).enqueue(new Callback() {
            @Override public void onFailure(Call call, IOException e) { runOnUiThread(() -> tvMiningStatus.setText("● OFFLINE")); tvMiningStatus.setTextColor(Color.RED); }
            @Override public void onResponse(Call call, Response resp) throws IOException {
                if (!resp.isSuccessful()) return;
                try {
                    JSONObject j = new JSONObject(resp.body().string());
                    runOnUiThread(() -> updateUI(j));
                } catch (JSONException e) { e.printStackTrace(); }
            }
        });
    }

    private void updateUI(JSONObject j) {
        try {
            String st = j.optString("status", "IDLE");
            boolean run = j.optBoolean("running", false);
            mining = run;
            tvMiningStatus.setText(run ? "● RUNNING" : "● " + st);
            tvMiningStatus.setTextColor(run ? Color.parseColor("#00FF41") : Color.parseColor("#FFD700"));
            btnStartMining.setEnabled(!run); btnStopMining.setEnabled(run);

            int gp = j.optInt("games_played", 0), gw = j.optInt("games_won", 0);
            double tp = j.optDouble("total_power", 0);
            String lg = j.optString("last_game", "--"), lr = j.has("last_reward") ? j.optJSONObject("last_reward").optString("amount", "--") : "--";

            tvPowerBar.setText(buildBar("POWER", (int)(tp*1000), "#00FF41"));
            tvGamesBar.setText(buildBar("GAMES", gp, "#3B82F6"));
            tvWonBar.setText(buildBar("WON", gw, "#FFD700"));
            tvLastGame.setText("Último: " + (lg.length()>10 ? lg.substring(11,19) : lg));
            tvLastReward.setText("Reward: " + lr);
            tvCooldown.setText("ADB: " + (j.optBoolean("adb_connected",false)?"CONNECTED":"DISCONNECTED"));

        } catch (Exception e) { e.printStackTrace(); }
    }

    private void httpPost(String path, String body) {
        Request r = new Request.Builder().url(BASE + path).post(RequestBody.create(JSON, body)).build();
        client.newCall(r).enqueue(new Callback() {
            @Override public void onFailure(Call call, IOException e) { appendLog("│ ❌ [HTTP] " + path + " FAILED"); }
            @Override public void onResponse(Call call, Response resp) throws IOException {
                appendLog("│ ✅ [HTTP] " + path + " → " + resp.code());
                pollStatus();
            }
        });
    }

    private void appendLog(String t) { runOnUiThread(() -> { tvMiningLog.append(t+"\n"); scrollMiningLog.fullScroll(View.FOCUS_DOWN); }); }
    private String buildBar(String label, int v, String c) {
        int n = Math.min(v,20); StringBuilder sb = new StringBuilder();
        for(int i=0;i<n;i++) sb.append("█");
        for(int i=0;i<20-n;i++) sb.append("░");
        return label+"  "+sb+"  "+v;
    }
}
