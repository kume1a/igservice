# IG Service — API Documentation

A small Flask service that wraps [`instagrapi`](https://github.com/subzeroid/instagrapi) to expose three HTTP endpoints: one to log in with Instagram credentials and obtain a reusable settings blob, one to fetch account info from that blob, and one to upload an IGTV video using that blob.

- **Framework:** Flask (served by Waitress)
- **Base URL:** `http://{HOST}:{PORT}` (defaults: `localhost:8080`)
- **Content-Type:** `application/json` (all request bodies)
- **Blueprint prefix:** none — endpoints are mounted at the application root.

---

## Project layout

```
src/
  app.py                  # Flask app factory + Waitress entry point
  config.py               # env-driven configuration (SECRET, HOST, PORT)
  constant.py             # fixed constants (UPLOAD_DIR)
  auth.py                 # X-Secret blueprint hook
  routes.py               # thin Flask route handlers
  services/
    instagram.py          # Instagram login + IGTV upload (instagrapi wrapper)
  utils/
    downloads.py          # SSRF-checked download-to-temp context manager
```

The routes layer parses requests, calls into `services/instagram.py`, and serialises the response. All Instagram-specific behaviour lives in the service module; all temp-file handling lives in the utils module.

---

## Auth model

Every endpoint is gated by a shared-secret header check defined in [src/auth.py](src/auth.py).

| Header | Required | Description |
| --- | --- | --- |
| `X-Secret` | Yes | Must equal the `SECRET` env var. Compared with `hmac.compare_digest`. |

| Condition | Status | Body |
| --- | --- | --- |
| `SECRET` not configured server-side | `500` | `{"error": "Server misconfiguration"}` |
| `X-Secret` missing or wrong | `401` | `{"error": "Invalid secret"}` |

---

## Instagram auth model: `settings`

This service does **not** ask for `sessionId`. Instead, `/login` returns a full `instagrapi` settings blob (cookies + device fingerprint + UUIDs + user-agent + authorization headers), and the other two routes accept that blob as a `settings` field.

Why: Instagram aggressively invalidates sessions when the device fingerprint changes between calls. Reusing the same settings blob means every subsequent request looks like the same "device" to Instagram, which dramatically reduces session bumps and challenge prompts.

**Operational note:** password logins from datacenter IPs are routinely blocked by Instagram (`ChallengeRequired`). Run `/login` from a residential/mobile IP (your laptop, a phone-tethered machine, or via a residential proxy). After that, the saved settings blob can be used from any IP — but ideally from a stable one.

The blob is opaque to the client; treat it as a single credential. Do not edit it. Persist it like a password.

---

## Configuration

Read in [src/config.py](src/config.py) from `.env.local` first, real env vars override.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET` | *(required)* | Shared secret expected in `X-Secret`. |
| `HOST` | *(required)* | Bind address. |
| `PORT` | *(required)* | Bind port. |

`UPLOAD_DIR` (default `./upload`) is a constant in [src/constant.py](src/constant.py).

---

## Endpoints

### 1. `POST /login`

Log in with Instagram username + password and return a settings blob you can persist and pass to other endpoints.

#### Request

```json
{
  "igUsername": "your_username",
  "igPassword": "your_password"
}
```

#### Response — `200 OK`

```json
{
  "settings": {
    "cookies": { "...": "..." },
    "device_settings": { "...": "..." },
    "uuids": { "...": "..." },
    "user_agent": "...",
    "authorization_data": { "...": "..." },
    "last_login": 0
  }
}
```

The shape comes from `instagrapi.Client.get_settings()`. Save it as-is.

#### Errors

| Status | Body | When |
| --- | --- | --- |
| `400` | `{"error": "Missing required fields: <names>"}` | `igUsername` or `igPassword` missing/empty. |
| `401` | `{"error": "Invalid Instagram username or password"}` | `BadPassword` from instagrapi. |
| `401` | `{"error": "Two-factor authentication is enabled on this account; not supported."}` | `TwoFactorRequired`. |
| `401` | `{"error": "Login failed: ..."}` | Any other instagrapi exception. |
| `403` | `{"error": "Instagram demanded a checkpoint/challenge. ..."}` | `ChallengeRequired` — almost always an IP-reputation issue. Run from a residential/mobile IP. |

---

### 2. `POST /accountInfo`

Fetch the authenticated account's profile info using a saved settings blob.

#### Request

```json
{
  "settings": { "...": "..." }
}
```

#### Response — `200 OK`

```json
{
  "userId": "1234567890",
  "account": { "...": "instagrapi Account model serialised to JSON" }
}
```

#### Errors

| Status | Body | When |
| --- | --- | --- |
| `400` | `{"error": "Missing settings"}` | `settings` missing or empty. |
| `400` | `{"error": "Invalid settings payload"}` | `Client.set_settings(...)` rejected the dict. |
| `500` | `{"error": "Failed to fetch account info"}` | `account_info()` raised (expired session, network, etc.). |

---

### 3. `POST /uploadIGTVVideo`

Upload a video to IGTV using a saved settings blob. Video (and optional thumbnail) are downloaded from URLs you provide into a temp file under `UPLOAD_DIR`, uploaded, then cleaned up — successful or not — by the `download_to_temp` context manager in [src/utils/downloads.py](src/utils/downloads.py).

#### Request

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `settings` | object | Yes | Settings blob from `/login`. |
| `title` | string | Yes | IGTV title. |
| `caption` | string | Yes | IGTV caption. |
| `videoURL` | string | Yes | HTTP(S) URL to the video. Non-`http(s)` schemes are rejected (SSRF guard). |
| `thumbnailURL` | string | No | HTTP(S) URL to a thumbnail image. |

```json
{
  "settings": { "...": "..." },
  "title": "My IGTV title",
  "caption": "Caption text with #hashtags",
  "videoURL": "https://example.com/video.mp4",
  "thumbnailURL": "https://example.com/thumb.jpg"
}
```

#### Response — `200 OK`

```json
{ "mediaId": "3201234567890123456_12345678" }
```

#### Errors

| Status | Body | When |
| --- | --- | --- |
| `400` | `{"error": "Missing required fields: <names>"}` | One of `settings`, `title`, `caption`, `videoURL` missing. |
| `400` | `{"error": "Invalid settings payload"}` | `Client.set_settings(...)` rejected the dict. |
| `500` | `{"error": "Upload failed"}` | Any exception during download, login, or upload. Logged server-side. |

#### Lifecycle

1. Settings blob → fresh `Client` via `set_settings`.
2. Video URL → temp `.mp4` in `UPLOAD_DIR` via `download_to_temp`.
3. If `thumbnailURL` given, thumbnail → temp `.jpg` via `maybe_download_to_temp`.
4. `client.igtv_upload(...)`.
5. On context exit (success **or** error), both temp files are removed.

---

## Error response shape

```json
{ "error": "<human-readable message>" }
```

Branch on HTTP status, not on message text.

---

## Status codes

| Status | Meaning |
| --- | --- |
| `200` | OK. |
| `400` | Bad input (missing field, invalid settings blob). |
| `401` | Missing/wrong `X-Secret`, or Instagram rejected credentials during `/login`. |
| `403` | Instagram demanded a challenge during `/login` — IP reputation problem. |
| `500` | Server misconfigured, or unexpected error during upload / account fetch. |

---

## Running

```bash
python -m src.app
```

---

## Security notes

- **Set `SECRET`** to a high-entropy value and keep it out of source control.
- **Terminate TLS in front** of this service. The `X-Secret` header and the settings blob both travel in the request body/headers — anyone on the wire can replay them.
- **Treat the settings blob like a password.** It contains live session cookies + the device fingerprint Instagram has whitelisted; whoever holds it can act on the account.
- **SSRF surface** is limited: only `http`/`https` URL schemes are accepted. Internal IP ranges are *not* blocked.
- **Don't run `/login` from a datacenter IP** — Instagram will issue a checkpoint. Run it from residential/mobile network (or via a residential proxy), persist the blob, then use the other endpoints normally.
