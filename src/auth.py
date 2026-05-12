import hmac
import logging

from flask import jsonify, request

from src.config import SECRET

logger = logging.getLogger(__name__)


def require_shared_secret():
    """Blueprint before_request hook: validate the X-Secret header against SECRET."""
    if not SECRET:
        logger.error("SECRET environment variable is not set")
        return jsonify({"error": "Server misconfiguration"}), 500

    provided = request.headers.get("X-Secret", "")
    if not hmac.compare_digest(provided, SECRET):
        return jsonify({"error": "Invalid secret"}), 401
