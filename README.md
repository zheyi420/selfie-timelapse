# Selfie Timelapse

Generate face-aligned timelapse videos from your selfie photos.

## Features

- **Face Detection**: Uses MediaPipe Face Mesh to detect 468 facial landmarks, robust even with glasses
- **Face Alignment**: Scales, rotates, and translates each photo so your face is consistently positioned and sized
- **Time Ordering**: Automatically sorts photos by capture time (oldest first)
- **Configurable Output**: Adjustable FPS, resolution, and quality settings
- **Streaming Architecture**: Memory-efficient processing, handles thousands of photos

## Installation

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11. `uv sync` installs that Python if it is missing, and installs dependencies into `.venv` in this repository.

```bash
# Clone the repository
git clone https://github.com/zheyi420/selfie-timelapse.git
cd selfie-timelapse

# Create .venv and install dependencies
uv sync

# Run
uv run python -m selfie_timelapse <input_dir> --fps 10 -o test.mp4
```

## Usage

```bash
python -m selfie_timelapse <input_dir> [options]
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `input_dir` | Directory containing your selfie photos | (required) |
| `-o, --output` | Output video path | `./timelapse.mp4` |
| `--fps` | Frames per second | `10` |
| `--width` | Output video width | Mode of input widths |
| `--height` | Output video height | Mode of input heights |
| `--min-face-size` | Minimum face bounding box width (pixels) | `100` |
| `--debug-dir` | Save aligned frames as PNGs for debugging | (none) |
| `--log-level` | Logging level | `INFO` |

### Examples

```bash
# Basic usage
python -m selfie_timelapse ./my_selfies

# Custom FPS and output path
python -m selfie_timelapse ./my_selfies --fps 15 -o ./output/year2023.mp4

# Save debug frames to inspect alignment quality
python -m selfie_timelapse ./my_selfies --debug-dir ./debug_frames

# Force output resolution
python -m selfie_timelapse ./my_selfies --width 1280 --height 720
```

## Supported Photo Formats

- `.jpg`, `.jpeg`, `.png`
- Photos are sorted by: EXIF DateTimeOriginal > EXIF DateTime > filename timestamp > file modification time
- Supported filename patterns: `IMG_YYYYMMDD_HHMMSS.jpg`, `WIN_YYYYMMDD_HH_MM_SS_Pro.jpg`

## How It Works

1. **Scan & Sort**: Discovers all photos in the input directory and sorts them by capture time
2. **Detect Faces**: For each photo, detects facial landmarks using MediaPipe
3. **Align**: Computes a similarity transform (scale + rotate + translate) from the two eye centers so the eyes stay level and the same distance apart
4. **Render**: Warps each photo onto a consistent canvas and writes frames to an H.264 MP4 video
5. **Skip Bad Frames**: Photos without detectable faces are skipped with a warning logged

## License

MIT License - see [LICENSE](LICENSE) for details.

Coding agents: see [AGENTS.md](AGENTS.md).
