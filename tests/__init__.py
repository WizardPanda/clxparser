"""Shared helpers for the test suite (example data anonymized with dummy names)."""

from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
SAMPLES = {
    "samp1": DATA / "Samp1_20260804_161544_00.06.946.clx",
    "samp2": DATA / "Samp2_20260717_194348_00.00.332.clx",
    "samp3": DATA / "Samp3_20250721_183436_01.30.000.clx",
    "samp4": DATA / "Samp4_20260723_163251_00.00.946.clx",
    "samp5": DATA / "Samp5_20260813_110119_00.00.260.clx",
    "samp6": DATA / "Samp6_20250512_110653_01.23.279.clx",
    "samp7": DATA / "Samp7_20260319_211250_00.07.453.clx",
}

TIFFS = {
    ("samp1", 0): DATA / "Samp1_20260804_161544_00.06.946_0_16bit.tif",
    ("samp1", 1): DATA / "Samp1_20260804_161544_00.06.946_1_16bit.tif",
    ("samp2", 0): DATA / "Samp2_20260717_194348_00.00.332_0_16bit.tif",
    ("samp2", 1): DATA / "Samp2_20260717_194348_00.00.332_1_16bit.tif",
}


def has_sample_files() -> bool:
    return all(p.is_file() for p in SAMPLES.values()) and all(
        p.is_file() for p in TIFFS.values()
    )
