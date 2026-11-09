"""Tests for offline Brave Frontier asset metadata classification without user data."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze_ldplayer_assets_tar import scan, magic_format, safe_label

class AnalyzerTests(unittest.TestCase):
    def test_magic_and_folder_privacy(self):
        self.assertEqual(magic_format(b"\x89PNG\r\n\x1a\nfoo"),"PNG")
        self.assertEqual(magic_format(b"RIFF\x00\x00\x00\x00WEBPxxxx"),"WEBP")
        self.assertEqual(safe_label("units"),"units")
        self.assertEqual(safe_label("alice-1234"),"[other]")

    def test_tar_aggregation_no_raw_private_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"source.tar"
            content={
                "content/unit/001.png":b"\x89PNG\r\n\x1a\n"+b"\x00"*32,
                "content/mst/area_mst.json":b'{"areas":[]}',
                "content/unit/002.blob":b"mystery",
                "userpersonal123/private/userdata.bin":b"\x00"*20,
                "shared_prefs/oauth_session.json":b"{SECRET}",
                "content/music/loop.ogg":b"OggS\x00\x00",
            }
            with tarfile.open(p,"w") as archive:
                for name, data in content.items():
                    info=tarfile.TarInfo(name)
                    info.size=len(data)
                    archive.addfile(info,io.BytesIO(data))
            report=scan(p,{"area_mst.json","unit_mst.json"})
            self.assertEqual(report["regular_files"],6)
            self.assertEqual(report["excluded_sensitive_name_files"],1)
            self.assertEqual(report["mst_name_matches"],1)
            self.assertEqual(report["mst_json_like_matches"],1)
            self.assertEqual(report["mst_missing_name_matches"],1)
            formats={x["label"]:x["files"] for x in report["top_signatures"]}
            self.assertEqual(formats["PNG"],1)
            self.assertEqual(formats["OGG"],1)
            serialized=json.dumps(report)
            self.assertNotIn("userdata",serialized)
            self.assertNotIn("oauth_session",serialized)
            self.assertNotIn("userpersonal123",serialized)

if __name__=="__main__":
    unittest.main()
