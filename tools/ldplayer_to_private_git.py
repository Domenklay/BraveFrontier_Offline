#!/usr/bin/env python3
"""Export BF Revive game resources from LDPlayer; stage a reviewed private Git archive.

Commands:
  pull     Copy only the game's external data/cache/OBB folders using ADB.
  prepare  Select candidate resource files for MANUAL REVIEW (no secrets by design).
  publish  Upload reviewed files ONLY to a verified PRIVATE GitHub repository.

No command modifies Android app data. Never point publish at the raw dump.
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import re
import shutil
import subprocess
import sys

PKG = "sg.gumi.bravefrontier"
RESOURCE_EXT = frozenset((
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ogg", ".mp3", ".wav", ".mp4",
    ".json", ".plist", ".atlas", ".skel", ".anim", ".bytes",
    ".dat", ".bin", ".pak", ".obb", ".zip", ".unity3d", ".asset",
    ".bundle", ".cpk", ".acb", ".awb", ".lz4", ".gz", ".zst", ".txt",
))
SKIP_DIR = frozenset((
    "shared_prefs", "databases", "no_backup", "app_webview",
    "code_cache", ".git", ".thumbnails", "log", "logs", "crash", "crashlytics",
))
SKIP_SUFFIX = frozenset((
    ".db", ".sqlite", ".sqlite3", ".db-journal", ".db-wal", ".key",
    ".pem", ".p12", ".keystore", ".jks", ".log", ".xml",
))
SENSITIVE_NAME = re.compile(
    r"(?:^|[_\-.])(password|passwd|credential|secret|cookie|session|"
    r"account|device_id|access_token|refresh_token|auth_token)(?:$|[_\-.])",
    re.I
)
LFS_PATTERNS = ("*.obb", "*.bundle", "*.unity3d", "*.pak", "*.zip",
                "*.asset", "*.cpk", "*.acb", "*.awb")

def run(cmd, *, check=True, capture=False):
    result = subprocess.run([str(x) for x in cmd], check=False, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None,
                            errors="replace")
    if check and result.returncode:
        msg = (result.stderr or result.stdout or "").strip() if capture else ""
        raise RuntimeError("Command failed: " + " ".join(map(str, cmd)) + " " + msg)
    return result

def safe_resource(relative):
    if relative.is_absolute() or ".." in relative.parts:
        return False
    if any(x.lower() in SKIP_DIR for x in relative.parts):
        return False
    if any(SENSITIVE_NAME.search(x) for x in relative.parts):
        return False
    if relative.suffix.lower() in SKIP_SUFFIX:
        return False
    if relative.suffix.lower() not in RESOURCE_EXT:
        return False
    # Not all JSON/TXT files in app data are game data. Allow only the
    # recognizable MST tables and client content paths by default.
    if relative.suffix.lower() in {".json", ".txt"}:
        lower_parts = [p.lower() for p in relative.parts]
        return (relative.name.lower().endswith("_mst.json")
                or any(p in {"mst", "content", "game_content", "master"} for p in lower_parts))
    return True

def adb_for(args):
    binary = args.adb
    if not shutil.which(binary) and not Path(binary).is_file():
        raise RuntimeError("ADB not found. Specify --adb with your LDPlayer9 adb.exe path.")
    result = run([binary, "devices", "-l"], capture=True)
    devices = re.findall(r"^(\S+)\s+device(?:\s|$)", result.stdout, re.M)
    if args.serial:
        if args.serial not in devices:
            raise RuntimeError("Device not available: " + args.serial + "; " + str(devices))
        serial = args.serial
    elif len(devices) == 1:
        serial = devices[0]
    else:
        raise RuntimeError(f"Found {len(devices)} devices {devices}; pass --serial SERIAL")
    return [binary, "-s", serial]

def adb_shell_exists(adb, remote):
    return run(adb+["shell","test","-d",remote],check=False,capture=True).returncode == 0

def pull(args):
    adb = adb_for(args)
    pm = run(adb+["shell","pm","path",PKG],capture=True)
    if "package:" not in pm.stdout:
        raise RuntimeError("BF Revive is not installed as " + PKG)
    out = args.output.resolve()/"raw"
    out.mkdir(parents=True, exist_ok=True)
    targets = {
        "external_files": f"/sdcard/Android/data/{PKG}/files",
        "external_cache": f"/sdcard/Android/data/{PKG}/cache",
        "external_obb": f"/sdcard/Android/obb/{PKG}",
    }
    if args.private_files:
        root = run(adb+["root"],check=False,capture=True)
        run(adb+["wait-for-device"])
        uid = run(adb+["shell","id","-u"],capture=True)
        if uid.stdout.strip() != "0":
            raise RuntimeError("ADB is not root. Enable Root/ADB in LDPlayer settings, "
                               "restart the emulator, then retry --private-files.")
        targets["private_files"] = f"/data/data/{PKG}/files"
        if args.private_cache:
            targets["private_cache"] = f"/data/data/{PKG}/cache"
    copied = 0
    for label,remote in targets.items():
        if not adb_shell_exists(adb,remote):
            print("Not found (skipping):",remote)
            continue
        dest = out/label
        if dest.exists() and any(dest.iterdir()):
            raise RuntimeError("Refusing to overwrite existing backup: " + str(dest))
        dest.mkdir(parents=True, exist_ok=True)
        print(f"Pulling {remote} -> {dest}",flush=True)
        run(adb+["pull",remote,str(dest)])
        copied += 1
    if not copied:
        raise RuntimeError("No app resource folders were found. Inspect via ADB shell first.")
    print(f"Raw backup ready at: {out}")
    print("Do not push raw/ to GitHub. Run the 'prepare' command next.")

def prepare(args):
    raw = args.source.resolve()
    reviewed = args.output.resolve()
    if not raw.is_dir(): raise RuntimeError("Missing raw directory: "+str(raw))
    if reviewed.exists():
        raise RuntimeError("Review output already exists. Use a new directory: "+str(reviewed))
    if reviewed == raw or raw in reviewed.parents or reviewed in raw.parents:
        raise RuntimeError("Review output must be distinct from the raw input")
    candidates=[]
    counts=Counter()
    total=0
    for path in raw.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        rel=path.relative_to(raw)
        if not safe_resource(rel):
            continue
        size=path.stat().st_size
        candidates.append((path,rel,size))
        counts[rel.suffix.lower()]+=1
        total+=size
    if not candidates:
        raise RuntimeError("No recognized game-resource candidates; inspect the cache paths.")
    print(f"Candidates: {len(candidates)} files, {total/2**20:.1f} MiB")
    print("By extension:",dict(counts))
    if not args.confirm_review:
        print("Dry run only. Re-run with --confirm-review to copy candidates.")
        return
    reviewed.mkdir(parents=True, exist_ok=False)
    for path,rel,_ in candidates:
        dest=reviewed/rel
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,dest)
    print("Selected resources prepared at:",reviewed)
    print("IMPORTANT: Inspect all selected files before publishing, especially .dat/.bin.")
    print("Never push private user profiles, SQLite or authentication artifacts.")

def publish(args):
    source=args.source.resolve()
    if not source.is_dir():raise RuntimeError("Missing reviewed directory")
    if source.name.lower() in {"raw","external_files","external_cache","private_files","private_cache"}:
        raise RuntimeError("Refusing to publish raw app data; use a manually reviewed folder.")
    if args.repo.lower() in {"domenklay/bravefrontier_offline","domenklay/bravefrontier_offline.git"}:
        raise RuntimeError("Never push client assets to the PUBLIC source-code repository.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",args.repo):
        raise RuntimeError("Expected GitHub owner/repository, not a URL")
    for tool in ("gh","git"):
        if not shutil.which(tool):raise RuntimeError(tool+" missing; install Git and GitHub CLI.")
    private = run(["gh","repo","view",args.repo,"--json","isPrivate","--jq",".isPrivate"],
                  capture=True)
    if private.stdout.strip().lower() != "true":
        raise RuntimeError("Repository is not PRIVATE. Refusing to upload game assets.")
    run(["git","lfs","version"],capture=True)
    dest=args.workspace.resolve()
    if dest.exists() and not (dest/".git").is_dir():
        raise RuntimeError("Workspace exists but is not a Git clone: "+str(dest))
    if not dest.exists():
        dest.parent.mkdir(parents=True,exist_ok=True)
        run(["gh","repo","clone",args.repo,str(dest)])
    run(["git","-C",str(dest),"lfs","install","--local"])
    for pattern in LFS_PATTERNS:
        run(["git","-C",str(dest),"lfs","track",pattern])
    count=0
    total=0
    for path in source.rglob("*"):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(source)
        if not safe_resource(rel):
            continue
        size=path.stat().st_size
        if size>2*1024**3:
            raise RuntimeError("File over 2 GiB; split outside Git LFS: "+str(rel))
        relative=Path("assets")/rel
        target=dest/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
        if size > 50*1024**2:
            # Explicit LFS tracking, including unusual binary extensions.
            run(["git","-C",str(dest),"lfs","track",relative.as_posix()])
        count+=1
        total+=size
    if not count:raise RuntimeError("No reviewed assets selected")
    run(["git","-C",str(dest),"add","-A","--","assets",".gitattributes"])
    status=run(["git","-C",str(dest),"status","--short"],capture=True)
    print(f"Staged {count} files, {total/2**30:.2f} GiB in PRIVATE repo: {args.repo}")
    print(status.stdout[:4000])
    if not args.push:
        print("Review staged files. Re-run with --push to commit and upload.")
        return
    changed=run(["git","-C",str(dest),"diff","--cached","--quiet"],check=False)
    if changed.returncode==0:
        print("Nothing new to upload.")
        return
    run(["git","-C",str(dest),"commit","-m","Import personally archived BF client game resources"])
    run(["git","-C",str(dest),"push","-u","origin","HEAD"])
    print("Private asset push completed:",args.repo)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    x=sub.add_parser("pull")
    x.add_argument("--adb",required=True,help="Full path to LDPlayer 9 adb.exe")
    x.add_argument("--serial")
    x.add_argument("--output",type=Path,default=Path("C:/BF_Archive"))
    x.add_argument("--private-files",action="store_true",help="Also pull private app/files with root")
    x.add_argument("--private-cache",action="store_true",help="Also pull private app/cache, implies --private-files")
    y=sub.add_parser("prepare")
    y.add_argument("--source",type=Path,required=True,help="Raw backup folder")
    y.add_argument("--output",type=Path,required=True,help="New folder for manually reviewing files")
    y.add_argument("--confirm-review",action="store_true",help="Copy candidates (default is dry-run)")
    z=sub.add_parser("publish")
    z.add_argument("--source",type=Path,required=True,help="Manually reviewed resource folder")
    z.add_argument("--repo",required=True,help="Existing PRIVATE GitHub owner/name")
    z.add_argument("--workspace",type=Path,default=Path("C:/BF_Archive/asset-git"))
    z.add_argument("--push",action="store_true",help="Actually commit and push (default stages only)")
    a=p.parse_args()
    if a.command=="pull":a.private_files |= a.private_cache
    {"pull":pull,"prepare":prepare,"publish":publish}[a.command](a)

if __name__=="__main__":
    try:main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:sys.exit(str(exc))
