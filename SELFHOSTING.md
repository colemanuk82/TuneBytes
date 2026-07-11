# Self-hosting with Docker

This app is a PyQt desktop radio player, so the Docker image runs it inside a lightweight virtual display and exposes that desktop in the browser with noVNC.

## Run locally

```sh
docker compose up --build
```

Then open:

```text
http://localhost:6080/vnc.html?autoconnect=true&resize=remote
```

The compose file exposes the web UI on port `6080`, which makes it work with browsers, preview tools, and reverse proxies:

```yaml
"6080:6080"
```

If you only want it reachable from the same machine, change that line to:

```yaml
"127.0.0.1:6080:6080"
```

## Persistent data

Runtime state is stored in the `radio_data` Docker volume at `/data` inside the container:

- `/data/settings.json`
- `/data/station_order.json`
- `/data/logos`
- `/data/recordings`

The default station logos and app icons are still bundled into the image.

## Notes

noVNC gives you the app's visual desktop in a browser. Browser audio forwarding from a Linux desktop container is host-dependent, so playback may require extra PulseAudio/PipeWire configuration if you need sound outside the container host.
