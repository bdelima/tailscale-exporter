# Pulls the official tailscale CLI binary out of the real image (no need to
# reimplement anything or reinvent auth) and drops it into a tiny Python
# runtime that just shells out to it against the shared local socket.
FROM ghcr.io/tailscale/tailscale:latest AS tsbin

FROM python:3.12-slim
COPY --from=tsbin /usr/local/bin/tailscale /usr/local/bin/tailscale
COPY tailscale_exporter.py /app/tailscale_exporter.py

ARG VERSION=unknown
ARG REVISION=unknown
LABEL org.opencontainers.image.source="https://github.com/bdelima/tailscale-exporter" \
      org.opencontainers.image.url="https://github.com/bdelima/tailscale-exporter" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"
ENV APP_VERSION="${VERSION}"

EXPOSE 9810
CMD ["python3", "/app/tailscale_exporter.py"]
