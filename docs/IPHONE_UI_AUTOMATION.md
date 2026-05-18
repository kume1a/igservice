# Replace IG private-API client with iPhone UI automation

## Context

The service currently uses `instagrapi` (a reverse-engineered IG private API client) for login, account info, and IGTV uploads. This approach is hitting two structural problems:

1. **IP-based blocks** — IG flags datacenter/server IPs, throttles, and challenges sessions.
2. **API-level detection** — even with a valid session, request fingerprints (device ID drift, missing headers, unusual call patterns) get accounts flagged.

The proposed pivot: drive a **real iPhone over USB** running the real Instagram app, using Appium + WebDriverAgent (WDA). All traffic now comes from a normal consumer device on residential/cellular IP, and behavior looks human because we're actually touching the UI. This trades throughput (one device = one account, sequential) for survivability.

**Host:** a Beelink mini PC running **Ubuntu** is the always-on machine. iOS UI automation traditionally requires a Mac, but `go-ios` lets us run everything except WDA signing on Linux. WDA must be re-signed weekly on a Mac (free Apple ID limitation) — handled out-of-band on a cloud Mac (MacStadium / Scaleway hourly) or any borrowed Mac.

Scope of this plan: **1 iPhone, 1 IG account, proof of concept.** Multi-device farming, account rotation, and proxy/SIM rotation are explicitly out of scope.

Also: **IGTV was deprecated by IG in 2022.** The existing `/uploadIGTVVideo` endpoint is replaced by a Reels upload flow, with the route renamed to `/uploadReel`.

---

## Confirmed decisions

| Decision | Choice |
|---|---|
| Platform | iPhone via USB |
| Host machine | **Beelink mini PC, Ubuntu** (always-on) |
| iOS bridge | `go-ios` (replaces Xcode on Linux for device comms + WDA launch) |
| WDA signing | Free Apple ID — weekly re-sign on a **cloud/borrowed Mac**, IPA copied to Beelink |
| Service stack | Keep Python + Flask, swap only [src/services/instagram.py](../src/services/instagram.py) |
| Upload type | Reels (rename endpoint) |
| Media transfer to phone | `pymobiledevice3` → iPhone Photos over USB |

---

## Architecture

```
┌─────────────────┐    HTTP     ┌──────────────────────────────────┐
│ Existing client │────────────▶│  Beelink (Ubuntu) — always on    │
└─────────────────┘             │                                  │
                                │  Flask service                   │
                                │   ├─ routes.py                   │
                                │   └─ services/instagram.py       │  (rewritten)
                                │           │                      │
                                │           ▼                      │
                                │  Appium server (localhost:4723)  │
                                │           │                      │
                                │           ▼                      │
                                │  appium-xcuitest-driver          │
                                │           │  (uses go-ios on Linux)
                                │           ▼                      │
                                │  go-ios  ───── USB ─────▶ iPhone │
                                │           │              ├ WDA (XCTest)
                                │           │              └ Instagram iOS app
                                │           │                      │
                                │  pymobiledevice3 ──USB──▶ iPhone Photos
                                └──────────────────────────────────┘

  ┌────────────────────────────────────┐
  │ Cloud/borrowed Mac — weekly only   │
  │  Xcode → build & sign WDA.ipa      │
  │  scp WDA.ipa → Beelink             │
  └────────────────────────────────────┘
```

The Beelink runs everything day-to-day. The iPhone is wired to it via USB. Once a week, you spin up a cloud Mac (or borrow one), rebuild WDA.ipa with your free Apple ID, copy it to the Beelink, and re-install via `go-ios install`.

---

## Environment setup

### A. One-time, on the Beelink (Ubuntu)

1. Install USB / iOS plumbing:
   ```
   sudo apt update
   sudo apt install -y usbmuxd libimobiledevice-utils ideviceinstaller \
                       python3-pip nodejs npm
   sudo systemctl enable --now usbmuxd
   ```
2. Install **Appium 2** + xcuitest driver:
   ```
   sudo npm i -g appium
   appium driver install xcuitest
   ```
3. Install **go-ios** (replaces Xcode for device comms on Linux):
   ```
   wget https://github.com/danielpaulus/go-ios/releases/latest/download/go-ios-linux.zip
   unzip go-ios-linux.zip -d /usr/local/bin/
   chmod +x /usr/local/bin/ios
   ```
4. Install **pymobiledevice3** for media push:
   ```
   pip install pymobiledevice3 Appium-Python-Client
   ```
5. Plug iPhone in. On the phone, tap **Trust** when prompted. Verify:
   ```
   ios list                 # go-ios sees the device
   idevice_id -l            # libimobiledevice sees it too
   ```
   Record the UDID — you'll need it for `.env`.
6. On the iPhone: Settings → Privacy & Security → **Enable Developer Mode**, reboot, accept prompt.
7. Install Instagram from App Store on the iPhone. **Manually log in** to the target account. Disable "Save login info" prompts. Turn off iOS auto-correct / predictive text to make caption entry deterministic.

### B. One-time, on a Mac (cloud or borrowed)

