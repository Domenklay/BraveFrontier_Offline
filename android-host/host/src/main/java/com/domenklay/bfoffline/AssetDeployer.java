package com.domenklay.bfoffline;

import android.content.res.AssetManager;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** Verified extraction of supplied game data into private app storage. */
final class AssetDeployer {
    private static final String PREFIX = "bf-offline/";
    private AssetDeployer() {}

    static File deploy(AssetManager assets, File root) throws Exception {
        if (!root.isDirectory() && !root.mkdirs()) throw new IOException("Cannot create "+root);
        File marker = new File(root, ".manifest.sha256");
        MessageDigest manifestDigest = MessageDigest.getInstance("SHA-256");
        String manifestText;
        try (InputStream input = assets.open(PREFIX + "manifest.tsv")) {
            manifestText = readUtf8(input, 8 * 1024 * 1024);
        }
        String manifestHash = hex(manifestDigest.digest(
                manifestText.getBytes(StandardCharsets.UTF_8)));
        File config = new File(root, "config.json");
        if (marker.isFile() && config.isFile() &&
                readLocal(marker).trim().equals(manifestHash)) {
            return config;
        }
        String rootCanonical = root.getCanonicalPath() + File.separator;
        int count = 0;
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(new java.io.ByteArrayInputStream(
                    manifestText.getBytes(StandardCharsets.UTF_8)),
                    StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                if (line.isEmpty() || line.startsWith("#")) continue;
                String[] cols = line.split("\t", 3);
                if (cols.length != 3 || !cols[0].matches("[a-f0-9]{64}"))
                    throw new IOException("Invalid content manifest row");
                long expected = Long.parseLong(cols[1]);
                String relative = cols[2];
                if (relative.startsWith("/") || relative.contains("\\") ||
                        relative.contains("..") || relative.contains(":"))
                    throw new IOException("Invalid asset path: " + relative);
                File output = new File(root, relative);
                if (!output.getCanonicalPath().startsWith(rootCanonical))
                    throw new IOException("Asset escaped root");
                File parent = output.getParentFile();
                if (!parent.isDirectory() && !parent.mkdirs())
                    throw new IOException("Cannot create directory: " + parent);
                File temp = new File(parent, output.getName() + ".partial");
                MessageDigest digest = MessageDigest.getInstance("SHA-256");
                long total = 0;
                try (InputStream src = assets.open(PREFIX + relative);
                     FileOutputStream dst = new FileOutputStream(temp)) {
                    byte[] buf = new byte[65536];
                    int n;
                    while ((n = src.read(buf)) >= 0) {
                        if (n == 0) continue;
                        dst.write(buf, 0, n); digest.update(buf,0,n);
                        total += n;
                    }
                    dst.getFD().sync();
                }
                if (total != expected || !hex(digest.digest()).equals(cols[0]))
                    throw new IOException("Content hash mismatch: "+relative);
                if (output.exists() && !output.delete())
                    throw new IOException("Cannot replace "+relative);
                if (!temp.renameTo(output)) throw new IOException("Cannot rename "+relative);
                count++;
            }
        }
        if (count == 0 || !config.isFile()) throw new IOException("Missing complete game payload");
        try (FileOutputStream out = new FileOutputStream(marker)) {
            out.write(manifestHash.getBytes(StandardCharsets.UTF_8));
            out.getFD().sync();
        }
        return config;
    }
    private static String readUtf8(InputStream input, int max) throws IOException {
        java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[16384]; int n;
        while ((n = input.read(buf)) >= 0) {
            if (n == 0) continue;
            if (out.size() + n > max) throw new IOException("Manifest too large");
            out.write(buf,0,n);
        }
        return new String(out.toByteArray(),StandardCharsets.UTF_8);
    }
    private static String readLocal(File file) throws IOException {
        try (java.io.FileInputStream in = new java.io.FileInputStream(file)) {
            return readUtf8(in,1024);
        }
    }
    private static String hex(byte[] bytes) {
        StringBuilder result=new StringBuilder(bytes.length*2);
        for(byte b:bytes) result.append(String.format(java.util.Locale.ROOT,"%02x",b&0xff));
        return result.toString();
    }
}
