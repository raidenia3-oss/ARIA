package com.aura.ame.plugins;

import android.net.Uri;
import android.os.Environment;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.File;

/**
 * Plugin nativo de acceso a la tarjeta SD externa (Bloque 40, funcionalidad 2).
 * Gestiona directorios directamente en la SD del teléfono para la bóveda
 * literaria cifrada. Sin dependencias de nube.
 */
@CapacitorPlugin(name = "SDStorage")
public class SDStoragePlugin extends Plugin {

    @PluginMethod
    public void getSDCardPath(PluginCall call) {
        File[] dirs = getContext().getExternalFilesDirs(null);
        JSObject ret = new JSObject();
        if (dirs.length > 1 && dirs[1] != null) {
            ret.put("path", dirs[1].getAbsolutePath());
            ret.put("available", true);
        } else {
            File legacy = new File(
                Environment.getExternalStorageDirectory(), "AURA/SD_VAULT");
            ret.put("path", legacy.getAbsolutePath());
            ret.put("available", legacy.exists() || legacy.mkdirs());
        }
        call.resolve(ret);
    }

    @PluginMethod
    public void ensureVault(PluginCall call) {
        String sdPath = call.getString("sdPath");
        JSObject ret = new JSObject();
        try {
            File vault = new File(sdPath != null ? sdPath
                : Environment.getExternalStorageDirectory(), "AURA/SD_VAULT");
            boolean ok = vault.exists() || vault.mkdirs();
            ret.put("ok", ok);
            ret.put("path", vault.getAbsolutePath());
            call.resolve(ret);
        } catch (Exception e) {
            ret.put("ok", false);
            ret.put("error", e.getMessage());
            call.resolve(ret);
        }
    }

    @PluginMethod
    public void listFiles(PluginCall call) {
        String dir = call.getString("path");
        JSObject ret = new JSObject();
        try {
            File f = new File(dir);
            String[] names = f.list();
            ret.put("files", names != null ? names : new String[0]);
            call.resolve(ret);
        } catch (Exception e) {
            ret.put("files", new String[0]);
            call.resolve(ret);
        }
    }
}