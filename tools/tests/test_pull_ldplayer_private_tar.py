"""Tests for binary LDPlayer tar extraction; no emulator or private data needed."""
import io
from pathlib import Path
from types import SimpleNamespace
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pull_ldplayer_private_tar import root_available, stream_to_disk, pull_archive

class LDPlayerTarTests(unittest.TestCase):
    def test_root_positive_and_negative(self):
        cmd = SimpleNamespace(returncode=0,
                              stdout="uid=0(root) gid=0(root) context=u:r:su:s0")
        with patch("pull_ldplayer_private_tar.adb_run", return_value=cmd):
            self.assertTrue(root_available(["adb","-s","emulator-5554"]))
        cmd.stdout = "uid=2000(shell)"
        with patch("pull_ldplayer_private_tar.adb_run", return_value=cmd):
            self.assertFalse(root_available(["adb"]))

    def test_binary_pipe_preserves_bytes(self):
        raw=io.BytesIO()
        with tarfile.open(fileobj=raw,mode="w") as archive:
            payload=b"\x00\xff\x80brave-frontier\x00\xfe"
            item=tarfile.TarInfo("./game/hero.bin")
            item.size=len(payload)
            archive.addfile(item, io.BytesIO(payload))
        original=raw.getvalue()
        process=SimpleNamespace(stdout=io.BytesIO(original),kill=lambda:None)
        with tempfile.TemporaryDirectory() as td:
            part=Path(td)/"backup.tar.part"
            written,timeout=stream_to_disk(process,part,idle_seconds=15)
            self.assertEqual(written,len(original))
            self.assertFalse(timeout)
            self.assertEqual(part.read_bytes(),original)

    def test_private_export_never_calls_adb_pull(self):
        raw=io.BytesIO()
        with tarfile.open(fileobj=raw,mode="w") as archive:
            payload=b"image"
            item=tarfile.TarInfo("./hero.dat")
            item.size=len(payload)
            archive.addfile(item, io.BytesIO(payload))
        data=raw.getvalue()
        calls=[]
        class FakeProc:
            def __init__(self,cmd,**kwargs):
                calls.append(cmd)
                self.stdout=io.BytesIO(data)
            def wait(self,timeout=None):return 0
            def kill(self):pass
        def fake_adb_run(adb,tail):
            if tail[0] == "shell" and tail[1].startswith("su -c 'du "):
                return SimpleNamespace(returncode=0,stdout="1  /data/data/sg.gumi.bravefrontier/files")
            return SimpleNamespace(returncode=0,stdout="")
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"archive.tar"
            with patch("pull_ldplayer_private_tar.root_available",return_value=True), \
                 patch("pull_ldplayer_private_tar.adb_run",side_effect=fake_adb_run), \
                 patch("pull_ldplayer_private_tar.subprocess.Popen",side_effect=FakeProc):
                pull_archive(["adb","-s","emulator-5554"],out,idle_seconds=15)
            self.assertEqual(out.read_bytes(),data)
            self.assertFalse((Path(td)/"archive.tar.part").exists())
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][-2],"exec-out")
        self.assertIn("tar -C /data/data/sg.gumi.bravefrontier/files -cf - .",calls[0][-1])

if __name__ == "__main__":
    unittest.main()
