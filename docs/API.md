# IG Service — API Documentation

A small Flask service that wraps [`instagrapi`](https://github.com/subzeroid/instagrapi) to expose two HTTP endpoints: one to fetch Instagram account info from a session id, and one to upload an IGTV video using a previously obtained session id.

- **Framework:** Flask (served by Waitress)
- **Base URL:** `http://{HOST}:{PORT}` (defaults: `localhost:8080`)
- **Content-Type:** `application/json` (all request bodies)
- **Blueprint prefix:** none — endpoints are mounted at the application root.

---

## Project layout

```
src/
  app.py                  # Flask app factory + Waitress entry point
  config.py               # env-driven configuration
  auth.py                 # X-Secret blueprint hook
  routes.py               # thin Flask route handlers
  services/
    instagram.py          # Instagram login + IGTV upload (instagrapi wrapper)
  utils/
    downloads.py          # SSRF-checked download-to-temp context manager
```

The routes layer parses requests, calls into `services/instagram.py`, and serialises the response. All Instagram-specific behaviour lives in the service module; all temp-file handling lives in the utils module.

---

## Authentication

Every request to every endpoint is gated by a shared-secret check defined in [src/auth.py](src/auth.py) and registered as the blueprint's `before_request` hook in [src/routes.py](src/routes.py).

| Header | Required | Description |
| --- | --- | --- |
| `X-Secret` | Yes | Must equal the `SECRET` environment variable. Compared with `hmac.compare_digest` to prevent timing attacks. |

### Auth failure modes

| Condition | Status | Response body |
| --- | --- | --- |
| `SECRET` env var is not configured on the server | `500` | `{"error": "Server misconfiguration"}` |
| `X-Secret` header missing or wrong | `401` | `{"error": "Invalid secret"}` |

> Note: the auth check runs before *every* route in the `api` blueprint, including any future endpoints. There is no public/unauthenticated endpoint.

---

## Configuration

Configuration is read in [src/config.py](src/config.py) from `.env.local` first, with real process environment variables overriding file values.

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET` | *(unset — required)* | Shared secret expected in the `X-Secret` header. Service returns `500` on every request if this is unset. |
| `UPLOAD_DIR` | `upload` | Directory used to stage downloaded video/thumbnail files before uploading to Instagram. Created on app start. |
| `HOST` | `localhost` | Bind address for the Waitress server. |
| `PORT` | `8080` | Bind port for the Waitress server. |

---

## Endpoints

### 1. `POST /accountInfo`

Authenticates with an existing Instagram session id and returns the user id plus the full `account_info()` payload.

Defined in [src/routes.py](src/routes.py).

#### Request

**Headers**

| Header | Value |
| --- | --- |
| `X-Secret` | the configured server secret |
| `Content-Type` | `application/json` |

**Body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `sessionId` | string | Yes | A valid `instagrapi` session id. |

**Example**

```http
POST /accountInfo HTTP/1.1
Host: localhost:8080
Content-Type: application/json
X-Secret: my-shared-secret

{
  "sessionId": "1234567890%3Aabcdef%3A12"
}
```

#### Response

**`200 OK`**

```json
{
  "userId": "1234567890",
  "account": { "...": "instagrapi Account model serialized to JSON" }
}
```

#### Errors

| Status | Body | When |
| --- | --- | --- |
| `400` | `{"error": "Missing sessionId"}` | `sessionId` is missing or empty. |
| `401` | `{"error": "Invalid Instagram credentials"}` / `{"error": "Failed to authenticate with sessionId"}` | The session id was rejected by Instagram, or `login_by_sessionid` raised. |
| `500` | `{"error": "Failed to fetch account info"}` | Login succeeded but `account_info()` raised. |
| `401` / `500` | see [Authentication](#authentication) | Auth or server-config errors short-circuit before reaching this route. |

---

### 2. `POST /uploadIGTVVideo`

Uploads a video to IGTV using an existing Instagram session id. Both the video and the (optional) thumbnail are downloaded from URLs you provide, streamed to a temporary file inside `UPLOAD_DIR`, posted to Instagram, then cleaned up — successful or not — by the `download_to_temp` context manager in [src/utils/downloads.py](src/utils/downloads.py).

Defined in [src/routes.py](src/routes.py); upload logic in [src/services/instagram.py](src/services/instagram.py).

#### Request

**Headers**

| Header | Value |
| --- | --- |
| `X-Secret` | the configured server secret |
| `Content-Type` | `application/json` |

**Body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `sessionId` | string | Yes | A valid `instagrapi` session id. |
| `title` | string | Yes | IGTV title. |
| `caption` | string | Yes | IGTV caption. |
| `videoURL` | string | Yes | HTTP(S) URL to the source video. Downloaded with `urllib.request.urlretrieve`. Non-`http`/`https` schemes (`file://`, `ftp://`, etc.) are rejected to mitigate SSRF. |
| `thumbnailURL` | string | No | HTTP(S) URL to a thumbnail image. If omitted, IGTV is uploaded without a custom thumbnail. Same scheme validation as `videoURL`. |

**Example**

```http
POST /uploadIGTVVideo HTTP/1.1
Host: localhost:8080
Content-Type: application/json
X-Secret: my-shared-secret

{
  "sessionId": "1234567890%3Aabcdef%3A12",
  "title": "My IGTV title",
  "caption": "Caption text with #hashtags",
  "videoURL": "https://example.com/video.mp4",
  "thumbnailURL": "https://example.com/thumb.jpg"
}
```

#### Response

**`200 OK`**

```json
{
  "mediaId": "3201234567890123456_12345678"
}
```

`mediaId` is the Instagram media identifier returned by `client.igtv_upload(...)`.

#### Errors

| Status | Body | When |
| --- | --- | --- |
| `400` | `{"error": "Missing required fields: <names>"}` | One or more of `sessionId`, `title`, `caption`, `videoURL` is missing or empty. `thumbnailURL` is *not* part of this check. |
| `400` | `{"error": "Invalid Instagram credentials"}` | `login_by_sessionid` returned falsy or raised. |
| `500` | `{"error": "Upload failed"}` | Catches **any** exception thrown during URL download or upload. Concrete details are logged server-side via `logger.exception(...)` but intentionally not exposed to the client. |
| `401` / `500` | see [Authentication](#authentication) | Auth or server-config errors short-circuit before reaching this route. |

#### Side effects & lifecycle

1. `UPLOAD_DIR` is created at app startup.
2. The video URL is downloaded to a temp file (`.mp4` suffix) inside `UPLOAD_DIR` via `download_to_temp`.
3. If `thumbnailURL` is provided, it is downloaded to a temp file (`.jpg` suffix) in the same directory via `maybe_download_to_temp`.
4. `instagrapi.Client.login_by_sessionid(sessionId)` is called.
5. `client.igtv_upload(video_path, title, caption, thumbnail=...)` performs the upload.
6. On context exit (success **or** error), both temp files are removed. Failures during removal are logged but not propagated.

---

## Error response shape

All error responses share a single JSON shape:

```json
{ "error": "<human-readable message>" }
```

There is no error code field, no nested structure, and no per-field validation array — only `error`. Clients should branch on HTTP status, not on message text (messages may change).

---

## Status code summary

| Status | Meaning in this service |
| --- | --- |
| `200` | Operation succeeded. |
| `400` | Bad input — missing body, missing required field, or rejected Instagram credentials on upload. |
| `401` | Missing/wrong `X-Secret` header, or session id rejected by Instagram (on `/accountInfo`). |
| `500` | Server is misconfigured (no `SECRET`), or an unexpected error occurred during upload / account fetch. |

---

## Running the service

From the repository root:

```bash
python -m src.app
```

`src/app.py` creates the Flask app, registers the `api` blueprint, ensures `UPLOAD_DIR` exists, and serves with Waitress on `HOST:PORT`.

---

## Security notes

- **Always set `SECRET`** to a high-entropy value and keep it out of source control. Without it the service returns `500` on every request.
- **Terminate TLS in front** of this service (reverse proxy / load balancer). The `X-Secret` header is sent in plaintext; without HTTPS, anyone on the network path can capture it and impersonate the caller.
- **Treat `sessionId` like a password.** It grants account access until Instagram invalidates the session.
- **SSRF surface is limited but not zero.** URL scheme is restricted to `http`/`https`, but internal IP ranges are not blocked. Don't expose this service to untrusted callers if it sits on a network with sensitive internal HTTP services.
- **Temp files are best-effort cleaned.** A crash inside the `with` block (e.g. SIGKILL) can leave files in `UPLOAD_DIR`. Operators should monitor disk usage.
