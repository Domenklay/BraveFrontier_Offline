"""Tests for staged Android TAR and adb pull verification; no emulator required."""
import hashlib
import io
from pathlib import Path
from types import SimpleNamespace
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pull_ldplayer_staged_tar import check_tar_structure, pull_and_verify, check_root, STAGED

def make_valid_tar(path):
    with tarfile.open(path, mode="w") as archive:
        for name, data in (
            ("./sprites/001.webp", b"RIFF"+b"\0"*120+b"WEBP"),
            ("./sprites/002.webp", b"\xff\xd8\xff"+b"image"),
            ("./game/data/003.bin", b"\0" * (11 * 1024 * 1024)),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))

class StagedTarTests(unittest.TestCase):
    def test_valid_archive_structure(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"valid.tar"
            make_valid_tar(path)
            count, files, size = check_tar_structure(path)
            self.assertEqual(count, 3)
            self.assertEqual(files, 3)
            self.assertEqual(size, path.stat().st_size)

    def test_early_eof_with_lots_of_extra_bytes_is_not_complete(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"broken.tar"
            make_valid_tar(path)
            with path.open("ab") as out:
                out.write(b"\0" * 81920)
            with self.assertRaisesRegex(RuntimeError, "Invalid TAR ending"):
                check_tar_structure(path)

    def test_single_file_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/"one.tar"
            with tarfile.open(path,"w") as archive:
                info=tarfile.TarInfo("one.txt")
                data=b"one"
                info.size=len(data)
                archive.addfile(info,io.BytesIO(data))
            with self.assertRaisesRegex(RuntimeError, "only exposes"):
                check_tar_structure(path)

    def test_root_uid(self):
        with patch("pull_ldplayer_staged_tar.subprocess.run",
                   return_value=SimpleNamespace(returncode=0,stdout="uid=0(root) gid=0(root)")):
            self.assertTrue(check_root(["adb"]))
        with patch("pull_ldplayer_staged_tar.subprocess.run",
                   return_value=SimpleNamespace(returncode=0,stdout="uid=2000(shell)")):
            self.assertFalse(check_root(["adb"]))

    def test_verified_adb_pull_moves_part_to_tar(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            sample=root/"sample.tar"
            make_valid_tar(sample)
            data=sample.read_bytes()
            dest=root/"backed-up.tar"
            def fake_run(command,**kwargs):
                self.assertIn("pull", command)
                part=Path(command[-1])
                self.assertEqual(part.suffix,".part")
                part.write_bytes(data)
                return SimpleNamespace(returncode=0)
            with patch("pull_ldplayer_staged_tar.device_exists",return_value=True), \
                 patch("pull_ldplayer_staged_tar.device_size",return_value=len(data)), \
                 patch("pull_ldplayer_staged_tar.sha256_device",
                       return_value=hashlib.sha256(data).hexdigest()), \
                 patch("pull_ldplayer_staged_tar.subprocess.run",
                       side_effect=fake_run) as sender:
                pull_and_verify(["adb"],dest)
            self.assertTrue(sender.called)
            self.assertEqual(dest.read_bytes(),data)
            self.assertFalse((root/"backed-up.tar.part").exists())

if __name__ == "__main__":
    unittest.main()
