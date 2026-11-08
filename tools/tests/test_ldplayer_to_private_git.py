"""No Android device or proprietary game content is required for these tests."""
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from ldplayer_to_private_git import safe_resource, prepare, publish

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

    def test_never_push_to_public_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=SimpleNamespace(source=Path(tmp),repo="Domenklay/BraveFrontier_Offline",
                                 workspace=Path(tmp)/"repo",push=True)
            with self.assertRaisesRegex(RuntimeError,"PUBLIC"):
                publish(args)

if __name__=="__main__":
    unittest.main()
