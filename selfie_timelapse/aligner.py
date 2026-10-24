"""Face alignment using explicit similarity transform."""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from .detector import FaceLandmarks

logger = logging.getLogger(__name__)


def similarity_from_eyes(
    src_left: Tuple[float, float],
    src_right: Tuple[float, float],
    dst_left: Tuple[float, float],
    dst_right: Tuple[float, float],
) -> Optional[np.ndarray]:
    """Build a similarity transform that maps one eye pair onto another.

    The matrix is scale, rotation, and translation only. Rotation comes from
    the angle between the two eye lines. The nose is not used.
    """
    slx, sly = src_left
    srx, sry = src_right
    dlx, dly = dst_left
    drx, dry = dst_right

    src_dist = float(np.hypot(srx - slx, sry - sly))
    dst_dist = float(np.hypot(drx - dlx, dry - dly))
    if src_dist < 1e-6 or dst_dist < 1e-6:
        logger.warning("Eye distance is effectively zero")
        return None

    scale = dst_dist / src_dist
    rho = float(np.arctan2(dry - dly, drx - dlx) - np.arctan2(sry - sly, srx - slx))
    cos_r = float(np.cos(rho))
    sin_r = float(np.sin(rho))
    a = scale * cos_r
    b = scale * sin_r

    scx = (slx + srx) / 2.0
    scy = (sly + sry) / 2.0
    dcx = (dlx + drx) / 2.0
    dcy = (dly + dry) / 2.0

    return np.array(
        [
            [a, -b, dcx - a * scx + b * scy],
            [b, a, dcy - b * scx - a * scy],
        ],
        dtype=np.float32,
    )


def warp_image(
    image: np.ndarray,
    transform_matrix: np.ndarray,
    output_size: Tuple[int, int],
) -> np.ndarray:
    """Apply affine transform to image with black border fill.

    Args:
        image: Input image (BGR)
        transform_matrix: 2x3 affine matrix
        output_size: (width, height) of output canvas

    Returns:
        Warped image with black fill for out-of-bounds areas
    """
    return cv2.warpAffine(
        image,
        transform_matrix,
        output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )


class Aligner:
    """Aligns faces to a canonical template using explicit similarity transform."""

    def __init__(self, output_width: int, output_height: int):
        self.output_width = output_width
        self.output_height = output_height
        logger.debug(
            "Aligner initialized with output size %dx%d", output_width, output_height
        )

    @staticmethod
    def compute_eye_ratio(landmarks: FaceLandmarks, image_width: int) -> float:
        """Compute eye-distance to image-width ratio.

        Args:
            landmarks: Detected face landmarks (pixel coordinates)
            image_width: Width of the source image in pixels

        Returns:
            Ratio of eye distance to image width
        """
        lx, ly = landmarks.left_eye
        rx, ry = landmarks.right_eye
        eye_dist = float(np.hypot(rx - lx, ry - ly))
        return eye_dist / image_width

    def align(
        self, image: np.ndarray, landmarks: FaceLandmarks, target_eye_dist: float
    ) -> Optional[np.ndarray]:
        """Align image so face matches canonical template.

        Uses an explicit similarity transform constructed from the detected eye
        positions. This guarantees that the eyes are perfectly horizontal and
        spaced exactly at target_eye_dist.

        Args:
            image: Input BGR image
            landmarks: FaceLandmarks with left_eye, right_eye (pixel coordinates)
            target_eye_dist: Desired eye distance in the output frame

        Returns:
            Aligned image or None if transform fails
        """
        # Target eye center: centered horizontally, upper portion vertically.
        # Destination eyes stay horizontal and target_eye_dist apart.
        tx = 0.50 * self.output_width
        ty = 0.40 * self.output_height
        half = target_eye_dist / 2.0
        matrix = similarity_from_eyes(
            landmarks.left_eye,
            landmarks.right_eye,
            (tx - half, ty),
            (tx + half, ty),
        )
        if matrix is None:
            return None

        return warp_image(image, matrix, (self.output_width, self.output_height))
