import tempfile
import unittest
import xml.etree.ElementTree as ET
import struct
from pathlib import Path
from sys import path

ROOT=Path(__file__).resolve().parents[2]
path.insert(0,str(ROOT/"tools"))
from inject_host import add_manifest_hooks, validate_android_shared_library, ANDROID, ATTR

class ManifestInjectionTests(unittest.TestCase):
    def test_keeps_original_activity_and_adds_local_server(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"AndroidManifest.xml"
            file.write_text("""<?xml version="1.0"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
 package="sg.gumi.bravefrontier">
 <application android:label="Brave Frontier">
  <activity android:name="sg.gumi.bravefrontier.AppActivity">
    <intent-filter>
     <action android:name="android.intent.action.MAIN"/>
     <category android:name="android.intent.category.LAUNCHER"/>
    </intent-filter>
  </activity>
 </application>
</manifest>""",encoding="utf-8")
            self.assertEqual(add_manifest_hooks(file),"sg.gumi.bravefrontier")
            root=ET.parse(file).getroot()
            app=root.find("application")
            self.assertEqual(app.find("activity").get(ATTR("name")),
                             "sg.gumi.bravefrontier.AppActivity")
            self.assertEqual(app.find("provider").get(ATTR("name")),
                             "com.domenklay.bfoffline.OfflineBootstrapProvider")
            self.assertEqual(app.find("service").get(ATTR("process")),":bfserver")
            self.assertEqual(app.find("service").get(ATTR("exported")),"false")
            self.assertEqual(app.find("provider").get(ATTR("exported")),"false")
            self.assertEqual(app.get(ATTR("usesCleartextTraffic")),"true")
            permissions={n.get(ATTR("name")) for n in root.findall("uses-permission")}
            self.assertIn("android.permission.INTERNET",permissions)
            self.assertIn("android.permission.FOREGROUND_SERVICE",permissions)
            self.assertEqual(root.find("uses-sdk").get(ATTR("minSdkVersion")),"24")
            self.assertIsNone(app.find("activity").find("intent-filter"))
            bridge=app.findall("activity")[-1]
            self.assertEqual(bridge.get(ATTR("name")),
                             "com.domenklay.bfoffline.OfflineLaunchActivity")
            self.assertEqual(bridge.find("meta-data").get(ATTR("value")),
                             "sg.gumi.bravefrontier.AppActivity")
            self.assertIsNotNone(bridge.find("intent-filter"))

class NativeLibraryValidationTests(unittest.TestCase):
    def test_rejects_non_elf_and_wrong_cpu(self):
        with tempfile.TemporaryDirectory() as folder:
            candidate=Path(folder)/"server.so"
            candidate.write_bytes(b"not a native library")
            with self.assertRaisesRegex(RuntimeError, "ELF"):
                validate_android_shared_library(candidate)
            header=bytearray(64)
            header[:4]=b"\x7fELF"
            header[4]=2
            header[5]=1
            struct.pack_into("<HH",header,16,3,62) # x86_64
            candidate.write_bytes(header)
            with self.assertRaisesRegex(RuntimeError, "ARM64"):
                validate_android_shared_library(candidate)
            struct.pack_into("<HH",header,16,3,183) # AArch64
            candidate.write_bytes(header)
            validate_android_shared_library(candidate)

if __name__=="__main__":
    unittest.main()
