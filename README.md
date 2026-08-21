# share-safe

Strip GPS and other identifying metadata from photos and PDFs **before you share them**.

Runs entirely on your machine. Originals are never overwritten. No upload. No cloud.

[English](#english) | [中文](#中文)

---

## English

### Why

A screenshot, a vacation JPEG, or a scanned PDF can still hide:

- GPS coordinates (where you were)
- camera serial numbers
- device make/model
- EXIF thumbnails that copy the same tags again
- PDF document info / XMP with GPS

`share-safe` writes a **new** file with that metadata removed and prints a human report of what went away and what remains.

### Install

Python 3.11+:

```bash
pip install .
```

From a clone:

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Optional HEIC/HEIF support:

```bash
pip install "share-safe[heic]"
```

Without that extra, `.heic` / `.heif` files are **skipped with a warning** so a batch of mixed files still finishes.

### Usage

```bash
share-safe photo.jpg -o photo.safe.jpg
share-safe *.jpg -o ./safe/ --report
share-safe scan.pdf -o scan.safe.pdf
share-safe photo.jpg --check
share-safe ./inbox -o ./safe/
share-safe ./inbox -r -o ./safe/          # recurse
```

If `-o` is omitted, each input is written beside the original as `name.safe.ext`.

| Flag | Meaning |
| --- | --- |
| `-o` / `--output` | Output file (one input) or directory (batch) |
| `--check` | Report whether GPS is still present; write nothing |
| `--force` | Overwrite an **existing output** file. Inputs are never overwritten, even with `--force` |
| `--report` | Human report of removed vs remaining metadata (always printed) |
| `--keep-model` | Keep camera make/model. GPS is still always removed |
| `-r` / `--recursive` | Recurse into directories |
| `--version` | Print version |

`--check` exits `1` if any file still has GPS (useful in scripts). Exit `0` means no GPS found.

### What is removed (default)

- EXIF GPS IFD (latitude / longitude / altitude and related tags)
- XMP packets that often duplicate GPS
- Embedded EXIF thumbnails (and JPEG MPF preview segments)
- Camera serial, MakerNote, artist / owner fields
- Device make/model (unless `--keep-model`)
- IPTC/Photoshop APP13, JPEG COM comments
- PNG `eXIf` / text / time chunks
- WebP `EXIF` / `XMP ` chunks
- PDF document info and catalog XMP metadata

### What remains

- The actual pixels / PDF page content
- Orientation (so photos still display upright)
- Optional camera exposure tags (ISO, shutter, …) when present
- `DateTimeOriginal` if present (time is not GPS; strip by re-encoding elsewhere if you also need that gone)
- Color profiles (ICC)

JPEG sanitizing is **lossless for the image bitstream**: APP segments are rewritten; the compressed scan is copied as-is.

### Tests

Fixtures with known GPS are generated in pytest (Pillow + piexif / pypdf). Nothing is uploaded.

```bash
pytest
```

### License

MIT. See [LICENSE](LICENSE).

---

## 中文

在分享之前，去掉照片和 PDF 里的 GPS 与其它可识别元数据。

全程本地运行，**从不覆盖原文件**，不上传，不联网。

### 安装

需要 Python 3.11+：

```bash
pip install .
```

开发安装：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

可选 HEIC/HEIF：

```bash
pip install "share-safe[heic]"
```

未安装该可选依赖时，`.heic` / `.heif` 会 **警告并跳过**，不会让整批任务中断。

### 用法

```bash
share-safe photo.jpg -o photo.safe.jpg
share-safe *.jpg -o ./safe/ --report
share-safe scan.pdf -o scan.safe.pdf
share-safe photo.jpg --check
share-safe ./inbox -o ./safe/
```

省略 `-o` 时，会在原文件旁写出 `name.safe.ext`。

| 参数 | 含义 |
| --- | --- |
| `-o` / `--output` | 单文件输出路径，或批量输出目录 |
| `--check` | 只检查是否仍含 GPS，不写文件 |
| `--force` | 仅允许覆盖**已存在的输出文件**；即使加 `--force` 也不会覆盖输入 |
| `--report` | 打印去掉了什么、还留下什么（默认就会打印） |
| `--keep-model` | 保留相机品牌/型号；GPS 仍然一定会去掉 |
| `-r` / `--recursive` | 递归处理目录 |
| `--version` | 版本号 |

`--check` 若发现 GPS 则以状态码 `1` 退出，便于脚本使用。

### 默认会去掉

- EXIF GPS（经纬度、海拔等）
- 可能带 GPS 的 XMP
- 内嵌缩略图（缩略图里也可能有一份 EXIF）
- 机身序列号、MakerNote、作者等信息
- 设备品牌/型号（可用 `--keep-model` 保留）
- PDF 文档信息与 XMP 中的 GPS

### 会保留

- 图像像素 / PDF 页面内容
- 方向（Orientation）
- 拍摄参数（若有）
- `DateTimeOriginal`（时间不是 GPS；若连时间也要去掉需另做处理）

### 测试

CI 使用测试里现场生成的、带已知 GPS 的夹具图（piexif / Pillow），并断言输出不再含 GPS 标签。PDF 同理。

```bash
pytest
```

### 许可证

MIT，见 [LICENSE](LICENSE)。
