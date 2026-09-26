package com.ame.ecosystem;

import android.annotation.SuppressLint;
import android.app.WallpaperManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.util.Log;
import androidx.annotation.NonNull;
import androidx.work.*;
import java.io.InputStream;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * WallpaperRotationWorker — Rota automáticamente el fondo de pantalla.
 * Usa WorkManager para ser inmune a kill del sistema.
 *
 * Uso:
 *   WorksOnce con PeriodicWorkRequestBuilder para rotación periódica.
 *   El usuario selecciona lista de imágenes; cada intervalo cambia el fondo.
 *
 * Intervalos soportados: 15min, 30min, 1hour, 6hours, 12hours, 24hours.
 */
public class WallpaperRotationWorker extends Worker {

    private static final String TAG = "AURA-WallpaperRotation";
    private static final String KEY_IMAGE_URIS = "image_uris";
    private static final String KEY_INTERVAL_MINUTES = "interval_minutes";
    private static final String KEY_TARGET = "target"; // "home" or "lock"

    public WallpaperRotationWorker(@NonNull Context context, @NonNull WorkerParameters params) {
        super(context, params);
    }

    @NonNull
    @Override
    public Result doWork() {
        try {
            List<String> uris = getInputData().getStringArray(KEY_IMAGE_URIS) != null
                    ? java.util.Arrays.asList(getInputData().getStringArray(KEY_IMAGE_URIS))
                    : null;
            String target = getInputData().getString(KEY_TARGET);
            boolean isLockScreen = "lock".equals(target);

            if (uris == null || uris.isEmpty()) {
                Log.w(TAG, "No image URIs provided");
                return Result.failure();
            }

            // Rotar al siguiente índice
            android.content.SharedPreferences prefs = getApplicationContext()
                    .getSharedPreferences("aura_wallpaper", Context.MODE_PRIVATE);
            int currentIndex = prefs.getInt("rotation_index", 0);
            int nextIndex = currentIndex % uris.size();
            String uriStr = uris.get(nextIndex);
            Uri uri = Uri.parse(uriStr);

            Context ctx = getApplicationContext();
            WallpaperManager wm = WallpaperManager.getInstance(ctx);

            InputStream is = ctx.getContentResolver().openInputStream(uri);
            if (is != null) {
                Bitmap bmp = BitmapFactory.decodeStream(is);
                if (bmp != null) {
                    if (isLockScreen) {
                        wm.setBitmap(bmp, null, true, WallpaperManager.FLAG_LOCK);
                    } else {
                        wm.setBitmap(bmp);
                    }
                    Log.i(TAG, "Wallpaper set: index=" + nextIndex + " target=" + target);
                    prefs.edit().putInt("rotation_index", nextIndex + 1).apply();
                }
                is.close();
            }

            // Notificación de cambio (opcional)
            if (!isLockScreen) {
                androidx.core.app.NotificationCompat.Builder builder =
                        new androidx.core.app.NotificationCompat.Builder(ctx, "aura_wallpaper")
                                .setSmallIcon(android.R.drawable.ic_menu_gallery)
                                .setContentTitle("AURA Wallpaper")
                                .setContentText("Fondo rotado: " + (nextIndex + 1) + "/" + uris.size())
                                .setAutoCancel(true);
                // Nota: para usar notificaciones se necesita un NotificationChannel
                Log.i(TAG, "Rotation event for image " + (nextIndex + 1));
            }

            return Result.success();
        } catch (Exception e) {
            Log.e(TAG, "Wallpaper rotation failed", e);
            return Result.failure();
        }
    }

    /**
     * Método estático para programar la rotación automática.
     *
     * @param context          Contexto de la aplicación
     * @param imageUrls        Lista de URIs de imágenes en la galería
     * @param intervalMinutes  Intervalo en minutos (15, 30, 60, 360, 720, 1440)
     * @param target           "home" o "lock"
     */
    @SuppressLint("RestrictedApi")
    public static void scheduleRotation(
            @NonNull Context context,
            @NonNull List<String> imageUrls,
            long intervalMinutes,
            @NonNull String target
    ) {
        if (imageUrls.isEmpty()) {
            Log.w(TAG, "Cannot schedule rotation with empty image list");
            return;
        }

        androidx.work.Data inputData = new androidx.work.Data.Builder()
                .putStringArray(KEY_IMAGE_URIS, imageUrls.toArray(new String[0]))
                .putString(KEY_TARGET, target)
                .build();

        PeriodicWorkRequest request = new PeriodicWorkRequest.Builder(
                WallpaperRotationWorker.class,
                intervalMinutes, TimeUnit.MINUTES
        )
                .setInputData(inputData)
                .setConstraints(new Constraints.Builder()
                        .setRequiresBatteryNotLow(false)
                        .setRequiresCharging(false)
                        .build())
                .addTag("aura_wallpaper_rotation")
                .build();

        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "aura_wallpaper_rotation",
                ExistingPeriodicWorkPolicy.REPLACE,
                request
        );

        Log.i(TAG, "Wallpaper rotation scheduled: every " + intervalMinutes + " min");
    }

    /**
     * Cancela la rotación programada.
     */
    public static void cancelRotation(@NonNull Context context) {
        WorkManager.getInstance(context).cancelUniqueWork("aura_wallpaper_rotation");
        Log.i(TAG, "Wallpaper rotation cancelled");
    }
}
