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
