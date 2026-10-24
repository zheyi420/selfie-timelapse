"""Repository-local directory for downloaded models and library caches."""

import os
from pathlib import Path

_CACHE_DIRNAME = "cache"


def repo_root() -> Path:
    """Directory that contains this project's pyproject.toml."""
    here = Path(__file__).resolve().parent
    for candidate in (here, *here.parents):
        pyproject = candidate / "pyproject.toml"
        if not pyproject.is_file():
            continue
        text = pyproject.read_text(encoding="utf-8")
        if 'name = "selfie-timelapse"' in text:
            return candidate
    return here.parent


def cache_dir() -> Path:
    """Gitignored runtime cache at the repository root."""
    return repo_root() / _CACHE_DIRNAME


def models_dir() -> Path:
    """Downloaded model files."""
    path = cache_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepare_runtime_cache() -> None:
    """Keep matplotlib's config off the user home directory.

    MediaPipe depends on matplotlib, which otherwise creates ~/.matplotlib
    on import. This must run before that import.
    """
    mpl_dir = cache_dir() / "matplotlib"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))
