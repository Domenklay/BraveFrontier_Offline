#!/usr/bin/env python3
"""Compile PINNED original server sources with Android NDK (no gameplay rewrite).

Requires upstream server fetched with tools/sync_upstream.py, CMake 4+, Ninja,
Rust/Cargo, Android NDK, vcpkg and an Android-compatible C++ dependency graph.
Upstream CMake uses CMAKE_SOURCE_DIR, hence a disposable source checkout.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "upstream" / "server" / "server"
BRIDGE = ROOT / "android-host" / "native"
WORK = ROOT / "build" / "android-port" / "server"
OUT = ROOT / "build" / "android-port" / "arm64-v8a"
TARGET = ROOT / "android-host" / "host" / "src" / "main" / "jniLibs" / "arm64-v8a" / "libbf_offline_server.so"

def run(args):
    print("+", " ".join(map(str,args)), flush=True)
    subprocess.run([str(x) for x in args], check=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ndk", default=os.environ.get("ANDROID_NDK_HOME") or os.environ.get("ANDROID_NDK_ROOT"))
    parser.add_argument("--vcpkg", default=os.environ.get("VCPKG_ROOT"))
    parser.add_argument("--configure-only", action="store_true")
    args = parser.parse_args()
    if not SOURCE.is_dir():
        parser.error("Run python tools/sync_upstream.py first")
    if not args.ndk or not Path(args.ndk).is_dir():
        parser.error("Supply --ndk or ANDROID_NDK_HOME")
    if not args.vcpkg or not (Path(args.vcpkg)/"scripts"/"buildsystems"/"vcpkg.cmake").is_file():
        parser.error("Supply --vcpkg or VCPKG_ROOT")
    if WORK.exists(): shutil.rmtree(WORK)
    WORK.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(SOURCE,WORK,ignore=shutil.ignore_patterns(".git","out","*.obj","*.pdb"))
    cmakelists=WORK/"CMakeLists.txt"
    script=cmakelists.read_text(encoding="utf-8")
    anchor="project(GimuServer)"
    if anchor not in script: raise RuntimeError("Unexpected upstream CMake layout")
    script=script.replace(anchor,anchor+"\nset(CMAKE_POSITION_INDEPENDENT_CODE ON)",1)
    # Preserve upstream's CMAKE_SOURCE_DIR (packet generator expects it).
    script+="\n# Android bridge (added to disposable source checkout)\n"
    script+=f'add_subdirectory("{BRIDGE.as_posix()}" "{CMAKE_BINARY_DIR}/offline_bridge")\n'
    cmakelists.write_text(script,encoding="utf-8")
    vcpkg=Path(args.vcpkg).resolve()
    ndk=Path(args.ndk).resolve()
    run(["cmake","-S",WORK,"-B",OUT,"-G","Ninja",
         f"-DCMAKE_TOOLCHAIN_FILE={vcpkg/'scripts/buildsystems/vcpkg.cmake'}",
         f"-DVCPKG_CHAINLOAD_TOOLCHAIN_FILE={ndk/'build/cmake/android.toolchain.cmake'}",
         "-DVCPKG_TARGET_TRIPLET=arm64-android",
         "-DANDROID_ABI=arm64-v8a",
         "-DANDROID_PLATFORM=android-26",
         "-DANDROID_STL=c++_static",
         "-DGIMUSRV_FRONTEND=STANDALONE",
         "-DGIMU_ENABLE_DEBUG_CLI=OFF",
         "-DCMAKE_BUILD_TYPE=Release"])
    if args.configure_only: return
    run(["cmake","--build",OUT,"--target","bf_offline_server","--parallel","2"])
    lib=OUT/"offline_native"/"libbf_offline_server.so"
    if not lib.is_file(): raise RuntimeError(f"No compiled library at {lib}")
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(lib,TARGET)
    print("Existing server compiled for Android:",TARGET)
    print("Runtime and original-client boot are not yet verified.")

if __name__=="__main__":
    try:main()
    except (subprocess.CalledProcessError,RuntimeError) as e:
        sys.exit(f"Android NDK build unresolved: {e}")
