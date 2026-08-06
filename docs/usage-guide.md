# clxparser Usage & API Reference

> **中文文档：[clxparser 使用与 API 参考（中文）](usage-guide.zh-CN.md)**

`clxparser` is a Python library and command-line tool for reading Clinx
chemiluminescence instrument `.clx` captures. This guide covers installation,
the complete public API, the CLI, export formats, and troubleshooting.

The underlying binary layout is documented separately in
[`clx-format-spec.md`](clx-format-spec.md).

---

## 1. Installation

```bash
pip install .
# or, from the source tree during development:
pip install -e .
```

**Dependencies:**

| Requirement | Needed for | Optional? |
|---|---|---|
| Python ≥ 3.8 | everything | — |
| numpy ≥ 1.20 | `ClxImage.data`, 8-bit previews | no (package dependency) |

> Metadata parsing, TIFF export, 16-bit PNG export, the JSON sidecar and the
> whole CLI work with the **standard library only**. Install without numpy for a
> metadata/export-only environment:
>
> ```bash
> pip install -e . --no-deps
> ```

---

## 2. Quickstart

```python
import clxparser

f = clxparser.load("Samp1_20260804_161544_00.06.946.clx")

print(f.sample_name)     # 'Samp1_20260804_161544'
print(f.exposure_ms)     # 6946
print(f.capture_time)    # datetime.datetime(2026, 8, 4, 16, 15, 57, 224000)

# numpy array access, shape (height, width), dtype uint16
data = f.images[0].data

# one-line exports
f.images[0].save_tiff("image.tif")
f.images[0].save_png("image.png")
f.images[0].save("image.tif")   # format inferred from extension

# bulk export everything (instrument-style filenames + metadata.json)
clxparser.export_images(f, outdir="exports")

# human-readable summary / JSON metadata
print(f.summary())
print(f.to_dict())
```

---

## 3. Python API reference

### 3.1 `clxparser.load(path) -> ClxFile`

Read and parse a `.clx` file. Raises `FormatError` if the file is not a valid
capture (including a friendly message when the input is actually a TIFF).

```python
f = clxparser.load("capture.clx")
```

Raw bytes can be parsed without touching disk via
`clxparser.core.parse(data: bytes, path: str = "") -> ClxFile`.

### 3.2 `clxparser.ClxFile`

The parsed capture.

| Attribute / method | Type / returns | Description |
|---|---|---|
| `path` | `str` | Source file path |
| `magic` | `int` | Format signature (`0x25EB`) |
| `format_version` | `int` | Format version (`3`) |
| `software` | `str` | Software id (`"Clx695"`) |
| `build_datetime` | `datetime \| None` | Software build time |
| `sample_name` | `str` | Sample name from the header |
| `capture_time` | `datetime \| None` | Capture time (OLE date) |
| `exposure_ms` | `int` | Exposure in milliseconds |
| `filename_info` | `dict \| None` | Structured info parsed from the filename |
| `images` | `tuple[ClxImage, ...]` | Embedded images |
| `trailer` | `bytes` | Trailing settings block |
| `raw_header` | `bytes` | The opaque header bytes |
| `raw_trailer_info` | `dict` | Partially decoded trailer header/strings |
| `image_count` | `int` (property) | `len(images)` |
| `image_type` | `int \| None` (property) | The per-file image `type` constant |
| `channel_labels()` | `dict[int, str]` | `{0: "brightfield", 1: "fluorescence"}` for two-image captures, else `{}` |
| `summary()` | `str` | Human-readable multi-line summary |
| `to_dict()` | `dict` | JSON-serializable metadata |

`filename_info` example:

```python
{'sample': 'Samp1', 'date': '20260804', 'time': '161544',
 'exposure_ms': 6946, 'capture_time': datetime(...)}
```

### 3.3 `clxparser.ClxImage`

A single embedded image.

| Attribute / method | Description |
|---|---|
| `index` | Zero-based image index |
| `type` | The descriptor `type` field |
| `width`, `height` | Dimensions in pixels |
| `bits_per_sample` | Bit depth (`16`) |
| `min_value`, `max_value` | Reported pixel minimum / maximum |
| `byte_count` | Number of pixel bytes (`width·height·2`) |
| `pixel_offset` | Absolute byte offset of the pixel data in the file |
| `descriptor` | The validated `ImageDescriptor` |
| `data` | **numpy** `uint16` array, shape `(height, width)` — writable view |
| `to_tiff_bytes(dpi=600)` | Encode as a TIFF byte string |
| `save_tiff(path, dpi=600)` | Write a TIFF; returns the path |
| `to_png_bytes(**kwargs)` | Encode as a 16-bit grayscale PNG |
| `save_png(path, **kwargs)` | Write a PNG; returns the path |
| `save(path, fmt=None, **kwargs)` | Save, inferring format from the extension |
| `as_dict()` | JSON-serializable descriptor + index |

