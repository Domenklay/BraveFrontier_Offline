#!/usr/bin/env python3
"""Read-only verification of a LDPlayer Android private-data TAR export.

Does not extract, upload, modify, or list account filenames. Reads the archive
sequentially and reports whether complete TAR entries can be processed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import tarfile
import time

CHUNK = 8 * 1024 * 1024

def inspect(source: Path) -> dict:
    size = source.stat().st_size
    count = 0
    regular_bytes = 0
    consumed_bytes = 0
    types = Counter()
    error = None
    with source.open('rb') as f:
        first = f.read(512)
        f.seek(max(0, size - 8192))
        end = f.read()
        f.seek(0)
        last_report = time.monotonic()
        try:
            with tarfile.open(fileobj=f, mode='r|') as archive:
                for item in archive:
                    count += 1
                    types['regular' if item.isfile() else 'directory' if item.isdir() else 'other'] += 1
                    if item.isfile():
                        regular_bytes += item.size
                        member = archive.extractfile(item)
                        if member is None:
                            raise tarfile.ReadError('Unable to open a regular TAR member')
                        remaining = item.size
                        while remaining:
                            data = member.read(min(CHUNK, remaining))
                            if not data:
                                raise tarfile.ReadError('Truncated file payload')
                            consumed_bytes += len(data)
                            remaining -= len(data)
                        member.close()
                    if time.monotonic() - last_report > 5:
                        print(f'Checked {consumed_bytes/2**20:,.1f} MiB of file data; '
                              f'{count} TAR entries', flush=True)
                        last_report = time.monotonic()
        except (tarfile.TarError, OSError, EOFError) as exc:
            error = f'{type(exc).__name__}: {exc}'
    tail_zero_run = len(end) - len(end.rstrip(b'\0'))
    return {
        'archive_bytes': size,
        'archive_mib': round(size / 2**20, 1),
        'remainder_mod_512': size % 512,
        'tar_ustar_magic': first[257:262] == b'ustar',
        'entries_scanned': count,
        'regular_files': types['regular'],
        'directories': types['directory'],
        'other_entries': types['other'],
        'file_payload_bytes': regular_bytes,
        'payload_bytes_verified': consumed_bytes,
        'terminal_zero_run': tail_zero_run,
        'parsing_error': error,
        'length_aligned': size % 512 == 0,
        'trailer_looks_complete': tail_zero_run >= 1024 and size % 512 == 0,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tar', type=Path, help='Local .tar.part or .tar file')
    args = parser.parse_args()
    if not args.tar.is_file():
        parser.error('Archive does not exist: ' + str(args.tar))
    print('Reading TAR stream to validate payload, without extracting files.', flush=True)
    summary = inspect(args.tar)
    for key, value in summary.items():
        print(f'{key}: {value}', flush=True)
    if summary['parsing_error'] or not summary['trailer_looks_complete']:
        print('NOT VERIFIED as a complete TAR: keep the .part file; do not publish it.')
    else:
        print('TAR structure looks complete; still inspect contents before sharing.')

if __name__ == '__main__':
    main()
