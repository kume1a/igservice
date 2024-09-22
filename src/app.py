import urllib.request
import time
import os

from src.instagrapi import Client
from pathlib import Path
from waitress import serve
from flask import Flask, request
from dotenv import dotenv_values

config = {
    **dotenv_values(".env.local"),
    **os.environ,
}

app = Flask(__name__)


def validate_secret():
    env_secret = config.get('SECRET')
    request_secret = request.headers.get('X-Secret')

    if not env_secret:
        raise ValueError('Missing SECRET env variable')

    return request_secret == env_secret


@app.route("/getSessionId", methods=['POST'])
def test():
    if not validate_secret():
        return 'Invalid secret', 401
    
    body = request.get_json()

    if not body:
        return 'Invalid request or missing body', 400

    ig_username = body.get('igUsername')
    ig_password = body.get('igPassword')

    if not ig_username or not ig_password:
      return 'Invalid request, missing parameters', 400

    c = Client()
    success = c.login(ig_username, ig_password)

    if not success:
        return 'Invalid ig credentials', 400
    
    return {
        'sessionId': c.sessionid
    }

@app.route("/uploadIGTVVideo", methods=['POST'])
def upload_igtv_video():
    if not validate_secret():
        return 'Invalid secret', 401

    body = request.get_json()

    if not body:
        return 'Invalid request or missing body', 400

    session_id = body.get('sessionId')
    title = body.get('title')
    caption = body.get('caption')
    video_url = body.get('videoURL')
    thumbnail_url = body.get('thumbnailURL')

    if not session_id or not video_url \
            or not title or not caption:
        return 'Invalid request, missing parameters', 400

    try:
        video_path = f'upload/{time.time()}.mp4'
        thumbnail_path = f'upload/{time.time()}.jpg' if thumbnail_url else None

        urllib.request.urlretrieve(video_url, video_path)
        if thumbnail_url:
          urllib.request.urlretrieve(thumbnail_url, thumbnail_path)

        cl = Client()
        success = cl.login_by_sessionid(session_id)

        if not success:
            print('Invalid ig credentials, login failed')

            return 'Invalid ig credentials', 400

        media = cl.igtv_upload(
            Path(video_path),
            title,
            caption,
            thumbnail=Path(thumbnail_path) if thumbnail_path else None
        )

        print(f'Media uploaded successfully!, id: {media.id}')

        os.remove(video_path)
        if thumbnail_path:
          os.remove(thumbnail_path)

        return {
            'mediaId': media.id
        }
    except Exception as e:
        print(e)

        return str(e), 500


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=8081)
