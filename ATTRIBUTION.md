# Attribution

This repository's own code is licensed under the MIT License (see `LICENSE`). It uses or builds on the third-party projects below, each under its own license and copyright; nothing here relicenses them.

## Tailscale CLI

- **Project:** [tailscale/tailscale](https://github.com/tailscale/tailscale)
- **License:** BSD-3-Clause (copyright Tailscale Inc. and contributors)
- **How it's used:** the `tailscale` binary is copied unmodified from the official `ghcr.io/tailscale/tailscale` image into this image, and the exporter shells out to `tailscale status --json` against the local daemon's socket. No Tailscale cloud API is called.

## Base image

- The `python` slim image, with its own licenses (Debian packages: see `/usr/share/doc/*/copyright` inside the image).

## Trademarks

"Tailscale" is a trademark of Tailscale Inc. This is an unofficial project, not affiliated with or endorsed by Tailscale Inc.
