# clxparser 文档

一个轻量、最小依赖的 Python 库与 CLI，用于解析 **Clinx 化学发光仪器 `.clx`
采集文件** —— 元数据以及原始 16 位荧光与明场图像。

## 文档

- **[使用与 API 参考](usage-guide.zh-CN.md)** —— 安装、完整 Python API、CLI
  参考、导出格式、JSON 元数据模式、示例与故障排除。
- **[《`.clx` 文件格式规范》](clx-format-spec.zh-CN.md)** —— 逆向工程的二进制
  布局：文件头、版本块、图像描述符、像素数据、尾部数据、文件名约定与已知未知项。

英文版本：[English docs](index.md)

## 快速开始

```bash
pip install .
clxparser info capture.clx
clxparser extract capture.clx --outdir out
```

```python
import clxparser
f = clxparser.load("capture.clx")
data = f.images[0].data        # uint16 numpy 数组，(height, width)
f.images[1].save_tiff("fluo.tif")
```

> **注意：** 该格式由单台设备产生的少量文件逆向工程而来，**不保证**能解析所有
> Clinx 产品的全部 `.clx`。详见[格式规范](clx-format-spec.zh-CN.md)。
