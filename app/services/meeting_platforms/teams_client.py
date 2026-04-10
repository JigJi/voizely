"""
MS Teams Integration via Microsoft Graph API
ดึง meeting recordings จาก OneDrive /Recordings/ folder อัตโนมัติ
"""
import logging
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta

import msal
from sqlalchemy.orm import Session

from app.config import settings
from app.models.meeting import MeetingRecording
from app.services.meeting_platforms import MeetingPlatformClient

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class TeamsClient(MeetingPlatformClient):

    def __init__(self):
        self._app = msal.ConfidentialClientApplication(
            client_id=settings.MS_TEAMS_CLIENT_ID,
            client_credential=settings.MS_TEAMS_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.MS_TEAMS_TENANT_ID}",
        )
        self._token_cache: dict | None = None

    def _get_token(self) -> str:
        """Acquire access token via client credentials flow."""
        result = self._app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        if "access_token" not in result:
            error = result.get("error_description", result.get("error", "Unknown"))
            raise RuntimeError(f"Failed to acquire token: {error}")
        return result["access_token"]

    def _graph_get(self, url: str) -> dict:
        """Make authenticated GET request to Graph API."""
        token = self._get_token()
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def _graph_download(self, url: str, dest_path: str) -> bool:
        """Download file from Graph API to disk (streaming)."""
        token = self._get_token()
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
        })
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            return True
        except Exception as e:
            logger.error("Download failed: %s", e)
            return False

    def _get_poll_emails(self, db: Session) -> list[str]:
        """Get emails to poll: active users from DB + extra from config."""
        from app.models.user import User

        # Emails from active users in DB (AD login)
        db_users = (
            db.query(User.email)
            .filter(User.is_active == True, User.email.isnot(None), User.email != "")
            .all()
        )
        emails = {u.email.strip().lower() for u in db_users if u.email}

        # Extra emails from config (e.g. dev email as exception)
        for e in settings.MS_TEAMS_POLL_USERS.split(","):
            e = e.strip()
            if e:
                emails.add(e.lower())

        return list(emails)

    def discover_new_recordings(self, db: Session) -> list[dict]:
        """Scan OneDrive /Recordings/ folder for each user."""
        users = self._get_poll_emails(db)
        if not users:
            logger.warning("No users to poll (DB empty + MS_TEAMS_POLL_USERS empty)")
            return []

        new_recordings = []
        # Only look at files from the last 7 days
        cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"

        for email in users:
            try:
                recordings = self._discover_user_recordings(db, email, cutoff)
                new_recordings.extend(recordings)
            except Exception as e:
                logger.error("Failed to discover recordings for %s: %s", email, e)

        return new_recordings

    # Teams recording folder names vary by locale
    RECORDING_FOLDERS = ["Recordings", "การบันทึก"]

    def _discover_user_recordings(self, db: Session, email: str, cutoff: str) -> list[dict]:
        """Discover recordings for a single user."""
        # Try each possible folder name (varies by Teams locale)
        data = None
        for folder in self.RECORDING_FOLDERS:
            folder_encoded = urllib.parse.quote(folder)
            params = urllib.parse.urlencode({
                "$select": "id,name,lastModifiedDateTime,size,file,parentReference",
                "$top": "50",
            })
            url = f"{GRAPH_BASE}/users/{email}/drive/root:/{folder_encoded}:/children?{params}"
            try:
                data = self._graph_get(url)
                break  # Found the folder
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # Try next folder name
                raise

        if data is None:
            logger.info("No recordings folder for %s (tried: %s)", email, ", ".join(self.RECORDING_FOLDERS))
            return []

        items = data.get("value", [])
        recordings = []

        for item in items:
            name = item.get("name", "")
            # Teams recordings are .mp4
            if not name.lower().endswith(".mp4"):
                continue

            # Client-side date filter
            modified = item.get("lastModifiedDateTime", "")
            if modified and modified < cutoff:
                continue

            item_id = item["id"]
            drive_id = item.get("parentReference", {}).get("driveId", "")

            # Check if already processed
            existing = (
                db.query(MeetingRecording)
                .filter(
                    MeetingRecording.platform == "teams",
                    MeetingRecording.platform_recording_id == item_id,
                )
                .first()
            )
            if existing:
                continue

            # Parse meeting subject from filename
            # Teams format: "Meeting Subject-20260407_1030-Recording.mp4"
            subject = self._parse_subject_from_filename(name)

            # Build download URL
            download_url = f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content"

            # Try to fetch meeting attendees from calendar
            meeting_start = self._parse_datetime(item.get("lastModifiedDateTime"))
            attendees = self._fetch_meeting_attendees(email, subject, meeting_start)

            recordings.append({
                "platform_recording_id": item_id,
                "meeting_subject": subject,
                "meeting_organizer": email,
                "meeting_start_time": meeting_start,
                "recording_url": download_url,
                "attendees": attendees,
                "platform_metadata": {
                    "drive_id": drive_id,
                    "item_id": item_id,
                    "file_name": name,
                    "file_size": item.get("size", 0),
                },
            })

        logger.info("Found %d new recording(s) for %s", len(recordings), email)
        return recordings

    def _fetch_meeting_attendees(self, organizer_email: str, subject: str, meeting_start: datetime | None) -> list[str]:
        """Fetch attendees from calendar event matching subject + date.

        Search the organizer's calendar for events with matching subject around
        the recording date, then extract attendee email addresses.
        Returns list of attendee emails (excluding the organizer).
        """
        if not subject or not meeting_start:
            return []

        try:
            # Search within +/- 1 day of the recording date
            start_dt = (meeting_start - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
            end_dt = (meeting_start + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")

            # URL-encode the subject for the filter (escape single quotes)
            safe_subject = subject.replace("'", "''")
            params = urllib.parse.urlencode({
                "$filter": f"subject eq '{safe_subject}' and start/dateTime ge '{start_dt}' and start/dateTime le '{end_dt}'",
                "$select": "subject,attendees,organizer",
                "$top": "5",
            })
            url = f"{GRAPH_BASE}/users/{organizer_email}/calendar/events?{params}"
            data = self._graph_get(url)

            events = data.get("value", [])
            if not events:
                logger.debug("No calendar event found for '%s' (%s)", subject, organizer_email)
                return []

            # Use first matching event
            event = events[0]
            attendee_emails = []
            for att in event.get("attendees", []):
                email_addr = att.get("emailAddress", {}).get("address", "").strip().lower()
                if email_addr and email_addr != organizer_email.lower():
                    attendee_emails.append(email_addr)

            logger.info("Found %d attendee(s) for '%s'", len(attendee_emails), subject)
            return attendee_emails

        except Exception as e:
            logger.warning("Failed to fetch attendees for '%s': %s", subject, e)
            return []

    def download_recording(self, recording_info: dict, dest_path: str) -> bool:
        """Download recording from OneDrive."""
        url = recording_info.get("recording_url", "")
        if not url:
            logger.error("No recording_url in recording_info")
            return False
        return self._graph_download(url, dest_path)

    @staticmethod
    def _parse_subject_from_filename(filename: str) -> str:
        """Parse meeting subject from Teams recording filename.

        Teams format examples:
        - "Weekly Standup-20260407_1030-Recording.mp4"
        - "Meeting in channel-20260407_1030-Recording.mp4"
        """
        name = filename.rsplit(".", 1)[0]  # remove .mp4
        # Remove -Recording suffix
        if name.endswith("-Recording"):
            name = name[:-len("-Recording")]
        # Remove date-time suffix (last part after last -)
        parts = name.rsplit("-", 1)
        if len(parts) > 1 and len(parts[-1]) >= 8 and parts[-1][:8].isdigit():
            name = parts[0]
        return name.strip() or filename

    @staticmethod
    def _parse_datetime(dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        try:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
