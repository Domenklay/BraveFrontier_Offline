package com.domenklay.bfoffline;

import android.content.ContentProvider;
import android.content.ContentValues;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Build;
import android.util.Log;

/**
 * Starts the actual upstream C++ server in the ORIGINAL game's second process
 * before the first Activity starts. This is NOT a replacement game or server.
 */
public final class OfflineBootstrapProvider extends ContentProvider {
    @Override public boolean onCreate() {
        try {
            if (getContext() != null) {
                Intent service = new Intent(getContext(), EmbeddedServerService.class);
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    getContext().startForegroundService(service);
                } else {
                    getContext().startService(service);
                }
            }
        } catch (RuntimeException e) {
            Log.e("BF-Offline", "Cannot start native game-server service", e);
        }
        return true;
    }
    @Override public Cursor query(Uri uri, String[] projection, String selection,
                                   String[] selectionArgs, String sortOrder) {
        return null;
    }
    @Override public String getType(Uri uri) { return null; }
    @Override public Uri insert(Uri uri, ContentValues values) {
        throw new UnsupportedOperationException();
    }
    @Override public int delete(Uri uri, String selection, String[] selectionArgs) {
        throw new UnsupportedOperationException();
    }
    @Override public int update(Uri uri, ContentValues values, String selection,
                                String[] selectionArgs) {
        throw new UnsupportedOperationException();
    }
}
