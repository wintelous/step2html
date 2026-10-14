# Building the Step2HTML desktop app

The desktop app (`step2html_gui.py`, Qt/PySide6) bundles Python, OpenCASCADE (cadquery-ocp) and Qt
with PyInstaller, so users need nothing else installed. Build dependencies are pinned in
`requirements-app.txt`.

## macOS → `.dmg`

```bash
packaging/build_macos.sh
```

Produces `dist/Step2HTML-<version>-macos-<arch>.dmg` for the Mac it runs on (`x86_64` on Intel,
`arm64` on Apple Silicon; an Intel build also runs on Apple Silicon via Rosetta). Needs Python 3.12
(`PYTHON=/path/to/python3.12` to override) and creates `build/venv-macos` on first run.

The app is not signed or notarized. A downloaded copy is blocked by Gatekeeper the first time: open it
with right-click → **Open** (or run `xattr -dr com.apple.quarantine /Applications/Step2HTML.app`).

## Linux → `.deb`, Arch package, tarball

```bash
packaging/build_linux.sh
```

Runs entirely in Docker (x86_64), in throwaway containers named `step2html-build-*`:

1. builds the bundle in Debian 12 (glibc 2.36, so it also runs on newer Debian/Ubuntu and on Arch)
   and checks a conversion plus the window start-up;
2. packages it as `dist/linux/step2html_<version>_amd64.deb` and
   `dist/linux/step2html-<version>-linux-x86_64.tar.gz` (plus `PKGBUILD` and assets for makepkg);
3. builds `dist/linux/step2html-<version>-1-x86_64.pkg.tar.zst` with makepkg in an Arch container;
4. installs each package in clean Debian 12, Ubuntu 24.04 and Arch containers and repeats the checks.

`SKIP_BUNDLE=1 packaging/build_linux.sh` reuses an existing bundle and only redoes steps 3–4.

Installing:

```bash
sudo apt install ./step2html_<version>_amd64.deb                # Debian, Ubuntu, Mint, ...
sudo pacman -U step2html-<version>-1-x86_64.pkg.tar.zst         # Arch, Manjaro, EndeavourOS, ...
```

Both install the app under `/opt/step2html`, a menu entry, `step2html-gui` and the command-line
converter `step2html` (same options as `step2html.py`).

To remove the build images afterwards:
`docker image rm step2html-build debian:12 ubuntu:24.04 archlinux:latest python:3.12-slim-bookworm`.