`data` is a writable view backed by the image's pixel buffer; mutating it does
**not** modify the file on disk. It requires numpy.

### 3.4 `clxparser.FormatError`

Subclass of `ValueError`, raised for invalid/unsupported files.

### 3.5 `clxparser.core` — helpers

| Function | Description |
|---|---|
| `load(path)` / `parse(bytes, path="")` | File / bytes parsing |
| `ole_to_datetime(value)` | OLE Automation Date → naive `datetime` |
| `parse_build_date(text)` | `YYYYMMDDHHMM` → `datetime` (lenient) |
| `parse_filename(path)` | Instrument filename → structured dict or `None` |
| `find_descriptors(data)` | Locate validated image descriptors |
| `parse_descriptor(data, offset)` | Validate a descriptor at an offset |
| `parse_trailer_info(trailer, exposure_ms)` | Best-effort trailer decode |

Constants: `MAGIC`, `HEADER_SIZE`, `VERSION_BLOCK_SIZE`, `BUILD_DATE_SIZE`,
`DESCRIPTOR_SIZE` (34), `DESCRIPTOR_MARKER` (high byte `0xC0`), `MAX_DIMENSION`.

### 3.6 `clxparser.tiff` — TIFF writer

| Function | Description |
|---|---|
| `encode_tiff(width, height, bits_per_sample, pixels, dpi=600, photometric=1)` | Encode raw samples → baseline TIFF bytes |
| `image_to_tiff(image, dpi=600)` | Encode a `ClxImage` |

The TIFF is a single-strip baseline grayscale image. The **pixel data is
identical** to the instrument's own export; the container is a clean standard
layout (see the [format spec](clx-format-spec.md)).

### 3.7 `clxparser.png` — PNG writer

| Function | Description |
|---|---|
| `encode_png(width, height, bits, pixel_bytes_le, metadata=None)` | Encode samples → PNG bytes (stdlib) |
| `image_to_png(image, metadata=None)` | Lossless 16-bit grayscale PNG |
| `preview_to_png(image, low=None, high=None, percentiles=(1, 99), metadata=None)` | 8-bit auto-scaled preview |

16-bit PNGs are lossless. `metadata` is embedded as a `tEXt` chunk for
provenance. `preview_to_png` stretches the histogram between the 1st and 99th
percentiles (or explicit `low`/`high`) and requires numpy.

### 3.8 `clxparser.export` — bulk export

| Function | Description |
|---|---|
| `export_images(clxfile, outdir, formats=("tiff","png","json"), prefix=None, dpi=600, preview=False)` | Write all images + sidecars; returns list of paths |
| `image_metadata(clxfile)` | PNG-safe metadata dict |

`formats` accepts any of `tiff`, `png`, `json`. `preview=True` adds 8-bit
previews. The output naming mirrors the instrument's scheme (see §5).

---

## 4. Command-line interface

`clxparser` (installed console script) or `python -m clxparser`.

### 4.1 `clxparser info <file> [<file> ...]`

Print a human-readable summary of one or more captures:

```text
File            : Samp1_20260804_161544_00.06.946.clx
Sample          : Samp1_20260804_161544
Captured        : 2026-08-04 16:15:57.224000
Exposure        : 6946 ms
Software        : Clx695 (format v3)
Build date      : 2023-12-28 11:13:00
Images          : 2
  - [0] 687x550 16-bit type=4 min=0 max=65535 brightfield
  - [1] 687x550 16-bit type=4 min=1200 max=65535 fluorescence
Trailer         : 6456 bytes
```

### 4.2 `clxparser extract <file> [<file> ...]`

Export images and metadata.

| Option | Default | Description |
|---|---|---|
| `--outdir, -o DIR` | `.` | Output directory (created if needed) |
| `--formats tiff,png,json` | `tiff,png,json` | Comma-separated formats |
| `--preview` | off | Also write 8-bit preview PNGs |
| `--dpi N` | `600` | TIFF resolution |

### 4.3 `clxparser preview <file>`

Write an 8-bit auto-scaled preview PNG of one image.

| Option | Default | Description |
|---|---|---|
| `--out, -o PATH` | `<name>_preview.png` | Output path |
| `--image N` | `0` | Image index |
| `--low N` | 1st percentile | Stretch lower bound |
| `--high N` | 99th percentile | Stretch upper bound |

### 4.4 `clxparser --version`

Print the package version.

Exit codes: `0` on success, `2` on parse/IO errors.

---

## 5. Export formats

### 5.1 TIFF

Single-strip, uncompressed, baseline grayscale TIFF.

