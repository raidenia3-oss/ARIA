package com.ame.ecosystem.services;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.util.Log;
import android.view.Gravity;
import android.view.LayoutInflater;
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import com.ame.ecosystem.MainActivity;

import androidx.core.app.NotificationCompat;

/**
 * FloatingBubbleService — Overlay con burbuja flotante + panel expandible
 * Panel: Bot toggle, OSINT scanner, Chat IA (GBrian)
 */
public class FloatingBubbleService extends Service {
    private static final String TAG = "FloatBubble";
    private static final String CHANNEL_ID = "aura_bubble_channel";
    private static final int NOTIFICATION_ID = 9998;

    private WindowManager windowManager;
    private View bubbleView;
    private View panelView;
    private WindowManager.LayoutParams bubbleParams;
    private WindowManager.LayoutParams panelParams;
    private boolean panelVisible = false;
    private boolean botRunning = false;

    @Override
    public void onCreate() {
        super.onCreate();
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        createNotificationChannel();
        startForeground();
        createBubble();
        createPanel();
    }

    private void createBubble() {
        // Burbuja circular de 60dp
        bubbleView = new View(this);
        GradientDrawable circle = new GradientDrawable();
        circle.setShape(GradientDrawable.OVAL);
        circle.setColor(0xFF58A6FF);
        circle.setStroke(2, 0xFFFFFFFF);
        bubbleView.setBackground(circle);
        int sizePx = dpToPx(56);
        bubbleView.setMinimumWidth(sizePx);
        bubbleView.setMinimumHeight(sizePx);

        int type = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;

        bubbleParams = new WindowManager.LayoutParams(
                sizePx, sizePx,
                type,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE,
                PixelFormat.TRANSLUCENT
        );
        bubbleParams.gravity = Gravity.TOP | Gravity.START;
        bubbleParams.x = dpToPx(16);
        bubbleParams.y = dpToPx(300);

        // Touch listener: drag + tap
        final float[] touchX = new float[2];
        final float[] touchY = new float[2];
        final int[] startPos = new int[2];
        final boolean[] moved = {false};

        bubbleView.setOnTouchListener((v, event) -> {
            switch (event.getAction()) {
                case MotionEvent.ACTION_DOWN:
                    touchX[0] = event.getRawX();
                    touchY[0] = event.getRawY();
                    startPos[0] = bubbleParams.x;
                    startPos[1] = bubbleParams.y;
                    moved[0] = false;
                    return true;
                case MotionEvent.ACTION_MOVE:
                    float dx = event.getRawX() - touchX[0];
                    float dy = event.getRawY() - touchY[0];
                    if (Math.abs(dx) > 5 || Math.abs(dy) > 5) moved[0] = true;
                    bubbleParams.x = startPos[0] + (int) dx;
                    bubbleParams.y = startPos[1] + (int) dy;
                    windowManager.updateViewLayout(bubbleView, bubbleParams);
                    return true;
                case MotionEvent.ACTION_UP:
                    if (!moved[0]) togglePanel();
                    return true;
            }
            return false;
        });

        windowManager.addView(bubbleView, bubbleParams);
    }

    private void togglePanel() {
        if (panelVisible) {
            try { windowManager.removeView(panelView); } catch (Exception ignored) {}
            panelVisible = false;
        } else {
            if (panelView == null) createPanel();
            try { windowManager.addView(panelView, panelParams); } catch (Exception ignored) {}
            panelVisible = true;
        }
    }

    private void createPanel() {
        Context ctx = this;
        int panelW = dpToPx(280);
        int panelH = dpToPx(360);
        int type = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;

        panelParams = new WindowManager.LayoutParams(
                panelW, panelH,
                type,
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT
        );
        panelParams.gravity = Gravity.TOP | Gravity.START;
        panelParams.x = dpToPx(16);
        panelParams.y = dpToPx(200);

        LinearLayout panel = new LinearLayout(ctx);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dpToPx(12), dpToPx(10), dpToPx(12), dpToPx(10));
        GradientDrawable bg = new GradientDrawable();
        bg.setCornerRadius(dpToPx(16));
        bg.setColor(0xF00D1117);
        bg.setStroke(1, 0xFF30363D);
        panel.setBackground(bg);