This produces a signed `WDA.ipa` you copy to the Beelink. You repeat just this block weekly.

1. Open Xcode → clone or open the WebDriverAgent project from `appium-webdriveragent` (Appium ships it; or use upstream [appium/WebDriverAgent](https://github.com/appium/WebDriverAgent)).
2. Set Signing Team to your **free Apple ID** on both `WebDriverAgentLib` and `WebDriverAgentRunner` targets.
3. Set a unique Bundle Identifier on `WebDriverAgentRunner` (e.g. `com.yourname.WebDriverAgentRunner`).
4. Product → Archive → Distribute → **Development** → export as `.ipa`. (Or `xcodebuild build-for-testing` + zip the `.xctestrun` + `.app`; see go-ios docs for the exact bundle layout it expects.)
5. `scp WDA.ipa beelink:/opt/wda/WDA.ipa`.

### C. Per-signing-cycle, on the Beelink

After every new IPA arrives (initial install and every weekly refresh):

```
ios install --path=/opt/wda/WDA.ipa --udid=$IPHONE_UDID
# On iPhone: Settings → General → VPN & Device Management → Trust your developer cert
ios runwda --bundleid=com.yourname.WebDriverAgentRunner \
           --testrunnerbundleid=com.yourname.WebDriverAgentRunner.xctrunner \
           --xctestconfig=WebDriverAgentRunner.xctest \
           --udid=$IPHONE_UDID
```

Once `runwda` is up, Appium's xcuitest driver can talk to WDA on the standard port. A systemd service wrapping the `ios runwda` command keeps WDA alive across reboots.

### D. Weekly maintenance (recurring)

1. Spin up cloud Mac (MacStadium / Scaleway by-the-hour; ~$5-10/mo if disciplined).
2. Rebuild & re-export `WDA.ipa` (step B.1–B.4). Same Bundle ID as before.
3. `scp WDA.ipa beelink:/opt/wda/WDA.ipa`.
4. On Beelink: `ios install --path=/opt/wda/WDA.ipa` and restart the systemd unit.
5. Optional automation: a tiny script on the Mac side that does build+scp on a cron; a script on the Beelink that watches `/opt/wda/WDA.ipa` mtime and reinstalls.

---

## Code changes

### Files modified

#### [src/services/instagram.py](../src/services/instagram.py) — full rewrite
Replace all `instagrapi` calls with UI flows. Keep the function names so [src/routes.py](../src/routes.py) barely changes. New functions:

- `verify_logged_in(driver) -> dict` — open IG app, check we're on the home feed (not the login screen). Returns `{"loggedIn": True, "username": "..."}`. Replaces `login_with_credentials` semantics: in UI world the device is already logged in; this just confirms it.
- `get_account_info(driver) -> dict` — tap Profile tab, read username, follower count, following count, post count from the accessibility tree, return as JSON.
- `upload_reel(driver, video_path: str, caption: str) -> dict` — UI flow: tap `+` → swipe to Reel → tap gallery → select the most recent video (we just pushed it) → Next → enter caption → Share. Returns `{"posted": True}` once the share confirmation appears. (No reliable `mediaId` from UI; if needed we can scrape the resulting post URL from the profile grid.)

Humanization helpers in the same file:
- `human_delay(min_s=0.8, max_s=2.5)` — random sleep between actions.
- `human_tap(driver, element)` — tap with small random pixel offset from element center.

#### [src/routes.py](../src/routes.py) — minor edits
- `/login` → keep route, but now it calls `verify_logged_in` and returns `{"loggedIn": true}` instead of a `settings` blob. The `sessionid` concept becomes a no-op for single-device POC (we can echo back a dummy token or the device UDID for API compatibility).
- `/accountInfo` → calls `get_account_info`. Drop the `sessionid` requirement (or accept and ignore it for backwards compat).
- `/uploadIGTVVideo` → **rename to `/uploadReel`**. Body: `{ "videoURL": "...", "caption": "..." }`. Internally: download video via existing [src/utils/downloads.py](../src/utils/downloads.py), push to iPhone Photos, then call `upload_reel`.

#### [requirements.txt](../requirements.txt)
- Remove: `instagrapi`
- Add: `Appium-Python-Client`, `pymobiledevice3`

### Files added

#### `src/services/appium_driver.py`
Singleton-ish lifecycle for the Appium WebDriver. Holds one persistent driver bound to the configured UDID and IG bundle id (`com.burbn.instagram`). Exposes `get_driver()` that lazy-creates the session and reuses it across requests. Includes a `reset_driver()` for recovery when the session dies.

Capabilities to set (Linux/go-ios variant — Xcode signing caps are intentionally omitted since WDA is pre-installed):
```python
{
  "platformName": "iOS",
  "appium:automationName": "XCUITest",
  "appium:udid": IPHONE_UDID,
  "appium:bundleId": "com.burbn.instagram",
  "appium:updatedWDABundleId": WDA_BUNDLE_ID,
  "appium:usePrebuiltWDA": True,
  "appium:useXctestrunFile": False,
  "appium:webDriverAgentUrl": "http://127.0.0.1:8100",  # WDA started externally by go-ios runwda
  "appium:noReset": True,
}
```

The key trick: on Linux, the Appium driver **cannot build WDA**. We start WDA out-of-band via `ios runwda` (systemd unit), forward its port, and point Appium at the existing URL with `webDriverAgentUrl` — Appium then skips the Xcode build path entirely.

#### `src/services/iphone_media.py`
Wraps `pymobiledevice3` to push a local video file into the iPhone's Photos library over USB. Single function: `push_to_camera_roll(local_path: str) -> None`. Used by the `/uploadReel` flow right before invoking `upload_reel`.

#### `.env.example` additions
```
APPIUM_SERVER_URL=http://127.0.0.1:4723
WDA_URL=http://127.0.0.1:8100
IPHONE_UDID=<from `ios list`>
WDA_BUNDLE_ID=com.yourname.WebDriverAgentRunner
```

---

## Critical files (to read before/while implementing)

- [src/routes.py](../src/routes.py) — 3 endpoints, all route → service handoffs live here.
- [src/services/instagram.py](../src/services/instagram.py) — current instagrapi wrapper; the file being replaced.
- [src/utils/downloads.py](../src/utils/downloads.py) — existing video URL → local file helper; **reused as-is** before pushing to Photos.
- [src/app.py](../src/app.py) — Flask app factory; no changes expected.
- [src/config.py](../src/config.py) — env loader; add the four new vars above.

---

## Risks & caveats

1. **WDA 7-day expiry** with free Apple ID — requires recurring cloud-Mac access. Build the weekly resign into ops habits from day one (calendar reminder + scripts), otherwise the rig silently dies after 7 days. Upgrading to paid dev account ($99/yr) eliminates this entirely and is the obvious upgrade path once the POC is proven.
2. **go-ios edge cases** — go-ios is mature but iOS releases occasionally break it (Apple changes the lockdown / DTX protocol). Pin a known-good version, and watch the project's releases. Fallback if it breaks: temporarily run from a Mac until go-ios updates.
3. **IG UI changes** — Instagram redesigns the upload flow regularly. Selectors will break. Expect periodic maintenance. Prefer accessibility identifiers / `XCUIElementTypeButton` queries by label over brittle XPath.
4. **Behavioral flags still possible** — UI automation eliminates *fingerprint* signals but not *behavioral* ones. Robotic timing patterns will still get the account challenged. The humanization helpers are essential, not optional.
5. **Login challenges** — if IG ever logs the account out (random challenge, 2FA), the device will be on the login screen and `verify_logged_in` will fail. POC scope: surface the failure clearly; recovery is manual (log in by hand on the device). Automating 2FA / checkpoint flows is a follow-up.
6. **No media ID returned from UI uploads** — if downstream consumers rely on `mediaId` from the old `/uploadIGTVVideo` response, we'll need a scrape step after upload (open profile, get latest post URL). Confirm with consumer code whether this is needed.
7. **Throughput** — sequential per device. A Reel upload is ~30-60s of UI taps + upload time. Plan accordingly if any caller assumed API speeds.
8. **Beelink network egress** — the Beelink's IP is where IG sees traffic originate. For best signal, put it on the same residential WiFi a normal phone user would be on. Avoid VPS/datacenter networks.

---

## Verification plan

End-to-end, on the Beelink with iPhone plugged in:

1. **Environment sanity**
   - `ios list` shows the iPhone's UDID (go-ios).
   - `idevice_id -l` also sees it (usbmuxd healthy).
   - `ios runwda ...` brings WDA up on port 8100; `curl http://127.0.0.1:8100/status` returns 200.
   - `appium` starts cleanly on `:4723`.

2. **Service smoke test** (`waitress-serve src.app:app`)
   - `POST /login` with `X-Secret` → IG app foregrounds on iPhone, response is `{"loggedIn": true}`.
   - `POST /accountInfo` → returns the right username + follower count (verify against what you see on the phone).
   - `POST /uploadReel` with a small test video URL + caption →
     - Video downloads to Beelink (check `UPLOAD_DIR`).
     - Video appears in iPhone Photos (last item in camera roll).
     - IG app navigates the upload flow and shares.
     - Reel appears on the test account (verify on a second device or web).

3. **Resilience**
   - Kill the IG app mid-flow on the phone — confirm the next request re-launches it cleanly (driver session recovers).
   - Disconnect/reconnect USB — confirm driver re-establishes.

4. **Stay logged in for 24h** — leave the device idle overnight, run `/accountInfo` the next day, confirm session still works (this is the whole point of the pivot vs the old API approach).

---

## Out of scope (intentionally)

- Multi-device orchestration / device pool.
- Proxy or SIM rotation.
- Automating 2FA / login-challenge recovery.
- Stories, feed photos, DMs, follow/like/comment endpoints — can be added later by following the same `upload_reel` pattern (one function per UI flow). The architecture supports it; the POC just doesn't include them.
- Returning real `mediaId` post-upload (add if a consumer needs it).
