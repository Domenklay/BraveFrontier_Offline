import hashlib
import tempfile
import unittest
from pathlib import Path
from sys import path, argv

ROOT=Path(__file__).resolve().parents[2]
path.insert(0,str(ROOT/"tools"))
import stage_payload

class StagingTests(unittest.TestCase):
    def test_real_upstream_layout_without_proprietary_content(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            upstream=root/"upstream"
            deploy=upstream/"server"/"server"/"deploy"
            (deploy/"system").mkdir(parents=True)
            (deploy/"config.json").write_text(
                '{"listeners":[{"address": "127.0.0.1", "port": 9960}], '
                '"notice_url": "http://ios21900.bfww.gumi.sg/pages/versioninfo"}')
            (deploy/"system"/"flags.json").write_text("{}")
            archive=upstream/"data"/"archive"
            archive.mkdir(parents=True)
            (archive/"mission.json").write_text("[]")
            mst=root/"decoded"
            mst.mkdir()
            (mst/"unit_mst.json").write_text("[]")
            cache=upstream/"server"/"server"/"gimuserver"/"drogon"/"ServerCache.cpp"
            cache.parent.mkdir(parents=True,exist_ok=True)
            names=["unit_mst.json"]+[f"test_{i}_mst.json" for i in range(80)]
            cache.write_text("\n".join('forge::LoadMst<Table>(mstRoot, "'+n+'")' for n in names))
            for n in names:
                (mst/n).write_text("[]")
            content=root/"downloads"
            (content/"content").mkdir(parents=True)
            (content/"mst").mkdir()
            (content/"content"/"test.png").write_bytes(b"pixel bytes")
            (content/"mst"/"test.dat").write_bytes(b"table bytes")
            output=root/"out"
            old_up,old_argv=stage_payload.UP,argv[:]
            try:
                stage_payload.UP=upstream
                argv[:]=["stage_payload.py","--content-root",str(content),
                         "--decoded-mst",str(mst),"--out",str(output)]
                stage_payload.main()
            finally:
                stage_payload.UP=old_up
                argv[:]=old_argv
            self.assertTrue((output/"config.json").exists())
            self.assertIn("127.0.0.1:9960/pages/versioninfo",
                          (output/"config.json").read_text())
            self.assertTrue((output/"game_content"/"content"/"test.png").exists())
            lines=(output/"manifest.tsv").read_text().splitlines()
            self.assertTrue(any("game_content/content/test.png" in x for x in lines))
            for line in lines:
                digest,size,relative=line.split("\t",2)
                actual=output/relative
                self.assertEqual(int(size),actual.stat().st_size)
                self.assertEqual(digest,hashlib.sha256(actual.read_bytes()).hexdigest())

if __name__=="__main__":
    unittest.main()
