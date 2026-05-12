import logging

from flask import Blueprint, jsonify, request

from src.auth import require_shared_secret
from src.constant import UPLOAD_DIR
from src.services.instagram import (
    InstagramAuthError,
    InstagramChallengeError,
    client_from_settings,
    client_from_sessionid,
    login_with_credentials,
    upload_igtv,
)
from src.utils.downloads import download_to_temp, maybe_download_to_temp

logger = logging.getLogger(__name__)

api = Blueprint("api", __name__)
api.before_request(require_shared_secret)


def _missing_fields(body: dict, fields: tuple[str, ...]) -> list[str]:
    return [f for f in fields if not body.get(f)]


@api.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    missing = _missing_fields(body, ("igUsername", "igPassword"))
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        settings = login_with_credentials(body["igUsername"], body["igPassword"])
    except InstagramChallengeError as e:
        return jsonify({"error": str(e)}), 403
    except InstagramAuthError as e:
        return jsonify({"error": str(e)}), 401

    return jsonify({"settings": settings})


@api.route("/accountInfo", methods=["POST"])
def account_info():
    body = request.get_json(silent=True) or {}
    sessionid = body.get("sessionid")
    if not sessionid:
        return jsonify({"error": "Missing sessionid"}), 400

    try:
        client = client_from_sessionid(sessionid)
    except InstagramAuthError as e:
        return jsonify({"error": str(e)}), 400

    try:
        info = client.account_info()
    except Exception:
        logger.exception("Failed to fetch account info")
        return jsonify({"error": "Failed to fetch account info"}), 500

    return jsonify({
        "userId": str(client.user_id),
        "account": info.model_dump(mode="json"),
    })


@api.route("/uploadIGTVVideo", methods=["POST"])
def upload_igtv_video():
    body = request.get_json(silent=True) or {}
    missing = _missing_fields(body, ("sessionid", "title", "caption", "videoURL"))
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    try:
        client = client_from_sessionid(body["sessionid"])
    except InstagramAuthError as e:
        return jsonify({"error": str(e)}), 400

    try:
        with download_to_temp(body["videoURL"], ".mp4", UPLOAD_DIR) as video, \
                maybe_download_to_temp(body.get("thumbnailURL"), ".jpg", UPLOAD_DIR) as thumb:
            media_id = upload_igtv(client, video, body["title"], body["caption"], thumb)
    except Exception:
        logger.exception("Failed to upload IGTV video")
        return jsonify({"error": "Upload failed"}), 500

    logger.info("IGTV uploaded, media id: %s", media_id)
    return jsonify({"mediaId": media_id})
