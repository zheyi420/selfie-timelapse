"""Face alignment using similarity transform."""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CanonicalTemplate:
    """Target anchor positions for face alignment."""

    left_eye: Tuple[float, float]
    right_eye: Tuple[float, float]
    nose_tip: Tuple[float, float]

    @classmethod
    def from_size(cls, width: int, height: int) -> "CanonicalTemplate":
        """Create template for given output dimensions.

        Eye spacing is ~30% of frame width, face centered vertically.
        """
        return cls(
            left_eye=(0.35 * width, 0.40 * height),
            right_eye=(0.65 * width, 0.40 * height),
            nose_tip=(0.50 * width, 0.58 * height),
        )


def compute_similarity_transform(
    src_points: np.ndarray, dst_points: np.ndarray
) -> Optional[np.ndarray]:
    """Compute similarity transform (scale + rotation + translation) mapping src to dst.

    Args:
        src_points: Nx2 array of source points
        dst_points: Nx2 array of destination points

    Returns:
        2x3 affine transformation matrix, or None if computation fails
    """
    if src_points.shape != dst_points.shape or src_points.shape[0] < 2:
        return None

    matrix, inliers = cv2.estimateAffinePartial2D(
        src_points.astype(np.float32),
        dst_points.astype(np.float32),
        method=cv2.LMEDS,
    )

    if matrix is None or inliers is None:
        return None

    # Verify it's a valid similarity transform (no shear)
    # For similarity: matrix[0,0] == matrix[1,1] and matrix[0,1] == -matrix[1,0]
    # Allow small numerical errors
    a, b = matrix[0, 0], matrix[0, 1]
    c, d = matrix[1, 0], matrix[1, 1]

    if abs(a - d) > 0.1 or abs(b + c) > 0.1:
        logger.warning("Transform is not a valid similarity transform")
        return None

    return matrix


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
    """Aligns faces to a canonical template."""

    def __init__(self, output_width: int, output_height: int):
        self.output_size = (output_width, output_height)
        self.template = CanonicalTemplate.from_size(output_width, output_height)
        self.dst_points = np.array(
            [self.template.left_eye, self.template.right_eye, self.template.nose_tip],
            dtype=np.float32,
        )
        logger.debug(
            "Aligner initialized with output size %dx%d", output_width, output_height
        )

    def align(self, image: np.ndarray, landmarks) -> Optional[np.ndarray]:
        """Align image so face matches canonical template.

        Args:
            image: Input BGR image
            landmarks: FaceLandmarks object with left_eye, right_eye, nose_tip

        Returns:
            Aligned image or None if transform fails
        """
        src_points = np.array(
            [landmarks.left_eye, landmarks.right_eye, landmarks.nose_tip],
            dtype=np.float32,
        )

        matrix = compute_similarity_transform(src_points, self.dst_points)
        if matrix is None:
            return None

        return warp_image(image, matrix, self.output_size)
