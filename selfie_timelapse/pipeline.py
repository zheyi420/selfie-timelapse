"""Pipeline orchestration: sort -> detect -> align -> encode."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from tqdm import tqdm

from .aligner import Aligner
from .detector import FaceDetector
from .sorter import discover_images, sort_images_by_time
from .video_writer import VideoWriter

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the processing pipeline."""

    input_dir: Path
    output_path: Path
    fps: int = 10
    width: Optional[int] = None
    height: Optional[int] = None
    min_face_size: int = 100
    debug_dir: Optional[Path] = None


def _compute_output_size(images: list, config: PipelineConfig) -> tuple:
    """Determine output video dimensions."""
    if config.width is not None and config.height is not None:
        return (config.width, config.height)

    # Collect dimensions from all images
    widths = []
    heights = []
    for path in images:
        try:
            # Fast size check without loading full image
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is not None:
                h, w = img.shape[:2]
                widths.append(w)
                heights.append(h)
        except Exception:
            pass

    if not widths:
        logger.warning("Could not determine image sizes, using default 1280x720")
        return (1280, 720)

    # Use mode (most common) for width and height
    from statistics import mode

    try:
        target_w = mode(widths)
    except Exception:
        target_w = int(sum(widths) / len(widths))

    try:
        target_h = mode(heights)
    except Exception:
        target_h = int(sum(heights) / len(heights))

    # Allow user override of just one dimension
    if config.width is not None:
        target_w = config.width
    if config.height is not None:
        target_h = config.height

    logger.info("Output size: %dx%d", target_w, target_h)
    return (target_w, target_h)


def run_pipeline(config: PipelineConfig) -> dict:
    """Run the full processing pipeline.

    Returns:
        dict with statistics: total, processed, skipped, output_path
    """
    # Discover and sort images
    images = discover_images(config.input_dir)
    if not images:
        logger.error("No images found in %s", config.input_dir)
        return {"total": 0, "processed": 0, "skipped": 0, "output_path": None}

    sorted_images = sort_images_by_time(images)
    logger.info("Processing %d images", len(sorted_images))

    # Determine output size
    output_width, output_height = _compute_output_size(sorted_images, config)

    # Create debug directory if needed
    if config.debug_dir:
        config.debug_dir.mkdir(parents=True, exist_ok=True)

    # Initialize components
    detector = FaceDetector(min_face_size=config.min_face_size)
    aligner = Aligner(output_width, output_height)

    stats = {"total": len(sorted_images), "processed": 0, "skipped": 0}

    try:
        with VideoWriter(config.output_path, config.fps) as writer:
            for idx, path in enumerate(tqdm(sorted_images, desc="Processing")):
                try:
                    # Load image
                    image = cv2.imread(str(path))
                    if image is None:
                        logger.warning("Failed to load image: %s", path.name)
                        stats["skipped"] += 1
                        continue

                    # Detect face
                    landmarks = detector.detect(image)
                    if landmarks is None:
                        logger.warning("No face detected in %s, skipping", path.name)
                        stats["skipped"] += 1
                        continue

                    # Align face
                    aligned = aligner.align(image, landmarks)
                    if aligned is None:
                        logger.warning("Failed to align %s, skipping", path.name)
                        stats["skipped"] += 1
                        continue

                    # Write frame
                    writer.write_frame(aligned)
                    stats["processed"] += 1

                    # Save debug frame if requested
                    if config.debug_dir:
                        debug_path = config.debug_dir / f"frame_{idx:04d}.png"
                        cv2.imwrite(str(debug_path), aligned)

                except Exception as e:
                    logger.error("Error processing %s: %s", path.name, e)
                    stats["skipped"] += 1

    finally:
        detector.close()

    logger.info(
        "Pipeline complete: %d processed, %d skipped, %d total",
        stats["processed"],
        stats["skipped"],
        stats["total"],
    )
    logger.info("Output video: %s", config.output_path)

    stats["output_path"] = config.output_path
    return stats
