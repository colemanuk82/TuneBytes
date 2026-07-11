# Self-hosting the Current Web App

This setup is for the current React/Vite app in `web/`, not the older PyQt desktop container.

## Files added for web hosting

- `Dockerfile.web`
- `docker-compose.web.yml`
- `web-nginx.conf`

These do not replace the existing Docker files for the PyQt app.

## What to copy to Unraid

Copy this project folder to your Unraid appdata share, for example:

```text
/mnt/user/appdata/radio-player-web/
```

You need these items in that folder:

- `web/`
- `logos/`
- `Dockerfile.web`
- `docker-compose.web.yml`
- `web-nginx.conf`

You do not need to copy:

- `web/node_modules/`
- `web/dist/`
- `.git/`
- `.agents/`
- `.codex/`

Docker will install dependencies and build the site inside the image.

## Deploy on Unraid

In Unraid Compose Manager, use `docker-compose.web.yml` from the copied folder.

Example project path:

```text
/mnt/user/appdata/radio-player-web/
```

Then deploy the stack and open:

```text
http://YOUR-UNRAID-IP:8080
```

## Notes

- Station/theme/volume settings are stored in browser `localStorage`, so they are per browser/device.
- Folder-based custom stations are still browser-session based.
- Some streams may not expose metadata in every browser.
- Some streams may not play in every browser, especially HLS sources.

## Build an Android APK

The web app is also configured as a Capacitor Android app in `web/android/`.

Prerequisites:

- Android Studio or Android SDK command-line tools
- JDK 17 or newer
- `ANDROID_HOME` set to your Android SDK path

From `web/`, build a debug APK:

```powershell
npm.cmd run android:build
```

The debug APK is written to:

```text
web/android/app/build/outputs/apk/debug/app-debug.apk
```

The current Android configuration is a thin wrapper around the hosted web interface:

```text
http://100.109.43.62:8080
```

This keeps routes like `/streams/subwave` on the same web server that already works in the browser.

The SUB/WAVE station uses the nginx proxy route by default on the hosted web app:

```text
/streams/subwave
```

That relative URL only works inside the hosted website because the browser sends it to the same web server. Inside the Android APK, the app is served by Capacitor's local WebView origin, so the APK needs an absolute URL to your hosted web proxy. When building for Tailscale, use your host's Tailscale IP or MagicDNS name:

```powershell
$env:VITE_SUBWAVE_STREAM_URL = "http://YOUR-TAILSCALE-HOST:8080/streams/subwave"
npm.cmd run android:build
```

For example:

```powershell
$env:VITE_SUBWAVE_STREAM_URL = "http://100.x.y.z:8080/streams/subwave"
npm.cmd run android:build
```
