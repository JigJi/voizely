"""
Voiceprint Service: Speaker enrollment + identification using ECAPA-TDNN
"""
import json
import logging
import os
import subprocess

import numpy as np
import torch
import torchaudio

logger = logging.getLogger("voiceprint")

# Voiceprints now stored in DB (speaker_profiles table)

_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        from speechbrain.inference.speaker import EncoderClassifier
        logger.info("Loading ECAPA-TDNN model...")
        _classifier = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            run_opts={"device": "cuda" if torch.cuda.is_available() else "cpu"},
        )
        logger.info("ECAPA-TDNN loaded")
    return _classifier


def extract_embedding(audio_path, start_sec=None, end_sec=None):
    """Extract 192-dim speaker embedding from audio segment."""
    signal, sr = torchaudio.load(audio_path)

    # Crop if start/end specified
    if start_sec is not None and end_sec is not None:
        start_sample = int(start_sec * sr)
        end_sample = int(end_sec * sr)
        signal = signal[:, start_sample:end_sample]

    # Skip if too short (< 1 sec)
    if signal.shape[1] < sr:
        return None

    # Resample to 16kHz if needed
    if sr != 16000:
        signal = torchaudio.transforms.Resample(sr, 16000)(signal)

    # Mono
    if signal.shape[0] > 1:
        signal = signal.mean(dim=0, keepdim=True)

    classifier = _get_classifier()
    device = next(classifier.mods.parameters()).device
    embedding = classifier.encode_batch(signal.to(device))
    return embedding.squeeze().detach().cpu().numpy()


def create_voiceprint(audio_path, segments):
    """Create voiceprint from multiple segments of the same speaker.

    segments: list of (start_sec, end_sec) tuples
    Returns (voiceprint_vector, total_seconds) or (None, 0)
    """
    embeddings = []
    total_sec = 0

    for start, end in segments:
        duration = end - start
        if duration < 1.0:
            continue
        emb = extract_embedding(audio_path, start, end)
        if emb is not None:
            embeddings.append(emb)
            total_sec += duration

    if not embeddings:
        return None, 0

    # Remove outliers: segments with voice contamination
    if len(embeddings) >= 3:
        emb_array = np.array(embeddings)
        centroid = np.mean(emb_array, axis=0)
        centroid = centroid / np.linalg.norm(centroid)
        # Calculate cosine similarity to centroid
        similarities = np.array([
            np.dot(e, centroid) / (np.linalg.norm(e) * np.linalg.norm(centroid))
            for e in emb_array
        ])
        # Remove bottom 20% (outliers with mixed voices)
        threshold = np.percentile(similarities, 20)
        clean_mask = similarities >= threshold
        clean_embeddings = emb_array[clean_mask]
        removed = len(embeddings) - len(clean_embeddings)
        if removed > 0:
            logger.info("Removed %d/%d outlier segments (threshold=%.3f)", removed, len(embeddings), threshold)
        embeddings = list(clean_embeddings)

    if not embeddings:
        return None, 0

    # Average clean embeddings
    voiceprint = np.mean(embeddings, axis=0)
    voiceprint = voiceprint / np.linalg.norm(voiceprint)
    return voiceprint, total_sec


def _get_db():
    from app.database import SessionLocal
    return SessionLocal()


def _emb_to_bytes(emb):
    import struct
    return struct.pack(f'{len(emb)}f', *emb)


def _bytes_to_emb(data):
    import struct
    count = len(data) // 4
    return np.array(struct.unpack(f'{count}f', data))


