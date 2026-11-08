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
    # Android Clang + Glaze 6.5.1 rejects template extern variables specialized
    # for unnamed-namespace types. Give the two JSON DTOs external linkage,
    # without changing their structure or any server/game logic.
    capture = WORK/"gimuserver"/"forge"/"Capture.cpp"
    source = capture.read_text(encoding="utf-8")
    original_open = "namespace forge\n{\n\nnamespace\n{\n\nstruct RawRule"
    patched_open = "namespace forge\n{\n\nstruct RawRule"
    original_close = "struct CaptureOpts : glz::opts"
    patched_close = "namespace\n{\n\nstruct CaptureOpts : glz::opts"
    if source.count(original_open) != 1 or source.count(original_close) != 1:
        raise RuntimeError("Pinned upstream Capture.cpp layout changed")
    source = source.replace(original_open, patched_open, 1)
    source = source.replace(original_close, patched_close, 1)
    capture.write_text(source, encoding="utf-8")
    # Same upstream Glaze anonymous-type linkage issue applies to RawTuning.
    # Keep the source overlay private to the disposable Android build tree.
    tuning = WORK/"gimuserver"/"forge"/"Tuning.cpp"
    tuning_source = tuning.read_text(encoding="utf-8")
    tuning_open = "namespace forge\n{\n\nnamespace\n{\n\nstruct RawTuning"
    tuning_patched_open = "namespace forge\n{\n\nstruct RawTuning"
    tuning_close = "struct TuningOpts : glz::opts"
    tuning_patched_close = "namespace\n{\n\nstruct TuningOpts : glz::opts"
    if tuning_source.count(tuning_open) != 1 or tuning_source.count(tuning_close) != 1:
        raise RuntimeError("Pinned upstream Tuning.cpp layout changed")
    tuning_source = tuning_source.replace(tuning_open, tuning_patched_open, 1)
    tuning_source = tuning_source.replace(tuning_close, tuning_patched_close, 1)
    tuning.write_text(tuning_source, encoding="utf-8")
    # The pinned upstream has several additional Glaze DTOs declared in
    # anonymous namespaces. Clang 18 + Glaze 6.5 rejects their generated
    # external variable templates. Promote ONLY those data structs to their
    # enclosing named namespace in the disposable Android copy; all state,
    # functions, gameplay logic and files in upstream/ remain untouched.
    def promote_types(path, names):
        target = WORK/path
        contents = target.read_text(encoding="utf-8")
        for name in names:
            declaration = "struct " + name + "\n{"
            if contents.count(declaration) != 1:
                raise RuntimeError("Pinned upstream Glaze layout changed: " + str(path) + ": " + name)
            begin = contents.index(declaration)
            end = contents.find("\n};", begin)
            if end < 0:
                raise RuntimeError("Unterminated Glaze DTO: " + str(path) + ": " + name)
            end += len("\n};")
            contents = (contents[:begin]
                + "} // leave anonymous namespace for Glaze DTO\n\n"
                + contents[begin:end]
                + "\n\nnamespace\n{ // resume original anonymous namespace\n"
                + contents[end:])
        target.write_text(contents, encoding="utf-8")

    promote_types(Path("gimuserver/gme/common/EventRotation.cpp"),
                  ("RotationEvent", "EventRotationFile", "ScheduleEvent", "EventSchedule"))
    promote_types(Path("gimuserver/gme/common/Exchange.cpp"), ("ForgeOffer",))
    promote_types(Path("gimuserver/gme/common/SummonRotation.cpp"),
                  ("RotationGate", "RotationFile"))
    promote_types(Path("gimuserver/gme/common/UnitPick.cpp"), ("RacePickFile",))
    promote_types(Path("gimuserver/gme/common/NewsPosts.cpp"), ("NewsFile",))
    promote_types(Path("gimuserver/gme/common/RaidRooms.cpp"), ("RoomPartyRow",))
    # Request DTOs used directly by Glaze in existing quest and summoning
    # handlers are subject to the same NDK-only linkage restriction.
    promote_types(Path("gimuserver/gme/handlers/TrialDeck.cpp"),
                  ("TrialDeckRow", "TrialDeckReq", "TrialDeckResp"))
    promote_types(Path("gimuserver/gme/handlers/UnitOmniEvo.cpp"),
                  ("OmniRecipeTypeNode", "OmniEvoBody"))
    promote_types(Path("gimuserver/gme/handlers/UnitSelectorGachaTicket.cpp"),
                  ("SelectorReqItem", "SelectorReq"))
    cmakelists=WORK/"CMakeLists.txt"
    script=cmakelists.read_text(encoding="utf-8")
    anchor="project(GimuServer)"
    if anchor not in script: raise RuntimeError("Unexpected upstream CMake layout")
    # The upstream has no C++20 modules. New CMake 4 enables module scanning for
    # C++23 targets and can select Ubuntu clang-scan-deps while Android NDK Clang
    # compiled the PCH, producing an incompatible-PCH toolchain error.
    script=script.replace(anchor,anchor+"\nset(CMAKE_POSITION_INDEPENDENT_CODE ON)"
                          +"\nset(CMAKE_CXX_SCAN_FOR_MODULES OFF)",1)
    # Preserve upstream's CMAKE_SOURCE_DIR (packet generator expects it).
    script+="\n# Android bridge (added to disposable source checkout)\n"
    script += 'add_subdirectory("{}" "${{CMAKE_BINARY_DIR}}/offline_bridge")\n'.format(BRIDGE.as_posix())
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
    # Trim only DWARF/debug data. Keep JNI dynamic symbols and C++ static
    # initialisers needed by Drogon's original controller registrations.
    original_size = TARGET.stat().st_size
    llvm_tools = ndk/"toolchains"/"llvm"/"prebuilt"
    candidates = sorted(llvm_tools.glob("*/bin/llvm-strip"))
    if not candidates:
        candidates = sorted(llvm_tools.glob("*/bin/llvm-strip.exe"))
    if not candidates:
        raise RuntimeError("NDK llvm-strip executable not found")
    strip_tool = candidates[0]
    run([strip_tool, "--strip-debug", TARGET])
    nm_tool = strip_tool.with_name("llvm-nm" + (".exe" if strip_tool.suffix == ".exe" else ""))
    if not nm_tool.is_file():
        raise RuntimeError("NDK llvm-nm not found; cannot verify JNI exports")
    exports = subprocess.run([str(nm_tool), "-D", str(TARGET)],
                             check=True,capture_output=True,text=True).stdout
    for symbol in ("Java_com_domenklay_bfoffline_EmbeddedServerService_runNativeServer",
                   "Java_com_domenklay_bfoffline_EmbeddedServerService_stopNativeServer"):
        if symbol not in exports:
            raise RuntimeError("Required JNI entrypoint missing: " + symbol)
    print("Existing server compiled for Android:",TARGET)
    print(f"Native library size: {original_size} -> {TARGET.stat().st_size} bytes (debug stripped)")
    print("JNI exports verified; Android runtime and original client are not yet tested.")

if __name__=="__main__":
    try:main()
    except (subprocess.CalledProcessError,RuntimeError) as e:
        sys.exit(f"Android NDK build unresolved: {e}")
