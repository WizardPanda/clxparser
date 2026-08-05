"""Minimal, dependency-free baseline TIFF writer.

Writes a standard baseline grayscale TIFF with a single uncompressed strip.
The pixel samples are exactly the raw 16-bit values stored in the .clx
capture, so the exported image is **pixel-identical** to what the Clinx
instrument software exports — but the container layout is deliberately simple
and portable rather than a byte-level replica of the vendor's writer.

Layout::

    offset 0    : "II*\\0" + u32 offset-to-IFD
    offset 8    : pixel strip (uncompressed, little-endian, row-major)
    IFD         : 13 tags + zero next-IFD pointer
    rationals   : XResolution and YResolution (dpi / 1)

The output is a fully standards-compliant TIFF readable by ImageJ/Fiji,
Pillow, tifffile and most viewers.
"""

from __future__ import annotations

import struct

# TIFF field types
SHORT = 3
LONG = 4
RATIONAL = 5


def encode_tiff(
    width: int,
    height: int,
    bits_per_sample: int,
    pixels: bytes,
    dpi: int = 600,
    photometric: int = 1,
) -> bytes:
    """Encode raw grayscale pixels as a baseline TIFF byte string.

    ``pixels`` must contain ``width * height * bits_per_sample // 8`` bytes in
    little-endian sample order.
    """
    if bits_per_sample not in (8, 16, 32):
        raise ValueError(f"unsupported bits per sample: {bits_per_sample}")
    byte_count = width * height * bits_per_sample // 8
    if len(pixels) != byte_count:
        raise ValueError(
            f"pixel buffer size {len(pixels)} does not match "
            f"{width}x{height}x{bits_per_sample} bits ({byte_count} bytes)"
        )

    ifd_size = 2 + 13 * 12 + 4  # count + entries + next-IFD pointer
    ifd_offset = 8 + byte_count
    xres_offset = ifd_offset + ifd_size
    yres_offset = xres_offset + 8

    parts = [
        struct.pack("<4sI", b"II*\x00", ifd_offset),  # header
        bytes(pixels),  # pixel strip
    ]

    entries = [
        (254, LONG, 1, 0),  # NewSubfileType
        (256, LONG, 1, width),  # ImageWidth
        (257, LONG, 1, height),  # ImageLength
        (258, SHORT, 1, bits_per_sample),  # BitsPerSample
        (259, SHORT, 1, 1),  # Compression = none
        (262, SHORT, 1, photometric),  # PhotometricInterpretation
        (273, LONG, 1, 8),  # StripOffsets
        (277, SHORT, 1, 1),  # SamplesPerPixel
        (278, LONG, 1, height),  # RowsPerStrip
        (279, LONG, 1, byte_count),  # StripByteCounts
        (282, RATIONAL, 1, xres_offset),  # XResolution -> rational
        (283, RATIONAL, 1, yres_offset),  # YResolution -> rational
        (296, SHORT, 1, 2),  # ResolutionUnit = inch
    ]

    ifd = struct.pack("<H", len(entries))
    for tag, typ, count, value in entries:
        ifd += struct.pack("<HHII", tag, typ, count, value)
    ifd += struct.pack("<I", 0)  # next IFD

    parts.append(ifd)
    parts.append(struct.pack("<II", dpi, 1))  # XResolution rational
    parts.append(struct.pack("<II", dpi, 1))  # YResolution rational
    return b"".join(parts)


def image_to_tiff(image, dpi: int = 600) -> bytes:
    """Encode a parsed :class:`ClxImage` as a TIFF byte string."""
    return encode_tiff(
        width=image.width,
        height=image.height,
        bits_per_sample=image.bits_per_sample,
        pixels=bytes(image._pixel_buf),
        dpi=dpi,
    )
