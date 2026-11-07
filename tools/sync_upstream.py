#!/usr/bin/env python3
"""Fetch the pinned upstream sources instead of rewriting Brave Frontier."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "upstream.lock.json").read_text(encoding="utf-8"))
TARGET = ROOT / "upstream"

def command(*argv, cwd=None, capture=False):
    print("+", " ".join(argv), flush=True)
    return subprocess.run(argv, cwd=cwd, check=True, text=True, capture_output=capture)

def sync(name):
    info = LOCK[name]
    local = TARGET / name
    if not local.exists():
        command("git", "clone", "--no-checkout", info["repository"], str(local))
    if not (local / ".git").is_dir():
        raise RuntimeError(f"{local} is not a Git checkout; refusing to overwrite")
    status = command("git", "status", "--porcelain", cwd=local, capture=True).stdout
    if status.strip():
        raise RuntimeError(f"{local} has uncommitted changes; refusing to overwrite")
    command("git", "fetch", "origin", info["commit"], cwd=local)
    command("git", "checkout", "--detach", info["commit"], cwd=local)
    head = command("git", "rev-parse", "HEAD", cwd=local, capture=True).stdout.strip()
    if head != info["commit"]:
        raise RuntimeError(f"Unexpected commit for {name}: {head}")
    print(f"{name} pinned at {head}", flush=True)

def main():
    TARGET.mkdir(exist_ok=True)
    sync("server")
    sync("data")
    print("Upstream code and curated server data acquired.")
    print("Original APK, art, downloaded assets and decoded master tables are NOT included.")

if __name__ == "__main__":
    try:
        main()
    except (subprocess.CalledProcessError, RuntimeError) as e:
        sys.exit(str(e))
