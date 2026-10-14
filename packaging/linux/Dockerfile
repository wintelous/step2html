# Build environment for the Linux bundle: Debian 12 (glibc 2.36) so the result also runs on newer
# Debian/Ubuntu releases and on Arch.
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
      binutils file dpkg-dev \
      libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libfreetype6 libdbus-1-3 \
      libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
      libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 libx11-xcb1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-app.txt /tmp/requirements-app.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --quiet --upgrade pip \
    && /opt/venv/bin/pip install --quiet -r /tmp/requirements-app.txt
