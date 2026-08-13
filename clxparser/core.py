"""Core parsing of Clinx .clx instrument files.

Layout (verified against real instrument captures; little-endian):

    [File header]           0x0000 - 0x0123
        0x0000  u32  magic                    0x000025EB
        0x0004  u32  unknown                  6 (constant)
        0x0008  u32  unknown                  6 (constant)
        0x000C  f64  capture_time             OLE Automation Date
        0x0014  u32  exposure_ms
        0x0018  char[0x100] sample_name       null-terminated ASCII (fixed
                                               256-byte field; name bounded in
                                               practice by the Windows filename
                                               length)
        after NUL  (garbage)                   uninitialized bytes inside field

    [Version block]         0x0124 (repeated before every image)
        0x0000  u32  format_version           3
        0x0004  char[0x100] software_id       "Clx695"
        0x0104  char[0x100] build_date        "202312281113"  (YYYYMMDDHHMM)
        +6  zero padding

    [Image descriptor]      34 bytes
        u16 tag             leading 2-byte field; varies in BOTH bytes
                            (0xC03E, 0xC03D, 0x403E observed), not a marker
        u32 type            1, 2, 3 or 4 observed
        u32 width
        u32 height
        u32 bits_per_sample 16
        u32 max_value       (reported/actual pixel maximum)
        u32 min_value       (reported/actual pixel minimum)
        u32 byte_count      = width*height*bits/8
        u32 reserved        0

    [Pixel data]            byte_count bytes, uint16 little-endian, row-major

    ... version block + descriptor + pixel data repeated for each image ...

    [Trailer]               everything after the last image (fixed 6456 bytes
                            in the observed samples); begins with a statistics
                            header and embeds LUT/settings strings.

Descriptors are located by scanning every byte offset and accepting only
candidates that satisfy structural invariants (dimension bounds, bit depth,
byte_count == width*height*bits/8, min/max bounds, in-file bounds), which makes
the parser robust to files that embed additional metadata sections and does not
depend on a stable marker byte.
"""

from __future__ import annotations

import datetime as _dt
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MAGIC = 0x0000_25EB
HEADER_SIZE = 0x0124
VERSION_BLOCK_SIZE = 0x0104  # u32 version + char[0x100] software
BUILD_DATE_SIZE = 0x0100
DESCRIPTOR_SIZE = 34
MAX_DIMENSION = 8192
OLE_EPOCH = _dt.datetime(1899, 12, 30)

# Name of the string that encodes the software build time in both the header
# and the trailer.
BUILD_DATE_STRING = "202312281113"


class FormatError(ValueError):
    """Raised when a file cannot be interpreted as a .clx capture."""


def ole_to_datetime(value: float) -> _dt.datetime:
    """Convert an OLE Automation Date to a naive datetime."""
    return OLE_EPOCH + _dt.timedelta(days=value)


def parse_build_date(text: str) -> Optional[_dt.datetime]:
    """Parse the ``YYYYMMDDHHMM`` build-date string, tolerating garbage."""
    text = text.strip("\x00")
    candidates = []
    if len(text) >= 12:
        candidates.append(("%Y%m%d%H%M", text[:12]))
    if len(text) >= 8:
        candidates.append(("%Y%m%d", text[:8]))
    for fmt, value in candidates:
        try:
            return _dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


_FILENAME_RE = re.compile(
    r"^(?P<sample>.+?)_(?P<date>\d{8})_(?P<time>\d{6})_(?P<exp>\d{2}\.\d{2}\.\d{3})\.clx$"
)


def parse_filename(path) -> Optional[Dict[str, Any]]:
    """Extract structured info from an instrument-style .clx filename.

    Instrument filenames look like::

        {sample}_{YYYYMMDD}_{HHMMSS}_{MM.SS.mmm}.clx

    where ``MM.SS.mmm`` is the exposure as minutes.seconds.milliseconds.
    """
    name = Path(path).name
    m = _FILENAME_RE.match(name)
    if not m:
        return None
    minutes, seconds, millis = m.group("exp").split(".")
    exposure_ms = int(minutes) * 60000 + int(seconds) * 1000 + int(millis)
    try:
        captured = _dt.datetime.strptime(
            m.group("date") + m.group("time"), "%Y%m%d%H%M%S"
        )
    except ValueError:
        captured = None
    return {
        "sample": m.group("sample"),
        "date": m.group("date"),
        "time": m.group("time"),
        "exposure_ms": exposure_ms,
        "capture_time": captured,
    }