| TIFF tag | Value |
|---|---|
| ImageWidth / ImageLength | image dimensions |
| BitsPerSample | `16` |
| Compression | `1` (none) |
| PhotometricInterpretation | `1` (black-is-zero) |
| SamplesPerPixel | `1` |
| RowsPerStrip | `height` |
| X/YResolution | `600 / 1` (configurable) |
| ResolutionUnit | `2` (inch) |

### 5.2 PNG

16-bit grayscale PNGs (bit depth 16, color type 0). Lossless; PNG stores samples
big-endian, so little-endian pixels are byte-swapped at C speed. Metadata
(sample name, capture time, exposure, software, source file) is embedded as a
`tEXt` chunk. Previews are 8-bit with a 1–99 percentile stretch.

### 5.3 JSON metadata sidecar

`export_images(..., formats=("json",))` writes `<stem>_metadata.json` containing
`ClxFile.to_dict()`. Real output for the `Samp1` sample:

```json
{
  "file": "tests/data/Samp1_20260804_161544_00.06.946.clx",
  "magic": 9707,
  "format_version": 3,
  "software": "Clx695",
  "build_datetime": "2023-12-28 11:13:00",
  "sample_name": "Samp1_20260804_161544",
  "capture_time": "2026-08-04 16:15:57.224000",
  "exposure_ms": 6946,
  "filename_info": {
    "sample": "Samp1",
    "date": "20260804",
    "time": "161544",
    "exposure_ms": 6946,
    "capture_time": "2026-08-04 16:15:44"
  },
  "image_count": 2,
  "image_type": 4,
  "images": [
    { "index": 0, "offset": 814, "type": 4, "width": 687, "height": 550,
      "bits_per_sample": 16, "min_value": 0, "max_value": 65535, "byte_count": 755700 },
    { "index": 1, "offset": 757070, "type": 4, "width": 687, "height": 550,
      "bits_per_sample": 16, "min_value": 1200, "max_value": 65535, "byte_count": 755700 }
  ],
  "trailer_size": 6456,
  "trailer_info": {
    "field_0": 10, "full_scale": 65535, "type_0": 4, "type_1": 4,
    "exposure_ms": 6946, "max_value": 65535, "type_2": 4, "type_3": 4,
    "exposure_ms_matches_header": true,
    "Gray.pal": "Gray.pal",
    "202312281113": "202312281113"
  }
}
```

---

## 6. Worked example

```python
import clxparser
from clxparser import export_images

f = clxparser.load("Samp2_20260717_194348_00.00.332.clx")
assert f.image_count == 2

bf, fluo = f.images
print(bf.width, bf.height)          # 1375 1100
print(bf.max_value)                 # 65535

import numpy as np
arr = fluo.data                     # (1100, 1375) uint16
print(arr.mean(), arr.std())

# save the fluorescence channel as TIFF and a preview
fluo.save_tiff("fluorescence.tif")
export_images(f, outdir="exports", formats=("png", "json"), preview=True)
```

---

## 7. Design notes

- **Pixel-identity guarantee.** `ClxImage.data` and the TIFF/PNG exports carry
  exactly the same 16-bit pixel data as the instrument's own export. The TIFF
  *container* is intentionally a simple standard layout — it is not a byte-level
  replica of the vendor's writer.
- **numpy is lazy.** The metadata path and CLI never import numpy; it is loaded
  only when pixel arrays or previews are requested.
- **Eager reads.** Files are read fully into memory at parse time (simplest and
  fast for instrument-scale files, which are a few MB).
- **Channel order is stable**: image `0` is the bright field, image `1` the
  fluorescence/chemiluminescence channel, matching the instrument's own exports.
  `channel_labels()` returns this mapping for two-image captures.
- **Format is reverse-engineered** from a small number of files; see the
  portability warning in the [format spec](clx-format-spec.md).

---

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `FormatError: not a .clx file (bad magic 0x...)` | File is not a `.clx` capture |
| `FormatError: input looks like a TIFF image...` | You passed a `.tif`; load the `.clx` instead |
| `FormatError: no valid image descriptors found` | Unsupported/unknown variant — see portability note |
| `ImportError: numpy is required to access pixel data` | Install numpy, or only use metadata/export functions |
| `ValueError: unsupported format: 'jpg'` | `save()`/`export_images()` support `tiff`, `png`, `json` only |
| CLI exits `2` with `error: ...` | Invalid file path or parse failure |

---

## 9. Testing

```bash
python -m unittest discover -s tests -v
```

The suite verifies metadata, dimensions, exposure and capture time against the
shipped samples, asserts pixel-identity with the instrument TIFF exports, and
round-trips PNGs with a self-contained decoder.
