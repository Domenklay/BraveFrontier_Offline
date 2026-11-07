"""No proprietary game data is committed. Unit tests verify patch specification safety."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import patch_bfrevive_v20 as patch

class BFRevivePatchSpecTest(unittest.TestCase):
    def test_nine_nonoverlapping_fixed_length_guarded_patches(self):
        self.assertEqual(len(patch.PATCHES), 9)
        ranges = []
        for offset, before, after, purpose in patch.PATCHES:
            self.assertEqual(len(before), len(after), purpose)
            self.assertGreater(len(before), 0)
            self.assertNotEqual(before, after, purpose)
            new_range = range(offset, offset + len(before))
            self.assertFalse(any(
                new_range.start < stop and start < new_range.stop
                for start, stop in ranges
            ), f"Overlapping patch at {offset:#x}")
            ranges.append((new_range.start, new_range.stop))
        self.assertEqual(len({x[3] for x in patch.PATCHES}), 9)

    def test_rejects_other_libgame_versions(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            patch.patch_library(b"this is not the V20 native library")

    def test_localhost_hosts(self):
        for i in range(2):
            offset, before, after, purpose = patch.PATCHES[i]
            self.assertTrue(after.startswith(b"127.0.0.1:9960"))
            self.assertTrue(before.endswith(b"\0"))
            self.assertTrue(after.endswith(b"\0"))

if __name__ == "__main__":
    unittest.main()
