#!/usr/bin/env python3
"""Detailed, privacy-preserving inventory of Brave Frontier animation asset families.

Reads an existing verified TAR without extraction or network. Reports ONLY
aggregate counts; NEVER emits filenames, unit IDs, byte samples, or user data.
Can identify common BF unit_*.png / unit_*_cgs.csv / unit_cgg.csv families,
battle-effect .sam files, related sprite sheets and possible MST CSV names.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile

from analyze_ldplayer_assets_tar import private_name

UNIT_SHEET = re.compile(r"^unit_anime_(\d+)\.png$", re.I)
UNIT_PARTS = {
    "unit_cgg": re.compile(r"^unit_cgg_(\d+)\.csv$", re.I),
    "idle_cgs": re.compile(r"^unit_idle_cgs_(\d+)\.csv$", re.I),
    "atk_cgs": re.compile(r"^unit_atk_cgs_(\d+)\.csv$", re.I),
    "move_cgs": re.compile(r"^unit_move_cgs_(\d+)\.csv$", re.I),
}
UNIT_ILLUSTRATION = re.compile(r"^unit_ills_anime_(\d+)\.png$", re.I)
EFFECT_SHEET = re.compile(r"^(.*)_([1-9]\d{0,4})x([1-9]\d{0,4})\.png$", re.I)
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
SAM_RE = re.compile(r"battleeffect", re.I)
PLIST_START = b"<?xml"
SUFFIXES = ("sam", "png", "csv", "plist", "mp3", "dat")
MST_ENCRYPTED_NAME = re.compile(r"^Ver\\d+_[A-Za-z0-9]{8}(?:_[A-Za-z0-9_-]+)?\\.dat$", re.I)

def classify_png(head: bytes) -> str:
    if head.startswith(PNG_MAGIC):
        if len(head) < 24:
            return "PNG short header"
        w, h = struct.unpack(">II", head[16:24])
        if not (1 <= w <= 32768 and 1 <= h <= 32768):
            return "PNG bad dimensions"
        if head[12:16] != b"IHDR":
            return "PNG missing IHDR"
        return "PNG valid header"
    off = head.find(PNG_MAGIC)
    if off > 0:
        return "PNG embedded header"
    if head.startswith(b"\xff\xd8\xff"):
        return "JPEG data with PNG extension"
    if head.startswith(b"\x1f\x8b"):
        return "gzip data with PNG extension"
    if head[:2] in (b"\x78\x01", b"\x78\x9c", b"\x78\xda"):
        return "zlib-like data with PNG extension"
    if head[:4] == b"\0\0\0\0":
        return "zero-prefixed PNG-named data"
    return "unrecognized PNG-named data"

def csv_type(head: bytes) -> str:
    if not head:
        return "empty"
    if head.startswith(b"PK\x03\x04"): return "ZIP-like"
    if b"\0" in head[:256]: return "contains NUL"
    chars=head[:1024]
    printable=sum(b in (9,10,13) or 32<=b<=126 for b in chars)
    if printable/len(chars) >= .90:
        if b"," in chars: return "mostly ASCII, comma delimited"
        if b"\t" in chars: return "mostly ASCII, tab delimited"
        return "mostly ASCII text"
    try:
        chars.decode("utf-8")
        return "UTF-8 text (non-ASCII)"
    except UnicodeDecodeError:
        return "unknown binary or non-UTF-8"

def scan(path: Path, mst: set[str]) -> dict:
    file_ext = Counter()
    png_types = Counter()
    weird_png_prefixes = Counter()
    mst_dat_names = 0
    csv_types = Counter()
    plist_types = Counter()
    animation = Counter()
    family_ids = {"unit_anime":set(), "unit_cgg":set(), "idle_cgs":set(),
                  "atk_cgs":set(), "move_cgs":set()}
    illu_ids=set()
    sam_names=set()
    png_effect_bases=set()
    mst_csv_names=set()
    total=0
    ignored=0
    # Process file headers only. The TAR index is rebuilt locally; no extraction.
    with tarfile.open(path, "r:") as tar:
        for entry in tar:
            if not entry.isfile():
                continue
            total+=1
            name=entry.name.replace("\\", "/")
            components=PurePosixPath(name).parts
            if name.startswith("/") or ".." in components or ":" in name or private_name(name):
                ignored+=1
                continue
            basename=components[-1]
            lower=basename.lower()
            ext=Path(lower).suffix.lstrip(".")
            file_ext[ext or "[none]"]+=1
            if (match:=UNIT_SHEET.fullmatch(lower)):
                family_ids["unit_anime"].add(match.group(1))
                animation["unit sprite sheets by name"]+=1
            for label, expression in UNIT_PARTS.items():
                if (match:=expression.fullmatch(lower)):
                    family_ids[label].add(match.group(1))
                    animation[label+" by name"]+=1
            if (match:=UNIT_ILLUSTRATION.fullmatch(lower)):
                illu_ids.add(match.group(1))
            if lower.endswith(".sam"):
                sam_names.add(lower[:-4])
                if SAM_RE.search(lower):
                    animation["battle effect .sam by name"]+=1
            if lower.endswith(".png") and (match:=EFFECT_SHEET.fullmatch(lower)):
                png_effect_bases.add(match.group(1))
            if lower.endswith(".csv") and lower in mst:
                mst_csv_names.add(lower)
            if ext == "dat" and MST_ENCRYPTED_NAME.fullmatch(lower):
                mst_dat_names += 1
            if ext not in SUFFIXES:
                continue
            stream=tar.extractfile(entry)
            if stream is None:
                continue
            with stream:
                head=stream.read(2048)
            if ext=="png":
                category = classify_png(head)
                png_types[category] += 1
                if category == "unrecognized PNG-named data":
                    # Group unknown headers, never print names, contents or IDs.
                    weird_png_prefixes[head[:4].hex()] += 1
            elif ext=="csv":
                csv_types[csv_type(head)]+=1
            elif ext=="plist":
                plist_types["binary plist" if head.startswith(b"bplist00") else
                            "XML plist" if head.lstrip().startswith((PLIST_START, b"<plist"))
                            else "unrecognized plist"]+=1
    key_sets=family_ids
    sheets=key_sets["unit_anime"]
    all_unit_ids=set().union(*key_sets.values())
    complete=sheets.intersection(*(key_sets[k] for k in
        ("unit_cgg", "idle_cgs", "atk_cgs", "move_cgs")))
    complete_min=sheets.intersection(key_sets["unit_cgg"],key_sets["idle_cgs"])
    sam_paired=len(sam_names & png_effect_bases)
    return {
        "source_file_count": total,
        "skipped_sensitive_or_unsafe_names":ignored,
        "selected_extension_counts":{k:file_ext[k] for k in sorted(SUFFIXES)},
        "png_header_breakdown":dict(png_types.most_common()),
        "unknown_png_top_four_byte_prefixes": [
            {"hex":hexprefix, "count":count}
            for hexprefix,count in weird_png_prefixes.most_common(12)
        ],
        "csv_content_breakdown":dict(csv_types.most_common()),
        "plist_format_breakdown":dict(plist_types.most_common()),
        "unit_animation_filenames":dict(animation.most_common()),
        "unique_ids_by_unit_part":{key:len(val) for key,val in key_sets.items()},
        "unit_ids_seen_in_any_standard_part":len(all_unit_ids),
        "unit_ids_with_sheet_and_idle_frame_table":len(complete_min),
        "unit_ids_with_all_five_standard_parts":len(complete),
        "unit_illustration_ids":len(illu_ids),
        "sam_files_unique_stems":len(sam_names),
        "sam_stems_with_dimension_suffixed_png":sam_paired,
        "possible_mst_csv_by_name":len(mst_csv_names),
        "versioned_encrypted_mst_like_dat_names":mst_dat_names,
        "mst_total_required":len(mst),
        "notes":[
            "Only naming and file header heuristics: animation playback has not been tested.",
            "All counts are aggregates; no raw filenames, IDs, or file content included.",
            "PNG header check does not validate entire PNG image CRC, decoding or animation.",
            "No raw assets or account data were copied, extracted or uploaded."
        ]
    }

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    parser.add_argument("--required-mst",type=Path,
                        default=Path(__file__).resolve().parents[1]/
                                "docs"/"required_mst_2_19_6.json")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if not args.archive.is_file():
        parser.error("Missing TAR: "+str(args.archive))
    data=json.loads(args.required_mst.read_text(encoding="utf-8"))
    expected={name.lower().replace(".json",".csv") for name in data["tables"]}
    report=scan(args.archive,expected)
    text=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    print(text)
    if args.output:
        if args.output.exists():
            parser.error("Will not overwrite an existing report: "+str(args.output))
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding="utf-8")
        print("Aggregate report saved:",args.output)

if __name__=="__main__":
    main()
