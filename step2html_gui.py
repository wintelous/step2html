#!/usr/bin/env python3
"""
step2html_gui.py — desktop front-end for step2html (macOS / Linux).

Pick (or drop) a STEP file, choose where to save, press "Create viewer". The conversion itself runs
in a child process (this same executable with --convert-cli, or step2html.py when run from source),
so the window stays responsive and Cancel can stop it at any point.

Requires PySide6 (Qt) and, for the conversion, cadquery-ocp.
"""

import os
import re
import subprocess
import sys
import time

# The frozen app re-runs itself as the converter: `<app> --convert-cli <step2html args>`.
if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--convert-cli":
    import step2html
    step2html.main(sys.argv[2:])
    sys.exit(0)

from PySide6.QtCore import QEvent, QPointF, QProcess, QProcessEnvironment, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import (QBrush, QColor, QDesktopServices, QFont, QIcon, QLinearGradient, QPainter,
                           QPainterPath, QPen, QPixmap, QPolygonF, QGuiApplication)
from PySide6.QtWidgets import (QApplication, QButtonGroup, QCheckBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QProgressBar, QPushButton,
                               QSizePolicy, QVBoxLayout, QWidget)

try:
    from step2html import __version__ as VERSION
except Exception:                                   # converter deps missing: the GUI still opens
    VERSION = "1.0.1"

APP_NAME = "Step2HTML"
STEP_EXTS = (".step", ".stp", ".stpz", ".p21")
# Mesh detail presets -> (linear deflection in model units, angular deflection in radians)
DETAIL = {
    "coarse":   (0.5, 0.8, "Coarse — smallest file, visibly faceted curves"),
    "standard": (0.2, 0.5, "Standard — good balance of file size and smoothness"),
    "fine":     (0.05, 0.3, "Fine — smoothest curves, larger file, slower"),
}
# Progress the bar reaches at the start of each converter stage ([n/4] lines on stderr)
STAGES = {1: (2, "Reading STEP"), 2: (30, "Tessellating"), 3: (72, "Writing geometry"), 4: (88, "Writing HTML")}

# Colours shared with the HTML viewer (lib/viewer_template.html)
THEMES = {
    "dark": dict(bg1="#555c66", bg2="#3b4149", surface="#2f343b", surface2="rgba(255,255,255,0.055)",
                 hover="rgba(255,255,255,0.08)", border="rgba(255,255,255,0.10)",
                 border_strong="rgba(255,255,255,0.20)", text="#e4e7eb", text2="#a3a9b2", text3="#7c838d",
                 accent="#5b93f5", accent_hover="#6ea0f7", accent_soft="rgba(91,147,245,0.22)",
                 danger="#ff9b8f", ok="#7ccf93"),
    "light": dict(bg1="#e3e6e9", bg2="#c5cad1", surface="#eef0f2", surface2="rgba(20,30,45,0.05)",
                  hover="rgba(20,30,45,0.07)", border="rgba(20,30,45,0.12)",
                  border_strong="rgba(20,30,45,0.22)", text="#262b33", text2="#5b636e", text3="#8a919b",
                  accent="#3a74db", accent_hover="#2f66c8", accent_soft="rgba(58,116,219,0.16)",
                  danger="#c4483a", ok="#2f8a4b"),
}


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return ("%d B" % n) if unit == "B" else "%.1f %s" % (n, unit)
        n /= 1024.0


