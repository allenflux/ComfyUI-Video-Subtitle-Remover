import os
from pathlib import Path


MODELS_DIR_ENV = "VSR_MODELS_DIR"
DEFAULT_MODELS_DIR = Path("/app/ComfyUI/models/video-subtitle-remover-models")


def models_dir():
    """Return the configured root of the separately installed model repository."""
    configured = os.environ.get(MODELS_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    return DEFAULT_MODELS_DIR


def model_path(*parts):
    return models_dir().joinpath(*parts)


def require_model_file(path, description):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {description}: {path}. "
            f"Set {MODELS_DIR_ENV} to the model repository directory "
            f"(default: {DEFAULT_MODELS_DIR})."
        )
    return path
