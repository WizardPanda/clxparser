# clxparser 使用与 API 参考

`clxparser` 是一个用于读取 Clinx 化学发光仪器 `.clx` 采集文件的 Python 库与
命令行工具。本指南涵盖安装、完整的公共 API、命令行、导出格式与故障排除。

底层二进制布局在[《`.clx` 文件格式规范》](clx-format-spec.zh-CN.md)中单独
说明。

---

## 1. 安装

```bash
pip install .
# 或在源码目录开发时：
pip install -e .
```

**依赖：**

| 需求 | 用途 | 是否可选 |
|---|---|---|
| Python ≥ 3.8 | 一切功能 | — |
| numpy ≥ 1.20 | `ClxImage.data`、8 位预览 | 否（包的依赖） |

> 元数据解析、TIFF 导出、16 位 PNG 导出、JSON 旁路文件以及整个 CLI **仅依赖
> 标准库**。如需一个仅用于元数据/导出的环境，可不装 numpy：
>
> ```bash
> pip install -e . --no-deps
> ```

可选扩展：

```bash
pip install -e ".[image]"    # tifffile + Pillow（独立的图像读取器）
pip install -e ".[test]"     # pytest
```

---

## 2. 快速上手

```python
import clxparser

f = clxparser.load("Samp1_20260804_161544_00.06.946.clx")

print(f.sample_name)     # 'Samp1_20260804_161544'
print(f.exposure_ms)     # 6946
print(f.capture_time)    # datetime.datetime(2026, 8, 4, 16, 15, 57, 224000)

# numpy 数组访问，形状 (height, width)，dtype uint16
data = f.images[0].data

# 一键导出
f.images[0].save_tiff("image.tif")
f.images[0].save_png("image.png")
f.images[0].save("image.tif")   # 根据扩展名推断格式

# 批量导出全部（仪器风格文件名 + metadata.json）
clxparser.export_images(f, outdir="exports")

# 人类可读的摘要 / JSON 元数据
print(f.summary())
print(f.to_dict())
```

---

## 3. Python API 参考

### 3.1 `clxparser.load(path) -> ClxFile`

读取并解析一个 `.clx` 文件。若文件不是有效采集文件则抛出 `FormatError`
（若输入实际是 TIFF，会给出友好的提示）。

```python
f = clxparser.load("capture.clx")
```

不落盘、直接解析原始字节可用
`clxparser.core.parse(data: bytes, path: str = "") -> ClxFile`。

### 3.2 `clxparser.ClxFile`

解析后的采集文件。

| 属性 / 方法 | 类型 / 返回 | 说明 |
|---|---|---|
| `path` | `str` | 源文件路径 |
| `magic` | `int` | 格式签名（`0x25EB`） |
| `format_version` | `int` | 格式版本（`3`） |
| `software` | `str` | 软件标识（`"Clx695"`） |
| `build_datetime` | `datetime \| None` | 软件构建时间 |
| `sample_name` | `str` | 来自文件头的样本名 |
| `capture_time` | `datetime \| None` | 采集时间（OLE 日期） |
| `exposure_ms` | `int` | 曝光时长（毫秒） |
| `filename_info` | `dict \| None` | 从文件名解析的结构化信息 |
| `images` | `tuple[ClxImage, ...]` | 内嵌图像 |
| `trailer` | `bytes` | 尾部设置块 |
| `raw_header` | `bytes` | 不透明的文件头字节 |
| `raw_trailer_info` | `dict` | 部分解码的尾部头部/字符串 |
| `image_count` | `int`（属性） | `len(images)` |
| `image_type` | `int \| None`（属性） | 每文件图像 `type` 常量 |
| `channel_labels()` | `dict[int, str]` | `{idx: "brightfield"\|"fluorescence"}` 启发式 |
| `summary()` | `str` | 人类可读的多行摘要 |
| `to_dict()` | `dict` | JSON 可序列化的元数据 |

`filename_info` 示例：

```python
{'sample': 'Samp1', 'date': '20260804', 'time': '161544',
 'exposure_ms': 6946, 'capture_time': datetime(...)}
```

### 3.3 `clxparser.ClxImage`

一张内嵌图像。

