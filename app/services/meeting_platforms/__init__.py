"""
Meeting Platform Integration - Base interface
รองรับ: MS Teams, Zoom, Google Meet
"""
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session


class MeetingPlatformClient(ABC):
    """Base interface for meeting platform integrations."""

    @abstractmethod
    def discover_new_recordings(self, db: Session) -> list[dict]:
        """Return list of recording dicts not yet in DB.

        Each dict should contain:
            - platform_recording_id: str (unique ID from platform)
            - meeting_subject: str | None
            - meeting_organizer: str | None
            - meeting_start_time: datetime | None
            - recording_url: str | None
            - platform_metadata: dict (platform-specific data)
        """
        ...

    @abstractmethod
    def download_recording(self, recording_info: dict, dest_path: str) -> bool:
        """Download recording file to dest_path. Return True on success."""
        ...
