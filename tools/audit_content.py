#!/usr/bin/env python3
"""Inventory offline Brave Frontier content against exact upstream server source.

No network calls, no downloads, no proprietary files added to Git.
Prints missing decoded MST JSON and client downloadable content inventory.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/"upstream"/"server"/"server"/"gimuserver"/"drogon"/"ServerCache.cpp"
LOAD=re.compile(r'forge::LoadMst<[^>]+>\s*\(\s*mstRoot\s*,\s*"([^"]+\.json)"\s*\)')

def list_mst_sources(source):
    if not source.is_file():
        raise FileNotFoundError(f"Upstream source not found: {source}; run python tools/sync_upstream.py")
    tables=sorted(set(LOAD.findall(source.read_text(encoding="utf-8"))))
    if len(tables)<80:
        raise ValueError("Upstream loading API changed: cannot trust decoded MST inventory")
    return tables

def scan(source,mst_root,content_root):
    needed=list_mst_sources(source)
    missing=[name for name in needed if not (mst_root/name).is_file()]
    zero=[name for name in needed if (mst_root/name).is_file() and (mst_root/name).stat().st_size==0]
    assets={}
    for category in ("content","mst"):
        folder=content_root/category
        count=0
        total=0
        if folder.is_dir():
            for entry in folder.rglob("*"):
                if entry.is_file():
                    count+=1
                    total+=entry.stat().st_size
        assets[category]={"count":count,"bytes":total,"exists":folder.is_dir()}
    return {
        "decoded_master_tables_expected":len(needed),
        "decoded_master_tables_found":len(needed)-len(missing),
        "decoded_master_tables_missing":missing,
        "decoded_master_tables_zero_size":zero,
        "client_content":assets,
        "ready_for_server_boot":not missing and not zero and
            all(v["count"]>0 for v in assets.values())
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--decoded-mst",type=Path,required=True)
    p.add_argument("--client-content",type=Path,required=True,
                   help="Folder containing content/ and mst/")
    p.add_argument("--upstream-cache",type=Path,default=CACHE)
    p.add_argument("--json",action="store_true")
    a=p.parse_args()
    report=scan(a.upstream_cache,a.decoded_mst,a.client_content)
    if a.json:
        print(json.dumps(report,indent=2,ensure_ascii=False))
    else:
        n=report["decoded_master_tables_expected"]
        found=report["decoded_master_tables_found"]
        print(f"Decoded MST: {found}/{n} required by pinned upstream server source")
        for folder,stat in report["client_content"].items():
            print(f"Client /{folder}: {stat['count']} files, {stat['bytes']/2**20:.1f} MiB")
        if report["decoded_master_tables_missing"]:
            print("Missing decoded client MST tables:")
            print("\n".join("  "+x for x in report["decoded_master_tables_missing"]))
        print("Ready for server data-loading preflight:",report["ready_for_server_boot"])
    return 0 if report["ready_for_server_boot"] else 1

if __name__=="__main__":
    try:sys.exit(main())
    except (FileNotFoundError,ValueError) as exc:sys.exit(str(exc))
