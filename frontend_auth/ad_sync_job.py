"""Daily AD → backend speaker sync job.

Intended to be invoked from Task Scheduler at ~4am via run_ad_sync.bat.

Flow:
  1. List every user from every configured AD (bind as service account).
  2. If ANY AD fails to enumerate, abort without calling the backend — a
     partial batch would make the backend mark real employees as leavers.
  3. POST the combined list to backend /api/admin/sync-ad-speakers with
     the shared X-Internal-API-Key.
  4. Log outcome to LOG_DIR/ad_sync.log and print a one-line summary to
     stdout so Task Scheduler history is useful.

Exit codes: 0 success, 1 any failure (so scheduler can mark the run failed).
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

import httpx

from ad_service import list_all_ad_users
from config import AD_CONFIGS, settings


def _configure_logging() -> logging.Logger:
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("ad_sync")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(log_dir / "ad_sync.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(sh)
    return logger


def main() -> int:
    logger = _configure_logging()
    logger.info("=== AD sync run started (%s) ===", datetime.now().isoformat(timespec="seconds"))

    if not settings.INTERNAL_API_KEY:
        logger.error("INTERNAL_API_KEY missing from .env — cannot talk to backend")
        return 1

    all_users: list[dict] = []
    for cfg in AD_CONFIGS:
        try:
            users = list_all_ad_users(cfg)
        except Exception as e:
            logger.error("%s enumeration failed: %s", cfg["name"], e)
            logger.error("Aborting sync — partial batch would mark real users as leavers")
            return 1
        all_users.extend(users)

    if not all_users:
        logger.error("No users collected from any AD — aborting to be safe")
        return 1

    # De-duplicate by email (if a user somehow shows up in both ADs, keep first)
    seen = set()
    deduped = []
    for u in all_users:
        if u["email"] in seen:
            continue
        seen.add(u["email"])
        deduped.append(u)

    url = f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}/api/admin/sync-ad-speakers"
    logger.info("POST %s (%d users)", url, len(deduped))

    try:
        r = httpx.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-Internal-API-Key": settings.INTERNAL_API_KEY,
            },
            json={"users": deduped},
            timeout=60.0,
        )
    except httpx.RequestError as e:
        logger.error("Backend unreachable: %s", e)
        return 1

    if r.status_code != 200:
        logger.error("Backend returned %s: %s", r.status_code, r.text[:500])
        return 1

    result = r.json()
    logger.info(
        "Sync OK: received=%d created=%d updated=%d reactivated=%d inactive=%d",
        result.get("total_received", 0),
        result.get("created", 0),
        result.get("updated", 0),
        result.get("reactivated", 0),
        result.get("marked_inactive", 0),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
