"""Face alignment using explicit similarity transform."""

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from .detector import FaceLandmarks

logger = logging.getLogger(__name__)


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
        lx, ly = landmarks.left_eye
        rx, ry = landmarks.right_eye

        # Eye center in source image
        cx = (lx + rx) / 2.0
        cy = (ly + ry) / 2.0

        # Detected eye distance
        d = float(np.hypot(rx - lx, ry - ly))
        if d < 1e-6:
            logger.warning("Detected eye distance is effectively zero")
            return None

        # Scale factor to match target eye distance
        scale = target_eye_dist / d

        # Eye line angle (rotation needed to make eyes horizontal)
        theta = np.arctan2(ry - ly, rx - lx)

        # Target eye center position (centered horizontally, upper portion vertically)
        tx = 0.50 * self.output_width
        ty = 0.40 * self.output_height

        # Build explicit similarity transform matrix:
        # M = T_target * S * R(-theta) * T_center
        a = scale * np.cos(theta)
        b = scale * np.sin(theta)

        matrix = np.array(
            [
                [a, b, tx - a * cx - b * cy],
                [-b, a, ty + b * cx - a * cy],
            ],
            dtype=np.float32,
        )

        return warp_image(image, matrix, (self.output_width, self.output_height))
