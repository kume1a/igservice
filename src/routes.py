import hmac
import logging
import os
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request
from instagrapi import Client

from src.config import SECRET, UPLOAD_DIR

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)


@api.before_request
def check_auth():
    if not SECRET:
        logger.error("SECRET environment variable is not set")
        return jsonify({"error": "Server misconfiguration"}), 500

    request_secret = request.headers.get("X-Secret", "")
    if not hmac.compare_digest(request_secret, SECRET):
        return jsonify({"error": "Invalid secret"}), 401


@api.route("/getSessionId", methods=["POST"])
def get_session_id():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid request or missing body"}), 400

    ig_username = body.get("igUsername")
    ig_password = body.get("igPassword")

    if not ig_username or not ig_password:
        return jsonify({"error": "Missing igUsername or igPassword"}), 400

    client = Client()
    success = client.login(ig_username, ig_password)

    if not success:
        return jsonify({"error": "Invalid Instagram credentials"}), 400

    return jsonify({"sessionId": client.sessionid})


@api.route("/uploadIGTVVideo", methods=["POST"])
def upload_igtv_video():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "Invalid request or missing body"}), 400

    session_id = body.get("sessionId")
    title = body.get("title")
    caption = body.get("caption")
    video_url = body.get("videoURL")
    thumbnail_url = body.get("thumbnailURL")

    required = {
        "sessionId": session_id,
        "title": title,
        "caption": caption,
        "videoURL": video_url,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    video_path = None
    thumbnail_path = None

    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        video_path = _download_to_temp(video_url, ".mp4")
        if thumbnail_url:
            thumbnail_path = _download_to_temp(thumbnail_url, ".jpg")

        client = Client()
        success = client.login_by_sessionid(session_id)
        if not success:
            return jsonify({"error": "Invalid Instagram credentials"}), 400

        media = client.igtv_upload(
            Path(video_path),
            title,
            caption,
            thumbnail=Path(thumbnail_path) if thumbnail_path else None,
        )

        logger.info("Media uploaded successfully, id: %s", media.id)
        return jsonify({"mediaId": media.id})

    except Exception:
        logger.exception("Failed to upload IGTV video")
        return jsonify({"error": "Upload failed"}), 500

    finally:
        _cleanup(video_path)
        _cleanup(thumbnail_path)


def _validate_url(url: str) -> None:
    """Reject non-HTTP(S) URLs to prevent SSRF with local schemes."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")


def _download_to_temp(url: str, suffix: str) -> str:
    """Download a URL to a temporary file and return its path."""
    _validate_url(url)
    fd, path = tempfile.mkstemp(suffix=suffix, dir=UPLOAD_DIR)
    os.close(fd)
    try:
        urllib.request.urlretrieve(url, path)
    except Exception:
        _cleanup(path)
        raise
    return path


def _cleanup(path: str | None) -> None:
    """Safely remove a file if it exists."""
    if path:
        try:
            os.remove(path)
        except OSError:
            logger.warning("Failed to clean up file: %s", path)
