"""Image discovery, date extraction, and sorting."""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Filename patterns
IMG_PATTERN = re.compile(r"IMG_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})")
WIN_PATTERN = re.compile(r"WIN_(\d{4})(\d{2})(\d{2})_(\d{2})_(\d{2})_(\d{2})_Pro")


def discover_images(directory: Path) -> List[Path]:
    """Find all image files in directory, skipping non-images."""
    images = []
    if not directory.is_dir():
        logger.error("Input path is not a directory: %s", directory)
        return images

    for path in directory.iterdir():
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(path)

    logger.info("Discovered %d image files in %s", len(images), directory)
    return images


def _extract_exif_datetime(path: Path) -> Optional[datetime]:
    """Try to get DateTimeOriginal or DateTime from EXIF."""
    try:
        with Image.open(path) as img:
            exif = img._getexif()
            if not exif:
                return None

            # Map tag IDs to names
            exif_data = {TAGS.get(tag_id, tag_id): value for tag_id, value in exif.items()}

            for tag in ("DateTimeOriginal", "DateTime", "DateTimeDigitized"):
                if tag in exif_data:
                    value = exif_data[tag]
                    # EXIF datetime format: "2023:10:15 14:30:00"
                    try:
                        return datetime.strptime(str(value), "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        continue
    except Exception as e:
        logger.debug("EXIF read failed for %s: %s", path.name, e)

    return None


def _extract_filename_datetime(path: Path) -> Optional[datetime]:
    """Parse datetime from filename patterns."""
    name = path.stem

    # Try IMG_YYYYMMDD_HHMMSS pattern
    match = IMG_PATTERN.search(name)
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
        except ValueError:
            pass

    # Try WIN_YYYYMMDD_HH_MM_SS_Pro pattern
    match = WIN_PATTERN.search(name)
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
        except ValueError:
            pass

    return None


def extract_datetime(path: Path) -> datetime:
    """Extract capture datetime from image, falling back through multiple methods."""
    # Priority 1: EXIF DateTimeOriginal
    dt = _extract_exif_datetime(path)
    if dt:
        logger.debug("EXIF datetime for %s: %s", path.name, dt)
        return dt

    # Priority 2: Filename pattern
    dt = _extract_filename_datetime(path)
    if dt:
        logger.debug("Filename datetime for %s: %s", path.name, dt)
        return dt

    # Priority 3: File modification time
    mtime = os.path.getmtime(path)
    dt = datetime.fromtimestamp(mtime)
    logger.debug("Fallback mtime for %s: %s", path.name, dt)
    return dt


def sort_images_by_time(images: List[Path]) -> List[Path]:
    """Sort images by capture time (oldest first)."""
    timed_images: List[Tuple[datetime, Path]] = []

    for path in images:
        try:
            dt = extract_datetime(path)
            timed_images.append((dt, path))
        except Exception as e:
            logger.warning("Failed to extract datetime from %s: %s", path.name, e)
            # Put at the end with current time
            timed_images.append((datetime.now(), path))

    timed_images.sort(key=lambda x: x[0])
    return [path for _, path in timed_images]
