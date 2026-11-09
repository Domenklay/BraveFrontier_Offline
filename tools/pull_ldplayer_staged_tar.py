#!/usr/bin/env python3
"""Stage Brave Frontier's private files as TAR *inside* LDPlayer, then adb pull.

This avoids ADB exec-out streaming corruption. No game data is modified and
nothing is uploaded to GitHub. The staged archive contains PRIVATE app data:
do not publish it. Requires LDPlayer's 'su -c id' to return uid=0(root).
"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

SOURCE = "/data/data/sg.gumi.bravefrontier/files"
STAGED = "/sdcard/Download/bf-private-resources-stage-v1.tar"
BLOCK = 4 * 1024 * 1024
MIN_ENTRIES = 3

def adb_call(adb, command, timeout=30):
    return subprocess.run(adb + ["shell", "su -c '" + command + "'"],
                          capture_output=True, text=True, errors="replace",
                          timeout=timeout)

def check_root(adb):
    result = subprocess.run(adb + ["shell", "su", "-c", "id"],
                            capture_output=True, text=True, errors="replace", timeout=20)
    return result.returncode == 0 and bool(
        re.search(r"\buid=0(?:\(root\)|\b)", result.stdout))

def device_exists(adb, path):
    return adb_call(adb, "test -e " + path).returncode == 0

def device_size(adb, path):
    stat = adb_call(adb, "stat -c %s " + path)
    if stat.returncode == 0 and stat.stdout.strip().isdigit():
        return int(stat.stdout.strip())
    # Android image may not support stat -c, use a coarser fallback.
    du = adb_call(adb, "du -sk " + path)
    found = re.match(r"\s*(\d+)", du.stdout)
    return int(found.group(1)) * 1024 if du.returncode == 0 and found else None

def sha256_local(path):
    result = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(BLOCK)
            if not block:
                break
            result.update(block)
    return result.hexdigest()

def sha256_device(adb, path):
    result = adb_call(adb, "sha256sum " + path, timeout=900)
    if result.returncode:
        raise RuntimeError("Android sha256sum failed: " + result.stderr[-400:])
    matched = re.match(r"([a-fA-F0-9]{64})\b", result.stdout.strip())
    if not matched:
        raise RuntimeError("Android sha256sum returned an unrecognized result")
    return matched.group(1).lower()

def check_tar_structure(path):
    """Read headers without extracting; reject early EOF / stray trailing data."""
    count = regular = 0
    last_end = 0
    with tarfile.open(path, mode="r:") as archive:
        for item in archive:
            count += 1
            if item.isfile():
                regular += 1
            padded = ((item.size + 511) // 512) * 512
            last_end = max(last_end, item.offset_data + padded)
    size = path.stat().st_size
    if count < MIN_ENTRIES or regular < 2:
        raise RuntimeError(
            f"TAR only exposes {count} entries, {regular} files despite {size} bytes; "
            "the archive is incomplete or contains early end markers."
        )
    # Proper TARs have two zero header blocks and may pad their last record.
    trailer_bytes = size - last_end
    if size % 512 != 0 or trailer_bytes < 1024 or trailer_bytes > 10240:
        raise RuntimeError(f"Invalid TAR ending (size={size}, trailing={trailer_bytes})")
    with path.open("rb") as f:
        f.seek(last_end)
        if f.read(1024) != b"\0" * 1024:
            raise RuntimeError("Missing the two TAR end-of-archive blocks")
    return count, regular, size

def create_stage(adb, *, max_idle=240):
    if device_exists(adb, STAGED):
        current = device_size(adb, STAGED)
        print(f"Existing staged archive found in LDPlayer: {STAGED} "
              f"({current or 0} bytes). Will verify and reuse; no overwrite.", flush=True)
        return
    print("Creating TAR entirely inside LDPlayer (original game files untouched).",
          flush=True)
    cmd = adb + ["shell", "su -c 'tar -C " + SOURCE + " -cf " + STAGED + " .'"]
    last_size = -1
    last_change = time.monotonic()
    with tempfile.TemporaryFile() as err:
        process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=err)
        try:
            while process.poll() is None:
                time.sleep(5)
                current = device_size(adb, STAGED)
                if current is not None and current != last_size:
                    last_size = current
                    last_change = time.monotonic()
                    print(f"LDPlayer staged {current/2**20:,.1f} MiB", flush=True)
                if time.monotonic() - last_change > max_idle:
                    process.kill()
                    process.wait()
                    raise RuntimeError(
                        "LDPlayer TAR creation stalled. Incomplete staged file kept. "
                        "Do not use it; send the progress and diagnostics."
                    )
            code = process.wait()
            if code != 0:
                err.seek(0)
                raise RuntimeError("Android tar failed: " +
                                   err.read(2000).decode("utf-8", "replace"))
        except KeyboardInterrupt:
            process.kill()
            process.wait()
            print("Interrupted: staged file may be partial; no game content deleted.")
            raise
    print("Android TAR writing completed.", flush=True)

def pull_and_verify(adb, destination):
    if not device_exists(adb, STAGED):
        raise RuntimeError("No staged TAR exists on Android")
    expected = device_size(adb, STAGED)
    if expected is None or expected < 10 * 1024 * 1024:
        raise RuntimeError("Staged TAR unexpectedly small or unreadable: " + str(expected))
    if destination.exists():
        raise RuntimeError("Destination already exists: " + str(destination))
    part = destination.with_name(destination.name + ".part")
    if part.exists():
        raise RuntimeError("Another partial destination already exists: " + str(part))
    free = shutil.disk_usage(destination.parent).free
    if free < expected + 512 * 1024 * 1024:
        raise RuntimeError("Windows disk requires staged TAR size + 512 MiB free")
    print(f"Copying {expected/2**20:,.1f} MiB using adb pull (shows progress)...", flush=True)
    completed = subprocess.run(adb + ["pull", STAGED, str(part)])
    if completed.returncode != 0:
        raise RuntimeError("adb pull failed; partial Windows copy preserved at " + str(part))
    actual = part.stat().st_size
    if actual != expected:
        raise RuntimeError(f"Size mismatch: device {expected}, PC {actual}. "
                           f"Partial Windows copy: {part}")
    print("Comparing SHA256 checksums on device and Windows...", flush=True)
    source_hash = sha256_device(adb, STAGED)
    local_hash = sha256_local(part)
    if source_hash != local_hash:
        raise RuntimeError("SHA256 differs between Android and Windows; "
                           "do not use the archive. Windows copy: "+str(part))
    print("SHA256 equal:", local_hash, flush=True)
    count, files, size = check_tar_structure(part)
    part.replace(destination)
    print(f"Verified {files:,} regular files in {count:,} TAR entries, "
          f"{size/2**30:.2f} GiB.", flush=True)
    print("Saved PRIVATE archive:", destination, flush=True)
    print("Do NOT upload the raw TAR to GitHub; account data may be present.")
    print("Staged Android copy remains at:", STAGED)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-idle", type=int, default=240)
    args = parser.parse_args()
    if not args.adb.is_file():
        parser.error("ADB executable not found: " + str(args.adb))
    if args.max_idle < 30:
        parser.error("--max-idle must be at least 30 seconds")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    adb = [str(args.adb), "-s", args.serial]
    if not check_root(adb):
        parser.error("Root unavailable: adb -s emulator-5554 shell su -c id")
    create_stage(adb, max_idle=args.max_idle)
    pull_and_verify(adb, args.output.resolve())

if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        sys.exit(str(exc))
