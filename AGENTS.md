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
uv run python -m selfie_timelapse <input_dir> --fps 10 -o test.mp4
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
- 多张脸时选边界框面积最大的一张。
- 统一缩放：第一遍收集每张照片的 `双眼间距 / 画面宽度`，取中位数；第二遍用 `中位数 × 输出宽度` 作为目标眼间距，再输出对齐结果。
- 变换后的空缺用黑色填充。
- 检测不到人脸的照片跳过，并写日志。
- 时间排序，旧照片在前。同一张照片按这个顺序取时间，取到即停：
  1. EXIF `DateTimeOriginal`
  2. EXIF `DateTime`
  3. EXIF `DateTimeDigitized`
  4. 文件名 `IMG_YYYYMMDD_HHMMSS`
  5. 文件名 `WIN_YYYYMMDD_HH_MM_SS_Pro`
  6. 文件修改时间（`os.path.getmtime`）
- 只读取 `.jpg`、`.jpeg`、`.png`。视频和 ini 等其他文件忽略。
- 照片、输出视频和 `debug_frames/` 不提交。`test_photos/` 保持被 git 忽略。

## 测试

仓库没有自动化测试。改了对齐或排序之后，用少量照片（约 10–20 张）运行：

```bash
uv run python -m selfie_timelapse <temp_dir> --fps 10 -o test.mp4
```

完成前确认：

- 人脸对齐，大小一致，双眼水平
- 帧按时间从旧到新
- 跳过的照片在日志里有记录

需要看单帧时加上 `--debug-dir <dir>`。参数表见 README，不要在本文件重写。
