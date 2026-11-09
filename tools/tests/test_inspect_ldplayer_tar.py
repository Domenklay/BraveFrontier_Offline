"""Unit tests for read-only LDPlayer TAR inspection."""
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from inspect_ldplayer_tar import inspect

class InspectLDPlayerTarTests(unittest.TestCase):
    def test_valid_archive(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"valid.tar"
            with tarfile.open(path, "w") as archive:
                payload = b"unit art"*300
                item = tarfile.TarInfo("./content/hero.dat")
                item.size = len(payload)
                archive.addfile(item, io.BytesIO(payload))
            info = inspect(path)
            self.assertEqual(info["regular_files"], 1)
            self.assertEqual(info["payload_bytes_verified"], len(payload))
            self.assertIsNone(info["parsing_error"])
            self.assertTrue(info["trailer_looks_complete"])

    def test_trailing_junk_rejected_without_modifying_archive(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"partial.tar.part"
            with tarfile.open(path, "w") as archive:
                payload = b"\0\255"*256
                item = tarfile.TarInfo("units/001.bin")
                item.size=len(payload)
                archive.addfile(item, io.BytesIO(payload))
            with path.open("ab") as stream:
                stream.write(b"extra output or truncation marker")
            original = path.read_bytes()
            info=inspect(path)
            self.assertEqual(info["regular_files"], 1)
            self.assertNotEqual(info["remainder_mod_512"], 0)
            self.assertFalse(info["trailer_looks_complete"])
            self.assertEqual(path.read_bytes(), original)

if __name__ == "__main__":
    unittest.main()
