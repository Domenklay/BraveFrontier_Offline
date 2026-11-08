#!/usr/bin/env python3
"""Copy BF Revive's private files from a rooted LDPlayer into ONE local tar file.

Designed for Windows + LDPlayer 9, where 'adb root' is denied but 'su -c id'
works. Streams bytes unmodified via ADB exec-out. Never uploads anything.
The archive is PRIVATE: do not upload it to GitHub or share account data.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time

PKG = "sg.gumi.bravefrontier"
REMOTE = "/data/data/" + PKG + "/files"
BUFFER = 1024 * 1024

def adb_run(adb, tail):
    return subprocess.run([*adb, *tail], capture_output=True, text=True, errors="replace")

def root_available(adb):
    result = adb_run(adb, ["shell", "su", "-c", "id"])
    return result.returncode == 0 and bool(re.search(r"\buid=0(?:\(root\)|\b)", result.stdout))

def remote_size(adb):
    result = adb_run(adb, ["shell", "su -c 'du -sk " + REMOTE + "'"])
    if result.returncode == 0:
        match = re.match(r"\s*(\d+)", result.stdout)
        if match:
            return int(match.group(1)) * 1024
    return None

def stream_to_disk(process, part, *, idle_seconds=120, report_seconds=4):
    """Stream raw bytes; stderr is NOT a PIPE to avoid ADB/tar deadlocks.

    The watch thread terminates adb if NO bytes arrive for idle_seconds.
    The destination is a .part file until adb reports successful exit.
    """
    written = 0
    last_read = [time.monotonic()]
    done = threading.Event()
    timed_out = threading.Event()
    def watchdog():
        while not done.wait(3):
            if time.monotonic() - last_read[0] > idle_seconds:
                timed_out.set()
                process.kill()
                return

    watch = threading.Thread(target=watchdog, name="adb-idle-watchdog", daemon=True)
    watch.start()
    next_report = time.monotonic() + report_seconds
    try:
        with part.open("xb") as destination:
            while True:
                chunk = process.stdout.read(BUFFER)
                if not chunk:
                    break
                destination.write(chunk)
                written += len(chunk)
                last_read[0] = time.monotonic()
                if time.monotonic() >= next_report:
                    print(f"Downloaded {written / 2**20:,.1f} MiB; "
                          f"file: {part}", flush=True)
                    next_report = time.monotonic() + report_seconds
            destination.flush()
        return written, timed_out.is_set()
    finally:
        done.set()
        watch.join(timeout=2)
        process.stdout.close()

def pull_archive(adb, output, *, idle_seconds=120):
    if output.exists():
        raise RuntimeError(f"Refusing to overwrite existing archive: {output}")
    part = output.with_name(output.name + ".part")
    if part.exists():
        raise RuntimeError(f"Partial archive exists: {part}. Inspect it before retrying "
                           "with a different output name.")
    if not root_available(adb):
        raise RuntimeError("ADB su is not root. Check: adb -s emulator-5554 shell su -c id")
    exists = adb_run(adb, ["shell", "su -c 'test -d " + REMOTE + "'"])
    if exists.returncode:
        raise RuntimeError(f"Remote folder unavailable: {REMOTE}")
    estimate = remote_size(adb)
    free = shutil.disk_usage(output.parent).free
    if estimate is not None:
        print(f"Android source size ~{estimate / 2**30:.2f} GiB; "
              f"Windows free space {free / 2**30:.2f} GiB", flush=True)
        if free < estimate + 512 * 1024 * 1024:
            raise RuntimeError("Insufficient free disk space; use another drive with "
                               "at least game data size + 0.5 GiB free.")
    if free < 512 * 1024 * 1024:
        raise RuntimeError("Less than 0.5 GiB of free disk space.")
    # Android tar's stdout must remain binary. Do NOT use PowerShell's '>'
    # because Windows PowerShell 5.x can corrupt native binary output.
    cmd = [*adb, "exec-out", "su -c 'tar -C " + REMOTE + " -cf - .'"]
    print("Starting binary ADB tar stream (no per-file Windows extraction)...",
          flush=True)
    started = time.monotonic()
    with tempfile.TemporaryFile() as error_log:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=error_log)
        try:
            written, timed_out = stream_to_disk(process, part, idle_seconds=idle_seconds)
            status = process.wait(timeout=20)
        except (Exception, KeyboardInterrupt):
            process.kill()
            process.wait()
            print(f"Interrupted. Partial local data was kept as {part}", flush=True)
            raise
        error_log.seek(0)
        errors = error_log.read(4096).decode("utf-8", errors="replace").strip()
    if timed_out:
        raise RuntimeError(f"ADB stopped transferring for {idle_seconds}s. "
                           f"Partial archive: {part}. Diagnostics: {errors[:500]}")
    if status:
        raise RuntimeError(f"ADB/tar exited with status {status}; partial archive: {part}; "
                           f"diagnostics: {errors[:500]}")
    if not written or written % 512:
        raise RuntimeError(f"Empty or truncated tar stream (bytes={written}); "
                           f"partial archive: {part}; diagnostics: {errors[:500]}")
    part.replace(output)
    print(f"Saved: {output} ({written / 2**30:.2f} GiB) "
          f"in {(time.monotonic() - started)/60:.1f} min", flush=True)
    print("PRIVATE BACKUP: review and filter files before GitHub upload.", flush=True)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", default="emulator-5554")
    parser.add_argument("--output", type=Path, required=True,
                        help="Local output TAR file, e.g. C:\\BF_GameDump\\private_files.tar")
    parser.add_argument("--idle-seconds", type=int, default=120)
    args = parser.parse_args()
    if not args.adb.is_file():
        parser.error(f"ADB not found: {args.adb}")
    if args.idle_seconds < 15:
        parser.error("--idle-seconds must be at least 15")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    pull_archive([str(args.adb), "-s", args.serial], args.output.resolve(),
                 idle_seconds=args.idle_seconds)

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        sys.exit(str(exc))