def _read_cstr(data: bytes, offset: int, length: int) -> str:
    raw = data[offset : offset + length]
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


@dataclass(frozen=True)
class ImageDescriptor:
    """A validated 34-byte image descriptor found inside the file."""

    offset: int
    type: int
    width: int
    height: int
    bits_per_sample: int
    max_value: int
    min_value: int
    byte_count: int

    @property
    def pixel_offset(self) -> int:
        return self.offset + DESCRIPTOR_SIZE

    def as_dict(self) -> Dict[str, Any]:
        return {
            "offset": self.offset,
            "type": self.type,
            "width": self.width,
            "height": self.height,
            "bits_per_sample": self.bits_per_sample,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "byte_count": self.byte_count,
        }


def parse_descriptor(data: bytes, offset: int) -> Optional[ImageDescriptor]:
    """Parse and validate a descriptor candidate at ``offset``.

    Returns None when the bytes do not form a plausible descriptor. The leading
    2-byte field is not a reliable marker (high byte 0xC0/0x40, low byte
    0x3E/0x3D all observed), so descriptors are identified purely by their
    structural invariants; the most selective fields are checked first.
    """
    if offset + DESCRIPTOR_SIZE > len(data):
        return None
    width, height, bits, mx, mn, byte_count = struct.unpack_from(
        "<IIIIII", data, offset + 6
    )
    if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION):
        return None
    if bits not in (8, 16, 32):
        return None
    if byte_count != width * height * bits // 8:
        return None
    full_scale = (1 << bits) - 1
    if not (0 <= mn <= mx <= full_scale):
        return None
    if offset + DESCRIPTOR_SIZE + byte_count > len(data):
        return None
    (itype,) = struct.unpack_from("<I", data, offset + 2)
    return ImageDescriptor(
        offset=offset,
        type=itype,
        width=width,
        height=height,
        bits_per_sample=bits,
        max_value=mx,
        min_value=mn,
        byte_count=byte_count,
    )


def find_descriptors(data: bytes) -> List[ImageDescriptor]:
    """Find every valid image descriptor in the file.

    Scans every byte offset; the descriptor is recognised by its structural
    invariants, not by a marker byte. A cheap byte-level pre-filter skips the
    vast majority of offsets without a full ``struct.unpack``.
    """
    found: List[ImageDescriptor] = []
    n = len(data)
    if n < DESCRIPTOR_SIZE:
        return found
    # width is a u32 at offset+6 and must be < 8192, so its upper two bytes are
    # zero and the next byte is < 0x20. This rejects almost every pixel-data
    # offset with three byte reads before calling parse_descriptor.
    stop = n - DESCRIPTOR_SIZE + 1
    for offset in range(stop):
        if data[offset + 8] != 0 or data[offset + 9] != 0 or data[offset + 7] >= 0x20:
            continue
        desc = parse_descriptor(data, offset)
        if desc is not None:
            found.append(desc)
    return found


