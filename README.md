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

### POST /accountInfo

Fetch Instagram account info from an existing session ID.

**Request:**

```json
{
  "sessionId": "..."
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

Upload an IGTV video using a session ID.

**Request:**

```json
{
  "sessionId": "...",
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
