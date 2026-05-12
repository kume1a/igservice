# IG Service

A Flask-based microservice that wraps the [instagrapi](https://github.com/subzeroid/instagrapi) library to provide Instagram automation via a REST API.

## Prerequisites

- Python 3.10+
- Docker (optional)

## Setup (Local)

```bash
# Create and activate a virtual environment
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\Activate.ps1
```

```bash
# Install dependencies
make install
# or
pip install -r requirements.txt
```

Create a `.env.local` file in the project root:

```
SECRET=your-secret-key
```

## Running

### Local

```bash
make run
```

The server starts on `http://localhost:8080` by default. Override with `HOST` and `PORT` environment variables.

### Debug mode (Flask dev server)

```bash
make debug
```

### Docker

```bash
docker build -t igservice .
docker run -p 8080:8080 --env SECRET=your-secret-key igservice
```

## API

All endpoints require an `X-Secret` header matching the configured `SECRET`.

### POST /login

Log in with Instagram credentials and get back an `instagrapi` settings blob (device + cookies + uuids). Reuse it on subsequent calls instead of logging in repeatedly — Instagram blacklists IPs that do password logins from datacenters. Run this once from a residential/mobile IP, save the response, and pass `settings` to the other routes.

**Request:**

```json
{
  "igUsername": "your_username",
  "igPassword": "your_password"
}
```

**Response:**

```json
{
  "settings": { "cookies": { "...": "..." }, "device_settings": { "...": "..." }, "uuids": { "...": "..." }, "user_agent": "...", "authorization_data": { "...": "..." }, "last_login": 0 }
}
```

### POST /accountInfo

Fetch Instagram account info from a saved settings blob.

**Request:**

```json
{
  "settings": { "...": "..." }
}
```

**Response:**

```json
{
  "userId": "...",
  "account": { "...": "..." }
}
```

### POST /uploadIGTVVideo

Upload an IGTV video using a saved settings blob.

**Request:**

```json
{
  "settings": { "...": "..." },
  "title": "Video Title",
  "caption": "Video caption",
  "videoURL": "https://example.com/video.mp4",
  "thumbnailURL": "https://example.com/thumb.jpg"
}
```

`thumbnailURL` is optional.

**Response:**

```json
{
  "mediaId": "..."
}
```
