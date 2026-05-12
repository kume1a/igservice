import logging
from pathlib import Path
from typing import Optional

from instagrapi import Client

logger = logging.getLogger(__name__)


class InstagramAuthError(Exception):
    """Raised when a session id cannot be used to authenticate with Instagram."""


def login_with_session_id(session_id: str) -> Client:
    """Return an authenticated Client for `session_id`, or raise InstagramAuthError."""
    client = Client()
    try:
        ok = client.login_by_sessionid(session_id)
    except Exception as exc:
        logger.exception("login_by_sessionid raised")
        raise InstagramAuthError("Failed to authenticate with sessionId") from exc

    if not ok:
        raise InstagramAuthError("Invalid Instagram credentials")
    return client


def upload_igtv(
    client: Client,
    video_path: Path,
    title: str,
    caption: str,
    thumbnail_path: Optional[Path] = None,
) -> str:
    """Upload an IGTV video and return its Instagram media id."""
    media = client.igtv_upload(video_path, title, caption, thumbnail=thumbnail_path)
    return media.id
