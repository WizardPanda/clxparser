"""Bulk export of parsed .clx captures.

``export_images`` writes, for each embedded image, the instrument-compatible
TIFF and/or a lossless PNG, plus a JSON metadata sidecar — mirroring the
filename scheme of the instrument's own exports
(``{sample}_{date}_{time}_{exposure}_{index}_16bit.tif``).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_SUPPORTED = ("tiff", "png", "json")


def image_metadata(clxfile) -> Dict[str, Any]:
    """Small, PNG-safe metadata dict embedded as tEXt in exported PNGs."""
    return {
        "sample_name": clxfile.sample_name,
        "capture_time": clxfile.capture_time.isoformat(sep=" ")
        if clxfile.capture_time
        else None,
        "exposure_ms": clxfile.exposure_ms,
        "software": clxfile.software,
        "format_version": clxfile.format_version,
        "source_file": clxfile.path,
    }


def export_images(
    clxfile,
    outdir,
    formats: Iterable[str] = ("tiff", "png", "json"),
    prefix: Optional[str] = None,
    dpi: int = 600,
    preview: bool = False,
) -> List[str]:
    """Export every image in ``clxfile`` into ``outdir``.

    Returns the list of written file paths. Supported ``formats`` entries are
    ``tiff``, ``png`` and ``json``. When ``preview`` is true an extra
    ``_preview.png`` (8-bit auto-scaled) is written for each image.
    """
    formats = [fmt.lower() for fmt in formats]
    unknown = set(formats) - set(_SUPPORTED)
    if unknown:
        raise ValueError(f"unsupported format(s): {sorted(unknown)}")

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    base = prefix or Path(clxfile.path).stem
    written: List[str] = []

    for img in clxfile.images:
        stem = f"{base}_{img.index}_{img.bits_per_sample}bit"
        if "tiff" in formats:
            path = str(outdir / f"{stem}.tif")
            img.save_tiff(path, dpi=dpi)
            written.append(path)
        if "png" in formats:
            path = str(outdir / f"{stem}.png")
            img.save_png(path, metadata=image_metadata(clxfile))
            written.append(path)
        if preview:
            path = str(outdir / f"{base}_{img.index}_preview.png")
            from .png import preview_to_png

            Path(path).write_bytes(
                preview_to_png(img, metadata=image_metadata(clxfile))
            )
            written.append(path)

    if "json" in formats:
        path = str(outdir / f"{base}_metadata.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(clxfile.to_dict(), fh, indent=2, ensure_ascii=False)
        written.append(path)

    return written
