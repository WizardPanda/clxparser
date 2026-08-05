"""Command-line interface: ``clxparser info|extract|preview <file.clx>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core import FormatError, load
from .export import export_images, image_metadata


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clxparser",
        description=(
            "Parse and extract Clinx chemiluminescence instrument .clx "
            "captures (metadata + 16-bit fluorescence and bright-field images)."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    info = sub.add_parser("info", help="show metadata for one or more .clx files")
    info.add_argument("files", nargs="+", metavar="FILE")

    extract = sub.add_parser(
        "extract", help="export images and metadata from .clx files"
    )
    extract.add_argument("files", nargs="+", metavar="FILE")
    extract.add_argument(
        "--outdir", "-o", default=".", help="output directory (default: current dir)"
    )
    extract.add_argument(
        "--formats",
        default="tiff,png,json",
        help="comma-separated output formats: tiff,png,json (default: tiff,png,json)",
    )
    extract.add_argument(
        "--preview",
        action="store_true",
        help="also write 8-bit auto-scaled preview PNGs",
    )
    extract.add_argument(
        "--dpi", type=int, default=600, help="TIFF resolution (default: 600)"
    )

    preview = sub.add_parser("preview", help="write an 8-bit preview PNG of one image")
    preview.add_argument("file", metavar="FILE")
    preview.add_argument(
        "--out", "-o", help="output path (default: <name>_preview.png)"
    )
    preview.add_argument(
        "--image", type=int, default=0, help="image index to preview (default: 0)"
    )
    preview.add_argument(
        "--low", type=int, help="stretch lower bound (default: 1st percentile)"
    )
    preview.add_argument(
        "--high", type=int, help="stretch upper bound (default: 99th percentile)"
    )

    return parser


def cmd_info(files) -> int:
    for path in files:
        clx = load(path)
        print(clx.summary())
        print()
    return 0


def cmd_extract(files, outdir, formats, preview, dpi) -> int:
    formats = [fmt.strip().lower() for fmt in formats.split(",") if fmt.strip()]
    for path in files:
        clx = load(path)
        written = export_images(clx, outdir, formats=formats, preview=preview, dpi=dpi)
        for w in written:
            print(w)
    return 0


def cmd_preview(file, out, image, low, high) -> int:
    from .png import preview_to_png

    clx = load(file)
    if not 0 <= image < len(clx.images):
        raise ValueError(
            f"image index {image} out of range (file has {len(clx.images)} images)"
        )
    img = clx.images[image]
    out_path = out or str(Path(file).with_suffix("").name + "_preview.png")
    data = preview_to_png(img, low=low, high=high, metadata=image_metadata(clx))
    Path(out_path).write_bytes(data)
    print(out_path)
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "info":
            return cmd_info(args.files)
        if args.command == "extract":
            return cmd_extract(
                args.files, args.outdir, args.formats, args.preview, args.dpi
            )
        if args.command == "preview":
            return cmd_preview(args.file, args.out, args.image, args.low, args.high)
        return 2
    except (FormatError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
