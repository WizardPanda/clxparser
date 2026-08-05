# clxparser

A lightweight, dependency-minimal Python parser and CLI for **Clinx
chemiluminescence instrument `.clx` files** — the native capture format produced
by the imager in the lab. A `.clx` file bundles acquisition metadata (sample
name, capture time, exposure) together with the **raw 16-bit fluorescence and
bright-field images**.

The format was reverse-engineered and validated against real instrument
captures. The embedded pixels are **identical** to the `.tif` files the
instrument software writes out, and the exported TIFFs are **pixel-identical**
to the instrument's own export (same 16-bit pixel data in a clean, standard
TIFF container).

```
pip install .
# or, from the source tree:
pip install -e .
```

Dependencies: **numpy** (only needed to access pixel arrays / 8-bit previews).
Metadata parsing, TIFF and lossless PNG export, and the whole CLI work with the
Python standard library alone.

---

## Quickstart (Python)

```python
import clxparser

f = clxparser.load("Samp1_20260804_161544_00.06.946.clx")

f.sample_name        # 'Samp1_20260804_161544'
f.capture_time       # datetime(2026, 8, 4, 16, 15, 57, 224000)
f.exposure_ms        # 6946
f.software           # 'Clx695'
f.format_version     # 3
f.image_count        # 2

for img in f.images:
    print(img.width, img.height, img.bits_per_sample)   # e.g. 687 550 16
    data = img.data          # numpy array, shape (height, width), uint16

    img.save_tiff("out.tif") # pixel-identical to the instrument export
    img.save_png("out.png")  # lossless 16-bit grayscale PNG
    img.save("out.tif")      # format inferred from the extension

print(f.summary())
print(f.to_dict())           # JSON-serializable metadata

# Bulk export of everything, mirroring the instrument's naming scheme:
clxparser.export_images(f, outdir="exports", formats=("tiff", "png", "json"))
```

`img.data` is a writable `(height, width)` `uint16` array; the channel order is
stable across captures (`_0` = bright field, `_1` = fluorescence), and
`f.channel_labels()` returns a best-effort map, e.g. `{0: 'brightfield',
1: 'fluorescence'}`.

## Command-line

```
python -m clxparser info   capture.clx                 # show metadata
python -m clxparser extract capture.clx --outdir out   # tiff+png+json
python -m clxparser extract capture.clx --formats tiff,json
python -m clxparser preview capture.clx --image 1 --out preview.png
```

The console script `clxparser` is installed with the package and is equivalent
to `python -m clxparser`.

`extract` writes, per image, the instrument-style names
`<stem>_<i>_16bit.tif` / `_16bit.png` plus a `_metadata.json` sidecar
(`--preview` adds auto-scaled 8-bit previews).

## File format (reverse-engineered)

Little-endian throughout. Layout of a capture:

| Offset | Size | Field | Meaning |
|---|---|---|---|
| `0x000` | 4 | magic | `0x000025EB` |
| `0x004` | 4 | `=6` | constant |
| `0x008` | 4 | `=6` | constant |
| `0x00C` | 8 | capture time | **OLE Automation Date** (days since 1899-12-30) |
| `0x014` | 4 | exposure | milliseconds (e.g. 6946 ↔ filename `00.06.946`) |
| `0x018` | 22 | sample name | null-padded ASCII |
| `0x02E`–`0x123` | — | opaque | leftover C++ heap pointers, not metadata |
| `0x124` | 4 | format version | `3` |
| `0x128` | 256 | software id | `"Clx695"` |
| `0x228` | 256 | build date | `"202312281113"` (`YYYYMMDDHHMM`) |
| *per image* | 34 | descriptor | see below |
| *per image* | n | pixel data | raw `uint16` little-endian, row-major |

Image descriptor (34 bytes), located by scanning for the `0xC03E` marker and
validating the fields:

```
u16 marker        0xC03E
u32 type          2 or 4 (file-level constant)
u32 width
u32 height
u32 bits_per_sample   16
u32 max_value         (reported/actual pixel maximum)
u32 min_value         (reported/actual pixel minimum)
u32 byte_count        = width * height * bits / 8
u32 reserved          0
```

After the last image a fixed 6456-byte trailer holds a statistics header
(`0x0A`, 65535, type, type, exposure, max, type, type) and serialized
display/LUT settings including the string `"Gray.pal"`. It is exposed verbatim
as `f.trailer` and partially decoded in `f.to_dict()["trailer_info"]`.

The instrument's exported TIFFs embed the same raw strip data with a 13-tag
baseline IFD. `encode_tiff()` writes a clean, standard baseline TIFF with the
same 16-bit pixels in a single uncompressed strip — the image content is
identical to the instrument's export even though the container layout differs.

Filenames encode the same metadata as the header and are parsed for
cross-checks: `{sample}_{YYYYMMDD}_{HHMMSS}_{MM.SS.mmm}.clx`.

## Project layout

```
clxparser/
    __init__.py    public API (load, ClxFile, ClxImage, FormatError)
    core.py        parser: header, descriptor scan, metadata, filename helpers
    tiff.py        dependency-free TIFF writer (matches instrument export)
    png.py         dependency-free PNG writer (16-bit lossless + 8-bit preview)
    export.py      bulk export + metadata JSON
    cli.py         argparse CLI (info / extract / preview)
tests/             unittest suite, incl. pixel-identity checks vs real exports
```

## Tests

```
python -m unittest discover -s tests -v
```

The suite checks metadata, dimensions, exposure and capture time against the
real samples, asserts the embedded pixels and exported TIFFs carry the same
pixel data as the instrument's `.tif` files, and round-trips PNGs with a
self-contained decoder (no Pillow required).

## Notes & caveats

- **Reverse-engineered format.** This library was developed by reverse
  engineering a small number of `.clx` files output by a single device.
  Although the format is consistent across the available captures, it is **not
  guaranteed** that it can parse every `.clx` file produced by all Clinx
  products — other instruments, software versions, or acquisition modes may
  write a slightly different layout. Validate against your own files first.
- The descriptor `type` field (2 vs 4) is exposed but its semantics are unknown;
  it is constant within a capture.
- Only raw, uncompressed 16-bit (and 8/32-bit) images are supported — the only
  layout observed in real captures.
- Channel identification (`brightfield` vs `fluorescence`) is a heuristic based
  on mean intensity and should not be trusted for downstream decisions if your
  acquisition settings vary.

## License

MIT.
