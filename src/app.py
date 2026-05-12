import logging
import os

from flask import Flask
from waitress import serve

from src.config import HOST, PORT, UPLOAD_DIR
from src.routes import api


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(api)
    return app


app = create_app()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    serve(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
