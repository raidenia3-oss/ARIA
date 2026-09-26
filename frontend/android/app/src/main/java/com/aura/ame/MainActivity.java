package com.aura.ame;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

/**
 * AME Native Android entry point (Bloque 40).
 * Actividad Capacitor que sirve el frontend web exportado como APK local.
 * Sin telemetría de Google Play, sin servicios en la nube.
 */
public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(com.aura.ame.plugins.SDStoragePlugin.class);
        super.onCreate(savedInstanceState);
    }
}