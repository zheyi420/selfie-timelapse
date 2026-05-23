"""Pipeline orchestration: sort -> detect -> align -> encode."""

import logging
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
from tqdm import tqdm

from .aligner import Aligner
from .detector import FaceDetector, FaceLandmarks
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

    Uses a two-pass approach:
    1. First pass: detect all faces and collect eye-distance ratios
    2. Compute median ratio to determine unified target eye distance
    3. Second pass: align all frames with the unified scale and encode video

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

    # Initialize detector
    detector = FaceDetector(min_face_size=config.min_face_size)

    stats = {"total": len(sorted_images), "processed": 0, "skipped": 0}

    # ========================================================================
    # Pass 1: Detect all faces and collect eye-distance ratios
    # ========================================================================
    logger.info("Pass 1: Detecting faces and collecting eye ratios...")

    detections: List[Tuple[Path, FaceLandmarks, int, int]] = []
    ratios: List[float] = []

    for path in tqdm(sorted_images, desc="Detecting"):
        try:
            image = cv2.imread(str(path))
            if image is None:
                logger.warning("Failed to load image: %s", path.name)
                stats["skipped"] += 1
                continue

            h, w = image.shape[:2]

            # Detect face
            landmarks = detector.detect(image)
            if landmarks is None:
                logger.warning("No face detected in %s, skipping", path.name)
                stats["skipped"] += 1
                continue

            # Compute eye ratio for this image
            ratio = Aligner.compute_eye_ratio(landmarks, w)
            ratios.append(ratio)

            # Cache detection result (lightweight, avoids re-running MediaPipe)
            detections.append((path, landmarks, w, h))

        except Exception as e:
            logger.error("Error detecting %s: %s", path.name, e)
            stats["skipped"] += 1

    if not detections:
        logger.error("No faces detected in any image")
        detector.close()
        return {"total": stats["total"], "processed": 0, "skipped": stats["skipped"], "output_path": None}

    # Compute unified target eye distance from median ratio
    median_ratio = float(statistics.median(ratios))
    target_eye_dist = median_ratio * output_width

    logger.info(
        "Pass 1 complete: %d faces detected, median eye ratio=%.4f, target_eye_dist=%.1f px",
        len(detections),
        median_ratio,
        target_eye_dist,
    )

    # ========================================================================
    # Pass 2: Align and encode
    # ========================================================================
    logger.info("Pass 2: Aligning frames and writing video...")

    aligner = Aligner(output_width, output_height)

    try:
        with VideoWriter(config.output_path, config.fps) as writer:
            for idx, (path, landmarks, w, h) in enumerate(
                tqdm(detections, desc="Aligning")
            ):
                try:
                    # Reload image from disk (memory-efficient)
                    image = cv2.imread(str(path))
                    if image is None:
                        logger.warning("Failed to reload image: %s", path.name)
                        stats["skipped"] += 1
                        continue

                    # Align face with unified scale
                    aligned = aligner.align(image, landmarks, target_eye_dist)
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
