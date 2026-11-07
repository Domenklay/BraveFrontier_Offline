package com.domenklay.bfoffline;

import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;
import java.io.File;

/**
 * Hosts joppe2001/bf-private-server in a DEDICATED Android process.
 * It loads the real game-server library; no fabricated response handlers.
 * Requires native libbf_offline_server.so and a full asset payload.
 */
public final class EmbeddedServerService extends Service {
    private static final String TAG = "BF-Offline";
    private Thread worker;

    private static native void runNativeServer(String absoluteConfigPath);
    private static native void stopNativeServer();

    @Override public void onCreate() {
        super.onCreate();
        worker = new Thread(() -> {
            try {
                File root = new File(getFilesDir(), "bf_offline");
                File config = AssetDeployer.deploy(getAssets(), root);
                System.loadLibrary("bf_offline_server");
                Log.i(TAG, "Launching existing C++ game server with " + config);
                runNativeServer(config.getAbsolutePath());
            } catch (Throwable e) {
                // A missing library or MST is an actual error, never fake readiness.
                Log.e(TAG, "Game-server boot failed (not running)", e);
                stopSelf();
            }
        }, "bf-upstream-server");
        worker.start();
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
