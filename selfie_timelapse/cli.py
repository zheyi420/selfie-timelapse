"""Command-line interface."""

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .pipeline import PipelineConfig, run_pipeline

VIDEOS_DIR = Path("media") / "videos"
_STAMPED_NAME = re.compile(r"-\d{8}-\d{6}$")


def resolve_output_path(output: Optional[Path], now: Optional[datetime] = None) -> Path:
    """Place every video in media/videos and append a local timestamp to the name."""
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    stem = output.stem if output is not None and output.stem else "timelapse"
    if _STAMPED_NAME.search(stem) is None:
        stem = f"{stem}-{stamp}"
    return VIDEOS_DIR / f"{stem}.mp4"


def setup_logging(level: str):
    """Configure logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate face-aligned timelapse videos from selfie photos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing selfie photos",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output name (default: timelapse). Saved as media/videos/<name>-YYYYMMDD-HHMMSS.mp4",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=10,
        help="Frames per second (default: 10)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=None,
        help="Output video width (default: mode of input widths)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=None,
        help="Output video height (default: mode of input heights)",
    )
    parser.add_argument(
        "--min-face-size",
        type=int,
        default=100,
        help="Minimum face bounding box width in pixels (default: 100)",
    )
    parser.add_argument(
        "--debug-dir",
        type=Path,
        default=None,
        help="Save aligned frames as PNGs to this directory",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    args.output = resolve_output_path(args.output)
    setup_logging(args.log_level)

    # Validate input directory
    if not args.input_dir.exists():
        print(f"Error: Input directory does not exist: {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    if not args.input_dir.is_dir():
        print(f"Error: Input path is not a directory: {args.input_dir}", file=sys.stderr)
        sys.exit(1)

    # Create output directory if needed
    output_dir = args.output.parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig(
        input_dir=args.input_dir.resolve(),
        output_path=args.output.resolve(),
        fps=args.fps,
        width=args.width,
        height=args.height,
        min_face_size=args.min_face_size,
        debug_dir=args.debug_dir.resolve() if args.debug_dir else None,
    )

    stats = run_pipeline(config)

    if stats["processed"] == 0:
        print("Error: No frames were processed", file=sys.stderr)
        sys.exit(1)

    print(f"\nSuccess! Video saved to: {stats['output_path']}")
    print(f"  Total images: {stats['total']}")
    print(f"  Processed: {stats['processed']}")
    print(f"  Skipped: {stats['skipped']}")


if __name__ == "__main__":
    main()
