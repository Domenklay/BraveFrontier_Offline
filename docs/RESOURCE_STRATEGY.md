# Strategy for genuine offline client resources

Updated: 2026-11-07.

## What we have

- User-supplied BF Revive V20 APK (original Brave Frontier Global 2.19.6 client, patched by fans).
- Bundled client assets: 1,373 entries under assets/, about 30.8 MiB unpacked.
- Original emulator source and 18 curated JSON archive groups via pinned submodules.
- Pinned server ServerCache.cpp explicitly requests 126 distinct decoded master JSON tables.
- The full downloadable /content and /mst asset trees and decoded client master tables are **not** in the provided APK or the emulator repo.

## Why an enormous all-in-one APK is uncertain

Community preservation mirrors include several years of sprite art, effects,
music, scripts, images and extra game versions. The reported download volume
can exceed 11 GB, but this is NOT a verified size for the subset required by
the Global 2.19.6 client. Do not treat it as an exact base-game size.

A single Android APK with multi-gigabyte compressed resources may encounter
package/archive limits and require substantial additional free storage
because the existing server reads game data from normal files. We must first
identify the exact required local client content and compressed byte totals.

## Packaging preference

1. **Priority A:** original fan-patched APK with native server in the same
   installed package, all required assets bundled when final package size
   permits. No internet access for gameplay.
2. **Fallback B:** original APK and embedded native server, plus an offline
   resource pack stored locally on the phone; it must be imported once without
   a persistent network or PC dependency. Only adopt this if the inventory
   shows one APK is infeasible. The current Java service does not yet import
   such a pack.
3. Never silently depend on BF Revive's CDN at runtime.

## Verification gates

- Generate a complete inventory with:
  python tools/audit_content.py --decoded-mst DIR --client-content DIR
- Check missing master tables, 0-byte files, content and mst subfolders.
- Confirm native server can boot from a path inside Android app private files.
- Prove no essential remote request remains in flight on a fresh device with
  airplane mode enabled.
- Verify game modes, saves and characters; don't classify partial screens as a
  restored game.

## Reference

- joppe2001/bf-private-server/docs/GETTING_STARTED.md explains the three
  separate data roots and that the code repo ships no client content.
- https://bfrevive.net/bounty/ describes a large available CDN asset set.
- https://www.reddit.com/r/bravefrontier/comments/ucngf1/ describes the
  community archive. Its all-content download size is not our target size.

Copyrighted client resources must not be copied into a public source repo
without appropriate permission. All packaging tools work on data obtained
and held by the individual user.
