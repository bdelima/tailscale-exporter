# Design notes

## Why not the cloud API / OAuth

Homepage ships a native `tailscale` widget, but it authenticates against
`api.tailscale.com` with either a plain API access token (expires every 90
days, hard cap, no way to extend — see
[tailscale/tailscale#11412](https://github.com/tailscale/tailscale/issues/11412))
or an OAuth client (the client credentials don't expire, but the access
tokens they exchange for only last 1 hour, so something has to keep
refreshing them). Either way, Homepage's widget has to hold a live secret
that eventually goes stale.

None of that is needed for "what's this node's own status" — `tailscaled`
already knows its own hostname, address, routes, peers, and health with zero
network calls. This exporter just re-serves that local state as JSON.

## The socket-sharing gotcha

The obvious approach — bind-mount `/var/run/tailscale` out of the
`tailscale` container so a sidecar can read the socket — doesn't work with
the official image. `containerboot` (its entrypoint) always runs the real
`tailscaled` daemon with its socket at `/tmp/tailscaled.sock` *inside its own
container*, and only ever creates `/var/run/tailscale/tailscaled.sock` as a
**symlink** pointing at that real socket, purely so the CLI can find it
without extra flags. Bind-mounting `/var/run/tailscale` alone just exposes a
dangling symlink to anything else, since `/tmp` isn't shared.

The fix: set `TS_SOCKET` explicitly on the `tailscale` container to a path
*inside a volume that's already shared* — e.g. the same state directory
already mounted for `TS_STATE_DIR`. `containerboot` only creates the
compatibility symlink when `TS_SOCKET` differs from the default path; when
you set it, it puts the **real** socket at that path instead. Point the
exporter's own `TS_SOCKET` at the same path (mounted read-only) and it just
works, no extra volume needed beyond what's already there.

## Example compose wiring

```yaml
services:
  tailscale:
    image: ghcr.io/tailscale/tailscale:latest
    hostname: matrix
    container_name: tailscale
    volumes:
      - /opt/tailscale/state:/var/lib/tailscale
      - /dev/net/tun:/dev/net/tun
    environment:
      - TS_AUTHKEY=${TS_AUTHKEY}
      - TS_ACCEPT_DNS=true
      - TS_ROUTES=192.168.0.0/24
      - TS_USERSPACE=false
      - TS_STATE_DIR=/var/lib/tailscale
      - TS_SOCKET=/var/lib/tailscale/tailscaled.sock   # <-- the fix
    privileged: true
    network_mode: host
    restart: unless-stopped

  tailscale-exporter:
    image: bdelima/tailscale-exporter:latest
    container_name: tailscale-exporter
    restart: unless-stopped
    environment:
      - TS_SOCKET=/var/lib/tailscale/tailscaled.sock
    volumes:
      - /opt/tailscale/state:/var/lib/tailscale:ro
    networks:
      - npm_proxy
```

## Homepage widget mapping

```yaml
- Tailscale:
    icon: tailscale.png
    href: https://login.tailscale.com/admin/machines
    target: _blank
    description: VPN subnet router
    server: drakebay
    container: tailscale
    widget:
      type: customapi
      url: http://tailscale-exporter:9810/status
      refreshInterval: 15000
      display: list
      mappings:
        - field: online_peers
          label: Online in tailnet
          format: text
        - field: active_peers
          label: Active subnet connections
          format: text
        - field: advertised_routes
          label: Advertised routes
          format: text
        - field: health
          label: Health
          format: text
        - field: key_expiry
          label: Key expiry
          format: text
```

`display: list` matters here, not just cosmetically — Homepage's
`customapi` widget truncates to `mappings.slice(0, 4)` in its default
`block` display, silently dropping anything past the fourth field. `list`
display doesn't have that limit.
