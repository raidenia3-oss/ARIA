package com.aura.mobile;

import android.app.Application;
import android.content.Context;
import com.getcapacitor.BridgeActivity;
import com.getcapacitor.Plugin;

public class AuraApplication extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
    }

    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(base);
    }
}