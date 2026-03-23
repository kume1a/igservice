import os

from dotenv import dotenv_values

_env = {
    **dotenv_values(".env.local"),
    **os.environ,
}

SECRET = _env.get("SECRET")
UPLOAD_DIR = _env.get("UPLOAD_DIR", "upload")
HOST = _env.get("HOST", "localhost")
PORT = int(_env.get("PORT", "8080"))
