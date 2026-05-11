# IG Service — API Documentation

A small Flask service that wraps [`instagrapi`](https://github.com/subzeroid/instagrapi) to expose two HTTP endpoints: one to log in with Instagram credentials and obtain a session id, and one to upload an IGTV video using a previously obtained session id.

- **Framework:** Flask (served by Waitress)
- **Base URL:** `http://{HOST}:{PORT}` (defaults: `localhost:8080`)
- **Content-Type:** `application/json` (all request bodies)
- **Blueprint prefix:** none — endpoints are mounted at the application root.

---

## Authentication

Every request to every endpoint is gated by a shared-secret check that runs in the blueprint's [`before_request`](src/routes.py#L19-L27) hook.

| Header | Required | Description |
| --- | --- | --- |
| `X-Secret` | Yes | Must equal the `SECRET` environment variable. Compared with [`hmac.compare_digest`](src/routes.py#L26) to prevent timing attacks. |

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
| `UPLOAD_DIR` | `upload` | Directory used to stage downloaded video/thumbnail files before uploading to Instagram. Created on app start and per-request as needed. |
| `HOST` | `localhost` | Bind address for the Waitress server. |
| `PORT` | `8080` | Bind port for the Waitress server. |

---

## Endpoints

### 1. `POST /getSessionId`

Logs into Instagram with a username and password and returns a session id that can be reused for subsequent calls (e.g. `/uploadIGTVVideo`) without re-authenticating.

Defined at [src/routes.py:30-48](src/routes.py#L30-L48).

#### Request

**Headers**

| Header | Value |
| --- | --- |
| `X-Secret` | the configured server secret |
| `Content-Type` | `application/json` |

**Body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `igUsername` | string | Yes | Instagram account username. |
| `igPassword` | string | Yes | Instagram account password. |

**Example**

```http
POST /getSessionId HTTP/1.1
Host: localhost:8080
Content-Type: application/json
X-Secret: my-shared-secret

{
  "igUsername": "example_user",
  "igPassword": "example_password"
}
```

#### Response

**`200 OK`**

```json
{
  "sessionId": "1234567890%3Aabcdef%3A12"
}
```

The `sessionId` value is `instagrapi.Client.sessionid` after a successful `login()` call. Treat it as a sensitive credential — anyone holding it can act on the account until Instagram invalidates it.

#### Errors

| Status | Body | When |
| --- | --- | --- |
| `400` | `{"error": "Invalid request or missing body"}` | The request had no JSON body or the body was not parseable as JSON. |
| `400` | `{"error": "Missing igUsername or igPassword"}` | Either field is missing or empty. |
| `400` | `{"error": "Invalid Instagram credentials"}` | `instagrapi` returned a falsy result from `client.login(...)`. |
| `401` / `500` | see [Authentication](#authentication) | Auth or server-config errors short-circuit before reaching this route. |

> Note: the endpoint does **not** wrap the `instagrapi` login call in a try/except, so unexpected library-level exceptions (e.g. challenge-required, two-factor, rate-limited) will surface as a Flask `500` rather than a structured JSON error.

---

### 2. `POST /uploadIGTVVideo`

Uploads a video to IGTV using an existing Instagram session id. Both the video and the (optional) thumbnail are downloaded from URLs you provide, streamed to a temporary file inside `UPLOAD_DIR`, posted to Instagram, then cleaned up — successful or not.

Defined at [src/routes.py:51-104](src/routes.py#L51-L104).

#### Request

**Headers**

| Header | Value |
| --- | --- |
| `X-Secret` | the configured server secret |
| `Content-Type` | `application/json` |

**Body**

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `sessionId` | string | Yes | Session id from `/getSessionId` (or any other source of a valid `instagrapi` session). |
| `title` | string | Yes | IGTV title. |
| `caption` | string | Yes | IGTV caption. |
| `videoURL` | string | Yes | HTTP(S) URL to the source video. Downloaded with `urllib.request.urlretrieve`. Non-`http`/`https` schemes (`file://`, `ftp://`, etc.) are rejected to mitigate SSRF — see [`_validate_url`](src/routes.py#L107-L111). |
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
| `400` | `{"error": "Invalid request or missing body"}` | The request had no JSON body or the body was not parseable as JSON. |
| `400` | `{"error": "Missing required fields: <names>"}` | One or more of `sessionId`, `title`, `caption`, `videoURL` is missing or empty. `thumbnailURL` is *not* part of this check. |
| `400` | `{"error": "Invalid Instagram credentials"}` | `client.login_by_sessionid(sessionId)` returned a falsy value. |
| `500` | `{"error": "Upload failed"}` | Catches **any** exception thrown during URL download, login, or upload. Concrete details are logged server-side via `logger.exception(...)` but intentionally not exposed to the client. |
| `401` / `500` | see [Authentication](#authentication) | Auth or server-config errors short-circuit before reaching this route. |

#### Side effects & lifecycle

1. `UPLOAD_DIR` is created if missing.
2. The video URL is downloaded to a temp file (`.mp4` suffix) inside `UPLOAD_DIR` via [`_download_to_temp`](src/routes.py#L114-L124).
3. If `thumbnailURL` is provided, it is downloaded to a temp file (`.jpg` suffix) in the same directory.
4. `instagrapi.Client.login_by_sessionid(sessionId)` is called.
5. `client.igtv_upload(video_path, title, caption, thumbnail=...)` performs the upload.
6. **Always**, in the `finally` block, both temp files are removed via [`_cleanup`](src/routes.py#L127-L133). Failures here are logged but not propagated.

---

## Internal helpers

These are not endpoints but they shape the contract of `/uploadIGTVVideo`.

### `_validate_url(url)` — [src/routes.py:107-111](src/routes.py#L107-L111)

Rejects URLs whose scheme is not `http` or `https`. This is a basic SSRF guard against schemes like `file://` (would let a caller exfiltrate local files via the temp download path) or `gopher://`. It does **not** block private/internal IP ranges, so the service should not be exposed to untrusted callers on networks where SSRF to internal hosts would be sensitive.

### `_download_to_temp(url, suffix)` — [src/routes.py:114-124](src/routes.py#L114-L124)

Validates the URL, creates a temp file under `UPLOAD_DIR` with the given suffix, downloads the content with `urllib.request.urlretrieve`, and returns the path. On download failure, the partial file is removed before the exception is re-raised.

### `_cleanup(path)` — [src/routes.py:127-133](src/routes.py#L127-L133)

Best-effort `os.remove` that swallows `OSError` and logs a warning. Safe to call with `None`.

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
| `400` | Bad input — missing body, missing required field, or rejected Instagram credentials. |
| `401` | Missing or wrong `X-Secret` header. |
| `500` | Server is misconfigured (no `SECRET`), or an unexpected error occurred during upload. |

---

## Running the service

From the repository root:

```bash
# install dependencies (see pyproject/requirements as applicable)
python -m src.app
```

`src/app.py` creates the Flask app, registers the `api` blueprint, ensures `UPLOAD_DIR` exists, and serves with Waitress on `HOST:PORT`. See [src/app.py](src/app.py).

---

## Security notes

- **Always set `SECRET`** to a high-entropy value and keep it out of source control. Without it the service returns `500` on every request.
- **Terminate TLS in front** of this service (reverse proxy / load balancer). The `X-Secret` header is sent in plaintext; without HTTPS, anyone on the network path can capture it and impersonate the caller.
- **Treat `sessionId` like a password.** It grants account access until Instagram invalidates the session.
- **SSRF surface is limited but not zero.** URL scheme is restricted to `http`/`https`, but internal IP ranges are not blocked. Don't expose this service to untrusted callers if it sits on a network with sensitive internal HTTP services.
- **Temp files are best-effort cleaned.** A crash between the `mkstemp` call and the `finally` block (e.g. SIGKILL) can leave files in `UPLOAD_DIR`. Operators should monitor disk usage.
