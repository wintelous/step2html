#!/usr/bin/env bash
#
# Build the Linux packages in Docker (works from macOS or Linux; x86_64):
#   dist/linux/step2html_<v>_amd64.deb            Debian / Ubuntu / Mint ...
#   dist/linux/step2html-<v>-1-x86_64.pkg.tar.zst Arch / Manjaro / EndeavourOS ...
#   dist/linux/step2html-<v>-linux-x86_64.tar.gz  plain bundle (+ PKGBUILD for makepkg)
# Then installs each package in a clean container and runs a conversion + window check.
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/dist/linux"
mkdir -p "$OUT"
VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' step2html.py)"
MAINTAINER="${MAINTAINER:-step2html <step2html@localhost>}"     # set MAINTAINER="Name <email>" to sign the .deb
DOCKER="docker"
PLAT="--platform linux/amd64"
# every container is throwaway (--rm), named step2html-build-* and labelled, so it never mixes with other projects
RUN="$DOCKER run --rm $PLAT --label project=step2html-build"

if [ -z "${SKIP_BUNDLE:-}" ]; then          # SKIP_BUNDLE=1: reuse dist/linux, only package + test
rm -f "$OUT"/step2html*.deb "$OUT"/step2html-*.pkg.tar.zst "$OUT"/step2html-*-linux-x86_64.tar.gz
echo "[host] build image" >&2
cp packaging/requirements-app.txt packaging/linux/requirements-app.txt
$DOCKER build $PLAT -q --label project=step2html-build -t step2html-build packaging/linux >/dev/null
rm -f packaging/linux/requirements-app.txt

echo "[host] build bundle + .deb" >&2
$RUN --name step2html-build-bundle -e MAINTAINER="$MAINTAINER" -v "$ROOT":/src:ro -v "$OUT":/out step2html-build \
  bash /src/packaging/linux/build_in_container.sh

fi

echo "[host] Arch package (makepkg)" >&2
$RUN --name step2html-build-arch -v "$OUT":/out archlinux:latest bash -c '
  set -e
  pacman -Sy --noconfirm --needed base-devel >/dev/null
  useradd -m builder
  cp -r /out /home/builder/pkg && chown -R builder /home/builder/pkg
  su builder -c "cd /home/builder/pkg && makepkg -f --nodeps >/dev/null"
  cp /home/builder/pkg/step2html-*.pkg.tar.zst /out/'

SMOKE='export QT_QPA_PLATFORM=offscreen
  step2html --version
  step2html /out/smoke.step -o /tmp/smoke.html 2>&1 | grep -E "^\[|^done|^error"
  test -s /tmp/smoke.html
  STEP2HTML_SELFTEST=1 timeout 60 step2html-gui'
for img in debian:12 ubuntu:24.04; do
  echo "[host] test .deb on $img" >&2
  $RUN --name "step2html-build-test-${img%%:*}" -v "$OUT":/out:ro "$img" bash -c "set -e
    apt-get update -qq >/dev/null; apt-get install -y -qq /out/step2html_${VERSION}_amd64.deb >/dev/null
    $SMOKE"
done
echo "[host] test Arch package on archlinux" >&2
$RUN --name step2html-build-test-arch -v "$OUT":/out:ro archlinux:latest bash -c "set -e
  pacman -Sy --noconfirm >/dev/null; pacman -U --noconfirm /out/step2html-${VERSION}-1-x86_64.pkg.tar.zst >/dev/null
  $SMOKE"
rm -f "$OUT/smoke.step"
ls -lh "$OUT"/*.deb "$OUT"/*.pkg.tar.zst "$OUT"/*.tar.gz
