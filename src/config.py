import os

from dotenv import dotenv_values

_env = {
    **dotenv_values(".env.local"),
    **os.environ,
}

SECRET = _env.get("SECRET")
HOST = _env.get("HOST")
PORT = int(_env.get("PORT"))
