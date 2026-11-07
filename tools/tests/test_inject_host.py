import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from sys import path

ROOT=Path(__file__).resolve().parents[2]
path.insert(0,str(ROOT/"tools"))
from inject_host import add_manifest_hooks, ANDROID, ATTR

class ManifestInjectionTests(unittest.TestCase):
    def test_keeps_original_activity_and_adds_local_server(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"AndroidManifest.xml"
            file.write_text("""<?xml version="1.0"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
 package="sg.gumi.bravefrontier">
 <application android:label="Brave Frontier">
  <activity android:name="sg.gumi.bravefrontier.AppActivity"/>
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
            self.assertEqual(root.find("uses-permission").get(ATTR("name")),
                             "android.permission.INTERNET")

if __name__=="__main__":
    unittest.main()
