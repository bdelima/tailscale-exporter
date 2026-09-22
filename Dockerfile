# Pulls the official tailscale CLI binary out of the real image (no need to
# reimplement anything or reinvent auth) and drops it into a tiny Python
# runtime that just shells out to it against the shared local socket.
FROM ghcr.io/tailscale/tailscale:latest AS tsbin

FROM python:3.12-slim
COPY --from=tsbin /usr/local/bin/tailscale /usr/local/bin/tailscale
COPY tailscale_exporter.py /app/tailscale_exporter.py
EXPOSE 9810
CMD ["python3", "/app/tailscale_exporter.py"]
