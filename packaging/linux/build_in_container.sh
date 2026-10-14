#!/usr/bin/env bash
# Runs inside the Debian build container (see build_linux.sh): /src = repo (read-only), /out = output dir.
set -euo pipefail
export QT_QPA_PLATFORM=offscreen
PY=/opt/venv/bin/python
WORK=/tmp/work
rm -rf "$WORK"; mkdir -p "$WORK"
cp -r /src/step2html.py /src/step2html_gui.py /src/lib /src/packaging "$WORK/"
cd "$WORK"
VERSION="$($PY -c 'import re;print(re.search(r"__version__ = \"([^\"]+)\"",open("step2html.py").read()).group(1))')"
MAINTAINER="${MAINTAINER:-step2html <step2html@localhost>}"

echo "[linux] icons" >&2
$PY packaging/make_icon.py build/icons >/dev/null

echo "[linux] bundle (PyInstaller)" >&2
/opt/venv/bin/pyinstaller --noconfirm --clean --log-level WARN --distpath dist --workpath build/pyinstaller \
  packaging/step2html.spec
APP=dist/Step2HTML

echo "[linux] smoke tests" >&2
$PY packaging/make_test_step.py build/smoke.step >/dev/null
"$APP/step2html-gui" --convert-cli build/smoke.step -o build/smoke.html 2>&1 | grep -E '^\[|^done|^error' >&2
test -s build/smoke.html
STEP2HTML_SELFTEST=1 timeout 60 "$APP/step2html-gui" >&2
cp build/smoke.step /out/smoke.step              # reused by the clean-install tests

echo "[linux] tarball" >&2
TAR="step2html-$VERSION-linux-x86_64.tar.gz"
tar -C dist -czf "/out/$TAR" Step2HTML

echo "[linux] .deb" >&2
PKG=build/deb
rm -rf "$PKG"
install -d "$PKG/DEBIAN" "$PKG/opt" "$PKG/usr/bin" "$PKG/usr/share/applications"
cp -a "$APP" "$PKG/opt/step2html"
ln -s /opt/step2html/step2html-gui "$PKG/usr/bin/step2html-gui"
install -m 755 packaging/linux/step2html-cli "$PKG/usr/bin/step2html"
install -m 644 packaging/linux/step2html.desktop "$PKG/usr/share/applications/step2html.desktop"
for sz in 16 32 48 64 128 256 512; do
  install -D -m 644 "build/icons/step2html-$sz.png" "$PKG/usr/share/icons/hicolor/${sz}x${sz}/apps/step2html.png"
done
SIZE_KB="$(du -sk "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<CTRL
Package: step2html
Version: $VERSION
Section: graphics
Priority: optional
Architecture: amd64
Installed-Size: $SIZE_KB
Maintainer: $MAINTAINER
Depends: libc6 (>= 2.36), libgl1, libegl1, libxkbcommon0, libxkbcommon-x11-0, libfontconfig1, libfreetype6, libdbus-1-3, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, libxcb-render-util0, libxcb-shape0, libxcb-xinerama0, libxcb-xkb1, libx11-xcb1, libglib2.0-0
Description: Convert STEP CAD models into self-contained 3D HTML viewers
 Step2HTML turns a STEP (ISO 10303) assembly into a single HTML file with an
 interactive 3D viewer and parts tree that opens offline in any modern browser.
 Includes the desktop app (step2html-gui) and the command-line converter
 (step2html).
CTRL
DEB="step2html_${VERSION}_amd64.deb"
dpkg-deb --root-owner-group -Zxz --build "$PKG" "/out/$DEB" >/dev/null

cp packaging/linux/PKGBUILD packaging/linux/step2html.desktop packaging/linux/step2html-cli /out/
cp build/icons/step2html-*.png /out/ 2>/dev/null || true
sed -i "s/^pkgver=.*/pkgver=$VERSION/" /out/PKGBUILD
echo "[linux] done: $TAR, $DEB" >&2
