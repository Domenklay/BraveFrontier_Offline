package com.domenklay.bfoffline;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.Gravity;
import android.widget.TextView;
import android.util.Log;
import java.net.HttpURLConnection;
import java.net.URL;
import java.io.InputStream;
import java.io.File;

/**
 * Launch gateway INSIDE the patched original APK. The game's own Activity is
 * not opened until the actual upstream C++ localhost server responds to /dls.
 * This avoids first-boot races while multi-GB resources are unpacked.
 */
public final class OfflineLaunchActivity extends Activity {
    private static final String META_ORIGINAL = "bf_offline.original_activity";
    private TextView state;
    private Thread poller;
    private volatile boolean destroyed;

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        state = new TextView(this);
        state.setBackgroundColor(Color.rgb(15,21,31));
        state.setTextColor(Color.rgb(233,189,107));
        state.setTextSize(19);
        state.setGravity(Gravity.CENTER);
        state.setPadding(28,28,28,28);
        state.setText("Brave Frontier Offline\n\nЗапуск локального сервера…");
        setContentView(state);

        final String original;
        try {
            ActivityInfo ai = getPackageManager().getActivityInfo(
                    new ComponentName(this, OfflineLaunchActivity.class),
                    PackageManager.GET_META_DATA);
            original = ai.metaData != null ? ai.metaData.getString(META_ORIGINAL) : null;
            if (original == null || original.isEmpty())
                throw new IllegalStateException("Original launcher component not registered");
            startService(new Intent(this,EmbeddedServerService.class));
        } catch (Exception ex) {
            Log.e("BF-Offline","Launch integration missing",ex);
            state.setText("Не удалось подготовить офлайн-клиент.\nПроверьте сборку и logcat.");
            return;
        }

        poller = new Thread(() -> {
            // Server process can take time to extract downloaded content on
            // the first launch. Never send a request to an external host.
            final long deadline = SystemClock.elapsedRealtime() + 10L * 60L * 1000L;
            while (!destroyed && SystemClock.elapsedRealtime() < deadline) {
                File bootError = new File(getFilesDir(), "bf_offline/.boot_error.txt");
                if (bootError.isFile()) {
                    runOnUiThread(() -> {
                        if (!destroyed && !isFinishing())
                            state.setText("Локальный сервер не запустился.\\n"
                                + "Проверьте игровые таблицы и библиотеку сервера.\\n"
                                + "Подробности: adb logcat | grep BF-Offline");
                    });
                    return;
                }
                if (isLocalServerReady()) {
                    runOnUiThread(() -> {
                        if (destroyed || isFinishing()) return;
                        Intent launch = new Intent();
                        launch.setClassName(getPackageName(), original);
                        try {
                            startActivity(launch); // the ORIGINAL Brave Frontier Activity
                            finish();
                        } catch (RuntimeException ex) {
                            Log.e("BF-Offline","Original Activity cannot launch",ex);
                            state.setText("Не удалось открыть оригинальную игру.\nСмотрите logcat.");
                        }
                    });
                    return;
                }
                SystemClock.sleep(650);
            }
            runOnUiThread(() -> {
                if (!destroyed && !isFinishing()) {
                    state.setText("Локальный сервер не запустился.\n\n"
                            + "Нужны библиотека C++ сервера и все игровые данные.\n"
                            + "Подробности: adb logcat | grep BF-Offline");
                }
            });
        }, "bf-offline-readiness");
        poller.start();
    }

    private static boolean isLocalServerReady() {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection)
                    new URL("http://127.0.0.1:9960/dls").openConnection();
            connection.setConnectTimeout(900);
            connection.setReadTimeout(900);
            connection.setUseCaches(false);
            if (connection.getResponseCode() != 200) return false;
            try (InputStream input = connection.getInputStream()) {
                int first;
                do {first = input.read();} while(first == ' ' || first == '\n');
                return first == '{'; // actual JSON reply, not an open port only
            }
        } catch (Exception ignored) {
            return false;
        } finally {
            if(connection != null) connection.disconnect();
        }
    }

    @Override protected void onDestroy() {
        destroyed = true;
        if(poller != null) poller.interrupt();
        super.onDestroy();
    }
}
