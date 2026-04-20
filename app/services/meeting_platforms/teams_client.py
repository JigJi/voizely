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

    def _graph_download(self, url: str, dest_path: str, max_attempts: int = 3) -> bool:
        """Download file from Graph API to disk (streaming).
        Retries on transient errors (token expiry, network blip).
        """
        import time
        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                # Fresh token each attempt — handles long downloads where token expired
                token = self._get_token()
                req = urllib.request.Request(url, headers={
                    "Authorization": f"Bearer {token}",
                })
                with urllib.request.urlopen(req, timeout=600) as resp:
                    with open(dest_path, "wb") as f:
                        while True:
                            chunk = resp.read(64 * 1024)
                            if not chunk:
                                break
                            f.write(chunk)
                logger.info("Downloaded %s on attempt %d", dest_path, attempt)
                return True
            except Exception as e:
                last_error = e
                logger.warning("Download attempt %d/%d failed: %s: %s",
                               attempt, max_attempts, type(e).__name__, e)
                if attempt < max_attempts:
                    time.sleep(2 ** attempt)  # 2s, 4s backoff
        logger.error("Download failed after %d attempts: %s: %s",
                     max_attempts, type(last_error).__name__, last_error)
        return False

    def _get_poll_emails(self, db: Session) -> list[str]:
        """Get emails to poll: active users + organizers found in their calendars + extras from config.

        We expand beyond active DB users by reading their calendars and adding any meeting
        organizer email we find. This way recordings stored in non-Voizely-user OneDrives
        still get discovered.
        """
        from app.models.user import User

        # Emails from active users in DB (AD login) — skip @local placeholders
        db_users = (
            db.query(User.email)
            .filter(User.is_active == True, User.email.isnot(None), User.email != "")
            .all()
        )
        active_emails = {
            u.email.strip().lower() for u in db_users
            if u.email and "@local" not in u.email
        }

        # Extra emails from config (e.g. dev email as exception)
        for e in settings.MS_TEAMS_POLL_USERS.split(","):
            e = e.strip().lower()
            if e:
                active_emails.add(e)

        # Expand: pull organizer emails from each active user's calendar
        all_emails = set(active_emails)
        for user_email in active_emails:
            try:
                organizers = self.get_user_calendar_organizers(user_email)
                new_orgs = organizers - all_emails
                if new_orgs:
                    logger.info("Discovered %d new organizer(s) from %s calendar", len(new_orgs), user_email)
                all_emails.update(organizers)
            except Exception as e:
                logger.warning("Failed to expand organizers for %s: %s", user_email, e)

        return list(all_emails)

    def get_user_calendar_organizers(self, email: str, days: int = 30) -> set[str]:
        """Get unique organizer emails from user's calendar (online meetings only).
        Used to expand the poll list so we can scan organizer OneDrives for recordings.
        """
        start_dt = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        end_dt = datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")

        params = urllib.parse.urlencode({
            "startDateTime": start_dt,
            "endDateTime": end_dt,
            "$select": "isOnlineMeeting,organizer",
            "$top": "200",
        })
        url = f"{GRAPH_BASE}/users/{email}/calendarView?{params}"

        try:
            data = self._graph_get(url)
        except Exception as e:
            logger.error("Failed to fetch calendar organizers for %s: %s", email, e)
            return set()

        organizers = set()
        for item in data.get("value", []):
            if not item.get("isOnlineMeeting"):
                continue
            org_email = item.get("organizer", {}).get("emailAddress", {}).get("address", "")
            if org_email:
                organizers.add(org_email.strip().lower())
        return organizers

    def discover_new_recordings(self, db: Session) -> list[dict]:
        """Scan OneDrive /Recordings/ folder for each user."""
        users = self._get_poll_emails(db)
        if not users:
            logger.warning("No users to poll (DB empty + MS_TEAMS_POLL_USERS empty)")
            return []

        new_recordings = []
        # Look at files from the last 30 days (matches calendar lookup window)
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat() + "Z"

        for email in users:
            try:
                recordings = self._discover_user_recordings(db, email, cutoff)
                new_recordings.extend(recordings)
            except Exception as e:
                logger.error("Failed to discover recordings for %s: %s", email, e)

        return new_recordings

    # Teams recording folder names vary by locale and Teams version
    RECORDING_FOLDERS = ["Recordings", "การบันทึก", "การประชุม", "Meetings"]

    def _discover_user_recordings(self, db: Session, email: str, cutoff: str) -> list[dict]:
        """Discover recordings for a single user. Scans ALL known folder names (some may exist
        but be empty while another holds the real recordings)."""
        items = []
        for folder in self.RECORDING_FOLDERS:
            folder_encoded = urllib.parse.quote(folder)
            params = urllib.parse.urlencode({
                "$select": "id,name,lastModifiedDateTime,size,file,parentReference",
                "$top": "200",
            })
            url = f"{GRAPH_BASE}/users/{email}/drive/root:/{folder_encoded}:/children?{params}"
            try:
                data = self._graph_get(url)
                items.extend(data.get("value", []))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    continue  # Folder doesn't exist for this locale — try next
                logger.warning("Error scanning %s/%s: %s", email, folder, e)
            except Exception as e:
                logger.warning("Error scanning %s/%s: %s", email, folder, e)

        if not items:
            logger.info("No recording files found for %s", email)
            return []

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

            # If calendar lookup failed, at least include the OneDrive owner as attendee
            if not attendees:
                attendees = [email.lower()]
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
                if email_addr:
                    attendee_emails.append(email_addr)

            # Always include organizer as attendee (they were invited to their own meeting)
            org_lower = organizer_email.lower()
            if org_lower not in attendee_emails:
                attendee_emails.append(org_lower)

            logger.info("Found %d attendee(s) for '%s'", len(attendee_emails), subject)
            return attendee_emails

        except Exception as e:
            logger.warning("Failed to fetch attendees for '%s': %s", subject, e)
            return []

    def get_user_calendar_subjects(self, email: str, days: int = 30) -> list[dict]:
        """Get online meeting subjects from user's calendar for the last N days.
        Returns list of {"subject": str, "start_time": datetime}.
        """
        start_dt = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
        end_dt = datetime.utcnow().strftime("%Y-%m-%dT23:59:59Z")

        params = urllib.parse.urlencode({
            "startDateTime": start_dt,
            "endDateTime": end_dt,
            "$select": "subject,start,end,isOnlineMeeting",
            "$top": "200",
            "$orderby": "start/dateTime desc",
        })
        url = f"{GRAPH_BASE}/users/{email}/calendarView?{params}"

        try:
            data = self._graph_get(url)
        except Exception as e:
            logger.error("Failed to fetch calendar for %s: %s", email, e)
            return []

        events = []
        for item in data.get("value", []):
            if not item.get("isOnlineMeeting"):
                continue
            subject = self._normalize_subject(item.get("subject"))
            start_str = item.get("start", {}).get("dateTime", "")
            if subject:
                events.append({
                    "subject": subject,
                    "start_time": self._parse_datetime(start_str),
                })
        logger.info("Calendar for %s: %d online meetings (last %d days)", email, len(events), days)
        return events

    def download_recording(self, recording_info: dict, dest_path: str) -> bool:
        """Download recording from OneDrive."""
        url = recording_info.get("recording_url", "")
        if not url:
            logger.error("No recording_url in recording_info")
            return False
        return self._graph_download(url, dest_path)

    # NBSP, BOM, zero-width space/non-joiner/joiner, word joiner, Thai Phinthu,
    # plus standard whitespace — stripped from both ends of a subject.
    _SUBJECT_STRIP = " \t\n\r\f\v\u00a0\ufeff\u200b\u200c\u200d\u2060\u0e3a"

    @staticmethod
    def _normalize_subject(subject: str | None) -> str:
        """Normalize a meeting subject so calendar event and recording filename
        forms compare equal. Strips invisible chars from both edges and
        collapses internal whitespace (incl. NBSP)."""
        if not subject:
            return ""
        import re
        s = subject.strip(TeamsClient._SUBJECT_STRIP)
        s = re.sub(r"\s+", " ", s)
        return s

    @staticmethod
    def _parse_subject_from_filename(filename: str) -> str:
        """Parse meeting subject from Teams recording filename.

        Teams format examples (varies by locale):
        - "Weekly Standup-20260407_1030-Recording.mp4"
        - "Meeting in channel-20260407_1030-Meeting Recording.mp4"
        - "ประชุมทีม-20260407_1030-การบันทึกการประชุม.mp4"
        """
        name = filename.rsplit(".", 1)[0]  # remove .mp4
        # Remove recording suffix (varies by locale)
        for suffix in ("-Meeting Recording", "-การบันทึกการประชุม", "-Recording"):
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        # Remove date-time suffix (last part after last -)
        parts = name.rsplit("-", 1)
        if len(parts) > 1 and len(parts[-1]) >= 8 and parts[-1][:8].isdigit():
            name = parts[0]
        return TeamsClient._normalize_subject(name) or filename

    @staticmethod
    def _parse_datetime(dt_str: str | None) -> datetime | None:
        if not dt_str:
            return None
        # Graph API returns 7 decimal places (e.g. "2026-04-10T10:30:00.0000000")
        # which Python's fromisoformat can't handle (max 6). Truncate to microseconds.
        import re
        s = dt_str.replace("Z", "+00:00")
        # Match .NNNNNNN (7+ digits) and truncate to 6
        s = re.sub(r"\.(\d{6})\d+", r".\1", s)
        try:
            return datetime.fromisoformat(s)
        except (ValueError, AttributeError):
            return None
