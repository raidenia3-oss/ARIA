package com.aura.mobile;

import android.content.Context;
import android.media.AudioManager;
import android.os.Vibrator;
import android.util.Log;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.Timer;
import java.util.TimerTask;

@CapacitorPlugin(name = "VolumeButtonPlugin")
public class VolumeButtonPlugin extends Plugin {
    private static final String TAG = "VolumeButtonPlugin";
    private AudioManager audioManager;
    private Vibrator vibrator;
    private boolean isRecording = false;
    private Timer recordingTimer;
    private long lastVolumeDownPressTime = 0;
    private static final long DOUBLE_PRESS_THRESHOLD_MS = 500;

    @Override
    public void load() {
        super.load();
        audioManager = (AudioManager) getContext().getSystemService(Context.AUDIO_SERVICE);
        vibrator = (Vibrator) getContext().getSystemService(Context.VIBRATOR_SERVICE);
    }

    @PluginMethod
    public void startListening(PluginCall call) {
        Log.d(TAG, "Iniciando escucha de botones de volumen");
        call.resolve();
    }

    @PluginMethod
    public void stopListening(PluginCall call) {
        Log.d(TAG, "Deteniendo escucha de botones de volumen");
        if (recordingTimer != null) {
            recordingTimer.cancel();
        }
        call.resolve();
    }

    @Override
    public void handleOnResume() {
        super.handleOnResume();
        setupVolumeButtonListener();
    }

    @Override
    public void handleOnPause() {
        super.handleOnPause();
        removeVolumeButtonListener();
    }

    private void setupVolumeButtonListener() {
        audioManager.registerMediaButtonEventReceiver(new MediaButtonReceiver());
    }

    private void removeVolumeButtonListener() {
        audioManager.unregisterMediaButtonEventReceiver(new MediaButtonReceiver());
    }

    private class MediaButtonReceiver extends AudioManager.OnMediaButtonEventListener {
        @Override
        public boolean onMediaButtonEvent(Intent intent) {
            if (intent.getAction().equals(Intent.ACTION_MEDIA_BUTTON)) {
                KeyEvent event = intent.getExtras().getParcelable("android.intent.extra.KEY_EVENT");
                if (event != null) {
                    int keyCode = event.getKeyCode();
                    boolean isDown = event.getAction() == KeyEvent.ACTION_DOWN;

                    if (keyCode == KeyEvent.KEYCODE_VOLUME_DOWN) {
                        if (isDown) {
                            long currentTime = System.currentTimeMillis();
                            if (currentTime - lastVolumeDownPressTime < DOUBLE_PRESS_THRESHOLD_MS) {
                                // Ignorar presiones rápidas repetidas
                                return true;
                            }
                            lastVolumeDownPressTime = currentTime;

                            // Vibración al presionar el botón
                            if (vibrator != null && vibrator.hasVibrator()) {
                                vibrator.vibrate(50); // Vibración corta al presionar
                            }

                            // Iniciar grabación de voz
                            startVoiceRecording();
                        } else {
                            // Soltar el botón
                            stopVoiceRecording();
                        }
                        return true;
                    }
                }
            }
            return false;
        }
    }

    private void startVoiceRecording() {
        if (!isRecording) {
            isRecording = true;
            Log.d(TAG, "Iniciando grabación de voz...");

            // Notificar al frontend de JavaScript
            JSObject ret = new JSObject();
            ret.put("event", "voiceRecordingStarted");
            notifyListeners("voiceRecordingStatus", ret);

            // Configurar temporizador para detener grabación después de 10 segundos de inactividad
            recordingTimer = new Timer();
            recordingTimer.schedule(new TimerTask() {
                @Override
                public void run() {
                    if (isRecording) {
                        stopVoiceRecording();
                    }
                }
            }, 10000); // 10 segundos de inactividad
        }
    }

    private void stopVoiceRecording() {
        if (isRecording) {
            isRecording = false;
            if (recordingTimer != null) {
                recordingTimer.cancel();
                recordingTimer = null;
            }

            // Notificar al frontend de JavaScript
            JSObject ret = new JSObject();
            ret.put("event", "voiceRecordingStopped");
            ret.put("success", true);
            notifyListeners("voiceRecordingStatus", ret);

            // Vibración de confirmación
            if (vibrator != null && vibrator.hasVibrator()) {
                vibrator.vibrate(100); // Vibración doble (100ms)
            }
        }
    }
}