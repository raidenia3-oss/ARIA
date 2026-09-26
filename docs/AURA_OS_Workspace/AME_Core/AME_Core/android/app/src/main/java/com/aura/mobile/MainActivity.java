package com.aura.mobile;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginList;

import java.util.ArrayList;
import java.util.List;

public class MainActivity extends BridgeActivity {

    private static final String TAG = "AURA-MainActivity";
    private ShareTargetHandler shareHandler;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Configurar plugins adicionales
        List<Plugin> plugins = new ArrayList<>();
        plugins.add(new VolumeButtonPlugin(this));
        this.init(savedInstanceState, new PluginList(plugins), null);

        // Inicializar el manejador de Share Target
        WebView webView = getBridge().getWebView();
        if (webView != null) {
            shareHandler = new ShareTargetHandler(this, webView);
            Log.d(TAG, "ShareTargetHandler inicializado");
        }

        // Procesar el intent que abrió la app (posiblemente un Share)
        handleIncomingIntent(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        Log.d(TAG, "onNewIntent recibido");
        handleIncomingIntent(intent);
    }

    private void handleIncomingIntent(Intent intent) {
        if (intent == null) return;

        String action = intent.getAction();
        if (action != null && (action.equals(Intent.ACTION_SEND) || action.equals(Intent.ACTION_SEND_MULTIPLE))) {
            Log.d(TAG, "Share Intent detectado: " + action);
            if (shareHandler != null) {
                shareHandler.handleShareIntent(intent);
            } else {
                Log.w(TAG, "ShareTargetHandler no inicializado aún");
            }
        }
    }
}
