"""Dependency-free PNG encoder.

Produces standard grayscale PNGs:

* **16-bit** (bit depth 16, color type 0) for lossless export of the raw
  image data. PNG stores samples big-endian, so little-endian pixels are
  byte-swapped at C speed using the stdlib ``array`` module.
* **8-bit** (bit depth 8) for auto-scaled preview thumbnails.

Optional ``tEXt`` metadata (sample name, capture time, exposure, software) can
be embedded for provenance.
"""

from __future__ import annotations

import array
import struct
import zlib
from typing import Any, Dict, Optional

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def _to_big_endian(pixel_bytes_le: bytes, bits: int) -> bytes:
    if bits == 16:
        samples = array.array("H")
        samples.frombytes(pixel_bytes_le)
        samples.byteswap()
        return samples.tobytes()
    return pixel_bytes_le  # 8-bit samples are byte aligned already


def _tEXt_chunk(metadata: Optional[Dict[str, Any]]) -> bytes:
    if not metadata:
        return b""
    pairs = []
    for key, value in metadata.items():
        if value is None:
            continue
        if any(c == "\x00" for c in key):
            continue
        text = str(value)
        if len(text) > 2000:  # tEXt limit is ~2^31; be conservative
            text = text[:2000]
        try:
            pairs.append((key + "\x00" + text).encode("latin-1"))
        except UnicodeEncodeError:
            continue
    if not pairs:
        return b""
    return _chunk(b"tEXt", b"\n".join(pairs))


def encode_png(
    width: int,
    height: int,
    bits: int,
    pixel_bytes_le: bytes,
    metadata: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Encode grayscale little-endian samples as a PNG byte string."""
    if bits not in (8, 16):
        raise ValueError(f"unsupported PNG bit depth: {bits}")
    expected = width * height * bits // 8
    if len(pixel_bytes_le) != expected:
        raise ValueError(
            f"pixel buffer size {len(pixel_bytes_le)} does not match "
            f"{width}x{height} at {bits} bits ({expected} bytes)"
        )

    samples = _to_big_endian(pixel_bytes_le, bits)
    row_len = width * bits // 8
    raw = bytearray(expected + height)
    out_pos = 0
    src_pos = 0
    for _ in range(height):
        raw[out_pos] = 0  # filter: None
        out_pos += 1
        raw[out_pos : out_pos + row_len] = samples[src_pos : src_pos + row_len]
        out_pos += row_len
        src_pos += row_len
    compressed = zlib.compress(bytes(raw), 6)

    ihdr = struct.pack(">IIBBBBB", width, height, bits, 0, 0, 0, 0)
    out = _SIGNATURE
    out += _chunk(b"IHDR", ihdr)
    out += _tEXt_chunk(metadata)
    out += _chunk(b"IDAT", compressed)
    out += _chunk(b"IEND", b"")
    return out


def image_to_png(image, metadata: Optional[Dict[str, Any]] = None) -> bytes:
    """Encode a parsed :class:`ClxImage` as a lossless 16-bit grayscale PNG."""
    return encode_png(
        width=image.width,
        height=image.height,
        bits=image.bits_per_sample,
        pixel_bytes_le=bytes(image._pixel_buf),
        metadata=metadata,
    )


def preview_to_png(
    image,
    low: Optional[int] = None,
    high: Optional[int] = None,
    percentiles: tuple = (1, 99),
    metadata: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Encode an 8-bit auto-scaled preview of the image as a PNG.

    Intensity is stretched linearly from the ``percentiles`` of the pixel
    histogram to the full 8-bit range (or from ``low``/``high`` when given).
    Requires numpy.
    """
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "preview encoding requires numpy; install it with `pip install numpy`"
        ) from exc

    arr = image.data
    if low is None or high is None:
        lo, hi = np.percentile(arr, list(percentiles))
        low = int(lo)
        high = int(hi)
    if high <= low:
        high = low + 1
    scaled = np.clip(
        (arr.astype(np.float32) - low) * (255.0 / (high - low)), 0, 255
    ).astype(np.uint8)
    return encode_png(
        width=image.width,
        height=image.height,
        bits=8,
        pixel_bytes_le=scaled.tobytes(),
        metadata=metadata,
    )
