package com.domenklay.bfoffline;

import android.app.Service;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.os.Build;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;
import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * Hosts joppe2001/bf-private-server in a DEDICATED Android process.
 * It loads the real game-server library; no fabricated response handlers.
 * Requires native libbf_offline_server.so and a full asset payload.
 */
public final class EmbeddedServerService extends Service {
    private static final String TAG = "BF-Offline";
    private Thread worker;
    private static final String CHANNEL = "bf_offline_local_server";
    private static final int NOTIFICATION_ID = 9960;

    private static native void runNativeServer(String absoluteConfigPath);
    private static native void stopNativeServer();

    @Override public void onCreate() {
        super.onCreate();
        startInForegroundIfAllowed();
        worker = new Thread(() -> {
            File root = new File(getFilesDir(), "bf_offline");
            File failureFlag = new File(root, ".boot_error.txt");
            if (failureFlag.isFile()) failureFlag.delete();
            try {
                File config = AssetDeployer.deploy(getAssets(), root);
                System.loadLibrary("bf_offline_server");
                Log.i(TAG, "Launching existing C++ game server with " + config);
                runNativeServer(config.getAbsolutePath());
            } catch (Throwable e) {
                // A missing library or MST is an actual error, never fake readiness.
                Log.e(TAG, "Game-server boot failed (not running)", e);
                if (root.isDirectory()) {
                    try (FileOutputStream out = new FileOutputStream(failureFlag)) {
                        out.write(("Ошибка локального сервера: " + e.getClass().getSimpleName()
                                + ": " + e.getMessage()).getBytes(StandardCharsets.UTF_8));
                    } catch (Exception ignored) {
                        Log.w(TAG, "Could not save local boot diagnostic");
                    }
                }
                stopSelf();
            }
        }, "bf-upstream-server");
        worker.start();
    }


    private void startInForegroundIfAllowed() {
        try {
            Notification.Builder builder;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                NotificationManager manager =
                    (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
                if (manager != null) {
                    NotificationChannel channel = new NotificationChannel(
                        CHANNEL, "Brave Frontier — локальный сервер",
                        NotificationManager.IMPORTANCE_LOW);
                    channel.setDescription("Поддерживает локальную игру без внешнего сервера");
                    manager.createNotificationChannel(channel);
                }
                builder = new Notification.Builder(this, CHANNEL);
            } else {
                builder = new Notification.Builder(this);
            }
            Notification notification = builder
                .setSmallIcon(android.R.drawable.stat_sys_download_done)
                .setContentTitle("Brave Frontier Offline")
                .setContentText("Локальный сервер игры работает на телефоне")
                .setOngoing(true).build();
            startForeground(NOTIFICATION_ID, notification);
        } catch (RuntimeException ex) {
            // FGS launch can be restricted by OS or device settings.
            // The original foreground Activity also calls startService.
            Log.w(TAG, "Could not enable persistent local server", ex);
        }
    }

    @Override public int onStartCommand(Intent i, int flags, int startId) {
        return START_STICKY;
    }
    @Override public IBinder onBind(Intent i) { return null; }
    @Override public void onDestroy() {
        try { stopNativeServer(); } catch (UnsatisfiedLinkError ignored) {}
        super.onDestroy();
    }
}