        // ─── Título ─────────────────────────────
        TextView title = new TextView(ctx);
        title.setText("🧠 AURA Quick Panel");
        title.setTextColor(0xFF58A6FF);
        title.setTextSize(14);
        panel.addView(title);

        addSeparator(panel);

        // ─── Módulo Bot ─────────────────────────
        TextView botLabel = new TextView(ctx);
        botLabel.setText("🤖 Roller Bot");
        botLabel.setTextColor(0xFF3FB950);
        botLabel.setTextSize(12);
        botLabel.setPadding(0, dpToPx(6), 0, 0);
        panel.addView(botLabel);

        Switch botSwitch = new Switch(ctx);
        botSwitch.setTextOff("OFF");
        botSwitch.setTextOn("ON");
        botSwitch.setChecked(botRunning);
        botSwitch.setTextSize(11);
        botSwitch.setOnCheckedChangeListener((btn, checked) -> {
            botRunning = checked;
            AuraPassiveService svc = AuraPassiveService.getInstance();
            if (svc != null) {
                String cmd = checked ? "{\"action\":\"bot_start\"}" : "{\"action\":\"bot_stop\"}";
                svc.sendToServer(cmd);
            }
            Toast.makeText(ctx, checked ? "Bot activado" : "Bot desactivado", Toast.LENGTH_SHORT).show();
        });
        panel.addView(botSwitch);

        TextView statusBot = new TextView(ctx);
        statusBot.setText("Estado: inactivo");
        statusBot.setTextColor(0xFF8B949E);
        statusBot.setTextSize(10);
        statusBot.setTag("bot_status");
        panel.addView(statusBot);

        addSeparator(panel);

        // ─── Módulo OSINT ───────────────────────
        TextView osintLabel = new TextView(ctx);
        osintLabel.setText("🔍 OSINT Scanner");
        osintLabel.setTextColor(0xFF58A6FF);
        osintLabel.setTextSize(12);
        panel.addView(osintLabel);

        LinearLayout osintRow = new LinearLayout(ctx);
        osintRow.setOrientation(LinearLayout.HORIZONTAL);

        EditText osintInput = new EditText(ctx);
        osintInput.setHint("IP o usuario");
        osintInput.setTextSize(11);
        osintInput.setTextColor(0xFFC9D1D9);
        osintInput.setMaxLines(1);
        LinearLayout.LayoutParams inputLp = new LinearLayout.LayoutParams(0, dpToPx(36), 1f);
        inputLp.setMarginEnd(dpToPx(4));
        osintInput.setLayoutParams(inputLp);

        Button osintBtn = new Button(ctx);
        osintBtn.setText("▶");
        osintBtn.setTextSize(11);
        osintBtn.setTextColor(0xFFFFFFFF);
        osintBtn.setPadding(dpToPx(8), 0, dpToPx(8), 0);
        GradientDrawable btnBg = new GradientDrawable();
        btnBg.setCornerRadius(dpToPx(6));
        btnBg.setColor(0xFF1F6FEB);
        osintBtn.setBackground(btnBg);
        osintBtn.setOnClickListener(v -> {
            String target = osintInput.getText().toString().trim();
            if (target.isEmpty()) {
                Toast.makeText(ctx, "Ingresa un objetivo", Toast.LENGTH_SHORT).show();
                return;
            }
            AuraPassiveService svc = AuraPassiveService.getInstance();
            if (svc != null) {
                svc.sendToServer("{\"action\":\"osint_scan\",\"target\":\"" + target + "\"}");
                Toast.makeText(ctx, "Escaneando: " + target, Toast.LENGTH_SHORT).show();
                osintInput.setText("");
            } else {
                Toast.makeText(ctx, "Sin conexión a AURA Core", Toast.LENGTH_SHORT).show();
            }
        });

        osintRow.addView(osintInput);
        osintRow.addView(osintBtn);
        panel.addView(osintRow);

        addSeparator(panel);