def draw_app_icon(p, size):
    """App icon: an isometric cube on a slate rounded square (also used by packaging/make_icon.py)."""
    s = float(size)
    p.setRenderHint(QPainter.Antialiasing)
    m = s * 0.06
    rect = QRectF(m, m, s - 2 * m, s - 2 * m)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, QColor("#5d6672")); grad.setColorAt(1, QColor("#2f343b"))
    path = QPainterPath(); path.addRoundedRect(rect, s * 0.2, s * 0.2)
    p.fillPath(path, QBrush(grad))
    p.setPen(QPen(QColor(255, 255, 255, 40), max(1.0, s * 0.008))); p.drawPath(path)
    c, r = QPointF(s / 2, s * 0.52), s * 0.27                     # cube centre and "radius"
    h = r * 0.5
    top = QPolygonF([QPointF(c.x(), c.y() - r), QPointF(c.x() + r * 0.87, c.y() - h),
                     QPointF(c.x(), c.y()), QPointF(c.x() - r * 0.87, c.y() - h)])
    left = QPolygonF([QPointF(c.x() - r * 0.87, c.y() - h), QPointF(c.x(), c.y()),
                      QPointF(c.x(), c.y() + r), QPointF(c.x() - r * 0.87, c.y() + h)])
    right = QPolygonF([QPointF(c.x(), c.y()), QPointF(c.x() + r * 0.87, c.y() - h),
                       QPointF(c.x() + r * 0.87, c.y() + h), QPointF(c.x(), c.y() + r)])
    p.setPen(QPen(QColor(20, 24, 30, 120), max(1.0, s * 0.012), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    for poly, col in ((top, "#9cc0ff"), (left, "#5b93f5"), (right, "#3a6fd0")):
        p.setBrush(QColor(col)); p.drawPolygon(poly)


def app_icon():
    icon = QIcon()
    for sz in (16, 32, 64, 128, 256, 512):
        pm = QPixmap(sz, sz); pm.fill(Qt.transparent)
        p = QPainter(pm); draw_app_icon(p, sz); p.end()
        icon.addPixmap(pm)
    return icon


class DropZone(QFrame):
    """Dashed drop target that turns into a file card once a file is chosen."""

    def __init__(self, on_file, parent=None):
        super().__init__(parent)
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.on_file = on_file
        self.setMinimumHeight(136)
        lay = QVBoxLayout(self); lay.setContentsMargins(18, 16, 18, 16); lay.setSpacing(6)
        lay.addStretch(1)
        self.primary = QLabel("Drop a STEP file here"); self.primary.setObjectName("dropPrimary")
        self.primary.setAlignment(Qt.AlignCenter)
        self.secondary = QLabel(".step · .stp"); self.secondary.setObjectName("muted")
        self.secondary.setAlignment(Qt.AlignCenter); self.secondary.setWordWrap(True)
        self.choose = QPushButton("Choose file…"); self.choose.setObjectName("secondary")
        self.choose.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(); row.addStretch(1); row.addWidget(self.choose); row.addStretch(1)
        lay.addWidget(self.primary); lay.addWidget(self.secondary); lay.addSpacing(6); lay.addLayout(row)
        lay.addStretch(1)

    def set_file(self, path):
        if not path:
            self.primary.setText("Drop a STEP file here"); self.secondary.setText(".step · .stp")
            self.choose.setText("Choose file…"); self.setProperty("filled", False)
        else:
            name = os.path.basename(path)
            fm = self.primary.fontMetrics()
            self.primary.setText(fm.elidedText(name, Qt.ElideMiddle, max(200, self.width() - 40)))
            self.primary.setToolTip(name)
            try:
                size = human(os.path.getsize(path))
            except OSError:
                size = "?"
            folder = self.secondary.fontMetrics().elidedText(os.path.dirname(path), Qt.ElideMiddle,
                                                             max(200, self.width() - 140))
            self.secondary.setText("%s · %s" % (size, folder))
            self.secondary.setToolTip(os.path.dirname(path))
            self.choose.setText("Choose another…"); self.setProperty("filled", True)
        self.style().unpolish(self); self.style().polish(self)

    @staticmethod
    def _step_path(event):
        md = event.mimeData()
        if md.hasUrls():
            for u in md.urls():
                if u.isLocalFile() and u.toLocalFile().lower().endswith(STEP_EXTS):
                    return u.toLocalFile()
        return None

    def _hot(self, on):
        self.setProperty("hot", on); self.style().unpolish(self); self.style().polish(self)

    def dragEnterEvent(self, e):
        if self._step_path(e):
            e.acceptProposedAction(); self._hot(True)

    def dragLeaveEvent(self, e):
        self._hot(False)

    def dropEvent(self, e):
        self._hot(False)
        p = self._step_path(e)
        if p:
            e.acceptProposedAction(); self.on_file(p)


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(540)
        self.input = None
        self.output = None
        self.output_custom = False
        self.proc = None
        self.stage = 0
        self.t0 = 0.0
        self.last_error = ""
        self.cancelled = False

        outer = QVBoxLayout(self); outer.setContentsMargins(24, 22, 24, 18); outer.setSpacing(14)

        # header
        head = QHBoxLayout(); head.setSpacing(14)
        logo = QLabel(); pm = QPixmap(52, 52); pm.fill(Qt.transparent)
        p = QPainter(pm); draw_app_icon(p, 52); p.end(); logo.setPixmap(pm)
        titles = QVBoxLayout(); titles.setSpacing(1)
        t = QLabel("STEP to HTML"); t.setObjectName("title")
        st = QLabel("Turn a STEP model into a self-contained 3D viewer"); st.setObjectName("muted")
        titles.addStretch(1); titles.addWidget(t); titles.addWidget(st); titles.addStretch(1)
        head.addWidget(logo); head.addLayout(titles, 1)
        outer.addLayout(head)

        # drop zone
        self.drop = DropZone(self.set_input)
        self.drop.choose.clicked.connect(self.pick_input)
        outer.addWidget(self.drop)

        # settings card
        card = QFrame(); card.setObjectName("card")
        g = QGridLayout(card); g.setContentsMargins(16, 14, 16, 14); g.setHorizontalSpacing(12); g.setVerticalSpacing(10)
        g.setColumnStretch(1, 1)
        g.addWidget(self._label("Save as"), 0, 0)
        self.out_edit = QLineEdit(); self.out_edit.setReadOnly(True); self.out_edit.setPlaceholderText("Choose a STEP file first")
        self.out_btn = QPushButton("Change…"); self.out_btn.setObjectName("secondary"); self.out_btn.setEnabled(False)
        self.out_btn.clicked.connect(self.pick_output)
        g.addWidget(self.out_edit, 0, 1); g.addWidget(self.out_btn, 0, 2)
        g.addWidget(self._label("Title"), 1, 0)
        self.title_edit = QLineEdit(); self.title_edit.setPlaceholderText("Defaults to the file name")
        g.addWidget(self.title_edit, 1, 1, 1, 2)
        g.addWidget(self._label("Detail"), 2, 0)
        seg = QFrame(); seg.setObjectName("seg"); sl = QHBoxLayout(seg); sl.setContentsMargins(3, 3, 3, 3); sl.setSpacing(2)
        self.detail_group = QButtonGroup(self)
        for key, label in (("coarse", "Coarse"), ("standard", "Standard"), ("fine", "Fine")):
            b = QPushButton(label); b.setCheckable(True); b.setObjectName("segBtn"); b.setCursor(Qt.PointingHandCursor)
            b.setProperty("key", key); self.detail_group.addButton(b); sl.addWidget(b)
            if key == "standard":
                b.setChecked(True)
        self.detail_group.buttonToggled.connect(lambda *_: self._detail_hint())
        g.addWidget(seg, 2, 1, 1, 2)
        self.detail_hint = QLabel(); self.detail_hint.setObjectName("hint")
        g.addWidget(self.detail_hint, 3, 1, 1, 2)
        self.open_after = QCheckBox("Open in the browser when finished"); self.open_after.setChecked(True)
        g.addWidget(self.open_after, 4, 1, 1, 2)
        outer.addWidget(card)
        self._detail_hint()

        # status
        self.progress = QProgressBar(); self.progress.setRange(0, 1000); self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6); self.progress.hide()
        self.status = QLabel(); self.status.setObjectName("status"); self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse); self.status.hide()
        outer.addWidget(self.progress); outer.addWidget(self.status)

        # actions
        act = QHBoxLayout(); act.setSpacing(8)
        self.open_btn = QPushButton("Open viewer"); self.open_btn.setObjectName("secondary"); self.open_btn.hide()
        self.reveal_btn = QPushButton({"darwin": "Show in Finder", "win32": "Show in Explorer"}.get(sys.platform, "Show in folder"))
        self.reveal_btn.setObjectName("secondary"); self.reveal_btn.hide()
        self.open_btn.clicked.connect(lambda: self.open_path(self.output))
        self.reveal_btn.clicked.connect(lambda: self.reveal(self.output))
        self.go = QPushButton("Create viewer"); self.go.setObjectName("primary"); self.go.setEnabled(False)
        self.go.setCursor(Qt.PointingHandCursor); self.go.setMinimumHeight(40)
        self.go.clicked.connect(self.go_clicked)
        act.addWidget(self.open_btn); act.addWidget(self.reveal_btn); act.addStretch(1); act.addWidget(self.go)
        outer.addLayout(act)

        foot = QLabel("step2html %s" % VERSION); foot.setObjectName("foot"); foot.setAlignment(Qt.AlignRight)
        outer.addWidget(foot)

        self.tick = QTimer(self); self.tick.setInterval(120); self.tick.timeout.connect(self._advance)
        self.apply_theme()
        sh = QGuiApplication.styleHints()
        if hasattr(sh, "colorSchemeChanged"):
            sh.colorSchemeChanged.connect(lambda *_: self.apply_theme())

    # ---------- look ----------
    @staticmethod
    def _label(text):
        l = QLabel(text); l.setObjectName("fieldLabel"); return l

    def theme_name(self):
        sh = QGuiApplication.styleHints()
        try:
            if sh.colorScheme() == Qt.ColorScheme.Light:
                return "light"
            if sh.colorScheme() == Qt.ColorScheme.Dark:
                return "dark"
        except AttributeError:
            pass
        return "dark" if self.palette().window().color().lightness() < 128 else "light"

    def apply_theme(self):
        c = THEMES[self.theme_name()]
        self.setStyleSheet("""
        QWidget#root { background: qradialgradient(cx:0.5, cy:0.35, radius:0.9, fx:0.5, fy:0.35,
                       stop:0 %(bg1)s, stop:1 %(bg2)s); color: %(text)s; font-size: 13px; }
        QLabel { color: %(text)s; background: transparent; }
        QLabel#title { font-size: 20px; font-weight: 600; }
        QLabel#muted, QLabel#hint { color: %(text2)s; }
        QLabel#hint { font-size: 12px; }
        QLabel#foot { color: %(text3)s; font-size: 11px; }
        QLabel#fieldLabel { color: %(text2)s; }
        QLabel#dropPrimary { font-size: 15px; font-weight: 600; }
        QFrame#card { background: %(surface)s; border: 1px solid %(border)s; border-radius: 14px; }
        QFrame#drop { background: %(surface2)s; border: 2px dashed %(border_strong)s; border-radius: 14px; }
        QFrame#drop[filled="true"] { background: %(surface)s; border: 1px solid %(border)s; }
        QFrame#drop[hot="true"] { background: %(accent_soft)s; border: 2px dashed %(accent)s; }
        QLineEdit { background: %(surface2)s; border: 1px solid %(border)s; border-radius: 8px;
                    padding: 6px 9px; color: %(text)s; selection-background-color: %(accent)s; }
        QLineEdit:focus { border: 1px solid %(accent)s; }
        QLineEdit:read-only { color: %(text2)s; }
        QPushButton { color: %(text)s; }
        QPushButton#secondary { background: %(surface2)s; border: 1px solid %(border)s; border-radius: 8px;
                                padding: 6px 12px; }
        QPushButton#secondary:hover { background: %(hover)s; }
        QPushButton#secondary:disabled { color: %(text3)s; }
        QPushButton#primary { background: %(accent)s; color: white; border: 0; border-radius: 10px;
                              padding: 8px 22px; font-weight: 600; font-size: 14px; }
        QPushButton#primary:hover { background: %(accent_hover)s; }
        QPushButton#primary:disabled { background: %(surface2)s; color: %(text3)s; }
        QPushButton#primary[busy="true"] { background: %(surface2)s; color: %(text)s; border: 1px solid %(border_strong)s; }
        QFrame#seg { background: %(surface2)s; border-radius: 9px; }
        QPushButton#segBtn { background: transparent; border: 0; border-radius: 7px; padding: 6px 10px; color: %(text2)s; }
        QPushButton#segBtn:hover { color: %(text)s; }
        QPushButton#segBtn:checked { background: %(accent_soft)s; color: %(accent)s; font-weight: 600; }
        QCheckBox { color: %(text)s; spacing: 8px; }
        QProgressBar { background: %(surface2)s; border: 0; border-radius: 3px; }
        QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
        QLabel#status[kind="error"] { color: %(danger)s; }
        QLabel#status[kind="ok"] { color: %(ok)s; font-weight: 600; }
        QLabel#status[kind="busy"] { color: %(text2)s; }
        QToolTip { color: %(text)s; background: %(surface)s; border: 1px solid %(border)s; }
        """ % c)

    def _set_status(self, text, kind):
        self.status.setText(text); self.status.setProperty("kind", kind)
        self.status.style().unpolish(self.status); self.status.style().polish(self.status)
        self.status.setVisible(bool(text))

    def _detail_hint(self):
        self.detail_hint.setText(DETAIL[self.detail_key()][2])

    def detail_key(self):
        b = self.detail_group.checkedButton()
        return b.property("key") if b else "standard"

    # ---------- files ----------
    def pick_input(self):
        start = os.path.dirname(self.input) if self.input else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Choose a STEP file", start,
                                              "STEP files (*.step *.stp *.STEP *.STP *.stpz *.p21);;All files (*)")
        if path:
            self.set_input(path)

    def set_input(self, path):
        if self.proc:
            return
        self.input = path
        self.drop.set_file(path)
        if not self.output_custom:
            stem = os.path.splitext(path)[0]
            self.output = stem + ".html"
        self._show_output()
        self.title_edit.setPlaceholderText(os.path.splitext(os.path.basename(path))[0])
        self.out_btn.setEnabled(True); self.go.setEnabled(True)
        self.open_btn.hide(); self.reveal_btn.hide(); self._set_status("", "")
        self.progress.hide()

    def pick_output(self):
        start = self.output or os.path.expanduser("~")
        path, _ = QFileDialog.getSaveFileName(self, "Save viewer as", start, "HTML file (*.html)")
        if path:
            if not path.lower().endswith((".html", ".htm")):
                path += ".html"
            self.output = path; self.output_custom = True
            self._show_output()

    def _show_output(self):              # keep the file name visible: show the end of a long path
        self.out_edit.setText(self.output); self.out_edit.setToolTip(self.output)
        self.out_edit.setCursorPosition(len(self.output))

    # ---------- run ----------
    def converter_command(self):
        lin, ang, _ = DETAIL[self.detail_key()]
        args = [self.input, "-o", self.output, "--tol-linear", str(lin), "--tol-angular", str(ang)]
        title = self.title_edit.text().strip()
        if title:
            args += ["--title", title]
        if getattr(sys, "frozen", False):
            if sys.platform == "win32":                  # windowed apps have no console: use the CLI exe
                return os.path.join(os.path.dirname(sys.executable), "step2html-cli.exe"), args
            return sys.executable, ["--convert-cli"] + args
        here = os.path.dirname(os.path.abspath(__file__))
        return sys.executable, [os.path.join(here, "step2html.py")] + args

    def go_clicked(self):
        if self.proc:
            self.cancelled = True
            self.proc.kill()
            return
        if not self.input or not os.path.isfile(self.input):
            self._set_status("The STEP file can't be found.", "error"); return
        if os.path.exists(self.output):
            r = QMessageBox.question(self, APP_NAME, "%s already exists.\nReplace it?" % os.path.basename(self.output),
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if r != QMessageBox.Yes:
                return
        prog, args = self.converter_command()
        self.proc = QProcess(self)
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONIOENCODING", "utf-8")          # non-ASCII paths/names survive any console code page
        self.proc.setProcessEnvironment(env)
        if sys.platform == "win32" and hasattr(self.proc, "setCreateProcessArgumentsModifier"):
            def _no_console(a):                         # CREATE_NO_WINDOW: no console flashing up
                a.flags |= 0x08000000
            self.proc.setCreateProcessArgumentsModifier(_no_console)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._finished)
        self.proc.errorOccurred.connect(self._proc_error)
        self.stage, self.last_error, self.cancelled = 0, "", False
        self.t0 = time.time()
        self.progress.setValue(0); self.progress.show()
        self._set_status("Starting…", "busy")
        self.open_btn.hide(); self.reveal_btn.hide()
        self._busy(True)
        self.tick.start()
        self.proc.start(prog, args)

    def _busy(self, on):
        self.go.setText("Cancel" if on else "Create viewer")
        self.go.setProperty("busy", on); self.go.style().unpolish(self.go); self.go.style().polish(self.go)
        for w in (self.drop, self.out_btn, self.title_edit):
            w.setEnabled(not on)
        for b in self.detail_group.buttons():
            b.setEnabled(not on)

    def _read(self):
        data = bytes(self.proc.readAllStandardOutput()).decode("utf-8", "replace")
        for line in data.splitlines():
            line = line.strip()
            m = re.match(r"\[(\d)/4\]", line)
            if m:
                self.stage = int(m.group(1))
                self.progress.setValue(max(self.progress.value(), STAGES.get(self.stage, (0, ""))[0] * 10))
            elif line.startswith("error:"):
                self.last_error = line[6:].strip()
            elif self.last_error and line and not line.startswith(("note:", "warning:", "done:", "[")):
                self.last_error += " " + line          # multi-line error message

    def _advance(self):                  # creep forward inside a stage so long steps still look alive
        if not self.proc:
            return
        cur = self.progress.value()
        nxt = STAGES.get(self.stage + 1, (99, ""))[0] * 10
        self.progress.setValue(cur + max(1, int((nxt - 20 - cur) * 0.015)) if cur < nxt - 20 else cur)
        el = int(time.time() - self.t0)
        label = STAGES.get(self.stage, (0, "Starting"))[1]
        self._set_status("%s…  %d:%02d" % (label, el // 60, el % 60), "busy")

    def _proc_error(self, err):
        if err == QProcess.FailedToStart:
            self.last_error = "the converter could not be started."

    def _finished(self, code, status):
        self.tick.stop()
        proc, self.proc = self.proc, None
        if proc:
            self._read_rest(proc)
        self._busy(False)
        el = int(time.time() - self.t0)
        if self.cancelled:
            self.progress.hide(); self._set_status("Cancelled.", "busy"); return
        if code == 0 and status == QProcess.NormalExit and os.path.isfile(self.output):
            self.progress.setValue(1000)
            self._set_status("✓  Created %s · %s · %d:%02d" % (os.path.basename(self.output),
                             human(os.path.getsize(self.output)), el // 60, el % 60), "ok")
            self.open_btn.show(); self.reveal_btn.show()
            if self.open_after.isChecked():
                self.open_path(self.output)
        else:
            self.progress.hide()
            self._set_status("Conversion failed: " + (self.last_error or "the converter stopped unexpectedly (exit code %s)." % code), "error")

    def _read_rest(self, proc):
        rest = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        if rest:
            self.proc = proc
            for line in rest.splitlines():
                if line.strip().startswith("error:"):
                    self.last_error = line.strip()[6:].strip()
            self.proc = None

    # ---------- after ----------
    @staticmethod
    def open_path(path):
        if path and os.path.exists(path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    @staticmethod
    def reveal(path):
        if not path or not os.path.exists(path):
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", path])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(path)))

    def closeEvent(self, e):
        if self.proc:
            r = QMessageBox.question(self, APP_NAME, "A conversion is running. Stop it and quit?",
                                     QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if r != QMessageBox.Yes:
                e.ignore(); return
            self.cancelled = True; self.proc.kill(); self.proc.waitForFinished(3000)
        e.accept()


class App(QApplication):
    """Also accepts files dropped on the Dock icon / opened with the app (macOS FileOpen events)."""

    def __init__(self, argv):
        super().__init__(argv)
        self.window = None
        self.pending = None

    def event(self, e):
        if e.type() == QEvent.FileOpen:
            path = e.file()
            if path.lower().endswith(STEP_EXTS):
                if self.window:
                    self.window.set_input(path)
                else:
                    self.pending = path
            return True
        return super().event(e)


def main():
    app = App(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setWindowIcon(app_icon())
    w = Window()
    app.window = w
    # a STEP path on the command line (e.g. "Open with" on Linux)
    for a in sys.argv[1:]:
        if a.lower().endswith(STEP_EXTS) and os.path.isfile(a):
            app.pending = os.path.abspath(a)
    if app.pending:
        w.set_input(app.pending)
    w.resize(QSize(580, w.sizeHint().height()))
    w.show()
    if os.environ.get("STEP2HTML_SELFTEST"):        # build check: the window opens, then quit
        QTimer.singleShot(800, lambda: (print("selftest: window ok", flush=True), app.quit()))
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
