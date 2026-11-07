#!/usr/bin/env python3
"""Byte-checked localhost patch for user-owned BF Revive V20 (Global 2.19.6.0).

This patches the EXISTING game's native client; it does NOT emulate the server,
install an APK, or redistribute game assets. The unsigned output must later be
combined with the upstream server and re-signed, once the server is functional.
"""
from __future__ import annotations
import argparse
import hashlib
import zipfile
from pathlib import Path

LIB = 'lib/arm64-v8a/libgame.so'
SOURCE_SHA256 = 'b7e856193c378edd17ac12b0551e001535454d112c9e4e346e83d3bd934e0281'
RESULT_SHA256 = '37dd87af1e64f115882d23aa11b525a915e1f84e99fe2798d26ba4c55b7e5af5'

def exact_patch(offset: int, original: bytes, updated: bytes, purpose: str):
    assert len(original) == len(updated)
    return (offset, original, updated, purpose)

PATCHES = (
    exact_patch(0x232711F, b'api.bfrevive.net\0', b'127.0.0.1:9960\0\0\0', 'Boot API host'),
    exact_patch(0x23270E6, b'cdn.bfrevive.net\0', b'127.0.0.1:9960\0\0\0', 'Asset recovery host'),
    exact_patch(0x2369CE3, b'https://\0', b'http://\0\0', 'Shared game API scheme'),
    exact_patch(0xF5FBEC, bytes.fromhex('694ec7f2'), bytes.fromhex('49e7c5f2'), 'SSO HTTPS assembly 1'),
    exact_patch(0xF5FBF0, bytes.fromhex('08028052'), bytes.fromhex('c8018052'), 'SSO HTTPS length'),
    exact_patch(0xF5FBF4, bytes.fromhex('e9e5e5f2'), bytes.fromhex('e905e0f2'), 'SSO HTTPS assembly 2'),
    exact_patch(0x1C7A5C8, bytes.fromhex('08028052'), bytes.fromhex('c8018052'), 'DLS host HTTPS length'),
    exact_patch(0x1C7A5DC, bytes.fromhex('684ec7f2'), bytes.fromhex('48e7c5f2'), 'DLS host HTTPS assembly 1'),
    exact_patch(0x1C7A5E0, bytes.fromhex('e8e5e5f2'), bytes.fromhex('e805e0f2'), 'DLS host HTTPS assembly 2'),
)

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def patch_library(content: bytes) -> bytes:
    actual = digest(content)
    if actual != SOURCE_SHA256:
        raise ValueError(f'Unsupported or already-patched libgame.so SHA256 {actual}; expected {SOURCE_SHA256}')
    target = bytearray(content)
    for offset, original, updated, purpose in PATCHES:
        if target[offset:offset+len(original)] != original:
            raise ValueError(f'{purpose}: unexpected bytes at 0x{offset:X}, refusing to patch')
        target[offset:offset+len(original)] = updated
    result = bytes(target)
    if digest(result) != RESULT_SHA256:
        raise ValueError('Output native hash mismatch, refusing to export')
    return result

def verify(apk: Path) -> bytes:
    if not zipfile.is_zipfile(apk):
        raise ValueError('Not an Android APK/ZIP')
    with zipfile.ZipFile(apk) as source:
        if 'AndroidManifest.xml' not in source.namelist():
            raise ValueError('APK manifest missing')
        return patch_library(source.read(LIB))

def make_unsigned_apk(source: Path, output: Path, updated_lib: bytes) -> None:
    if source.resolve() == output.resolve():
        raise ValueError('Never overwrite the source APK')
    if output.exists():
        raise FileExistsError(f'Output exists: {output}')
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(source) as input_zip, zipfile.ZipFile(output, 'w', allowZip64=True) as target:
            for member in input_zip.infolist():
                name = member.filename
                upper = name.upper()
                # Original signatures are invalidated by libgame.so changes.
                if upper.startswith('META-INF/') and (upper.endswith(('.RSA', '.DSA', '.EC', '.SF'))
                                                      or upper == 'META-INF/MANIFEST.MF'):
                    continue
                content = updated_lib if name == LIB else input_zip.read(member)
                target.writestr(member, content)
            target.comment = b'UNSIGNED - BF REVIVE V20 LOCALHOST PATCH, NOT INSTALLABLE'
    except Exception:
        output.unlink(missing_ok=True)
        raise
    with zipfile.ZipFile(output) as result:
        if digest(result.read(LIB)) != RESULT_SHA256:
            output.unlink(missing_ok=True)
            raise ValueError('Output verification failed')

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', type=Path, help='Your own BF Revive V20 APK')
    parser.add_argument('--unsigned-apk', type=Path, help='Build unsigned staging APK; NOT installable')
    parser.add_argument('--patched-lib', type=Path, help='Write patched libgame.so only (local private file)')
    args = parser.parse_args()
    updated = verify(args.apk)
    print('Supported BF Revive V20 client confirmed; all 9 guarded localhost patches verified.')
    print('Native output SHA-256:', digest(updated))
    if args.patched_lib:
        if args.patched_lib.exists():
            parser.error('Patched library path already exists')
        args.patched_lib.parent.mkdir(parents=True, exist_ok=True)
        args.patched_lib.write_bytes(updated)
        print('Private patched native library:', args.patched_lib)
    if args.unsigned_apk:
        make_unsigned_apk(args.apk, args.unsigned_apk, updated)
        print('Unsigned staging APK:', args.unsigned_apk)
        print('NOT installable: original signing was removed; an actual embedded server is NOT included.')

if __name__ == '__main__':
    main()
