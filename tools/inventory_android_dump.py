#!/usr/bin/env python3
"""Read-only resource inventory of a Brave Frontier emulator dump.

Does NOT connect to the internet, upload or copy files. It excludes sensitive
app state, sessions, databases and preferences. An inventory alone does not
decode client master tables or guarantee complete content coverage.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

SKIP_DIRS = {"shared_prefs","databases","no_backup","app_webview",
             "code_cache","crash","crashlytics",".thumbnails","logs","log"}
SKIP_EXT = {".db",".sqlite",".sqlite3",".log",".pem",".key",".p12",".jks",".keystore",".xml"}
PRIVATE_WORDS = ("token","password","credential","secret","session","cookie","auth")

def detect(head, name):
    if head.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
    if head.startswith(b"\xff\xd8\xff"): return "jpeg"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP": return "webp"
    if head.startswith((b"GIF89a",b"GIF87a")): return "gif"
    if head.startswith(b"OggS"): return "ogg"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE": return "wav"
    if head.startswith(b"ID3") or (len(head)>2 and head[0]==0xff and (head[1]&0xe0)==0xe0): return "mp3"
    if head.startswith((b"PK\x03\x04",b"PK\x05\x06",b"PK\x07\x08")): return "zip"
    if head.startswith(b"\x1f\x8b"): return "gzip"
    if head.startswith(b"\x28\xb5\x2f\xfd"): return "zstd"
    if head.startswith(b"SQLite format 3\x00"): return "sqlite"
    if head.startswith(b"UnityFS"): return "unityfs"
    if name.lower().endswith(".json") and head.lstrip().startswith((b"{",b"[")): return "json"
    return "binary"

def private(path):
    if any(part.lower() in SKIP_DIRS for part in path.parts): return True
    name=path.name.lower()
    if path.suffix.lower() in SKIP_EXT: return True
    if any(word in name for word in PRIVATE_WORDS): return True
    return name in {"cookies","cookies-journal","web data","local state"}

def scan(roots, expected_mst):
    records=[]
    excluded=0
    counts=Counter()
    amounts=Counter()
    found=set()
    seen=set()
    for root_number, root in enumerate(roots, 1):
        if not root.is_dir(): raise ValueError("Missing input directory: "+str(root))
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink(): continue
            relative=path.relative_to(root)
            if private(relative):
                excluded+=1
                continue
            resolved=path.resolve()
            if resolved in seen: continue
            seen.add(resolved)
            try:
                size=path.stat().st_size
                with path.open("rb") as stream: head=stream.read(256)
            except OSError:
                excluded+=1
                continue
            kind=detect(head,path.name)
            if kind=="sqlite":
                excluded+=1
                continue
            records.append({"root":root_number,"path":relative.as_posix(),
                            "bytes":size,"type":kind})
            counts[kind]+=1
            amounts[kind]+=size
            if path.name in expected_mst and kind=="json":
                try:
                    with path.open("r",encoding="utf-8-sig") as stream: json.load(stream)
                    found.add(path.name)
                except (OSError,UnicodeError,ValueError): pass
    return {
        "input_roots":len(roots),
        "note":"Read-only local scan; account/session/config files excluded.",
        "scanned_files":len(records),
        "excluded_files":excluded,
        "total_scanned_bytes":sum(row["bytes"] for row in records),
        "formats":{name:{"files":count,"bytes":amounts[name]}
                   for name,count in sorted(counts.items())},
        "mst_expected":len(expected_mst),
        "mst_found_decoded":sorted(found),
        "mst_missing_decoded":sorted(set(expected_mst)-found),
        "files":records
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,action="append",required=True,
                   help="Android package directory; may be repeated")
    p.add_argument("--required-mst",type=Path,
                   default=Path(__file__).resolve().parents[1]/"docs"/"required_mst_2_19_6.json")
    p.add_argument("--out",type=Path,required=True,help="Write local JSON report")
    a=p.parse_args()
    if a.out.exists(): p.error("Refusing to overwrite "+str(a.out))
    if not a.required_mst.is_file(): p.error("Missing table list "+str(a.required_mst))
    expected=json.loads(a.required_mst.read_text(encoding="utf-8"))["tables"]
    report=scan(a.root,expected)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Found {report['scanned_files']} candidate files, {report['total_scanned_bytes']/2**20:.1f} MiB")
    for kind,counts in report["formats"].items():
        print(f"  {kind:9s} {counts['files']:>7d} files {counts['bytes']/2**20:>9.1f} MiB")
    print(f"Decoded MST present: {len(report['mst_found_decoded'])}/{report['mst_expected']}")
    print("Report:",a.out)
    print("Never publish app-private dumps or unreviewed inventory manifests.")
    return 0

if __name__=="__main__":
    try: sys.exit(main())
    except (ValueError,OSError) as exc: sys.exit(str(exc))
