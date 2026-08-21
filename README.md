# share-safe

去掉照片和 PDF 里的 GPS 及其他可识别元数据。

## 安装

Python 3.11+。

```bash
pip install .
```

HEIC/HEIF 需要额外依赖；未安装时这类文件会警告并跳过：

```bash
pip install "share-safe[heic]"
```

## 用法

省略 `-o` 时写到旁边的 `name.safe.ext`。

```bash
share-safe photo.jpg -o photo.safe.jpg
share-safe *.jpg -o ./safe/
share-safe scan.pdf -o scan.safe.pdf
share-safe photo.jpg --check
share-safe ./inbox -o ./safe/
share-safe ./inbox -r -o ./safe/
```

## 选项

| 参数 | 含义 |
| --- | --- |
| `-o` | 单文件输出路径，或批量输出目录 |
| `--check` | 只检查是否仍含 GPS，不写文件。发现 GPS 时退出码 `1` |
| `--report` | 打印处理报告（命令行始终打印；图形界面可关） |
| `--force` | 覆盖已存在的输出文件 |
| `--keep-model` | 保留相机品牌/型号；GPS 仍会去掉 |
| `-r` | 递归处理目录 |

默认会去掉 EXIF GPS、相关 XMP、内嵌缩略图、序列号 / MakerNote，以及 PDF 文档信息。会保留像素/页面内容、Orientation，以及拍摄参数（若有）。

## 图形界面

```bash
share-safe gui
```

窗口里始终显示绝对**输入路径**和**输出路径**（文件或目录），可用系统对话框浏览。可勾选 `--check` / `--report`。处理走与命令行相同的逻辑，结果报告显示在窗口内。

## English

Strip GPS and other identifying metadata from JPEG/PNG/WebP/HEIC images and PDFs. Default output is `name.safe.ext` next to the input.

## 许可

MIT
