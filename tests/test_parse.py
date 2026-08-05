"""Tests for the core .clx parser against real instrument samples."""

import datetime as dt
import json
import unittest

from tests import SAMPLES, TIFFS, has_sample_files
from clxparser import FormatError, load
from clxparser.core import (
    MAGIC,
    ole_to_datetime,
    parse_build_date,
    parse_filename,
)

SAMP1 = "samp1"
SAMP2 = "samp2"


@unittest.skipUnless(has_sample_files(), "instrument sample files not present")
class TestClxParse(unittest.TestCase):
    def test_magic_and_version(self):
        for key in (SAMP1, SAMP2):
            f = load(SAMPLES[key])
            self.assertEqual(f.magic, MAGIC)
            self.assertEqual(f.software, "Clx695")
            self.assertEqual(f.format_version, 3)

    def test_build_date(self):
        for key in (SAMP1, SAMP2):
            f = load(SAMPLES[key])
            self.assertEqual(f.build_datetime, dt.datetime(2023, 12, 28, 11, 13))

    def test_sample_name_and_exposure(self):
        f = load(SAMPLES[SAMP1])
        self.assertEqual(f.sample_name, "Samp1_20260804_161544")
        self.assertEqual(f.exposure_ms, 6946)
        g = load(SAMPLES[SAMP2])
        self.assertEqual(g.sample_name, "Samp2_20260717_194348")
        self.assertEqual(g.exposure_ms, 332)

    def test_capture_time_matches_filename_date(self):
        for key, expected in ((SAMP1, 2026), (SAMP2, 2026)):
            f = load(SAMPLES[key])
            ct = f.capture_time
            file_time = (f.filename_info or {}).get("capture_time")
            if ct is None or file_time is None:
                self.fail(f"missing capture time for {key}")
            self.assertEqual(ct.year, expected)
            self.assertEqual(ct.date(), file_time.date())

    def test_image_count_and_dimensions(self):
        f = load(SAMPLES[SAMP1])
        self.assertEqual(f.image_count, 2)
        self.assertEqual([(i.width, i.height) for i in f.images], [(687, 550)] * 2)
        g = load(SAMPLES[SAMP2])
        self.assertEqual([(i.width, i.height) for i in g.images], [(1375, 1100)] * 2)
        for img in f.images + g.images:
            self.assertEqual(img.bits_per_sample, 16)
            self.assertEqual(img.byte_count, img.width * img.height * 2)

    def test_descriptor_min_max_match_data(self):
        for key in (SAMP1, SAMP2):
            f = load(SAMPLES[key])
            for img in f.images:
                data = img.data
                self.assertEqual(img.min_value, int(data.min()))
                self.assertEqual(img.max_value, int(data.max()))

    def test_pixels_identical_to_exported_tiff_strips(self):
        for key in (SAMP1, SAMP2):
            f = load(SAMPLES[key])
            for i, img in enumerate(f.images):
                tif = TIFFS[(key, i)].read_bytes()
                strip = tif[24 : 24 + img.byte_count]
                self.assertEqual(bytes(img._pixel_buf), strip, (key, i))

    def test_channel_labels(self):
        for key in (SAMP1, SAMP2):
            f = load(SAMPLES[key])
            self.assertEqual(f.channel_labels(), {0: "brightfield", 1: "fluorescence"})

    def test_trailer_size(self):
        for key in (SAMP1, SAMP2):
            f = load(SAMPLES[key])
            self.assertEqual(len(f.trailer), 6456)
            self.assertTrue(f.raw_trailer_info["exposure_ms_matches_header"])

    def test_to_dict_json_serializable(self):
        f = load(SAMPLES[SAMP2])
        d = f.to_dict()
        json.dumps(d)  # must not raise
        self.assertEqual(d["image_count"], 2)
        self.assertEqual(len(d["images"]), 2)
        self.assertEqual(d["images"][0]["width"], 1375)

    def test_summary_mentions_key_fields(self):
        f = load(SAMPLES[SAMP1])
        summary = f.summary()
        self.assertIn("Samp1", summary)
        self.assertIn("6946 ms", summary)
        self.assertIn("Clx695", summary)


@unittest.skipUnless(has_sample_files(), "instrument sample files not present")
class TestClxErrors(unittest.TestCase):
    def test_non_clx_raises(self):
        with self.assertRaises(FormatError):
            load(__file__)  # a python file, not a capture

    def test_tiff_input_detected(self):
        with self.assertRaises(FormatError) as ctx:
            load(TIFFS[(SAMP1, 0)])
        self.assertIn("TIFF", str(ctx.exception))


class TestHelpers(unittest.TestCase):
    def test_ole_to_datetime(self):
        self.assertEqual(ole_to_datetime(46238.0).date(), dt.date(2026, 8, 4))
        self.assertEqual(ole_to_datetime(0.0), dt.datetime(1899, 12, 30))

    def test_parse_build_date(self):
        self.assertEqual(
            parse_build_date("202312281113"), dt.datetime(2023, 12, 28, 11, 13)
        )
        self.assertEqual(parse_build_date("20231228"), dt.datetime(2023, 12, 28))
        self.assertIsNone(parse_build_date("garbage"))
        self.assertIsNone(parse_build_date(""))

    def test_parse_filename(self):
        info = parse_filename("Samp1_20260804_161544_00.06.946.clx")
        self.assertIsNotNone(info)
        self.assertEqual(info["sample"], "Samp1")
        self.assertEqual(info["exposure_ms"], 6946)
        self.assertEqual(info["capture_time"], dt.datetime(2026, 8, 4, 16, 15, 44))

        info = parse_filename("Samp2_20260717_194348_00.00.332.clx")
        self.assertIsNotNone(info)
        self.assertEqual(info["exposure_ms"], 332)
        self.assertIsNone(parse_filename("random.bin"))


if __name__ == "__main__":
    unittest.main()
