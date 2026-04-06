import logging
import os
from threading import Lock

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from faster_whisper import WhisperModel

from app.config import settings

logger = logging.getLogger(__name__)

_models: dict[str, WhisperModel] = {}
_lock = Lock()


def get_whisper_model(model_size: str | None = None) -> WhisperModel:
    model_size = model_size or settings.WHISPER_MODEL_SIZE

    if model_size not in _models:
        with _lock:
            if model_size not in _models:
                logger.info(
                    "Loading Whisper model: %s on %s (%s)",
                    model_size,
                    settings.WHISPER_DEVICE,
                    settings.WHISPER_COMPUTE_TYPE,
                )
                _models[model_size] = WhisperModel(
                    model_size,
                    device=settings.WHISPER_DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE,
                    download_root=settings.WHISPER_MODEL_DIR,
                )
                logger.info("Whisper model loaded: %s", model_size)
    return _models[model_size]
