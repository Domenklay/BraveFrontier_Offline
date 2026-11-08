"""No Android device or proprietary game content is required for these tests."""
import tempfile
import io
import tarfile
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
import unittest
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ldplayer_to_private_git import safe_resource, prepare, publish, private_root_mode, stream_private_tar

class LDPlayerToPrivateGitTest(unittest.TestCase):
    def test_resource_filter_keeps_real_event_token_mst(self):
        self.assertTrue(safe_resource(Path("external_files/files/content/unit/12345.png")))
        self.assertTrue(safe_resource(Path("private_files/files/mst/event_token_mst.json")))
        self.assertFalse(safe_resource(Path("external_files/files/shared_prefs/user.bin")))
        self.assertFalse(safe_resource(Path("external_files/files/auth_token.bin")))
        self.assertFalse(safe_resource(Path("private_files/files/accounts.sqlite")))
        self.assertFalse(safe_resource(Path("private_files/files/user_config.json")))
        self.assertFalse(safe_resource(Path("../../.ssh/id_rsa")))

    def test_prepare_dry_run_then_copy_safe_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            raw=root/"raw"
            (raw/"external_files"/"files"/"content").mkdir(parents=True)
            folder=raw/"external_files"/"files"/"content"
            (folder/"hero01.webp").write_bytes(b"RIFFfakeWEBP")
            (folder/"session-token.bin").write_bytes(b"secret")
            (folder/"event_token_mst.json").write_text("[]",encoding="utf-8")
            reviewed=root/"reviewed"
            args=SimpleNamespace(source=raw,output=reviewed,confirm_review=False)
            prepare(args)
            self.assertFalse(reviewed.exists())
            args.confirm_review=True
            prepare(args)
            self.assertTrue((reviewed/"external_files"/"files"/"content"/"hero01.webp").exists())
            self.assertTrue((reviewed/"external_files"/"files"/"content"/"event_token_mst.json").exists())
            self.assertFalse((reviewed/"external_files"/"files"/"content"/"session-token.bin").exists())

    def test_su_fallback_when_adbd_is_not_root(self):
        def fake_run(cmd, **kwargs):
            output = "2000\\n" if "su" not in cmd else "0\\n"
            return SimpleNamespace(returncode=0, stdout=output)
        with patch("ldplayer_to_private_git.run", side_effect=fake_run):
            self.assertEqual(private_root_mode(["adb", "-s", "emulator-5554"]), "su")

    def test_safe_stream_extracts_files_but_not_symlinks(self):
        contents = io.BytesIO()
        with tarfile.open(fileobj=contents, mode="w") as tar:
            payload = b"textures"
            record = tarfile.TarInfo("./sprites/unit01.webp")
            record.size = len(payload)
            tar.addfile(record, io.BytesIO(payload))
            symlink = tarfile.TarInfo("./sprites/unsafe-link")
            symlink.type = tarfile.SYMTYPE
            symlink.linkname = "../../outside"
            tar.addfile(symlink)
        contents.seek(0)
        proc = SimpleNamespace(stdout=contents, stderr=io.BytesIO(),
                               wait=lambda: 0, kill=lambda: None)
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ldplayer_to_private_git.subprocess.Popen", return_value=proc):
                count = stream_private_tar(["adb"], "/data/data/sg.gumi.bravefrontier/files",
                                           Path(tmp))
            self.assertEqual(count, 1)
            self.assertEqual((Path(tmp)/"sprites"/"unit01.webp").read_bytes(), b"textures")
            self.assertFalse((Path(tmp)/"sprites"/"unsafe-link").exists())

    def test_never_push_to_public_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(source=Path(tmp),repo="Domenklay/BraveFrontier_Offline",
                                 workspace=Path(tmp)/"repo",push=True)
            with self.assertRaisesRegex(RuntimeError,"PUBLIC"):
                publish(args)

if __name__=="__main__":
    unittest.main()
