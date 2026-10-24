"""Face identity embeddings using the OpenCV Zoo SFace ONNX model."""

import logging
import urllib.request
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort

from .aligner import similarity_from_eyes, warp_image
from .detector import FaceLandmarks
from .runtime_cache import models_dir

logger = logging.getLogger(__name__)

# OpenCV Zoo SFace. Cosine threshold published with that model.
SFACE_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_recognition_sface/face_recognition_sface_2021dec.onnx"
)
SFACE_FILENAME = "face_recognition_sface_2021dec.onnx"
COSINE_THRESHOLD = 0.363

INPUT_SIZE = 112
# Canonical 112x112 eye positions. Both eyes share a y so the crop stays horizontal.
TEMPLATE_LEFT_EYE = (38.2946, 51.6963)
TEMPLATE_RIGHT_EYE = (73.5318, 51.6963)
_MIN_MODEL_BYTES = 1_000_000


class FaceEmbedder:
    """Embeds an aligned face crop into an L2-normalized identity vector."""

    def __init__(self):
        model_path = self._get_model_path()
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.session = ort.InferenceSession(
            model_path,
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self._channels_last = self._input_is_channels_last()
        logger.debug("FaceEmbedder initialized")

    @staticmethod
    def _get_model_path() -> str:
        """Return a local SFace model, downloading it once into the repo cache."""
        dest = models_dir() / SFACE_FILENAME
        if dest.exists() and dest.stat().st_size >= _MIN_MODEL_BYTES:
            return str(dest)

        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            dest.unlink()

        logger.info("Downloading face recognition model...")
        request = urllib.request.Request(
            SFACE_URL, headers={"User-Agent": "selfie-timelapse"}
        )
        with urllib.request.urlopen(request) as response, dest.open("wb") as handle:
            handle.write(response.read())

        if dest.stat().st_size < _MIN_MODEL_BYTES:
            dest.unlink(missing_ok=True)
            raise RuntimeError("Downloaded face recognition model is incomplete")

        logger.info("Model downloaded to %s", dest)
        return str(dest)

    def _input_is_channels_last(self) -> bool:
        shape = self.session.get_inputs()[0].shape
        return len(shape) == 4 and shape[-1] == 3

    def embed(
        self, image: np.ndarray, landmarks: FaceLandmarks
    ) -> Optional[np.ndarray]:
        """Return an L2-normalized embedding, or None when the crop cannot be made."""
        matrix = similarity_from_eyes(
            landmarks.left_eye,
            landmarks.right_eye,
            TEMPLATE_LEFT_EYE,
            TEMPLATE_RIGHT_EYE,
        )
        if matrix is None:
            return None

        aligned = warp_image(image, matrix, (INPUT_SIZE, INPUT_SIZE))
        rgb = cv2.cvtColor(aligned, cv2.COLOR_BGR2RGB)
        blob = self._to_blob(rgb)
        output = self.session.run(None, {self.input_name: blob})[0]
        vector = np.asarray(output, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if norm < 1e-6:
            return None
        return vector / norm

    def _to_blob(self, rgb: np.ndarray) -> np.ndarray:
        """Match SFace's expected layout: 112x112 RGB floats in 0..255."""
        tensor = rgb.astype(np.float32)
        if self._channels_last:
            return tensor[None, ...]
        return np.transpose(tensor, (2, 0, 1))[None, ...]

    def close(self):
        """Release the ONNX session."""
        self.session = None
