"""Local sample exporter tests; synthetic PNG/CSV data only, no game content."""
import io
import json
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from extract_bf_animation_sample import extract_sample, index_units, pick_units

PNG=(b"\x89PNG\r\n\x1a\n"+struct.pack(">I",13)+b"IHDR"+
     struct.pack(">II",512,512)+b"\x08\x06\x00\x00\x00"+b"\0"*7)

def add(archive,name,data):
    item=tarfile.TarInfo(name)
    item.size=len(data)
    archive.addfile(item,io.BytesIO(data))

def fill_unit(archive,uid,image=PNG,include_move=True):
    add(archive,f"unit_anime_{uid}.png",image)
    for typ in ("cgg","idle","atk","move"):
        if typ=="move" and not include_move:
            continue
        name=(f"unit_cgg_{uid}.csv" if typ=="cgg" else f"unit_{typ}_cgs_{uid}.csv")
        add(archive,name,b"0,0,1\n")

class AnimationSampleTests(unittest.TestCase):
    def test_selects_complete_readable_and_skips_private_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"assets.tar"
            dest=Path(tmp)/"sample"
            with tarfile.open(source,"w") as archive:
                fill_unit(archive,"10011")
                fill_unit(archive,"10012",image=b"\x12"*40)
                fill_unit(archive,"10013",include_move=False)
                add(archive,"shared_prefs/account.csv",b"secret")
                add(archive,"../../../exfiltrate/file.txt",b"do-not-extract")
            manifests,skipped=extract_sample(source,dest,5,set())
            self.assertEqual([x["unit_id"] for x in manifests],["10011"])
            self.assertEqual(manifests[0]["sprite_size"],{"width":512,"height":512})
            self.assertEqual(skipped["non_standard_png"],1)
            self.assertEqual(skipped["incomplete"],1)
            self.assertEqual(len(list((dest/"Units"/"10011").iterdir())),5)
            self.assertEqual((dest/"list.txt").read_text(), "10011\n")
            self.assertFalse((Path(tmp)/"exfiltrate").exists())
            self.assertFalse((dest/"shared_prefs").exists())
            self.assertEqual(json.loads((dest/"manifest.json").read_text())["unit_count"],1)
            with self.assertRaisesRegex(RuntimeError,"already exists"):
                extract_sample(source,dest,5,set())

    def test_rejects_oversized_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError,"1..50"):
                extract_sample(Path(tmp)/"archive.tar",Path(tmp)/"dest",51,set())

    def test_requested_specific_unit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/"assets.tar"
            with tarfile.open(source,"w") as archive:
                fill_unit(archive,"10011")
                fill_unit(archive,"10014")
            units,_=extract_sample(source,Path(tmp)/"only-14",3,{"10014"})
            self.assertEqual([x["unit_id"] for x in units],["10014"])

if __name__=="__main__":
    unittest.main()