def save_voiceprint(speaker_name, voiceprint, total_seconds):
    """Save voiceprint to DB (speaker_profiles table)."""
    from app.models.transcription import SpeakerProfile
    from datetime import datetime, timezone, timedelta

    db = _get_db()
    try:
        p = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == speaker_name).first()
        if p and p.embedding:
            old_emb = _bytes_to_emb(p.embedding)
            old_sec = p.total_seconds or 0
            total = old_sec + total_seconds
            updated = (old_emb * old_sec + voiceprint * total_seconds) / total
            updated = updated / np.linalg.norm(updated)
            p.embedding = _emb_to_bytes(updated)
            p.total_seconds = total
            p.num_sessions = (p.num_sessions or 0) + 1
            p.updated_at = datetime.now(timezone(timedelta(hours=7)))
        elif p:
            p.embedding = _emb_to_bytes(voiceprint)
            p.total_seconds = total_seconds
            p.num_sessions = 1
            p.updated_at = datetime.now(timezone(timedelta(hours=7)))
        else:
            p = SpeakerProfile(
                nickname=speaker_name,
                embedding=_emb_to_bytes(voiceprint),
                total_seconds=total_seconds,
                num_sessions=1,
            )
            db.add(p)
        db.commit()
        logger.info("Saved voiceprint: %s (%.0fs total)", speaker_name, p.total_seconds)
    finally:
        db.close()


def load_all_voiceprints():
    """Load all voiceprints from DB. Returns {nickname: np.array}."""
    from app.models.transcription import SpeakerProfile
    db = _get_db()
    try:
        profiles = db.query(SpeakerProfile).filter(SpeakerProfile.embedding.isnot(None)).all()
        return {p.nickname: _bytes_to_emb(p.embedding) for p in profiles}
    finally:
        db.close()


def list_voiceprints():
    """List all speaker profiles (legacy, used by old API)."""
    from app.models.transcription import SpeakerProfile
    db = _get_db()
    try:
        profiles = db.query(SpeakerProfile).order_by(SpeakerProfile.nickname).all()
        return [{
            "name": p.nickname,
            "full_name": p.full_name or "",
            "organization": p.organization or "",
            "department": p.department or "",
            "position": p.position or "",
            "total_seconds": p.total_seconds or 0,
            "num_sessions": p.num_sessions or 0,
            "updated_at": p.updated_at.isoformat() if p.updated_at else "",
        } for p in profiles]
    finally:
        db.close()


def update_profile(speaker_name, **fields):
    """Update profile fields (legacy, used by old API)."""
    from app.models.transcription import SpeakerProfile
    from datetime import datetime, timezone, timedelta
    db = _get_db()
    try:
        p = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == speaker_name).first()
        if not p:
            return False
        for key in ["full_name", "organization", "department", "position"]:
            if key in fields:
                setattr(p, key, fields[key])
        p.updated_at = datetime.now(timezone(timedelta(hours=7)))
        db.commit()
        return True
    finally:
        db.close()


def delete_voiceprint(speaker_name):
    """Delete a speaker profile (legacy)."""
    from app.models.transcription import SpeakerProfile
    db = _get_db()
    try:
        p = db.query(SpeakerProfile).filter(SpeakerProfile.nickname == speaker_name).first()
        if not p:
            return False
        db.delete(p)
        db.commit()
        return True
    finally:
        db.close()


