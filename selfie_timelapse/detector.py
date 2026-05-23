"""Face detection using MediaPipe Face Landmarker (Tasks API)."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import cv2
import mediapipe as mp
from mediapipe.tasks.python.vision import FaceLandmarker, RunningMode
from mediapipe.tasks.python.core.base_options import BaseOptions
import numpy as np

logger = logging.getLogger(__name__)

# MediaPipe landmark indices for anchor points (468-point model)
LEFT_EYE_INDICES = [33, 246, 161, 160, 159, 158, 157, 133]
RIGHT_EYE_INDICES = [362, 398, 384, 385, 386, 387, 388, 263]
NOSE_TIP_INDEX = 1


@dataclass
class FaceLandmarks:
    """Detected face landmarks and bounding box."""

    left_eye: Tuple[float, float]
    right_eye: Tuple[float, float]
    nose_tip: Tuple[float, float]
    bbox: Tuple[int, int, int, int]  # x, y, w, h


class FaceDetector:
    """MediaPipe Face Landmarker detector."""

    def __init__(self, min_detection_confidence: float = 0.5, min_face_size: int = 100):
        self.min_face_size = min_face_size

        # Download model if not present
        model_path = self._get_model_path()

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.IMAGE,
            num_faces=10,
            min_face_detection_confidence=min_detection_confidence,
            min_tracking_confidence=0.5,
        )
        self.landmarker = FaceLandmarker.create_from_options(options)
        logger.debug("FaceDetector initialized")

    @staticmethod
    def _get_model_path() -> str:
        """Get or download the face landmarker model."""
        # Try to use the model bundled with mediapipe
        import mediapipe as mp
        import os

        # Check if model file exists in mediapipe package
        package_dir = Path(mp.__file__).parent
        model_path = package_dir / "face_landmarker_v2_with_blendshapes.task"

        if model_path.exists():
            return str(model_path)

        # Alternative: try to find face_landmarker.task
        model_path = package_dir / "face_landmarker.task"
        if model_path.exists():
            return str(model_path)

        # Download model if not found
        logger.info("Downloading face landmarker model...")
        url = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
        import urllib.request

        download_path = Path.home() / ".mediapipe" / "face_landmarker.task"
        download_path.parent.mkdir(parents=True, exist_ok=True)

        if not download_path.exists():
            urllib.request.urlretrieve(url, download_path)
            logger.info("Model downloaded to %s", download_path)

        return str(download_path)

    def detect(self, image: np.ndarray) -> Optional[FaceLandmarks]:
        """Detect face in image and return landmarks.

        If multiple faces are detected, selects the largest one by bounding box area.
        Returns None if no suitable face is found.
        """
        if image is None or image.size == 0:
            return None

        # MediaPipe expects RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = image.shape[:2]

        # Create MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        # Detect landmarks
        results = self.landmarker.detect(mp_image)

        if not results.face_landmarks:
            return None

        best_landmarks = None
        best_area = 0

        for face_landmarks in results.face_landmarks:
            # Compute bounding box from all landmarks
            xs = [lm.x for lm in face_landmarks]
            ys = [lm.y for lm in face_landmarks]

            min_x = min(xs)
            max_x = max(xs)
            min_y = min(ys)
            max_y = max(ys)

            bbox_x = int(min_x * w)
            bbox_y = int(min_y * h)
            bbox_w = int((max_x - min_x) * w)
            bbox_h = int((max_y - min_y) * h)

            # Skip faces that are too small
            if bbox_w < self.min_face_size or bbox_h < self.min_face_size:
                continue

            area = bbox_w * bbox_h
            if area > best_area:
                best_area = area

                # Extract anchor points
                left_eye = self._compute_eye_center(face_landmarks, LEFT_EYE_INDICES, w, h)
                right_eye = self._compute_eye_center(face_landmarks, RIGHT_EYE_INDICES, w, h)
                nose_tip = self._get_landmark_point(face_landmarks, NOSE_TIP_INDEX, w, h)

                best_landmarks = FaceLandmarks(
                    left_eye=left_eye,
                    right_eye=right_eye,
                    nose_tip=nose_tip,
                    bbox=(bbox_x, bbox_y, bbox_w, bbox_h),
                )

        return best_landmarks

    @staticmethod
    def _compute_eye_center(
        landmarks: list, indices: list, img_w: int, img_h: int
    ) -> Tuple[float, float]:
        """Compute the mean position of eye contour landmarks."""
        points = [(landmarks[i].x * img_w, landmarks[i].y * img_h) for i in indices]
        avg_x = sum(p[0] for p in points) / len(points)
        avg_y = sum(p[1] for p in points) / len(points)
        return (avg_x, avg_y)

    @staticmethod
    def _get_landmark_point(
        landmarks: list, index: int, img_w: int, img_h: int
    ) -> Tuple[float, float]:
        """Get a single landmark point in pixel coordinates."""
        lm = landmarks[index]
        return (lm.x * img_w, lm.y * img_h)

    def close(self):
        """Release MediaPipe resources."""
        self.landmarker.close()
