"""Complete reset — wipes all user data, bringing the app to a
"first-time-user" state for every user.

Kept:
  - users (so login still works)
  - correction_dict (useful vocab accumulated over time)

Wiped:
  - transcription_segments, transcriptions
  - audio_files (DB rows + files on disk)
  - meeting_recordings
  - user_calendar_cache
  - speaker_profiles (ALL rows — both manual and ad)
    The daily AD sync at 04:00 will repopulate ~214 humans on its next
    run; the new ad_service filter (frontend_auth commit 5fdc1d2) drops
    the ~15 non-human accounts (krbtgt, guest, testuser, ...) so they
    won't come back.
  - transcription_groups (every row, incl. is_default=True — a fresh
    install has none)

Usage:
  cd C:\\deploy\\voizely
  venv\\Scripts\\python.exe scripts\\wipe_all.py           # dry-run, shows counts
  venv\\Scripts\\python.exe scripts\\wipe_all.py --confirm  # actually wipes
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models.audio import AudioFile
from app.models.transcription import (
    Transcription,
    TranscriptionSegment,
    SpeakerProfile,
    TranscriptionGroup,
)
from app.models.meeting import MeetingRecording, UserCalendarCache
from app.models.user import User


def main():
    parser = argparse.ArgumentParser(description="Wipe all user-generated data.")
    parser.add_argument("--confirm", action="store_true",
                        help="actually perform the wipe (default is dry-run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        counts = {
            "transcription_segments": db.query(TranscriptionSegment).count(),
            "transcriptions": db.query(Transcription).count(),
            "meeting_recordings": db.query(MeetingRecording).count(),
            "audio_files": db.query(AudioFile).count(),
            "user_calendar_cache": db.query(UserCalendarCache).count(),
            "speaker_profiles (manual)":
                db.query(SpeakerProfile).filter(SpeakerProfile.source == "manual").count(),
            "speaker_profiles (ad — will be repopulated by daily sync)":
                db.query(SpeakerProfile).filter(SpeakerProfile.source == "ad").count(),
            "transcription_groups": db.query(TranscriptionGroup).count(),
        }

        print("=== Wipe plan ===")
        for k, v in counts.items():
            print(f"  DELETE {k}: {v}")
        kept_users = db.query(User).count()
        print(f"  KEEP users: {kept_users}")

        if not args.confirm:
            print("\nDry run. Re-run with --confirm to actually wipe.")
            return

        # 1. Delete audio files on disk
        deleted_files = 0
        missing_files = 0
        for a in db.query(AudioFile).all():
            if not a.file_path:
                continue
            if os.path.exists(a.file_path):
                try:
                    os.remove(a.file_path)
                    deleted_files += 1
                except OSError as e:
                    print(f"WARN: couldn't delete {a.file_path}: {e}")
            else:
                missing_files += 1
        print(f"\nDisk: deleted {deleted_files} files, {missing_files} were already gone")

        # 2. DB wipe, FK-safe order
        db.query(TranscriptionSegment).delete(synchronize_session=False)
        db.query(MeetingRecording).delete(synchronize_session=False)
        db.query(Transcription).delete(synchronize_session=False)
        db.query(AudioFile).delete(synchronize_session=False)
        db.query(UserCalendarCache).delete(synchronize_session=False)
        # Wipe ALL speaker profiles — daily AD sync will re-populate humans
        db.query(SpeakerProfile).delete(synchronize_session=False)
        db.query(TranscriptionGroup).delete(synchronize_session=False)
        db.commit()
        print("DB: wipe committed")

        # 3. Final summary
        print("\n=== After wipe ===")
        print(f"  transcriptions: {db.query(Transcription).count()}")
        print(f"  audio_files: {db.query(AudioFile).count()}")
        print(f"  meeting_recordings: {db.query(MeetingRecording).count()}")
        print(f"  speaker_profiles (total): {db.query(SpeakerProfile).count()}")
        print(f"    of which source='ad': {db.query(SpeakerProfile).filter(SpeakerProfile.source=='ad').count()}")
        print(f"    of which source='manual': {db.query(SpeakerProfile).filter(SpeakerProfile.source=='manual').count()}")
        print(f"  transcription_groups: {db.query(TranscriptionGroup).count()}")
        print(f"  users: {db.query(User).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
