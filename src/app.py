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
    env_secret = os.getenv('SECRET')
    request_secret = request.headers.get('X-Secret')

    if not env_secret:
        raise ValueError('Missing SECRET env variable')

    return request_secret == env_secret


@app.route("/uploadIGTVVideo", methods=['POST'])
def upload_igtv_video():
    if not validate_secret():
        return 'Invalid secret', 401

    body = request.get_json(silent=True)

    if not body:
        return 'Invalid request or missing body', 400

    ig_username = body.get('igUsername')
    ig_password = body.get('igPassword')
    video_url = body.get('videoURL')
    title = body.get('title')
    caption = body.get('caption')
    thumbnail_url = body.get('thumbnailURL')

    if not ig_username or not ig_password or not video_url \
            or not title or not caption or not thumbnail_url:
        return 'Invalid request, missing parameters', 400

    try:
        video_path = f'upload/{time.time()}.mp4'
        thumbnail_path = f'upload/{time.time()}.jpg'

        urllib.request.urlretrieve(video_url, video_path)
        urllib.request.urlretrieve(thumbnail_url, thumbnail_path)

        cl = Client()
        success = cl.login(ig_username, ig_password)

        if not success:
            print('Invalid ig credentials, login failed')

            return 'Invalid ig credentials', 400

        media = cl.igtv_upload(
            Path(video_path),
            title,
            caption,
            Path(thumbnail_path)
        )

        print(f'Media uploaded successfully!, id: {media.id}')

        os.remove(video_path)
        os.remove(thumbnail_path)

        return media.id
    except Exception as e:
        print(e)

        return str(e), 500


if __name__ == "__main__":
    serve(app, host="0.0.0.0", port=8080)
