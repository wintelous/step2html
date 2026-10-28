#!/usr/bin/env python3
"""Render the app icon (same drawing as the window header) into PNGs, plus .icns on macOS.

Usage: python packaging/make_icon.py <out-dir>
Writes <out-dir>/step2html.png (512 px), <out-dir>/step2html-<size>.png, <out-dir>/step2html.ico and, on macOS,
<out-dir>/step2html.icns.
"""
import os
import shutil
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import Qt                      # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter   # noqa: E402

import step2html_gui                               # noqa: E402


def render(size, path):
    img = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    step2html_gui.draw_app_icon(p, size)
    p.end()
    img.save(path)


def main():
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "build/icons")
    os.makedirs(out, exist_ok=True)
    app = QGuiApplication(sys.argv[:1])            # noqa: F841 (needed for painting)
    for sz in (16, 32, 48, 64, 128, 256, 512, 1024):
        render(sz, os.path.join(out, "step2html-%d.png" % sz))
    shutil.copy(os.path.join(out, "step2html-512.png"), os.path.join(out, "step2html.png"))
    ico = os.path.join(out, "step2html.ico")               # Windows icon (all standard sizes in one file)
    try:
        from PIL import Image
        Image.open(os.path.join(out, "step2html-1024.png")).save(
            ico, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    except ImportError:
        render(256, ico)                                     # Qt's ICO writer: single 256 px image
    if sys.platform == "darwin":
        iconset = os.path.join(out, "step2html.iconset")
        os.makedirs(iconset, exist_ok=True)
        for sz in (16, 32, 128, 256, 512):
            render(sz, os.path.join(iconset, "icon_%dx%d.png" % (sz, sz)))
            render(sz * 2, os.path.join(iconset, "icon_%dx%d@2x.png" % (sz, sz)))
        subprocess.check_call(["iconutil", "-c", "icns", iconset, "-o", os.path.join(out, "step2html.icns")])
        shutil.rmtree(iconset)
    print("icons written to", out)


if __name__ == "__main__":
    main()
