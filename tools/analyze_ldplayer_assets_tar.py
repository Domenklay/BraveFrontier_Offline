#!/usr/bin/env python3
"""Analyze a verified LDPlayer Brave Frontier TAR without extracting private data.

Reports aggregate sizes, extension/signature counts and potential MST filenames.
Never prints individual private filenames and never uploads game data.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

MAGIC_READ_SIZE = 96
PRIVATE_SEGMENTS = {
    "shared_prefs", "databases", "app_webview", "code_cache", "no_backup",
    "app_sslcache", "app_fiverocks", "logs", "crash", "crashlytics"
}
PRIVATE_TOKENS = (
    "token", "password", "passwd", "secret", "cookie", "session",
    "credential", "oauth", "account", "login", "auth",
)
ASSET_HINTS = {
    "unit": ("unit", "units", "character", "characters", "hero", "monster", "summon"),
    "animation": ("anim", "animation", "atlas", "sprite", "sprites", "motion", "battle"),
    "texture": ("texture", "textures", "image", "images", "bitmap", "portrait"),
    "sound": ("audio", "sound", "voice", "music", "bgm", "se"),
    "table": ("mst", "master", "table", "tables", "database"),
    "content": ("content", "download", "resource", "resources", "cache"),
}

def magic_format(head: bytes) -> str:
    if head.startswith(b"\x89PNG\r\n\x1a\n"): return "PNG"
    if head.startswith(b"\xff\xd8\xff"): return "JPEG"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP": return "WEBP"
    if head[:6] in (b"GIF89a", b"GIF87a"): return "GIF"
    if head.startswith(b"OggS"): return "OGG"
    if head.startswith(b"RIFF") and head[8:12] == b"WAVE": return "WAV"
    if head.startswith(b"ID3"): return "MP3"
    if head.startswith(b"PK\x03\x04"): return "ZIP"
    if head.startswith(b"\x1f\x8b"): return "GZIP"
    if head.startswith(b"\x28\xb5\x2f\xfd"): return "ZSTD"
    if head.startswith(b"SQLite format 3\x00"): return "SQLITE"
    if head.startswith(b"UnityFS"): return "UNITYFS"
    if head.lstrip()[:1] in (b"{", b"["): return "JSON-like"
    return "unknown"

def safe_label(segment: str) -> str:
    """Don't expose unique usernames, paths, IDs, or credential-like names."""
    if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,29}", segment)
        or any(word in segment.lower() for word in PRIVATE_TOKENS)):
        return "[other]"
    return segment

def private_name(name: str) -> bool:
    parts = [part.lower() for part in PurePosixPath(name).parts]
    return (any(part in PRIVATE_SEGMENTS for part in parts)
            or any(token in part for part in parts for token in PRIVATE_TOKENS)
            or any(part.endswith(s) for part in parts
                   for s in (".sqlite", ".sqlite3", ".db", ".key", ".pem")))

def bucket_data(counter: Counter, sizes: Counter, limit: int) -> list[dict]:
    return [{"label": key, "files": count, "bytes": sizes[key]}
            for key, count in counter.most_common(limit)]

def scan(archive_path: Path, required_mst: set[str], *, top: int=18) -> dict:
    extensions=Counter()
    extension_bytes=Counter()
    signatures=Counter()
    signature_bytes=Counter()
    folders=Counter()
    folder_bytes=Counter()
    hints=Counter()
    hints_bytes=Counter()
    all_files=0
    all_bytes=0
    private_files=0
    private_bytes=0
    possible_mst=set()
    decoded_mst=set()
    suspicious_paths=0
    non_regular=0
    with tarfile.open(archive_path, "r:") as archive:
        for member in archive:
            if not member.isfile():
                non_regular+=1
                continue
            name=member.name.replace("\\", "/")
            parts=PurePosixPath(name).parts
            if (name.startswith("/") or ".." in parts or
                not parts or ":" in name or "\0" in name):
                suspicious_paths+=1
                continue
            all_files+=1
            all_bytes+=member.size
            hidden=private_name(name)
            if hidden:
                private_files+=1
                private_bytes+=member.size
                continue
            ext=PurePosixPath(parts[-1]).suffix.lower() or "[no extension]"
            if len(ext)>20: ext="[other extension]"
            extensions[ext]+=1
            extension_bytes[ext]+=member.size
            category="/".join(safe_label(x) for x in parts[:-1][:2]) or "[root]"
            folders[category]+=1
            folder_bytes[category]+=member.size
            for label,words in ASSET_HINTS.items():
                if any(w in x.lower() for x in parts for w in words):
                    hints[label]+=1
                    hints_bytes[label]+=member.size
            if parts[-1].lower() in required_mst:
                possible_mst.add(parts[-1].lower())
            header=b""
            if member.size:
                stream=archive.extractfile(member)
                if stream:
                    with stream:
                        header=stream.read(MAGIC_READ_SIZE)
            kind=magic_format(header)
            signatures[kind]+=1
            signature_bytes[kind]+=member.size
            if parts[-1].lower() in required_mst and kind=="JSON-like":
                decoded_mst.add(parts[-1].lower())
    return {
        "archive_gib": round(archive_path.stat().st_size/(1024**3), 3),
        "regular_files": all_files,
        "regular_file_bytes": all_bytes,
        "excluded_sensitive_name_files": private_files,
        "excluded_sensitive_name_bytes": private_bytes,
        "skipped_unsafe_paths": suspicious_paths,
        "non_regular_entries": non_regular,
        "top_extensions": bucket_data(extensions, extension_bytes, top),
        "top_signatures": bucket_data(signatures, signature_bytes, top),
        "top_directories_redacted": bucket_data(folders, folder_bytes, top),
        "resource_path_hints": bucket_data(hints, hints_bytes, top),
        "mst_required": len(required_mst),
        "mst_name_matches": len(possible_mst),
        "mst_json_like_matches": len(decoded_mst),
        "mst_missing_name_matches": len(required_mst-possible_mst),
        "note": "Aggregate metadata only. File signatures and names do not verify usable assets or decoded MST tables.",
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--required-mst",type=Path,
                        default=Path(__file__).resolve().parents[1]/
                                "docs"/"required_mst_2_19_6.json")
    parser.add_argument("--output",type=Path,
                        help="Optional JSON aggregate report (no raw file paths)")
    parser.add_argument("--top",type=int,default=18)
    args=parser.parse_args()
    if not args.archive.is_file():
        parser.error("Archive not found: "+str(args.archive))
    if not args.required_mst.is_file():
        parser.error("MST list not found: "+str(args.required_mst))
    if args.top<1 or args.top>100:
        parser.error("--top must be in 1..100")
    try:
        mst_data=json.loads(args.required_mst.read_text(encoding="utf-8"))
        expected={x.lower() for x in mst_data["tables"]}
        data=scan(args.archive,expected,top=args.top)
    except (OSError, ValueError, tarfile.TarError) as exc:
        parser.error(f"Cannot analyze archive: {exc}")
    result=json.dumps(data,ensure_ascii=False,indent=2)
    print(result,flush=True)
    if args.output:
        if args.output.exists():
            parser.error("Refusing to overwrite existing report: "+str(args.output))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result+"\n",encoding="utf-8")
        print("Local aggregate report:",args.output)
    print("Nothing extracted or uploaded; do not upload the raw private TAR.")

if __name__=="__main__":
    main()
