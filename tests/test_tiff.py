"""Tests for TIFF export: pixels must match the instrument's exports."""

import struct
import unittest

from tests import SAMPLES, TIFFS, has_sample_files
from clxparser import load
from clxparser.tiff import encode_tiff, image_to_tiff


def tiff_strip_bytes(tif: bytes, byte_count: int) -> bytes:
    """Extract the pixel strip of an instrument-exported TIFF (starts at 24)."""
    return tif[24 : 24 + byte_count]


@unittest.skipUnless(has_sample_files(), "instrument sample files not present")
class TestTiffExport(unittest.TestCase):
    def test_pixels_match_official_exports(self):
        for key in ("samp1", "samp2"):
            clx = load(SAMPLES[key])
            for i, img in enumerate(clx.images):
                official = TIFFS[(key, i)].read_bytes()
                mine = image_to_tiff(img)
                self.assertEqual(
                    mine[8 : 8 + img.byte_count],
                    tiff_strip_bytes(official, img.byte_count),
                    msg=f"{key} image {i} pixels differ from instrument export",
                )

    def test_standard_single_strip_layout(self):
        clx = load(SAMPLES["samp2"])
        img = clx.images[0]
        data = image_to_tiff(img)
        # 8-byte header + one strip + 13-tag IFD + two rationals
        self.assertEqual(len(data), 8 + img.byte_count + 2 + 13 * 12 + 4 + 16)
        self.assertTrue(data.startswith(b"II*\x00"))
        ifd_offset = struct.unpack_from("<I", data, 4)[0]
        self.assertEqual(ifd_offset, 8 + img.byte_count)
        self.assertEqual(struct.unpack_from("<H", data, ifd_offset)[0], 13)


class TestTiffWriter(unittest.TestCase):
    def test_pixel_size_mismatch_raises(self):
        with self.assertRaises(ValueError):
            encode_tiff(10, 10, 16, b"\x00" * 100)  # needs 200 bytes

    def test_bad_bits_raises(self):
        with self.assertRaises(ValueError):
            encode_tiff(10, 10, 7, b"\x00" * 100)

    def test_roundtrip_structure(self):
        data = encode_tiff(4, 3, 16, b"\x01\x02" * 12)
        self.assertTrue(data.startswith(b"II*\x00"))
        self.assertEqual(len(data), 8 + 24 + 162 + 16)
        # strip data at offset 8 is untouched
        self.assertEqual(data[8:32], b"\x01\x02" * 12)


if __name__ == "__main__":
    unittest.main()
