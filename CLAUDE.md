# selfie-timelapse

## 项目概述

一个将自拍照按时间顺序合成为人脸稳定化视频的 Python 工具。通过人脸关键点检测和相似变换，将不同拍摄距离、角度下的自拍照对齐为统一的面部大小和位置，生成流畅的时间轴视频。

## 运行环境

- **操作系统**: Windows 10
- **Python 环境**: Anaconda (`D:\Tools\Anaconda\anaconda3`)
- **启动方式**:
  - PowerShell: `%WINDIR%\System32\WindowsPowerShell\v1.0\powershell.exe -ExecutionPolicy ByPass -NoExit -Command "& 'D:\Tools\Anaconda\anaconda3\shell\condabin\conda-hook.ps1' ; conda activate 'D:\Tools\Anaconda\anaconda3' "`
  - CMD: `%WINDIR%\System32\cmd.exe "/K" D:\Tools\Anaconda\anaconda3\Scripts\activate.bat D:\Tools\Anaconda\anaconda3`
- **依赖安装**: 所有 Python 包必须通过 conda 环境安装（`pip install` 在激活的 conda 环境中运行）

## 核心功能

1. **图片扫描与排序**: 读取指定目录中的照片，按拍摄时间升序排列（老照片在前）
2. **人脸检测**: 使用 MediaPipe Face Mesh 检测 468 个面部关键点，支持戴眼镜的情况
3. **人脸对齐**: 基于眼睛中心和鼻尖的相似变换（缩放+旋转+平移），统一所有人脸大小和位置
4. **视频生成**: 输出 H.264 编码的 MP4 视频，帧率可配置（默认 10 fps）
5. **异常处理**: 无人脸照片自动跳过并记录日志

## 输入文件特征

- **照片位置**: 用户运行前将照片复制到项目目录（不被 git 跟踪）
- **参考目录**: `C:\Users\21632\Pictures\Camera Roll` 和 `D:\Me\Camera Roll`
- **文件名格式**:
  - `IMG_YYYYMMDD_HHMMSS.jpg`（手机摄像头）
  - `WIN_YYYYMMDD_HH_MM_SS_Pro.jpg`（Windows 摄像头应用）
- **照片尺寸**: 多为 1280x720
- **其他文件**: MP4 视频和 ini 文件等自动忽略

## 技术栈

| 库 | 用途 |
|---|---|
| `mediapipe` | 人脸检测与 468 点面部关键点 |
| `opencv-python` | 图像读取、相似变换计算、仿射变换 |
| `imageio[ffmpeg]` | 视频编码写入（H.264 MP4）|
| `Pillow` | EXIF 元数据读取 |
| `numpy` | 数组/矩阵运算 |
| `tqdm` | 进度条 |

## 对齐策略

- **变换类型**: 相似变换（4 自由度：缩放+旋转+平移），禁止剪切和宽高比扭曲
- **锚点**: 左眼中心、右眼中心、鼻尖
- **标准模板**: 眼间距占画面宽度 30%，人脸位于中上部
- **填充**: 变换后空缺区域用黑色填充
- **多脸处理**: 选择面积最大的人脸

## 使用方式

```bash
python -m selfie_timelapse <input_dir> [options]
```

### 参数

- `input_dir`: 包含自拍照的目录
- `-o, --output PATH`: 输出视频路径（默认: `./timelapse.mp4`）
- `--fps INT`: 每秒帧数（默认: 10）
- `--width INT`: 输出宽度（默认: 输入图片中最常见的宽度）
- `--height INT`: 输出高度（默认: 输入图片中最常见的高度）
- `--min-face-size INT`: 最小可接受人脸边界框宽度，像素（默认: 100）
- `--debug-dir PATH`: 保存对齐后的 PNG 帧到该目录（调试用）
- `--log-level`: 日志级别（默认: INFO）

## GitHub

- **仓库**: https://github.com/zheyi420/selfie-timelapse
- **注意**: 照片文件不应提交到 git，需在 `.gitignore` 中配置
