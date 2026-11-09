"""Tests for offline BF asset family statistics, using synthetic fake assets."""
import io
from pathlib import Path
import struct
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from profile_bf_asset_families import scan, classify_png, csv_type

PNG=b"\x89PNG\r\n\x1a\n"+struct.pack(">I",13)+b"IHDR"+struct.pack(">II",256,256)+b"\x08\x06\x00\x00\x00"

class BFAssetFamilyTests(unittest.TestCase):
    def test_magic(self):
        self.assertEqual(classify_png(PNG),"PNG valid header")
        self.assertEqual(classify_png(b"123"+PNG),"PNG embedded header")
        self.assertEqual(classify_png(b"\0\0\0\0AAAA"),"zero-prefixed PNG-named data")
        self.assertEqual(classify_png(b"\x1f\x8bZ"),"gzip data with PNG extension")
        self.assertEqual(csv_type(b"1,2,3\n4,5,6\n"),"mostly ASCII, comma delimited")
    def test_unit_bundle_and_sam_pairing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"faketar.tar"
            files={
                "unit_anime_10011.png":PNG,
                "unit_cgg_10011.csv":b"0,0\n",
                "unit_idle_cgs_10011.csv":b"0,0\n",
                "unit_atk_cgs_10011.csv":b"1,1\n",
                "unit_move_cgs_10011.csv":b"2,2\n",
                "unit_anime_10012.png":b"\0\0\0\0obfuscated",
                "unit_idle_cgs_10012.csv":b"0,0\n",
                "10011BattleEffectFire.sam":b"sam data",
                "10011BattleEffectFire_512x512.png":PNG,
                "unit_ills_anime_10011.png":PNG,
                "unit_mst.csv":b"hero,id\n",
                "Ver1084_2r9cNSdt_1.dat":b"encrypted MST data",
                "misc_obfuscated.png":b"QRP0unknown data",
                "content/shared_prefs/session.txt":b"secret private",
            }
            with tarfile.open(p, "w") as tar:
                for name,raw in files.items():
                    item=tarfile.TarInfo(name)
                    item.size=len(raw)
                    tar.addfile(item,io.BytesIO(raw))
            result=scan(p,{"unit_mst.csv"})
            self.assertEqual(result["unit_ids_with_all_five_standard_parts"],1)
            self.assertEqual(result["unit_ids_with_sheet_and_idle_frame_table"],1)
            self.assertEqual(result["unit_ids_seen_in_any_standard_part"],2)
            self.assertEqual(result["sam_stems_with_dimension_suffixed_png"],1)
            self.assertEqual(result["possible_mst_csv_by_name"],1)
            self.assertEqual(result["versioned_encrypted_mst_like_dat_names"],1)
            self.assertTrue(any(x["hex"] == "51525030" and x["count"] == 1
                                for x in result["unknown_png_top_four_byte_prefixes"]))
            self.assertEqual(result["skipped_sensitive_or_unsafe_names"],1)
            self.assertEqual(result["png_header_breakdown"]["PNG valid header"],3)
            self.assertEqual(result["png_header_breakdown"]["zero-prefixed PNG-named data"],1)

if __name__=="__main__":
    unittest.main()
