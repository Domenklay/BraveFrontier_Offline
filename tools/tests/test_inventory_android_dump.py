import tempfile
import unittest
from pathlib import Path
from sys import path as search_path

search_path.insert(0,str(Path(__file__).resolve().parents[1]))
from inventory_android_dump import detect, scan

class AndroidDumpInventoryTests(unittest.TestCase):
    def test_magic_formats(self):
        self.assertEqual(detect(b"\x89PNG\r\n\x1a\n","image.dat"),"png")
        self.assertEqual(detect(b"UnityFS\x00","bundle.bin"),"unityfs")
        self.assertEqual(detect(b"\x28\xb5\x2f\xfd","data"),"zstd")
        self.assertEqual(detect(b"not json","unit_mst.json"),"binary")

    def test_privacy_and_master_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"files").mkdir()
            (root/"files"/"image.dat").write_bytes(b"\x89PNG\r\n\x1a\n"+b"\0"*64)
            (root/"files"/"unit_mst.json").write_text('{"rows":[]}',encoding="utf-8")
            (root/"files"/"session_token.dat").write_text("sensitive")
            (root/"files"/"save.db").write_bytes(b"SQLite format 3\0"+b"\0"*64)
            (root/"shared_prefs").mkdir()
            (root/"shared_prefs"/"user.bin").write_text("private")
            report=scan([root],["unit_mst.json","area_mst.json"])
            self.assertEqual(report["scanned_files"],2)
            self.assertEqual(report["excluded_files"],3)
            self.assertEqual(report["formats"]["png"]["files"],1)
            self.assertEqual(report["mst_found_decoded"],["unit_mst.json"])
            self.assertEqual(report["mst_missing_decoded"],["area_mst.json"])
            self.assertFalse(any("session" in row["path"] for row in report["files"]))
