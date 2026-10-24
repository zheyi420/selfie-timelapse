"""Lock the protagonist from a small solo-photo sample, then pick that face."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .detector import FaceDetector, FaceLandmarks
from .embedder import COSINE_THRESHOLD, FaceEmbedder

logger = logging.getLogger(__name__)

SAMPLE_FIRST_ROUND = 24
SAMPLE_TARGET_SOLOS = 20
SAMPLE_MIN_SOLOS = 8
SAMPLE_BUDGET = 40
MIN_CLUSTER_SIZE = 3
AMBIGUOUS_FRACTION = 0.40

# path -> (faces, width, height) from the sampling pass
DetectionCache = Dict[Path, Tuple[List[FaceLandmarks], int, int]]


@dataclass
class IdentityLock:
    """Protagonist prototype and detections already computed while sampling."""

    prototype: Optional[np.ndarray]
    cache: DetectionCache


def even_indices(count: int, slots: int) -> List[int]:
    """Evenly spaced indexes across ``count`` items."""
    if count <= 0 or slots <= 0:
        return []
    if count <= slots:
        return list(range(count))
    if slots == 1:
        return [0]

    seen = set()
    ordered: List[int] = []
    for slot in range(slots):
        index = round(slot * (count - 1) / (slots - 1))
        if index not in seen:
            seen.add(index)
            ordered.append(index)
    return ordered


def largest_gap_midpoint(count: int, visited: set) -> Optional[int]:
    """Index in the middle of the widest unvisited span."""
    if count <= 0 or len(visited) >= count:
        return None

    points = [-1, *sorted(visited), count]
    best_gap = 0
    best_mid: Optional[int] = None
    for left, right in zip(points, points[1:]):
        gap = right - left - 1
        if gap <= best_gap:
            continue
        mid = (left + right) // 2
        if mid < 0 or mid >= count or mid in visited:
            candidates = list(range(left + 1, right))
            if not candidates:
                continue
            mid = candidates[len(candidates) // 2]
        best_gap = gap
        best_mid = mid
    return best_mid


def _cluster_prototype(
    embeddings: List[np.ndarray],
) -> Tuple[Optional[np.ndarray], int]:
    """Largest connected component at the cosine threshold, as a unit vector."""
    count = len(embeddings)
    if count == 0:
        return None, 0

    parent = list(range(count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left in range(count):
        for right in range(left + 1, count):
            if float(np.dot(embeddings[left], embeddings[right])) >= COSINE_THRESHOLD:
                union(left, right)

    groups: Dict[int, List[int]] = {}
    for index in range(count):
        groups.setdefault(find(index), []).append(index)

    ranked = sorted(groups.values(), key=len, reverse=True)
    largest = ranked[0]
    if len(largest) < MIN_CLUSTER_SIZE:
        return None, len(largest)

    if (
        len(ranked) > 1
        and len(largest) >= AMBIGUOUS_FRACTION * count
        and len(ranked[1]) >= AMBIGUOUS_FRACTION * count
    ):
        logger.warning(
            "Protagonist sample is ambiguous: largest cluster %d, next %d, sample %d; using the larger cluster",
            len(largest),
            len(ranked[1]),
            count,
        )

    prototype = np.mean([embeddings[index] for index in largest], axis=0)
    norm = float(np.linalg.norm(prototype))
    if norm < 1e-6:
        return None, len(largest)
    return (prototype / norm).astype(np.float32), len(largest)


def lock_protagonist(
    paths: List[Path], detector: FaceDetector, embedder: FaceEmbedder
) -> IdentityLock:
    """Embed a time-spread sample of solo photos and average the main cluster.

    Stops once 20 solo embeddings are kept. If the first evenly spaced round
    already has at least 8, it does not keep scanning. Otherwise it fills the
    widest gaps until 20 solos or 40 detections. Group photos are detected and
    cached, and do not vote.
    """
    count = len(paths)
    cache: DetectionCache = {}
    solos: List[np.ndarray] = []
    visited: set = set()

    def visit(index: int) -> None:
        if index in visited or index < 0 or index >= count:
            return
        visited.add(index)
        path = paths[index]
        try:
            image = cv2.imread(str(path))
            if image is None:
                logger.warning("Failed to load image: %s", path.name)
                return
            faces = detector.detect(image)
            height, width = image.shape[:2]
            cache[path] = (faces, width, height)
            if len(faces) == 1:
                embedding = embedder.embed(image, faces[0])
                if embedding is not None:
                    solos.append(embedding)
        except Exception as exc:
            logger.error("Error sampling %s: %s", path.name, exc)

    for index in even_indices(count, SAMPLE_FIRST_ROUND):
        if len(solos) >= SAMPLE_TARGET_SOLOS:
            break
        visit(index)

    if len(solos) < SAMPLE_MIN_SOLOS:
        while (
            len(solos) < SAMPLE_TARGET_SOLOS
            and len(visited) < SAMPLE_BUDGET
            and len(visited) < count
        ):
            midpoint = largest_gap_midpoint(count, visited)
            if midpoint is None:
                break
            visit(midpoint)

    logger.info(
        "Protagonist sample: detected %d photos, kept %d solo embeddings",
        len(visited),
        len(solos),
    )

    prototype, cluster_size = _cluster_prototype(solos)
    if prototype is None:
        logger.error(
            "Could not lock a protagonist from %d solo samples; falling back to the largest face",
            len(solos),
        )
    else:
        logger.info(
            "Protagonist prototype locked from %d of %d solo embeddings",
            cluster_size,
            len(solos),
        )
    return IdentityLock(prototype=prototype, cache=cache)


def largest_face(faces: List[FaceLandmarks]) -> FaceLandmarks:
    """Face with the largest bounding-box area."""
    return max(faces, key=lambda face: face.bbox[2] * face.bbox[3])


def select_face(
    faces: List[FaceLandmarks],
    image: Optional[np.ndarray],
    prototype: Optional[np.ndarray],
    embedder: FaceEmbedder,
    path: Path,
) -> Optional[FaceLandmarks]:
    """Pick the face to align.

    A single face is used as-is. With a prototype, a group photo keeps the
    face whose cosine similarity is highest and at least the SFace threshold.
    Without a prototype, the largest face is used.
    """
    if not faces:
        return None
    if prototype is None:
        return largest_face(faces)
    if len(faces) == 1:
        return faces[0]
    if image is None:
        logger.warning("No image available to match protagonist in %s, skipping", path.name)
        return None

    best: Optional[FaceLandmarks] = None
    best_score = -1.0
    for face in faces:
        embedding = embedder.embed(image, face)
        if embedding is None:
            continue
        score = float(np.dot(embedding, prototype))
        if score > best_score:
            best_score = score
            best = face

    if best is None or best_score < COSINE_THRESHOLD:
        if best is None:
            logger.warning("No protagonist embedding in %s, skipping", path.name)
        else:
            logger.warning(
                "No protagonist in %s (best cosine %.3f), skipping",
                path.name,
                best_score,
            )
        return None

    logger.info(
        "Selected protagonist in %s (cosine %.3f, %d faces)",
        path.name,
        best_score,
        len(faces),
    )
    return best
