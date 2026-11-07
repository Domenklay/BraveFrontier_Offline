#!/usr/bin/env python3
"""Read-only APK verification for the upstream Brave Frontier v2.19.6 patcher."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = json.loads((ROOT / "upstream.lock.json").read_text(encoding="utf-8"))["client"]["arm64LibgameSha256"]
LIB = "lib/arm64-v8a/libgame.so"

def main(argv):
    if len(argv) != 2:
        print("Usage: python tools/check_client.py path/to/BraveFrontier.apk")
        return 2
    apk = Path(argv[1])
    if not apk.is_file() or not zipfile.is_zipfile(apk):
        print("Invalid or missing APK file:", apk)
        return 2
    with zipfile.ZipFile(apk) as z:
        names = set(z.namelist())
        if "AndroidManifest.xml" not in names or "classes.dex" not in names:
            print("Missing Android application metadata")
            return 1
        if LIB not in names:
            print("Missing library:", LIB)
            return 1
        digest = hashlib.sha256()
        with z.open(LIB) as fp:
            for part in iter(lambda: fp.read(1024 * 1024), b""):
                digest.update(part)
        actual = digest.hexdigest()
        print("APK:     ", apk.name)
        print("SHA256:  ", actual)
        print("Expected:", EXPECTED)
        if actual != EXPECTED:
            print("UNSUPPORTED BUILD: do not patch with the pinned upstream patcher")
            return 1
        print("MATCH: the arm64 libgame.so matches the upstream expected original")
        print("Runtime functionality and complete assets still require separate verification")
        return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
