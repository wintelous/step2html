#!/usr/bin/env bash
#
# Build Step2HTML.app and a .dmg for the Mac's own architecture (x86_64 or arm64).
#   packaging/build_macos.sh            -> dist/Step2HTML-<version>-macos-<arch>.dmg
# Uses PYTHON (default: python3.12) to create build/venv-macos on first run.
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3.12}"
VENV="build/venv-macos"

if [ ! -x "$VENV/bin/python" ]; then
  echo "[build] creating $VENV with $PY" >&2
  "$PY" -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r packaging/requirements-app.txt

VERSION="$("$VENV/bin/python" -c 'import re;print(re.search(r"__version__ = \"([^\"]+)\"",open("step2html.py").read()).group(1))')"
ARCH="$(uname -m)"

echo "[build] icons" >&2
"$VENV/bin/python" packaging/make_icon.py build/icons >/dev/null

echo "[build] app bundle (PyInstaller)" >&2
rm -rf dist/Step2HTML dist/Step2HTML.app
"$VENV/bin/pyinstaller" --noconfirm --clean --log-level WARN \
  --distpath dist --workpath build/pyinstaller packaging/step2html.spec

echo "[build] smoke test: convert a generated STEP with the bundled converter" >&2
"$VENV/bin/python" packaging/make_test_step.py build/smoke.step >/dev/null
dist/Step2HTML.app/Contents/MacOS/Step2HTML --convert-cli build/smoke.step -o build/smoke.html 2>&1 | grep -E '^\[|^done|^error' >&2
test -s build/smoke.html

echo "[build] disk image" >&2
STAGE="build/dmg"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R dist/Step2HTML.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="dist/Step2HTML-$VERSION-macos-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -quiet -volname "Step2HTML $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$DMG"
rm -rf "$STAGE"
echo "done: $DMG ($(du -h "$DMG" | cut -f1))" >&2
