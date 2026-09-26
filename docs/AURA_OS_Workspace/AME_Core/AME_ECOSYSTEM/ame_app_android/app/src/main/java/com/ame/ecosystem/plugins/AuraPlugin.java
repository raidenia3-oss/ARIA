package com.ame.ecosystem.plugins;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import com.ame.ecosystem.services.AuraPassiveService;
import com.ame.ecosystem.services.FloatingBubbleService;

/**
 * AuraPlugin — Plugin Android puro (sin Capacitor)
 * Expone métodos estáticos para iniciar/detener servicios de fondo
 */
public class AuraPlugin {

    private static Context appContext;

    public static void init(Context context) {
        appContext = context.getApplicationContext();
    }

    public static boolean hasOverlayPermission() {
        if (appContext == null) return false;
        return Settings.canDrawOverlays(appContext);
    }

    public static void requestOverlayPermission(Context activityContext) {
        Intent intent = new Intent(
            Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
            Uri.parse("package:" + appContext.getPackageName())
        );
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        activityContext.startActivity(intent);
    }

    public static boolean startPassiveService(String wsUrl) {
        if (appContext == null || !Settings.canDrawOverlays(appContext)) return false;
        Intent intent = new Intent(appContext, AuraPassiveService.class);
        intent.putExtra("ws_url", wsUrl);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            appContext.startForegroundService(intent);
        } else {
            appContext.startService(intent);
        }
        return true;
    }

    public static boolean stopPassiveService() {
        if (appContext == null) return false;
        Intent intent = new Intent(appContext, AuraPassiveService.class);
        appContext.stopService(intent);
        return true;
    }

    public static boolean startBubbleService() {
        if (appContext == null || !Settings.canDrawOverlays(appContext)) return false;
        Intent intent = new Intent(appContext, FloatingBubbleService.class);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            appContext.startForegroundService(intent);
        } else {
            appContext.startService(intent);
        }
        return true;
    }

    public static boolean stopBubbleService() {
        if (appContext == null) return false;
        Intent intent = new Intent(appContext, FloatingBubbleService.class);
        appContext.stopService(intent);
        return true;
    }

    public static void sendToServer(String message) {
        AuraPassiveService svc = AuraPassiveService.getInstance();
        if (svc != null && svc.isConnected()) {
            svc.sendToServer(message);
        }
    }

    public static boolean isServiceRunning() {
        AuraPassiveService svc = AuraPassiveService.getInstance();
        return svc != null && svc.isConnected();
    }
}
