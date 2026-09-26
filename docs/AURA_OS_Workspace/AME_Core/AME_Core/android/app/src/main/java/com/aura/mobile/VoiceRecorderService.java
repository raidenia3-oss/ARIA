package com.aura.mobile;

import android.app.Service;
import android.content.Intent;
import android.media.MediaRecorder;
import android.os.IBinder;
import android.util.Log;
import java.io.IOException;

public class VoiceRecorderService extends Service {
    private static final String TAG = "VoiceRecorderService";
    private MediaRecorder mediaRecorder;
    private String outputFile;

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        Log.d(TAG, "Servicio de grabación de voz creado");
    }

    public void startRecording(String filePath) {
        outputFile = filePath;
        mediaRecorder = new MediaRecorder();
        mediaRecorder.setAudioSource(MediaRecorder.AudioSource.VOICE_RECOGNITION);
        mediaRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
        mediaRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
        mediaRecorder.setOutputFile(outputFile);

        try {
            mediaRecorder.prepare();
            mediaRecorder.start();
            Log.d(TAG, "Grabación iniciada: " + outputFile);
        } catch (IOException e) {
            Log.e(TAG, "Error al iniciar grabación: " + e.getMessage());
        }
    }

    public void stopRecording() {
        if (mediaRecorder != null) {
            mediaRecorder.stop();
            mediaRecorder.release();
            mediaRecorder = null;
            Log.d(TAG, "Grabación detenida");
        }
    }

    public String getOutputFile() {
        return outputFile;
    }
}