@dataclass
class ClxImage:
    """A single 16-bit image (bright field or fluorescence) embedded in a .clx."""

    index: int
    descriptor: ImageDescriptor
    _pixel_buf: bytearray = field(repr=False)

    @property
    def type(self) -> int:
        return self.descriptor.type

    @property
    def width(self) -> int:
        return self.descriptor.width

    @property
    def height(self) -> int:
        return self.descriptor.height

    @property
    def bits_per_sample(self) -> int:
        return self.descriptor.bits_per_sample

    @property
    def min_value(self) -> int:
        return self.descriptor.min_value

    @property
    def max_value(self) -> int:
        return self.descriptor.max_value

    @property
    def byte_count(self) -> int:
        return self.descriptor.byte_count

    @property
    def pixel_offset(self) -> int:
        return self.descriptor.pixel_offset

    @property
    def data(self):
        """Return the image as a writable numpy array shaped (height, width).

        Requires numpy. The returned array is backed by this image's pixel
        buffer; mutating it does not affect the original file on disk.
        """
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "numpy is required to access pixel data; install it with "
                "`pip install numpy`"
            ) from exc
        dtype = {8: "u1", 16: "<u2", 32: "<u4"}[self.bits_per_sample]
        return np.frombuffer(self._pixel_buf, dtype=dtype).reshape(
            self.height, self.width
        )

    def as_dict(self) -> Dict[str, Any]:
        d = self.descriptor.as_dict()
        d["index"] = self.index
        return d

    def to_tiff_bytes(self, dpi: int = 600) -> bytes:
        """Encode this image as a TIFF byte string (pixels match the instrument export)."""
        from .tiff import image_to_tiff

        return image_to_tiff(self, dpi=dpi)

    def save_tiff(self, path, dpi: int = 600) -> str:
        """Write this image to a TIFF file; returns the output path."""
        path = str(path)
        Path(path).write_bytes(self.to_tiff_bytes(dpi=dpi))
        return path

    def to_png_bytes(self, **kwargs) -> bytes:
        """Encode this image as a 16-bit grayscale PNG (stdlib only)."""
        from .png import image_to_png

        return image_to_png(self, **kwargs)

    def save_png(self, path, **kwargs) -> str:
        """Write this image to a PNG file; returns the output path."""
        path = str(path)
        Path(path).write_bytes(self.to_png_bytes(**kwargs))
        return path

    def save(self, path, fmt: Optional[str] = None, **kwargs) -> str:
        """Save this image, inferring the format from the extension when omitted.

        Supported formats: ``tiff``/``tif`` and ``png``.
        """
        path = str(path)
        if fmt is None:
            fmt = Path(path).suffix.lstrip(".").lower()
        if fmt in ("tiff", "tif"):
            return self.save_tiff(path, **kwargs)
        if fmt == "png":
            return self.save_png(path, **kwargs)
        raise ValueError(f"unsupported format: {fmt!r}")

    def __repr__(self) -> str:
        return (
            f"<ClxImage index={self.index} {self.width}x{self.height} "
            f"bits={self.bits_per_sample} type={self.type}>"
        )


@dataclass
class ClxFile:
    """A parsed .clx file: metadata plus a tuple of embedded images."""

    path: str
    magic: int
    format_version: int
    software: str
    build_datetime: Optional[_dt.datetime]
    sample_name: str
    capture_time: Optional[_dt.datetime]
    exposure_ms: int
    filename_info: Optional[Dict[str, Any]]
    images: Tuple[ClxImage, ...]
    trailer: bytes
    raw_header: bytes = field(repr=False)
    raw_trailer_info: Dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def image_type(self) -> Optional[int]:
        """File-level image type constant (2 or 4 in the observed samples)."""
        if self.images:
            return self.images[0].type
        return None

    def channel_labels(self) -> Dict[int, str]:
        """Channel labels for two-image captures.

        The instrument writes images in a stable order: index 0 is the bright
        field and index 1 the fluorescence/chemiluminescence channel. When
        exactly two images are present this returns ``{0: "brightfield",
        1: "fluorescence"}``; otherwise an empty dict.
        """
        if len(self.images) != 2:
            return {}
        return {
            0: "brightfield",
            1: "fluorescence",
        }

    def summary(self) -> str:
        lines = [
            f"File            : {self.path}",
            f"Sample          : {self.sample_name or '-'}",
            f"Captured        : {self.capture_time.isoformat(sep=' ') if self.capture_time else '-'}",
            f"Exposure        : {self.exposure_ms} ms",
            f"Software        : {self.software} (format v{self.format_version})",
            f"Build date      : {self.build_datetime.isoformat(sep=' ') if self.build_datetime else '-'}",
            f"Images          : {self.image_count}",
        ]
        if self.filename_info:
            lines.append(
                f"Filename meta   : sample={self.filename_info['sample']!r} "
                f"date={self.filename_info['date']} time={self.filename_info['time']} "
                f"exposure={self.filename_info['exposure_ms']} ms"
            )
        for img in self.images:
            hint = self.channel_labels().get(img.index, "")
            lines.append(
                f"  - [{img.index}] {img.width}x{img.height} {img.bits_per_sample}-bit "
                f"type={img.type} min={img.min_value} max={img.max_value} "
                f"{hint}".rstrip()
            )
        lines.append(f"Trailer         : {len(self.trailer)} bytes")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return _json_safe(
            {
                "file": self.path,
                "magic": self.magic,
                "format_version": self.format_version,
                "software": self.software,
                "build_datetime": self.build_datetime.isoformat(sep=" ")
                if self.build_datetime
                else None,
                "sample_name": self.sample_name,
                "capture_time": self.capture_time.isoformat(sep=" ")
                if self.capture_time
                else None,
                "exposure_ms": self.exposure_ms,
                "filename_info": self.filename_info,
                "image_count": self.image_count,
                "image_type": self.image_type,
                "images": [img.as_dict() for img in self.images],
                "trailer_size": len(self.trailer),
                "trailer_info": self.raw_trailer_info,
            }
        )

    def __repr__(self) -> str:
        return (
            f"<ClxFile {Path(self.path).name!r} {self.image_count} images "
            f"sample={self.sample_name!r}>"
        )


