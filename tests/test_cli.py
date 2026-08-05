"""End-to-end CLI tests (subprocess)."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import SAMPLES, TIFFS, has_sample_files
from clxparser import load
from clxparser.core import MAGIC

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_cli(*args, cwd=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "clxparser", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or PROJECT_ROOT),
        env=env,
    )


@unittest.skipUnless(has_sample_files(), "instrument sample files not present")
class TestCli(unittest.TestCase):
    def test_version(self):
        r = run_cli("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("clxparser", r.stdout)

    def test_info(self):
        r = run_cli("info", str(SAMPLES["samp1"]))
        self.assertEqual(r.returncode, 0)
        self.assertIn("Samp1", r.stdout)
        self.assertIn("6946 ms", r.stdout)
        self.assertIn("Clx695", r.stdout)

    def test_extract_tiff_matches_official(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_cli(
                "extract",
                str(SAMPLES["samp2"]),
                "--outdir",
                tmp,
                "--formats",
                "tiff",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            clx = load(SAMPLES["samp2"])
            for i in (0, 1):
                out = Path(tmp) / f"Samp2_20260717_194348_00.00.332_{i}_16bit.tif"
                self.assertTrue(out.is_file())
                img = clx.images[i]
                # pixel strip: ours at offset 8, instrument's at offset 24
                ours = out.read_bytes()[8 : 8 + img.byte_count]
                official = TIFFS[("samp2", i)].read_bytes()[24 : 24 + img.byte_count]
                self.assertEqual(ours, official)

    def test_extract_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_cli(
                "extract",
                str(SAMPLES["samp1"]),
                "--outdir",
                tmp,
                "--formats",
                "json",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            meta = json.loads(
                (
                    Path(tmp) / "Samp1_20260804_161544_00.06.946_metadata.json"
                ).read_text()
            )
            self.assertEqual(meta["magic"], MAGIC)
            self.assertEqual(meta["image_count"], 2)

    def test_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "prev.png"
            r = run_cli(
                "preview", str(SAMPLES["samp1"]), "--out", str(out), "--image", "1"
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(out.is_file())
            self.assertEqual(out.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_bad_file_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "not_a_clx.bin"
            bad.write_bytes(b"hello world not a capture")
            r = run_cli("info", str(bad))
            self.assertEqual(r.returncode, 2)
            self.assertIn("error", r.stderr)


if __name__ == "__main__":
    unittest.main()