        // ─── Módulo IA (GBrian) ─────────────────
        TextView iaLabel = new TextView(ctx);
        iaLabel.setText("💬 Chat IA (GBrian)");
        iaLabel.setTextColor(0xFFA371F7);
        iaLabel.setTextSize(12);
        panel.addView(iaLabel);

        LinearLayout iaRow = new LinearLayout(ctx);
        iaRow.setOrientation(LinearLayout.HORIZONTAL);

        EditText iaInput = new EditText(ctx);
        iaInput.setHint("Pregunta a la IA...");
        iaInput.setTextSize(11);
        iaInput.setTextColor(0xFFC9D1D9);
        iaInput.setMaxLines(1);
        LinearLayout.LayoutParams iaInputLp = new LinearLayout.LayoutParams(0, dpToPx(36), 1f);
        iaInputLp.setMarginEnd(dpToPx(4));
        iaInput.setLayoutParams(iaInputLp);

        Button iaBtn = new Button(ctx);
        iaBtn.setText("➤");
        iaBtn.setTextSize(11);
        iaBtn.setTextColor(0xFFFFFFFF);
        iaBtn.setPadding(dpToPx(8), 0, dpToPx(8), 0);
        GradientDrawable iaBtnBg = new GradientDrawable();
        iaBtnBg.setCornerRadius(dpToPx(6));
        iaBtnBg.setColor(0xFFA371F7);
        iaBtn.setBackground(iaBtnBg);
        iaBtn.setOnClickListener(v -> {
            String q = iaInput.getText().toString().trim();
            if (q.isEmpty()) return;
            AuraPassiveService svc = AuraPassiveService.getInstance();
            if (svc != null) {
                svc.sendToServer("{\"action\":\"gbrian_chat\",\"message\":\"" + q + "\"}");
                Toast.makeText(ctx, "Enviando a IA...", Toast.LENGTH_SHORT).show();
                iaInput.setText("");
            } else {
                Toast.makeText(ctx, "Sin conexión", Toast.LENGTH_SHORT).show();
            }
        });

        iaRow.addView(iaInput);
        iaRow.addView(iaBtn);
        panel.addView(iaRow);

        // ─── Botón cerrar ───────────────────────
        Button closeBtn = new Button(ctx);
        closeBtn.setText("✕ Cerrar");
        closeBtn.setTextSize(10);
        closeBtn.setTextColor(0xFF8B949E);
        GradientDrawable closeBg = new GradientDrawable();
        closeBg.setCornerRadius(dpToPx(6));
        closeBg.setColor(0x00000000);
        closeBtn.setBackground(closeBg);
        LinearLayout.LayoutParams closeLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dpToPx(28));
        closeLp.setMargins(0, dpToPx(6), 0, 0);
        closeBtn.setLayoutParams(closeLp);
        closeBtn.setOnClickListener(v -> togglePanel());

        panel.addView(closeBtn);

        panelView = panel;
    }

    private void addSeparator(LinearLayout parent) {
        View sep = new View(this);
        GradientDrawable sepBg = new GradientDrawable();
        sepBg.setColor(0xFF21262D);
        sep.setBackground(sepBg);
        LinearLayout.LayoutParams sepLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dpToPx(1));
        sepLp.setMargins(0, dpToPx(6), 0, dpToPx(6));
        sep.setLayoutParams(sepLp);
        parent.addView(sep);
    }

    private int dpToPx(int dp) {
        return (int) (dp * getResources().getDisplayMetrics().density);
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "AURA Bubble",
                    NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Burbuja flotante de AURA");
            channel.setShowBadge(false);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private void startForeground() {
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification n = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("AURA Bubble")
                .setContentText("Panel flotante activo")
                .setSmallIcon(android.R.drawable.ic_menu_info_details)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
        startForeground(NOTIFICATION_ID, n);
    }

    @Override
    public void onDestroy() {
        super.onDestroy();
        try {
            if (bubbleView != null) windowManager.removeView(bubbleView);
            if (panelView != null && panelVisible) windowManager.removeView(panelView);
        } catch (Exception ignored) {}
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