| 属性 / 方法 | 说明 |
|---|---|
| `index` | 从零开始的图像索引 |
| `type` | 描述符的 `type` 字段 |
| `width`, `height` | 像素尺寸 |
| `bits_per_sample` | 位深（`16`） |
| `min_value`, `max_value` | 记录的像素最小值 / 最大值 |
| `byte_count` | 像素字节数（`width·height·2`） |
| `pixel_offset` | 像素数据在文件中的绝对字节偏移 |
| `descriptor` | 已验证的 `ImageDescriptor` |
| `data` | **numpy** `uint16` 数组，形状 `(height, width)` —— 可写视图 |
| `to_tiff_bytes(dpi=600)` | 编码为 TIFF 字节串 |
| `save_tiff(path, dpi=600)` | 写入 TIFF；返回路径 |
| `to_png_bytes(**kwargs)` | 编码为 16 位灰度 PNG |
| `save_png(path, **kwargs)` | 写入 PNG；返回路径 |
| `save(path, fmt=None, **kwargs)` | 保存，根据扩展名推断格式 |
| `as_dict()` | JSON 可序列化的描述符 + 索引 |

`data` 是一个由图像像素缓冲区支持的可写视图；修改它**不会**改动磁盘上的
文件。需要 numpy。

### 3.4 `clxparser.FormatError`

`ValueError` 的子类，对无效/不支持的文件抛出。

### 3.5 `clxparser.core` —— 辅助函数

| 函数 | 说明 |
|---|---|
| `load(path)` / `parse(bytes, path="")` | 文件 / 字节解析 |
| `ole_to_datetime(value)` | OLE 自动化日期 → 朴素 `datetime` |
| `parse_build_date(text)` | `YYYYMMDDHHMM` → `datetime`（宽松） |
| `parse_filename(path)` | 仪器文件名 → 结构化 dict 或 `None` |
| `find_descriptors(data)` | 定位已验证的图像描述符 |
| `parse_descriptor(data, offset)` | 校验某偏移处的描述符 |
| `parse_trailer_info(trailer, exposure_ms)` | 尽力解码尾部数据 |

常量：`MAGIC`、`HEADER_SIZE`、`VERSION_BLOCK_SIZE`、`BUILD_DATE_SIZE`、
`DESCRIPTOR_SIZE`（34）、`DESCRIPTOR_MARKER`（`0xC03E`）、`MAX_DIMENSION`。

### 3.6 `clxparser.tiff` —— TIFF 写入器

| 函数 | 说明 |
|---|---|
| `encode_tiff(width, height, bits_per_sample, pixels, dpi=600, photometric=1)` | 原始采样 → baseline TIFF 字节 |
| `image_to_tiff(image, dpi=600)` | 编码一个 `ClxImage` |

TIFF 为单条带 baseline 灰度图像。**像素数据与仪器自身导出完全相同**；容器为
干净的标准布局（见[格式规范](clx-format-spec.zh-CN.md)）。

### 3.7 `clxparser.png` —— PNG 写入器

| 函数 | 说明 |
|---|---|
| `encode_png(width, height, bits, pixel_bytes_le, metadata=None)` | 采样 → PNG 字节（标准库） |
| `image_to_png(image, metadata=None)` | 无损 16 位灰度 PNG |
| `preview_to_png(image, low=None, high=None, percentiles=(1, 99), metadata=None)` | 8 位自动缩放预览 |

16 位 PNG 是无损的。`metadata` 作为 `tEXt` 块嵌入以记录来源。
`preview_to_png` 在直方图的第 1 与第 99 百分位之间拉伸（或使用显式
`low`/`high`），需要 numpy。

### 3.8 `clxparser.export` —— 批量导出

| 函数 | 说明 |
|---|---|
| `export_images(clxfile, outdir, formats=("tiff","png","json"), prefix=None, dpi=600, preview=False)` | 导出全部图像 + 旁路文件；返回路径列表 |
| `image_metadata(clxfile)` | PNG 安全的元数据 dict |

`formats` 接受 `tiff`、`png`、`json` 中的任意组合。`preview=True` 会额外生成
8 位预览。输出命名遵循仪器方案（见 §5）。

---

## 4. 命令行界面

`clxparser`（已安装的控制台脚本）或 `python -m clxparser`。

