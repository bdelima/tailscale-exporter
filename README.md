# tailscale-exporter

A tiny read-only HTTP shim in front of the local `tailscale` CLI, for
dashboards (e.g. [Homepage](https://gethomepage.dev)'s `customapi` widget)
that want live Tailscale status without holding a cloud API key or OAuth
secret that expires.

It never calls `api.tailscale.com`. It only reads the local `tailscaled`
daemon's own state, over the same UNIX socket the `tailscale` CLI itself
uses (`tailscale status --json`), and re-serves a flattened summary as JSON.

## Why

Tailscale's cloud API access tokens expire every 90 days; an OAuth client
avoids that but its access tokens still only last an hour, so something has
to keep refreshing them. Neither is needed for the common case of "show me
this node's own status on a dashboard" — the local daemon already knows all
of that about itself, with no credential involved at all.

## What it serves

`GET /status` returns:

```json
{
  "hostname": "matrix",
  "dns_name": "matrix.example.ts.net",
  "address": "100.x.x.x",
  "os": "linux",
  "online": true,
  "tags": "tag:container",
  "advertised_routes": "192.168.0.0/24",
  "key_expiry": "Never",
  "version": "1.102.4-xxxxxxx",
  "health_ok": true,
  "health": "OK",
  "health_issues": [],
  "active_peers": 1,
  "online_peers": 2,
  "total_peers": 4,
  "rx_bytes": 0,
  "tx_bytes": 0,
  "generated_at": "2026-09-20T01:21:51Z"
}
```

- `active_peers` / `online_peers` / `total_peers` are derived from the
  daemon's peer map: `active` means a peer has exchanged a packet with this
  node in roughly the last 2 minutes (Tailscale's own definition), `online`
  means currently connected to the control plane. `active_peers` is a
  reasonable at-a-glance proxy for "how many clients currently have traffic
  flowing through this node as a subnet router" — but it can't separate
  LAN-bound forwarded traffic from traffic addressed to the peer's own
  Tailscale IP, since both ride the same WireGuard tunnel. For real
  per-connection detail, you'd need `conntrack` against the kernel's
  `ts-forward` chain, which this exporter deliberately doesn't attempt.
- `health`/`health_ok` come from the daemon's own health-check array
  (`Status.Health`) — empty means no known problems.
- On any failure talking to the socket, `/status` returns
  `{"error": "..."}` with the CLI's actual stderr included, not just a
  generic non-zero-exit message.

See [`docs/design.md`](docs/design.md) for the deployment shape (the
socket-sharing gotcha in particular) and how it wires into a compose stack.

## Configuration

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `TS_SOCKET` | `/var/run/tailscale/tailscaled.sock` | Path to the tailscaled LocalAPI socket, shared read-only from the actual `tailscale` container. |
| `LISTEN_PORT` | `9810` | Port this exporter listens on. |
| `CACHE_SECONDS` | `5` | How long a response is cached before re-querying the CLI. |

## Building

```
docker build -t bdelima/tailscale-exporter:latest .
```

Pre-built multi-arch images (linux/amd64, linux/arm64) are published to
[Docker Hub](https://hub.docker.com/r/bdelima/tailscale-exporter) on every
tagged release.
