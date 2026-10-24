# selfie-timelapse

给人看的介绍、安装最短步骤、参数和示例见 [README.md](README.md)。本文件只写编码代理要执行的命令和必须守住的实现约束。

> 维护规则：用户在对话中提出新需求、变更或补充时，把相关内容写入本文件。不要把这些内容写回 `CLAUDE.md`。

## 项目概述

把自拍照按拍摄时间合成人脸稳定的视频。用面部关键点做相似变换，把不同距离、角度的脸对齐到统一大小和位置。

## 环境与命令

开发解释器是 Python 3.11，由仓库根目录的 `.python-version` 指定。`pyproject.toml` 里的 `requires-python = ">=3.9"` 是库的兼容下限，不要把它改成开发环境的锁定版本。

依赖只声明在 `pyproject.toml` 的 `dependencies`。第三方包装在仓库根目录的 `.venv`。解释器由 uv 安装，不进仓库。

用 uv。不要使用 conda。不要在未同步的环境里直接运行 `pip` 或 `python`。

```bash
uv sync
uv run python -m selfie_timelapse media/photos --fps 10
```

改过依赖后再执行：

```bash
uv lock
uv sync
```

提交 `uv.lock`。不要提交 `.venv`，也不要恢复 `requirements.txt`。

## 代码约定

改检测、对齐或排序时守住下面的行为。

- 人脸检测用 MediaPipe Tasks API 的 `FaceLandmarker`。不要改回 `mp.solutions.face_mesh`。
- 对齐是显式构造的相似变换（缩放、旋转、平移）。按双眼连线角度写旋转。不要调用 `cv2.estimateAffinePartial2D`。
- 锚点只有左眼中心和右眼中心。鼻尖不参与变换。
- 主角由时间上均匀抽到的少量单人照嵌入得到，不是全库聚类。先均匀看约 24 张；凑满 20 张单人照即停。这一轮不足 8 张单人照时，才在空隙里继续抽，检测预算约 40 张。合影不参与投票。向量按余弦相似度 0.363 聚类，最大簇的均值是原型。两簇都不少于样本的 40% 时打警告，仍用较大的一簇。凑不齐至少 3 张互相似的单人照时记错误日志，并退回面积最大的脸。
- 单人照采用唯一的那张脸，不再嵌入。
- 多张脸时选与主角原型余弦相似度最高、且不低于 0.363 的一张。没有达到阈值的合影跳过，并写日志。
- 统一缩放：第一遍只从选中的脸上收集 `双眼间距 / 画面宽度`，取中位数；第二遍用 `中位数 × 输出宽度` 作为目标眼间距，再输出对齐结果。
- 变换后的空缺用黑色填充。识别裁剪同样只用左右眼中心的相似变换，目标眼位是 112 模板上的 `(38.2946, 51.6963)` 和 `(73.5318, 51.6963)`。
- 检测不到人脸的照片跳过，并写日志。
- 时间排序，旧照片在前。同一张照片按这个顺序取时间，取到即停：
  1. EXIF `DateTimeOriginal`
  2. EXIF `DateTime`
  3. EXIF `DateTimeDigitized`
  4. 文件名 `IMG_YYYYMMDD_HHMMSS`
  5. 文件名 `WIN_YYYYMMDD_HH_MM_SS_Pro`
  6. 文件修改时间（`os.path.getmtime`）
- 只读取 `.jpg`、`.jpeg`、`.png`。视频和 ini 等其他文件忽略。
- 照片、输出视频和 `debug_frames/` 不提交。`media/` 保持被 git 忽略。
- 运行时文件放在仓库根目录的 `cache/`，不要写到用户主目录。`cache/models/` 放 SFace 和 face landmarker，`cache/matplotlib/` 是 matplotlib 的配置目录（`MPLCONFIGDIR`，MediaPipe 会带入 matplotlib）。`cache/` 保持被 git 忽略，也不要打进安装包。
- 用于生成视频的照片放在 `media/photos/`。不要再使用 `test_photos/`。
- 生成的视频一律写到 `media/videos/`。文件名带本地时间戳 `YYYYMMDD-HHMMSS`，默认是 `media/videos/timelapse-YYYYMMDD-HHMMSS.mp4`。`-o` 只改名称，不改目录，例如 `-o test` 得到 `media/videos/test-YYYYMMDD-HHMMSS.mp4`。不要把视频写到仓库根目录或其他目录。
- 安装时只打包 `selfie_timelapse`。`pyproject.toml` 里的 `[tool.setuptools.packages.find]` 保持 `include = ["selfie_timelapse*"]`，避免 `media/`、`debug_frames/` 被 setuptools 当成包。

## 测试

仓库没有自动化测试。改了对齐或排序之后，用少量照片（约 10–20 张）运行：

```bash
uv run python -m selfie_timelapse <temp_dir> --fps 10
```

完成前确认：

- 人脸对齐，大小一致，双眼水平
- 帧按时间从旧到新
- 跳过的照片在日志里有记录
- 合影帧对齐的是主角；没有主角的合影在日志里有记录

需要看单帧时加上 `--debug-dir <dir>`。参数表见 README，不要在本文件重写。
