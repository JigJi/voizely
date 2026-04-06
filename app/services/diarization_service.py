"""Speaker diarization using pyannote-audio."""

import logging
import os

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import torch

# Patch torch.load for pyannote compatibility with PyTorch 2.6+
_original_torch_load = torch.load


def _safe_torch_load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _original_torch_load(*args, **kwargs)


torch.load = _safe_torch_load

logger = logging.getLogger(__name__)

_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        from pyannote.audio import Pipeline
        from app.config import settings

        logger.info("Loading pyannote speaker-diarization-3.1...")
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=settings.HF_TOKEN,
        )
        _pipeline.to(torch.device("cpu"))
        logger.info("Pyannote diarization model loaded")
    return _pipeline


def diarize(
    audio_path: str, num_speakers: int | None = None, max_speakers: int = 8
) -> list[dict]:
    """Run speaker diarization and return list of {start, end, label}."""
    pipeline = get_pipeline()
    try:
        params = {}
        if num_speakers:
            params["num_speakers"] = num_speakers
        else:
            params["max_speakers"] = max_speakers

        diarization = pipeline(audio_path, **params)

        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": turn.start,
                "end": turn.end,
                "label": speaker,
            })

        unique = set(s["label"] for s in segments)
        logger.info(
            "Diarization: %d segments, %d speakers", len(segments), len(unique)
        )
        return segments
    except Exception as e:
        logger.warning("Diarization failed: %s", e)
        return []


def assign_speakers(
    whisper_segments: list[dict],
    diar_segments: list[dict],
) -> list[dict]:
    """Map speaker labels to whisper segments by maximum overlap."""
    # Build clean label mapping
    label_map = {}
    for ds in diar_segments:
        raw = ds["label"]
        if raw not in label_map:
            label_map[raw] = f"Speaker {len(label_map) + 1}"
        ds["_label"] = label_map[raw]

    for ws in whisper_segments:
        best_speaker = None
        max_overlap = 0.0
        for ds in diar_segments:
            overlap_start = max(ws["start"], ds["start"])
            overlap_end = min(ws["end"], ds["end"])
            overlap = max(0.0, overlap_end - overlap_start)
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = ds["_label"]
        ws["speaker"] = best_speaker or "Unknown"
    return whisper_segments
