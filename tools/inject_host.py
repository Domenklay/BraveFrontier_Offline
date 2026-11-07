#!/usr/bin/env python3
"""Experimental ONE-APK assembly for the ORIGINAL patched Brave Frontier.

Combines:
  (a) a user's individually patched original client (2.19.6),
  (b) our compiled AAR containing Android service/provider,
  (c) the NDK-compiled ORIGINAL upstream C++ server .so,
  (d) separately acquired client assets and MST data (never in Git).
Does not implement or replace ANY game logic.

Requires apktool 2.x, Android SDK build-tools (d8, zipalign, apksigner),
a signing keystore and the already-patched original APK.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ANDROID = "http://schemas.android.com/apk/res/android"
ATTR = lambda name: "{" + ANDROID + "}" + name
ET.register_namespace("android", ANDROID)
HOST_PACKAGE = "com.domenklay.bfoffline"

def run(*command):
    print("+", " ".join(map(str,command)),flush=True)
    subprocess.run([str(x) for x in command],check=True)

def add_manifest_hooks(manifest):
    doc = ET.parse(manifest)
    root = doc.getroot()
    package = root.attrib.get("package", "sg.gumi.bravefrontier")
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]*",package):
        raise RuntimeError("Cannot determine original APK package name")
    existing={p.get(ATTR("name")) for p in root.findall("uses-permission")}
    for permission in ("android.permission.INTERNET",
                       "android.permission.FOREGROUND_SERVICE"):
        if permission not in existing:
            node=ET.Element("uses-permission")
            node.set(ATTR("name"),permission)
            root.insert(0,node)
    application=root.find("application")
    if application is None: raise RuntimeError("Original APK manifest has no application")
    # The injected Android service requires API 26+; do not offer a broken
    # package to Android 4.x/5.x/6.x devices despite the legacy client's minSdk16.
    sdk = root.find("uses-sdk")
    if sdk is None:
        sdk = ET.Element("uses-sdk")
        root.insert(0, sdk)
    current_min = int(sdk.get(ATTR("minSdkVersion"), "1"))
    if current_min < 26:
        sdk.set(ATTR("minSdkVersion"), "26")
    if application.get(ATTR("name"))=="com.domenklay.bfoffline.OfflineBootstrapProvider":
        raise RuntimeError("Unexpected original Application value")
    # An extracted native .so may be compressed in the APK.
    application.set(ATTR("extractNativeLibs"),"true")
    application.set(ATTR("usesCleartextTraffic"),"true")
    provider=ET.SubElement(application,"provider")
    provider.set(ATTR("name"),HOST_PACKAGE+".OfflineBootstrapProvider")
    provider.set(ATTR("authorities"),package+".offline.bootstrap")
    provider.set(ATTR("exported"),"false")
    provider.set(ATTR("initOrder"),"1000")
    service=ET.SubElement(application,"service")
    service.set(ATTR("name"),HOST_PACKAGE+".EmbeddedServerService")
    service.set(ATTR("process"),":bfserver")
    service.set(ATTR("exported"),"false")
    # Move ONLY MAIN/LAUNCHER to a native-ready gate; leave the original
    # Activity, theme, resources, deep links and all gameplay code unchanged.
    candidates=[]
    for node in application:
        if node.tag not in ("activity","activity-alias"): continue
        for intent in list(node.findall("intent-filter")):
            actions={a.get(ATTR("name")) for a in intent.findall("action")}
            categories={a.get(ATTR("name")) for a in intent.findall("category")}
            if "android.intent.action.MAIN" in actions and \
                    "android.intent.category.LAUNCHER" in categories:
                candidates.append((node,intent))
    if len(candidates)!=1:
        raise RuntimeError("Expected exactly one original launcher, found "+str(len(candidates)))
    original,old_filter=candidates[0]
    name=original.get(ATTR("name"))
    if not name: raise RuntimeError("Original launcher has no component name")
    if name.startswith("."): name=package+name
    elif "." not in name: name=package+"."+name
    original.remove(old_filter)
    gateway=ET.SubElement(application,"activity")
    gateway.set(ATTR("name"),HOST_PACKAGE+".OfflineLaunchActivity")
    gateway.set(ATTR("exported"),"true")
    gateway.set(ATTR("screenOrientation"),"portrait")
    meta=ET.SubElement(gateway,"meta-data")
    meta.set(ATTR("name"),"bf_offline.original_activity")
    meta.set(ATTR("value"),name)
    launch_filter=ET.SubElement(gateway,"intent-filter")
    action=ET.SubElement(launch_filter,"action")
    action.set(ATTR("name"),"android.intent.action.MAIN")
    category=ET.SubElement(launch_filter,"category")
    category.set(ATTR("name"),"android.intent.category.LAUNCHER")
    doc.write(manifest,encoding="utf-8",xml_declaration=True)
    return package

def validate_android_shared_library(path: Path) -> None:
    # Reject Linux x86_64 builds or arbitrary binaries before APK signing.
    with path.open("rb") as native:
        header = native.read(64)
    if len(header) < 64 or header[:4] != b"\x7fELF":
        raise RuntimeError("Native server is not an ELF shared library")
    if header[4] != 2 or header[5] != 1:
        raise RuntimeError("Native server must be little-endian ELF64")
    kind, machine = struct.unpack_from("<HH", header, 16)
    if kind != 3 or machine != 183:
        raise RuntimeError("Native server is not an Android ARM64 shared object")

def validate_patched(path):
    if not zipfile.is_zipfile(path): raise RuntimeError("Patched client is not an APK")
    with zipfile.ZipFile(path) as z:
        name="lib/arm64-v8a/libgame.so"
        if name not in z.namelist(): raise RuntimeError("Original arm64 libgame.so absent")
        with z.open(name) as fp:
            blob=fp.read()
        if b"127.0.0.1:9960" not in blob:
            raise RuntimeError("Client not patched for localhost:9960; use upstream patch_apk.py first")
        if b"api-sl.bfww.gumi.sg\x00" in blob:
            print("Note: original hostname bytes still present elsewhere; review patch before real use.")
    print("Patched native client contains localhost:9960")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--patched-apk",type=Path,required=True)
    parser.add_argument("--host-aar",type=Path,required=True)
    parser.add_argument("--native-lib",type=Path,required=True)
    parser.add_argument("--payload",type=Path,required=True)
    parser.add_argument("--keystore",type=Path,required=True)
    parser.add_argument("--key-alias",required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--android-jar",type=Path,required=True)
    parser.add_argument("--apktool",default="apktool")
    parser.add_argument("--d8",default="d8")
    parser.add_argument("--zipalign",default="zipalign")
    parser.add_argument("--apksigner",default="apksigner")
    args=parser.parse_args()
    for path in (args.patched_apk,args.host_aar,args.native_lib,args.payload/"manifest.tsv",
                 args.keystore,args.android_jar):
        if not path.exists():
            parser.error(f"Missing build input: {path}")
    if not os.environ.get("BF_OFFLINE_KS_PASS"):
        parser.error("Set BF_OFFLINE_KS_PASS environment variable; never put secrets in CLI or Git")
    if not str(args.output.resolve()).startswith(str(Path.cwd().resolve())):
        print("Note: writing outside current working directory")
    validate_android_shared_library(args.native_lib)
    validate_patched(args.patched_apk)
    with tempfile.TemporaryDirectory(prefix="bf-apk-") as temporary:
        temp=Path(temporary)
        decoded=temp/"decoded"
        run(args.apktool,"d","--no-src","--force",args.patched_apk,"-o",decoded)
        pkg=add_manifest_hooks(decoded/"AndroidManifest.xml")
        print("Original package:",pkg)
        unsigned=temp/"apktool-unsigned.apk"
        run(args.apktool,"b",decoded,"-o",unsigned)
        with zipfile.ZipFile(args.host_aar) as aar:
            if "classes.jar" not in aar.namelist():
                raise RuntimeError("Host AAR contains no Java classes")
            jar=temp/"bridge.jar"
            jar.write_bytes(aar.read("classes.jar"))
        dexdir=temp/"host-dex"
        dexdir.mkdir()
        run(args.d8,"--min-api","24","--lib",args.android_jar,
            "--output",dexdir,jar)
        dexfiles=sorted(dexdir.glob("classes*.dex"))
        if not dexfiles:
            raise RuntimeError("Android D8 did not produce the service classes.dex")
        for sub in ("system","archive","mst","game_content"):
            if not (args.payload/sub).is_dir():
                raise RuntimeError("Required game payload missing: "+sub)
        packaged=temp/"packaged.apk"
        shutil.copy2(unsigned,packaged)
        with zipfile.ZipFile(packaged,"a",allowZip64=True) as archive:
            dexnames=archive.namelist()
            indices=[int(m.group(1) or 1) for name in dexnames
                     if (m:=re.fullmatch(r"classes(\d*)\.dex",name))]
            nextdex=max(indices,default=0)+1
            for dex in dexfiles:
                name="classes"+str(nextdex)+".dex"
                archive.write(dex,name,compress_type=zipfile.ZIP_DEFLATED)
                nextdex+=1
            archive.write(args.native_lib,
                          "lib/arm64-v8a/libbf_offline_server.so",
                          compress_type=zipfile.ZIP_DEFLATED)
            for file in sorted(args.payload.rglob("*")):
                if not file.is_file(): continue
                relative=file.relative_to(args.payload).as_posix()
                if ".." in Path(relative).parts:
                    raise RuntimeError("Unsafe payload entry: "+relative)
                archive.write(file,"assets/bf-offline/"+relative,
                              compress_type=zipfile.ZIP_DEFLATED)
        aligned=temp/"aligned.apk"
        run(args.zipalign,"-f","4",packaged,aligned)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        run(args.apksigner,"sign","--ks",args.keystore,
            "--ks-key-alias",args.key_alias,
            "--ks-pass","env:BF_OFFLINE_KS_PASS",
            "--out",args.output,aligned)
        run(args.apksigner,"verify","--verbose",args.output)
    print("Experimental same-package APK constructed:",args.output)
    print("IMPORTANT: success here does NOT mean the upstream C++ server boots or the game runs.")
    print("First install may spend a long time extracting bundled assets.")

if __name__=="__main__":
    try: main()
    except (RuntimeError,subprocess.CalledProcessError,zipfile.BadZipFile) as e:
        sys.exit("Single-APK integration not complete: "+str(e))