def _json_safe(value: Any) -> Any:
    """Recursively convert datetimes/bytes to JSON-serializable primitives."""
    if isinstance(value, _dt.datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, _dt.date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def parse_trailer_info(trailer: bytes, exposure_ms: int) -> Dict[str, Any]:
    """Best-effort decode of the trailing settings/statistics block."""
    info: Dict[str, Any] = {}
    if len(trailer) >= 32:
        info["field_0"] = struct.unpack_from("<I", trailer, 0)[0]
        info["full_scale"] = struct.unpack_from("<I", trailer, 4)[0]
        info["type_0"] = struct.unpack_from("<I", trailer, 8)[0]
        info["type_1"] = struct.unpack_from("<I", trailer, 12)[0]
        info["exposure_ms"] = struct.unpack_from("<I", trailer, 16)[0]
        info["max_value"] = struct.unpack_from("<I", trailer, 20)[0]
        info["type_2"] = struct.unpack_from("<I", trailer, 24)[0]
        info["type_3"] = struct.unpack_from("<I", trailer, 28)[0]
        info["exposure_ms_matches_header"] = info["exposure_ms"] == exposure_ms
    for needle in (b"Gray.pal", BUILD_DATE_STRING.encode("ascii")):
        idx = trailer.find(needle)
        if idx >= 0:
            text = _read_cstr(trailer, idx, 64)
            info[needle.decode("ascii")] = text
    return info


def parse(data: bytes, path: str = "") -> ClxFile:
    """Parse raw .clx bytes into a :class:`ClxFile`."""
    if len(data) < HEADER_SIZE + DESCRIPTOR_SIZE:
        raise FormatError("file too small to be a .clx capture")

    magic = struct.unpack_from("<I", data, 0)[0]
    if magic != MAGIC:
        if data[:4] in (b"II*\x00", b"MM\x00*"):
            raise FormatError(
                "input looks like a TIFF image, not a .clx capture (bad magic "
                f"0x{magic:08X})"
            )
        raise FormatError(f"not a .clx file (bad magic 0x{magic:08X})")

    capture_time = ole_to_datetime(struct.unpack_from("<d", data, 0x0C)[0])
    exposure_ms = struct.unpack_from("<I", data, 0x14)[0]
    sample_name = _read_cstr(data, 0x18, 0x100)
    format_version = struct.unpack_from("<I", data, 0x0124)[0]
    software = _read_cstr(data, 0x0128, 0x100)
    build_date_text = _read_cstr(data, 0x0228, 0x100)
    build_datetime = parse_build_date(build_date_text)

    descriptors = find_descriptors(data)
    if not descriptors:
        raise FormatError("no valid image descriptors found in file")

    images: List[ClxImage] = []
    for index, desc in enumerate(descriptors):
        start = desc.pixel_offset
        end = start + desc.byte_count
        images.append(
            ClxImage(
                index=index, descriptor=desc, _pixel_buf=bytearray(data[start:end])
            )
        )

    last_end = descriptors[-1].pixel_offset + descriptors[-1].byte_count
    trailer = data[last_end:]

    return ClxFile(
        path=str(path),
        magic=magic,
        format_version=format_version,
        software=software,
        build_datetime=build_datetime,
        sample_name=sample_name,
        capture_time=capture_time,
        exposure_ms=exposure_ms,
        filename_info=parse_filename(path),
        images=tuple(images),
        trailer=trailer,
        raw_header=bytes(data[:HEADER_SIZE]),
        raw_trailer_info=parse_trailer_info(trailer, exposure_ms),
    )


def load(path) -> ClxFile:
    """Read and parse a .clx file from ``path``."""
    data = Path(path).read_bytes()
    return parse(data, path=str(path))
