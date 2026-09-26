package com.ame.ecosystem;

import android.graphics.Color;
import android.os.Bundle;
import androidx.appcompat.app.AppCompatActivity;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class GlobalMapActivity extends AppCompatActivity {

    private WebView mapWebView;
    private LinearLayout nodesContainer;
    private TextView tvMapStatus;
    private Button btnRefreshMap;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_global_map);

        mapWebView = findViewById(R.id.mapWebView);
        nodesContainer = findViewById(R.id.nodesContainer);
        tvMapStatus = findViewById(R.id.tvMapStatus);
        btnRefreshMap = findViewById(R.id.btnRefreshMap);

        mapWebView.getSettings().setJavaScriptEnabled(true);
        mapWebView.getSettings().setDomStorageEnabled(true);
        mapWebView.setWebViewClient(new WebViewClient());

        // Leaflet dark map with OpenStreetMap CartoDB dark tiles
        String leafletHtml = "<!DOCTYPE html><html><head>"
            + "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            + "<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/>"
            + "<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script>"
            + "<style>"
            + "*{margin:0;padding:0;box-sizing:border-box;}"
            + "body{background:#0a0e17;font-family:monospace;}"
            + "#map{width:100%;height:100vh;}"
            + ".node-label{background:#0a0e17ee;border:1px solid #00ff41;padding:4px 8px;"
            + "color:#00ff41;font-size:11px;font-family:monospace;border-radius:2px;}"
            + ".pulse{animation:pulse 2s infinite;}"
            + "@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}"
            + "</style></head><body>"
            + "<div id='map'></div>"
            + "<script>"
            + "var map=L.map('map',{zoomControl:false,attributionControl:false})"
            + ".setView([-12.05,-77.04],2);"
            + "L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{"
            + "maxZoom:19"
            + "}).addTo(map);"
            + "function icon(c){return L.divIcon({"
            + "className:'',html:'<div style=\"width:14px;height:14px;border-radius:50%;"
            + "background:'+c+';border:2px solid #fff;box-shadow:0 0 12px '+c+';\""
            + "class=\"pulse\"></div>',iconSize:[14,14],iconAnchor:[7,7]});}"
            + "function lbl(t,c){return L.divIcon({"
            + "className:'',html:'<div class=\"node-label\" style=\"border-color:'+c+';color:'+c+'\">'+t+'</div>',"
            + "iconAnchor:[0,-10]});}"
            + "var n1=L.marker([-12.05,-77.04],{icon:icon('#00ff41')}).addTo(map);"
            + "n1.bindTooltip('NODO CENTRAL - PC Local',{permanent:true,direction:'top',className:'node-label'}).openTooltip();"
            + "var n2=L.marker([48.8566,2.3522],{icon:icon('#ffd700')}).addTo(map);"
            + "n2.bindTooltip('NODO CONCIENCIA - HF Paris',{permanent:true,direction:'top',className:'node-label'}).openTooltip();"
            + "var n3=L.marker([-12.04,-77.03],{icon:icon('#00bfff')}).addTo(map);"
            + "n3.bindTooltip('EMULADOR - AVD Bridge',{permanent:true,direction:'top',className:'node-label'}).openTooltip();"
            + "L.polyline([[-12.05,-77.04],[48.8566,2.3522]],{color:'#00ff4144',weight:1,dashArray:'5,10'}).addTo(map);"
            + "L.polyline([[-12.05,-77.04],[-12.04,-77.03]],{color:'#00bfff44',weight:1,dashArray:'5,10'}).addTo(map);"
            + "L.polyline([[-12.04,-77.03],[48.8566,2.3522]],{color:'#ffd70044',weight:1,dashArray:'5,10'}).addTo(map);"
            + "var targets=["
            + "[48.8566,2.3522,'HF Inference','#ff6b6b'],"
            + "[37.7749,-122.4194,'GitHub Repo','#ff6b6b'],"
            + "[37.3861,-122.0839,'Cloudflare','#ff6b6b'],"
            + "[37.7749,-122.4194,'Ollama Registry','#ff6b6b']"
            + "];"
            + "targets.forEach(function(t){"
            + "L.marker(t.slice(0,2),{icon:icon(t[3])}).addTo(map);"
            + "});"
            + "</script></body></html>";

        mapWebView.loadDataWithBaseURL(null, leafletHtml, "text/html", "UTF-8", null);
        loadNodes();
        btnRefreshMap.setOnClickListener(v -> { mapWebView.reload(); });
    }

    private void loadNodes() {
        nodesContainer.removeAllViews();
        tvMapStatus.setText("GLOBAL COMMAND MAP — 3 nodos | 4 objetivos");
        addNode("🖥️ NODE CENTRAL", "Peru (192.168.3.10)", "#00FF41");
        addNode("☁️ NODE CONCIENCIA", "Paris, France", "#FFD700");
        addNode("📱 EMULADOR AVD", "Bridge 10.0.2.2", "#00BFFF");
        addNode("━━━ OBJETIVOS ━━━", "", "#484F58");
        addNode("🤗 HF Inference", "Monitoring", "#FF6B6B");
        addNode("🐙 GitHub Repo", "Synced", "#FF6B6B");
        addNode("🛡️ Cloudflare", "Standby", "#FF6B6B");
        addNode("🦙 Ollama Registry", "Standby", "#FF6B6B");
    }

    private void addNode(String name, String info, String color) {
        TextView tv = new TextView(this);
        String text = info.isEmpty() ? name : name + "  ·  " + info;
        tv.setText("● " + text);
        tv.setTextColor(Color.parseColor(color));
        tv.setTextSize(11);
        tv.setPadding(0, 3, 0, 3);
        nodesContainer.addView(tv);
    }
}
