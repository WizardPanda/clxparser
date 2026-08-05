"""Shared helpers for the test suite (example data anonymized with dummy names)."""

from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
SAMPLES = {
    "samp1": DATA / "Samp1_20260804_161544_00.06.946.clx",
    "samp2": DATA / "Samp2_20260717_194348_00.00.332.clx",
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
