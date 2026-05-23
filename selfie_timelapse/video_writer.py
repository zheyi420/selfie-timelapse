"""Video writer using imageio-ffmpeg."""

import logging
from pathlib import Path

import imageio
import numpy as np

logger = logging.getLogger(__name__)


class VideoWriter:
    """Streaming video writer for frame-by-frame encoding."""

    def __init__(
        self,
        output_path: Path,
        fps: int,
        quality: int = 8,
    ):
        self.output_path = output_path
        self.fps = fps
        self.quality = quality
        self.writer = None
        self.frame_count = 0

    def __enter__(self):
        """Open video writer."""
        logger.info("Opening video writer: %s @ %d fps", self.output_path, self.fps)
        # Use imageio-ffmpeg for reliable H.264 MP4 encoding
        self.writer = imageio.get_writer(
            self.output_path,
            fps=self.fps,
            codec="libx264",
            quality=self.quality,
            pixelformat="yuv420p",
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Close video writer."""
        self.close()
        return False

    def write_frame(self, frame: np.ndarray):
        """Write a single frame to the video.

        Args:
            frame: BGR image as numpy array
        """
        if self.writer is None:
            raise RuntimeError("Video writer not opened")

        # imageio expects RGB
        rgb_frame = frame[:, :, ::-1]
        self.writer.append_data(rgb_frame)
        self.frame_count += 1

    def close(self):
        """Close the video writer and finalize the file."""
        if self.writer is not None:
            self.writer.close()
            self.writer = None
            logger.info(
                "Video saved: %s (%d frames)", self.output_path, self.frame_count
            )
