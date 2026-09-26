package com.aura.mobile;

import android.content.Context;
import android.util.Log;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.File;
import java.io.IOException;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.MediaType;
import okhttp3.MultipartBody;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;

@CapacitorPlugin(name = "WhisperIntegration")
public class WhisperIntegration extends Plugin {
    private static final String TAG = "WhisperIntegration";
    private static final String WHISPER_API_URL = "https://tunel-aura.trycloudflare.com/api/whisper";
    private OkHttpClient httpClient;

    @Override
    public void load() {
        super.load();
        httpClient = new OkHttpClient();
    }

    @PluginMethod
    public void processAudio(PluginCall call) {
        String filePath = call.getString("filePath");
        if (filePath == null) {
            call.reject("File path is required");
            return;
        }

        File audioFile = new File(filePath);
        if (!audioFile.exists()) {
            call.reject("Audio file does not exist");
            return;
        }

        // Crear cuerpo multipart para enviar el archivo de audio
        RequestBody requestBody = new MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("audio", audioFile.getName(),
                        RequestBody.create(MediaType.parse("audio/*"), audioFile))
                .build();

        // Crear la solicitud HTTP
        Request request = new Request.Builder()
                .url(WHISPER_API_URL)
                .post(requestBody)
                .build();

        // Ejecutar la solicitud
        httpClient.newCall(request).enqueue(new Callback() {
            @Override
            public void onFailure(Call call, IOException e) {
                JSObject ret = new JSObject();
                ret.put("success", false);
                ret.put("error", e.getMessage());
                notifyListeners("whisperResponse", ret);
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException {
                if (!response.isSuccessful()) {
                    JSObject ret = new JSObject();
                    ret.put("success", false);
                    ret.put("error", "HTTP " + response.code());
                    notifyListeners("whisperResponse", ret);
                    return;
                }

                String responseBody = response.body().string();
                JSObject ret = new JSObject();
                ret.put("success", true);
                ret.put("transcription", responseBody);
                notifyListeners("whisperResponse", ret);
            }
        });

        call.resolve();
    }
}