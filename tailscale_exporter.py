#!/usr/bin/env python3
"""
tailscale-exporter

Tiny read-only HTTP shim in front of the local `tailscale` CLI, talking to
the same tailscaled LocalAPI socket the CLI itself uses. Exists so Homepage's
customapi widget can show live Tailscale status without ever holding a
cloud API key/OAuth secret that expires -- this only ever reads local
daemon state via the UNIX socket, never calls api.tailscale.com.

Serves a single flattened JSON object at GET /status, built from
`tailscale --socket=<sock> status --json`, self-reported fields
(ipn/ipnstate.Status.Self, a *PeerStatus), a couple of top-level Status
fields (Version, Health), and an at-a-glance count of how many other
tailnet peers are currently active/online, derived from Status.Peer.

Note: "active" here means the peer has exchanged a packet with this
node in roughly the last 2 minutes (Tailscale's own definition of
PeerStatus.Active) -- it's a reasonable proxy for "currently has
traffic flowing through this subnet router," but it can't distinguish
LAN-bound forwarded traffic from traffic addressed to the peer's own
Tailscale IP, since both ride the same WireGuard tunnel. Good enough
for an at-a-glance count; not meant for per-connection detail.
"""

import json
import os
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SOCKET_PATH = os.environ.get("TS_SOCKET", "/var/run/tailscale/tailscaled.sock")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "9810"))
CACHE_SECONDS = float(os.environ.get("CACHE_SECONDS", "5"))
APP_VERSION = os.environ.get("APP_VERSION", "unknown")

_cache = {"ts": 0.0, "body": None}


def get_status():
    now = time.monotonic()
    if _cache["body"] is not None and (now - _cache["ts"]) < CACHE_SECONDS:
        return _cache["body"]

    try:
        raw = subprocess.run(
            ["tailscale", f"--socket={SOCKET_PATH}", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        status = json.loads(raw.stdout)
    except subprocess.CalledProcessError as e:
        # The CLI's own stderr is the actually-useful part (e.g. "permission
        # denied" vs. "no such file or directory" vs. "connection refused"
        # point at completely different fixes) -- surface it instead of
        # Python's generic "returned non-zero exit status" summary.
        detail = (e.stderr or e.stdout or "").strip() or "(no output from tailscale CLI)"
        body = json.dumps({"error": f"tailscale CLI failed: {detail}"}).encode()
        _cache["ts"] = now
        _cache["body"] = body
        return body
    except Exception as e:  # noqa: BLE001 - want any failure reported to the widget
        body = json.dumps({"error": str(e)}).encode()
        _cache["ts"] = now
        _cache["body"] = body
        return body

    self_peer = status.get("Self") or {}
    key_expiry = self_peer.get("KeyExpiry")
    tags = self_peer.get("Tags") or []
    routes = self_peer.get("PrimaryRoutes") or []
    health = status.get("Health") or []

    peer_map = status.get("Peer") or {}
    active_peers = sum(1 for p in peer_map.values() if p.get("Active"))
    online_peers = sum(1 for p in peer_map.values() if p.get("Online"))
    total_peers = len(peer_map)

    flat = {
        "hostname": self_peer.get("HostName", "-"),
        "dns_name": (self_peer.get("DNSName") or "-").rstrip("."),
        "address": (self_peer.get("TailscaleIPs") or ["-"])[0],
        "os": self_peer.get("OS", "-"),
        "online": bool(self_peer.get("Online", False)),
        "tags": ", ".join(tags) if tags else "-",
        "advertised_routes": ", ".join(routes) if routes else "none",
        "key_expiry": key_expiry if key_expiry else "Never",
        "version": status.get("Version", "-"),
        "exporter_version": APP_VERSION,  # this shim's own version, distinct from Tailscale's own "version" above
        "health_ok": len(health) == 0,
        "health": "OK" if not health else f"{len(health)} issue(s)",
        "health_issues": health,
        "active_peers": active_peers,
        "online_peers": online_peers,
        "total_peers": total_peers,
        "rx_bytes": self_peer.get("RxBytes", 0),
        "tx_bytes": self_peer.get("TxBytes", 0),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    body = json.dumps(flat).encode()
    _cache["ts"] = now
    _cache["body"] = body
    return body


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet down default per-request access log
        pass

    def do_GET(self):
        if self.path.rstrip("/") not in ("", "/status"):
            self.send_response(404)
            self.end_headers()
            return
        body = get_status()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", LISTEN_PORT), Handler)
    print(f"tailscale-exporter listening on :{LISTEN_PORT}, socket={SOCKET_PATH}")
    server.serve_forever()
