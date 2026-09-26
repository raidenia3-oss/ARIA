package com.ame.ecosystem.services;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.util.Log;
import androidx.core.app.NotificationCompat;

import com.ame.ecosystem.MainActivity;

import java.net.URI;
import java.net.URISyntaxException;
import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;

/**
 * AuraPassiveService — Foreground Service con WebSocket pasivo
 * Escucha alertas, estados del bot y respuestas de IA en tiempo real
 */
public class AuraPassiveService extends Service {
    private static final String TAG = "AuraPassive";
    private static final String CHANNEL_ID = "aura_passive_channel";
    private static final int NOTIFICATION_ID = 9999;

    // URL de AURA Core en la PC — configurable por intent
    private String wsUrl = "ws://192.168.0.100:8765";
    private WebSocket webSocket;
    private OkHttpClient client;
    private boolean connected = false;

    // Callback para comunicar eventos hacia la UI
    public interface MessageListener {
        void onMessage(String message);
        void onStatusChanged(String status);
    }
    private static MessageListener messageListener;
    private static AuraPassiveService instance;

    @Override
    public void onCreate() {
        super.onCreate();
        instance = this;
        createNotificationChannel();
        startForegroundWithNotification("AURA Core — Conectando...");

        client = new OkHttpClient.Builder()
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .pingInterval(30, TimeUnit.SECONDS)
                .build();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && intent.getStringExtra("ws_url") != null) {
            wsUrl = intent.getStringExtra("ws_url");
        }
        connectWebSocket();
        startBubbleService();
        return START_STICKY;
    }

    private void connectWebSocket() {
        Request request;
        try {
            request = new Request.Builder().url(wsUrl).build();
        } catch (IllegalArgumentException e) {
            Log.e(TAG, "URL WebSocket inválida: " + wsUrl);
            updateNotification("AURA Core — URL inválida");
            return;
        }

        webSocket = client.newWebSocket(request, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket ws, Response response) {
                connected = true;
                updateNotification("AURA Core — Conectado ✓");
                Log.i(TAG, "WebSocket conectado a " + wsUrl);
                if (messageListener != null) messageListener.onStatusChanged("connected");
            }

            @Override
            public void onMessage(WebSocket ws, String text) {
                Log.d(TAG, "Mensaje WS: " + text);
                if (messageListener != null) messageListener.onMessage(text);
                handleServerMessage(text);
            }

            @Override
            public void onClosing(WebSocket ws, int code, String reason) {
                ws.close(1000, null);
                connected = false;
                updateNotification("AURA Core — Desconectado");
                if (messageListener != null) messageListener.onStatusChanged("disconnected");
            }

            @Override
            public void onFailure(WebSocket ws, Throwable t, Response response) {
                connected = false;
                updateNotification("AURA Core — Reconectando...");
                Log.w(TAG, "WS fallo: " + t.getMessage());
                if (messageListener != null) messageListener.onStatusChanged("reconnecting");
                // Reconexión automática
                try { Thread.sleep(5000); } catch (InterruptedException ignored) {}
                connectWebSocket();
            }
        });
    }

    private void handleServerMessage(String json) {
        // Parsear mensajes del servidor
        // { "type": "bot_status", "data": { ... } }
        // { "type": "alert", "data": { "message": "..." } }
        // { "type": "gbrian_response", "data": { "response": "..." } }
        if (json.contains("alert")) {
            showIncomingNotification("AURA Alert", json);
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "AURA Core Background",
                NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Mantiene AURA Core activo en segundo plano");
            channel.setShowBadge(false);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private void startForegroundWithNotification(String text) {
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("AURA Core")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_menu_info_details)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();

        startForeground(NOTIFICATION_ID, notification);
    }

    private void updateNotification(String text) {
        Intent intent = new Intent(this, MainActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("AURA Core")
                .setContentText(text)
                .setSmallIcon(android.R.drawable.ic_menu_info_details)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();

        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) nm.notify(NOTIFICATION_ID, notification);
    }

    private void showIncomingNotification(String title, String body) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm == null) return;
        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(title)
                .setContentText(body.substring(0, Math.min(body.length(), 100)))
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .build();
        nm.notify((int) System.currentTimeMillis(), notification);
    }

    private void startBubbleService() {
        Intent intent = new Intent(this, FloatingBubbleService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent);
        } else {
            startService(intent);
        }
    }

    public void sendToServer(String message) {
        if (webSocket != null && connected) {
            webSocket.send(message);
        }
    }

    public boolean isConnected() { return connected; }

    public static void setMessageListener(MessageListener listener) {
        messageListener = listener;
    }

    public static AuraPassiveService getInstance() { return instance; }

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (webSocket != null) webSocket.close(1000, "Service destroyed");
        instance = null;
    }

    @Override
    public IBinder onBind(Intent intent) { return null; }
}
