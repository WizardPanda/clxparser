# clxparser — project notes

`clxparser` is a Python library + CLI for parsing Clinx chemiluminescence
instrument `.clx` files (metadata + 16-bit bright-field/fluorescence images).

## Commands

- Run tests (stdlib unittest, no pytest needed):
  `python -m unittest discover -s tests -v`
- Run the CLI: `python -m clxparser info <file.clx>` (or `extract`, `preview`)
- Verify the package installs: `pip install -e .` then `clxparser --version`
- Install without numpy for a metadata/export-only environment:
  `pip install -e . --no-deps`

## Documentation

- Docs live in `docs/`. Every document has an English (`docs/<name>.md`) and a
  Chinese (`docs/<name>.zh-CN.md`) version that must stay in sync.
- When editing a doc, update BOTH language versions (and cross-links) in the
  same commit; keep section structure and values identical, translating only
  prose. Add the sync note reminder below when touching docs.
- If a doc changes and the other language was not updated, flag it explicitly.

## Conventions

- Core parsing, TIFF and PNG export are stdlib-only (struct/datetime/array/
  zlib). numpy is used ONLY for pixel-array access (`ClxImage.data`) and 8-bit
  preview scaling, imported lazily — the metadata path and CLI must keep working
  without numpy.
- Little-endian throughout. See `clxparser/core.py` module docstring and
  README for the full format spec.
- When adding features, keep the pixel-identity guarantees: `ClxImage.data`
  must equal the pixel strip of the instrument's exported TIFF, and the images
  written by `ClxImage.to_tiff_bytes()`/`save_tiff()` must carry the same 16-bit
  pixel data as the official export. The TIFF *container* is intentionally a
  simple standard layout — do not reintroduce byte-level replication of the
  vendor's writer.
- Commit each feature separately with a clear message.
