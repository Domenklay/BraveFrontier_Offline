#!/usr/bin/env python3
"""Validate public demo content (no Android SDK required)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELEMENTS = {"fire", "water", "earth", "thunder", "light", "dark"}

def check(path):
    doc = json.loads((ROOT / path).read_text(encoding="utf-8"))
    assert doc.get("schema") == 1, f"{path}: unsupported schema"
    for group in ("units", "modes"):
        ids = set()
        for item in doc.get(group, []):
            ident = item["id"]
            assert re.fullmatch(r"[A-Za-z0-9_-]{1,40}", ident), f"{path}: invalid {ident}"
            assert ident not in ids, f"{path}: duplicate {ident}"
            ids.add(ident)
            assert item["element"] in ELEMENTS
            assert 1 <= len(item["name"].strip()) <= 60
            if group == "units":
                assert 1 <= item["hp"] <= 99999
                assert 1 <= item["atk"] <= 9999
                assert 0 <= item["def"] <= 9999
            else:
                assert 1 <= item["waves"] <= 50
                assert 10 <= item["enemyHp"] <= 999999
                assert 1 <= item["enemyAtk"] <= 9999
                assert 0 <= item["reward"] <= 1000000

for path in ("app/src/main/assets/content.json", "content-pack-example.json"):
    check(path)
    print("OK", path)