### 4.1 `clxparser info <file> [<file> ...]`

打印一个或多个采集文件的人类可读摘要：

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

导出图像与元数据。

| 选项 | 默认值 | 说明 |
|---|---|---|
| `--outdir, -o DIR` | `.` | 输出目录（按需创建） |
| `--formats tiff,png,json` | `tiff,png,json` | 逗号分隔的格式 |
| `--preview` | 关 | 同时写入 8 位预览 PNG |
| `--dpi N` | `600` | TIFF 分辨率 |

### 4.3 `clxparser preview <file>`

写入一张图像的 8 位自动缩放预览 PNG。

| 选项 | 默认值 | 说明 |
|---|---|---|
| `--out, -o PATH` | `<name>_preview.png` | 输出路径 |
| `--image N` | `0` | 图像索引 |
| `--low N` | 第 1 百分位 | 拉伸下界 |
| `--high N` | 第 99 百分位 | 拉伸上界 |

### 4.4 `clxparser --version`

打印包版本。

退出码：成功为 `0`，解析/IO 错误为 `2`。

---

## 5. 导出格式

### 5.1 TIFF

单条带、未压缩、baseline 灰度 TIFF。

| TIFF 标签 | 值 |
|---|---|
| ImageWidth / ImageLength | 图像尺寸 |
| BitsPerSample | `16` |
| Compression | `1`（无） |
| PhotometricInterpretation | `1`（黑为 0） |
| SamplesPerPixel | `1` |
| RowsPerStrip | `height` |
| X/YResolution | `600 / 1`（可配置） |
| ResolutionUnit | `2`（英寸） |

### 5.2 PNG

16 位灰度 PNG（位深 16，色彩类型 0）。无损；PNG 以大端序存储采样，因此小端序
像素会在 C 层快速字节交换。元数据（样本名、采集时间、曝光、软件、源文件）作为
`tEXt` 块嵌入。预览为 8 位，采用 1–99 百分位拉伸。

### 5.3 JSON 元数据旁路文件

`export_images(..., formats=("json",))` 写入 `<stem>_metadata.json`，包含
`ClxFile.to_dict()`。`Samp1` 样本的真实输出：

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

## 6. 完整示例

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

# 将荧光通道保存为 TIFF 及预览
fluo.save_tiff("fluorescence.tif")
export_images(f, outdir="exports", formats=("png", "json"), preview=True)
```

---

## 7. 设计说明

- **像素一致性保证。** `ClxImage.data` 以及 TIFF/PNG 导出携带与仪器自身导出
  完全相同的 16 位像素数据。TIFF *容器*刻意采用简单的标准布局 —— 并非对厂商
  写入器的字节级复刻。
- **numpy 是惰性加载的。** 元数据路径与 CLI 从不导入 numpy；只有在请求像素
  数组或预览时才加载。
- **整体读入。** 解析时把文件完整读入内存（对仪器规模的文件——几 MB——最简单
  也最快）。
- **通道标签是启发式的**，基于平均强度，若采集设置变化可能出错；如需可复现，
  请依赖索引顺序。
- **格式是逆向工程的**，来自少量文件；详见[格式规范](clx-format-spec.zh-CN.md)
  中的可移植性警告。

---

## 8. 故障排除

| 现象 | 原因 / 解决办法 |
|---|---|
| `FormatError: not a .clx file (bad magic 0x...)` | 文件不是 `.clx` 采集文件 |
| `FormatError: input looks like a TIFF image...` | 传入了 `.tif`；请加载 `.clx` |
| `FormatError: no valid image descriptors found` | 不支持/未知的变体 —— 见可移植性说明 |
| `ImportError: numpy is required to access pixel data` | 安装 numpy，或仅使用元数据/导出功能 |
| `ValueError: unsupported format: 'jpg'` | `save()`/`export_images()` 仅支持 `tiff`、`png`、`json` |
| CLI 以 `2` 退出并提示 `error: ...` | 文件路径无效或解析失败 |

---

## 9. 测试

```bash
python -m unittest discover -s tests -v
```

测试套件对照随附样本验证元数据、尺寸、曝光与采集时间，断言与仪器 TIFF 导出的
像素一致性，并使用自包含解码器对 PNG 做往返验证。