def get_speaker_suggestions(audio_path, deepgram_segments):
    """Get voiceprint suggestions with scores for all speakers.
    Returns list of {speaker, suggested_name, score}."""
    voiceprint_db = load_all_voiceprints()
    if not voiceprint_db:
        return []

    wav_path = audio_path + ".vpsug.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ar", "16000", "-ac", "1", wav_path,
    ], capture_output=True)

    try:
        speaker_segs = {}
        for seg in deepgram_segments:
            if seg.get("is_gap"):
                continue
            spk = seg["speaker"]
            if spk not in speaker_segs:
                speaker_segs[spk] = []
            speaker_segs[spk].append((seg["start"], seg["end"]))

        suggestions = []
        for spk_id, segments in speaker_segs.items():
            vp, total_sec = create_voiceprint(wav_path, segments)
            if vp is None:
                continue
            scores = []
            for name, stored_vp in voiceprint_db.items():
                score = float(np.dot(vp, stored_vp) / (np.linalg.norm(vp) * np.linalg.norm(stored_vp)))
                scores.append((name, score))
            scores.sort(key=lambda x: -x[1])
            if scores and scores[0][1] >= 0.50:
                suggestions.append({
                    "speaker": f"Speaker {spk_id + 1}",
                    "suggested_name": scores[0][0],
                    "score": round(scores[0][1], 3),
                })
                logger.info("VP suggest: Speaker %d → %s (%.3f)", spk_id, scores[0][0], scores[0][1])

        return suggestions
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def identify_speakers(audio_path, deepgram_segments, threshold=0.85):
    """Match Deepgram speakers against stored voiceprints.

    Only matches when best score >= threshold (0.85)

    deepgram_segments: list of {"start", "end", "speaker", "is_gap"}
    Returns: {speaker_index: matched_name} mapping
    """
    voiceprint_db = load_all_voiceprints()
    if not voiceprint_db:
        return {}

    # Convert audio to WAV for torchaudio
    wav_path = audio_path + ".vp.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ar", "16000", "-ac", "1", wav_path,
    ], capture_output=True)

    try:
        # Group segments by speaker
        speaker_segs = {}
        for seg in deepgram_segments:
            if seg.get("is_gap"):
                continue
            spk = seg["speaker"]
            if spk not in speaker_segs:
                speaker_segs[spk] = []
            speaker_segs[spk].append((seg["start"], seg["end"]))

        mapping = {}
        used_names = set()

        for spk_id, segments in speaker_segs.items():
            # Create voiceprint for this speaker
            vp, total_sec = create_voiceprint(wav_path, segments)
            if vp is None:
                continue

            # Score against all voiceprints
            scores = []
            for name, stored_vp in voiceprint_db.items():
                if name in used_names:
                    continue
                score = float(np.dot(vp, stored_vp) / (np.linalg.norm(vp) * np.linalg.norm(stored_vp)))
                scores.append((name, score))
            scores.sort(key=lambda x: -x[1])

            if not scores:
                continue

            best_name, best_score = scores[0]
            second_score = scores[1][1] if len(scores) > 1 else 0

            if best_score >= threshold:
                mapping[spk_id] = best_name
                used_names.add(best_name)
                logger.info("Speaker %d matched: %s (score=%.3f, margin=%.3f)", spk_id, best_name, best_score, best_score - second_score)
            else:
                logger.info("Speaker %d: no match (best=%.3f)", spk_id, best_score)

        return mapping

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def enroll_from_transcription(audio_path, transcription_id, speaker_label, speaker_name, db_session):
    """Enroll a speaker from a completed transcription.

    Called when user renames a speaker.
    """
    from app.models.transcription import TranscriptionSegment

    # Get segments for this speaker
    segments = db_session.query(TranscriptionSegment).filter(
        TranscriptionSegment.transcription_id == transcription_id,
        TranscriptionSegment.speaker == speaker_label,
    ).all()

    if not segments:
        # Try with new name (already renamed)
        segments = db_session.query(TranscriptionSegment).filter(
            TranscriptionSegment.transcription_id == transcription_id,
            TranscriptionSegment.speaker == speaker_name,
        ).all()

    if not segments:
        logger.warning("No segments found for enrollment: %s", speaker_name)
        return False

    seg_times = [(s.start_time, s.end_time) for s in segments]
    total_speech = sum(e - s for s, e in seg_times)

    if total_speech < 5.0:
        logger.warning("Not enough speech for enrollment: %.1fs", total_speech)
        return False

    # Convert audio to WAV
    wav_path = audio_path + ".enroll.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", audio_path,
        "-ar", "16000", "-ac", "1", wav_path,
    ], capture_output=True)

    try:
        vp, total_sec = create_voiceprint(wav_path, seg_times)
        if vp is None:
            return False

        save_voiceprint(speaker_name, vp, total_sec)
        return True
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
