import logging
from pathlib import Path
from typing import Any, Optional

from instagrapi import Client
from instagrapi.exceptions import BadPassword, ChallengeRequired, TwoFactorRequired

logger = logging.getLogger(__name__)


class InstagramAuthError(Exception):
    """Raised when Instagram credentials/settings are rejected."""


class InstagramChallengeError(Exception):
    """Raised when Instagram demands a checkpoint/challenge — typically an IP-reputation problem."""


def login_with_credentials(username: str, password: str) -> dict[str, Any]:
    """Log in with username/password and return a serialisable settings dict.

    The returned dict is what `instagrapi.Client.dump_settings` writes to disk — pass it
    back to other routes as the `settings` field so the same device fingerprint and
    session cookies are reused on subsequent calls.
    """
    client = Client()
    try:
        ok = client.login(username, password)
    except ChallengeRequired as exc:
        raise InstagramChallengeError(
            "Instagram demanded a checkpoint/challenge. This usually means the server's "
            "IP is flagged — retry from a residential/mobile IP or via a residential proxy."
        ) from exc
    except BadPassword as exc:
        raise InstagramAuthError("Invalid Instagram username or password") from exc
    except TwoFactorRequired as exc:
        raise InstagramAuthError(
            "Two-factor authentication is enabled on this account; not supported."
        ) from exc
    except Exception as exc:
        logger.exception("instagrapi login raised")
        raise InstagramAuthError(f"Login failed: {exc}") from exc

    if not ok:
        raise InstagramAuthError("Instagram login returned falsy")

    return client.get_settings()


def client_from_settings(settings: dict[str, Any]) -> Client:
    """Build a Client from a settings dict (as returned by /login)."""
    client = Client()
    try:
        client.set_settings(settings)
    except Exception as exc:
        logger.exception("set_settings raised")
        raise InstagramAuthError("Invalid settings payload") from exc
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
