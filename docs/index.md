# clxparser documentation

A lightweight, dependency-minimal Python library and CLI for parsing **Clinx
chemiluminescence instrument `.clx` captures** — metadata plus the raw 16-bit
fluorescence and bright-field images.

## Documents

- **[Usage & API reference](usage-guide.md)** — installation, complete Python
  API, CLI reference, export formats, JSON metadata schema, examples, and
  troubleshooting.
- **[`.clx` file format specification](clx-format-spec.md)** — the
  reverse-engineered binary layout: header, version block, image descriptors,
  pixel data, trailer, filename convention, and known unknowns.

## Quick start

```bash
pip install .
clxparser info capture.clx
clxparser extract capture.clx --outdir out
```

```python
import clxparser
f = clxparser.load("capture.clx")
data = f.images[0].data        # uint16 numpy array, (height, width)
f.images[1].save_tiff("fluo.tif")
```

> **Note:** the format was reverse-engineered from a small number of files
> produced by a single device and is not guaranteed to parse every `.clx` from
> all Clinx products. See the [format spec](clx-format-spec.md) for details.
