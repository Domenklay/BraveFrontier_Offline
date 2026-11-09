#!/usr/bin/env python3
"""Extract a small, clean Brave Frontier animation sample from verified LDPlayer TAR.

Only whitelisted unit animation PNG and CSV names are copied. Never extracts
Android account state, shared preferences, keys, databases or arbitrary paths.
Outputs BFFrameAnimator-compatible Units/<id>/ layout and list.txt locally.
No HTTP, GitHub, or emulator access needed. Originals remain untouched.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import tarfile

from analyze_ldplayer_assets_tar import private_name

PATTERNS = {
    "sheet": re.compile(r"^unit_anime_(\d+)\.png$", re.IGNORECASE),
    "cgg": re.compile(r"^unit_cgg_(\d+)\.csv$", re.IGNORECASE),
    "idle": re.compile(r"^unit_idle_cgs_(\d+)\.csv$", re.IGNORECASE),
    "atk": re.compile(r"^unit_atk_cgs_(\d+)\.csv$", re.IGNORECASE),
    "move": re.compile(r"^unit_move_cgs_(\d+)\.csv$", re.IGNORECASE),
}
PNG_MAGIC=b"\x89PNG\r\n\x1a\n"
MAX_SHEET=64*1024*1024
MAX_CSV=4*1024*1024
REQUIRED=frozenset(PATTERNS)

def safe_member(member):
    if not member.isfile():
        return False
    name=member.name.replace("\\","/")
    path=PurePosixPath(name)
    return (not path.is_absolute()
            and ".." not in path.parts
            and ":" not in name
            and "\0" not in name
            and not private_name(name))

def index_units(archive):
    all_found={}
    for member in archive:
        if not safe_member(member):
            continue
        filename=PurePosixPath(member.name).name
        for kind,expression in PATTERNS.items():
            match=expression.fullmatch(filename)
            if match:
                uid=match.group(1)
                if kind=="sheet" and not (32<=member.size<=MAX_SHEET):
                    break
                if kind!="sheet" and not (0<member.size<=MAX_CSV):
                    break
                all_found.setdefault(uid,{}).setdefault(kind,[]).append(member)
                break
    return all_found

def png_dimensions(archive, member):
    stream=archive.extractfile(member)
    if stream is None:
        return None
    with stream:
        head=stream.read(33)
    if not head.startswith(PNG_MAGIC) or len(head)<33 or head[12:16]!=b"IHDR":
        return None
    w,h=struct.unpack(">II",head[16:24])
    if not (1<=w<=32768 and 1<=h<=32768):
        return None
    return w,h

def pick_units(archive, found, count, only_ids):
    choices=[]
    rejected={"incomplete":0,"duplicate":0,"non_standard_png":0}
    for uid in sorted(found,key=lambda u:(int(u),u)):
        if only_ids and uid not in only_ids:
            continue
        kinds=found[uid]
        if set(kinds)!=REQUIRED:
            rejected["incomplete"]+=1
            continue
        if any(len(items)!=1 for items in kinds.values()):
            rejected["duplicate"]+=1
            continue
        dims=png_dimensions(archive,kinds["sheet"][0])
        if dims is None:
            rejected["non_standard_png"]+=1
            continue
        choices.append((uid,kinds,dims))
        if len(choices)>=count:
            break
    return choices,rejected

def extract_sample(source:Path,output:Path,count:int,ids:set[str]):
    if output.exists():
        raise RuntimeError("Destination already exists; choose a NEW directory: "+str(output))
    if not 1<=count<=50:
        raise RuntimeError("--count must be in 1..50")
    with tarfile.open(source,"r:") as archive:
        found=index_units(archive)
        choices,rejected=pick_units(archive,found,count,ids)
        if not choices:
            raise RuntimeError(
                "No matching complete unit with a standard PNG sprite sheet. "
                f"Inspect obfuscated PNGs next. Rejection counts: {rejected}")
        output.mkdir(parents=True,exist_ok=False)
        manifest=[]
        for uid,kinds,dims in choices:
            target=output/"Units"/uid
            target.mkdir(parents=True)
            copied={}
            for kind,items in kinds.items():
                member=items[0]
                # Use canonical asset name, never a tar-supplied path.
                name=(f"unit_anime_{uid}.png" if kind=="sheet" else
                      f"unit_cgg_{uid}.csv" if kind=="cgg" else
                      f"unit_{kind}_cgs_{uid}.csv")
                destination=target/name
                stream=archive.extractfile(member)
                if stream is None:
                    raise RuntimeError("Missing data for selected resource")
                with stream, destination.open("xb") as sink:
                    shutil.copyfileobj(stream,sink,length=1024*1024)
                copied[kind]={"bytes":destination.stat().st_size,"file":name}
            manifest.append({"unit_id":uid,"sprite_size":{"width":dims[0],"height":dims[1]},
                             "files":copied})
        (output/"list.txt").write_text("\n".join(x["unit_id"] for x in manifest)+"\n",
                                       encoding="utf-8")
        (output/"manifest.json").write_text(json.dumps(
            {"source":"local verified private Brave Frontier TAR",
             "unit_count":len(manifest),"selected":manifest,
             "rejection_counts":rejected,
             "notes":"PNG header only validated, not the full image decode or animation frames."},
             indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return manifest,rejected

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path,help="Verified local BF TAR")
    parser.add_argument("--output",type=Path,required=True,
                        help="New local directory, e.g. C:\\BF_GameDump\\bf-animation-sample")
    parser.add_argument("--count",type=int,default=5)
    parser.add_argument("--unit-id",action="append",default=[])
    args=parser.parse_args()
    if not args.archive.is_file():
        parser.error("Missing archive: "+str(args.archive))
    ids=set(args.unit_id)
    if any(not re.fullmatch(r"\d{1,12}",uid) for uid in ids):
        parser.error("--unit-id requires a numeric game unit ID")
    try:
        selected,rejected=extract_sample(args.archive,args.output,args.count,ids)
    except (RuntimeError,OSError,tarfile.TarError) as exc:
        parser.error(str(exc))
    print(f"Selected {len(selected)} complete units with readable PNG headers:")
    for unit in selected:
        d=unit["sprite_size"]
        print(f"  unit ID {unit['unit_id']} — sprite {d['width']}x{d['height']}, 4 CSV files")
    print("Skipped during selection:",rejected)
    print("Local output:",args.output)
    print("Compatible folder layout for BFFrameAnimator. No game assets were uploaded.")
    print("The selected graphics still require visual and animation-playback checks.")

if __name__=="__main__":
    main()
