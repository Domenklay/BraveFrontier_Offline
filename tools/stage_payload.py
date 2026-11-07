#!/usr/bin/env python3
"""Stage *existing upstream* server data plus separately obtained client data.

No assets are downloaded automatically and no licensed assets enter the repo.
Output is a directory designed for injection under APK assets/bf-offline/.
"""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
from audit_content import scan

ROOT=Path(__file__).resolve().parents[1]
UP=ROOT/"upstream"
DEFAULT_OUT=ROOT/"build"/"offline-payload"

def copy_dir(source,destination):
    if not source.is_dir():
        raise RuntimeError(f"Required source missing: {source}")
    if source.resolve()==destination.resolve():
        raise RuntimeError("Source and destination must differ")
    if any(p.is_symlink() for p in source.rglob("*")):
        raise RuntimeError(f"Symlinked content is not supported: {source}")
    shutil.copytree(source,destination,dirs_exist_ok=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--content-root",type=Path,required=True,
        help="Existing extracted client downloaded resources root containing content/ and mst/")
    parser.add_argument("--decoded-mst",type=Path,required=True,
        help="Existing decoded client master JSON tables (including unit_mst.json)")
    parser.add_argument("--out",type=Path,default=DEFAULT_OUT)
    args=parser.parse_args()
    server=UP/"server"/"server"/"deploy"
    archive=UP/"data"/"archive"
    root=args.out.resolve()
    if root==ROOT or root==Path("/"):
        parser.error("Unsafe --out path")
    if root.exists():
        parser.error("Output exists: choose an empty folder to prevent accidental data loss")
    if not (args.decoded_mst/"unit_mst.json").is_file():
        parser.error("Decoded master table unit_mst.json missing")
    if not (args.content_root/"content").is_dir() or not (args.content_root/"mst").is_dir():
        parser.error("Content root must contain content/ and mst/ directories")
    # Refuse packages which cannot start the pinned upstream server.
    # The upstream ServerCache.cpp uses many more tables than unit_mst.json.
    report = scan(UP/"server"/"server"/"gimuserver"/"drogon"/"ServerCache.cpp",
                  args.decoded_mst, args.content_root)
    if not report["ready_for_server_boot"]:
        missing = report["decoded_master_tables_missing"]
        parser.error(f"Incomplete game resources: decoded MST "
                     f"{report['decoded_master_tables_found']}/"
                     f"{report['decoded_master_tables_expected']} present; "
                     f"first missing: {missing[:8]}. "
                     f"Run python tools/audit_content.py --decoded-mst PATH "
                     f"--client-content PATH for full report.")
    config=server/"config.json"
    if not config.is_file():
        parser.error("Upstream config absent: run tools/sync_upstream.py")
    config_text=config.read_text(encoding="utf-8")
    if '"address": "127.0.0.1"' not in config_text or '"port": 9960' not in config_text:
        parser.error("Upstream config was changed: refusing to package non-loopback server")
    root.mkdir(parents=True)
    # Keep original upstream game-server configuration, except the original
    # notice URL host, which must never point outside the phone.
    config_text=config_text.replace("http://ios21900.bfww.gumi.sg/pages/versioninfo",
                                    "http://127.0.0.1:9960/pages/versioninfo")
    # The upstream DLS response determines *all subsequent* client hosts.
    # Pin both game and resources explicitly rather than relying on a
    # fallback derived from a listener or environment variable.
    server_marker = '"server": {'
    if server_marker not in config_text:
        parser.error("Cannot locate upstream DLS server configuration")
    if '"public_host"' in config_text or '"resource_host"' in config_text:
        parser.error("Review changed upstream host configuration before offline packing")
    config_text = config_text.replace(
        server_marker,
        server_marker + '\\n                    "public_host": "127.0.0.1:9960",'
                      + '\\n                    "resource_host": "127.0.0.1:9960",', 1)

    (root/"config.json").write_text(config_text,encoding="utf-8")
    copy_dir(server/"system",root/"system")
    copy_dir(archive,root/"archive")
    copy_dir(args.decoded_mst,root/"mst")
    copy_dir(args.content_root/"content",root/"game_content"/"content")
    copy_dir(args.content_root/"mst",root/"game_content"/"mst")
    entries=[]
    total=0
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.name=="manifest.tsv": continue
        sha=hashlib.sha256()
        with file.open("rb") as stream:
            for block in iter(lambda:stream.read(1024*1024),b""):
                sha.update(block)
        relative=file.relative_to(root).as_posix()
        size=file.stat().st_size
        total+=size
        entries.append(f"{sha.hexdigest()}\t{size}\t{relative}")
    (root/"manifest.tsv").write_text("\n".join(entries)+"\n",encoding="utf-8")
    print(f"Staged {len(entries)} files, {total/1024/1024:.1f} MiB at {root}")
    print("All payload content stays local; do NOT commit/distribute unlicensed game assets.")
    if total>1_500_000_000:
        print("WARNING: one monolithic APK this large may not install; investigate split asset delivery.")
    print("No native server or original APK was built by this command.")

if __name__=="__main__":
    try: main()
    except RuntimeError as e:sys.exit(str(e))
