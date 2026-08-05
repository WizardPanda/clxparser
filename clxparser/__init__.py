"""clxparser: a lightweight parser for Clinx chemiluminescence instrument .clx files.

A .clx file is the native capture format of a chemiluminescence imager. It bundles
sample metadata (name, capture time, exposure) together with the raw 16-bit pixel
data of the fluorescence and bright-field images. This package parses that format,
exposes the metadata, and can export the embedded images to standard TIFF and PNG
files (the TIFF export carries the same pixel data as the instrument's own export).
"""

from .core import ClxFile, ClxImage, FormatError, load

__all__ = ["ClxFile", "ClxImage", "FormatError", "load"]

__version__ = "0.1.0"
