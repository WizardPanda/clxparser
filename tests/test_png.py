"""Tests for the stdlib PNG encoder (16-bit lossless + 8-bit preview).

Includes a small self-contained PNG decoder so the round-trip test does not
depend on Pillow.
"""

import array
import struct
import unittest
import zlib

from tests import SAMPLES, has_sample_files
from clxparser import load
from clxparser.png import encode_png, image_to_png, preview_to_png

_SIG = b"\x89PNG\r\n\x1a\n"


def decode_png(data: bytes):
    """Decode a grayscale PNG; returns (width, height, bits, pixels_le)."""
    assert data.startswith(_SIG)
    pos = 8
    idat = b""
    width = height = bits = None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        pos += 4
        tag = data[pos : pos + 4]
        pos += 4
        chunk = data[pos : pos + length]
        pos += length
        (crc,) = struct.unpack(">I", data[pos : pos + 4])
        pos += 4
        assert crc == (zlib.crc32(tag + chunk) & 0xFFFFFFFF), "bad CRC"
        if tag == b"IHDR":
            width, height, bits, ctype = struct.unpack(">IIBB", chunk[:10])
            assert ctype == 0  # grayscale
            assert chunk[10:13] == b"\x00\x00\x00"  # no compression/filter/interlace
        elif tag == b"IDAT":
            idat += chunk
        elif tag == b"IEND":
            break
    raw = zlib.decompress(idat)
    assert width is not None and height is not None and bits is not None
    row_len = width * bits // 8
    assert len(raw) == (row_len + 1) * height
    out = bytearray()
    for y in range(height):
        base = y * (row_len + 1)
        assert raw[base] == 0  # filter None
        out += raw[base + 1 : base + 1 + row_len]
    if bits == 16:
        samples = array.array("H")
        samples.frombytes(bytes(out))
        samples.byteswap()  # PNG is big-endian -> native little-endian
        out = samples.tobytes()
    return width, height, bits, bytes(out)


class TestPngEncode(unittest.TestCase):
    def test_signature_and_chunk_crc(self):
        png = encode_png(4, 3, 8, bytes([1, 2, 3, 4] * 3))
        self.assertTrue(png.startswith(_SIG))
        decode_png(png)  # validates CRC integrity

    def test_8bit_roundtrip(self):
        pixels = bytes(range(16)) * 2  # 4x8
        w, h, bits, out = decode_png(encode_png(4, 8, 8, pixels))
        self.assertEqual((w, h, bits), (4, 8, 8))
        self.assertEqual(out, pixels)

    def test_16bit_roundtrip(self):
        pixels = bytes(range(32)) * 4  # 8x8 at 16-bit
        w, h, bits, out = decode_png(encode_png(8, 8, 16, pixels))
        self.assertEqual((w, h, bits), (8, 8, 16))
        self.assertEqual(out, pixels)

    def test_size_mismatch_raises(self):
        with self.assertRaises(ValueError):
            encode_png(4, 4, 16, b"\x00" * 10)


@unittest.skipUnless(has_sample_files(), "instrument sample files not present")
class TestImagePng(unittest.TestCase):
    def test_16bit_image_roundtrip(self):
        for key in ("samp1", "samp2"):
            clx = load(SAMPLES[key])
            for img in clx.images:
                png = image_to_png(img)
                w, h, bits, out = decode_png(png)
                self.assertEqual((w, h, bits), (img.width, img.height, 16))
                self.assertEqual(out, bytes(img._pixel_buf))

    def test_preview_is_8bit(self):
        clx = load(SAMPLES["samp1"])
        png = preview_to_png(clx.images[0])
        w, h, bits, _ = decode_png(png)
        self.assertEqual(bits, 8)
        self.assertEqual((w, h), (clx.images[0].width, clx.images[0].height))


if __name__ == "__main__":
    unittest.main()
