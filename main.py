#!/usr/bin/env python3
"""Kirei — a desktop front-end for realesrgan-ncnn-vulkan."""
from __future__ import annotations

import hashlib
import io
import os
import re
import shlex
import sys
import zipfile
from pathlib import Path

from PySide6.QtCore import (QElapsedTimer, QPointF, QProcess, QRectF, QSettings,
                            QSize, Qt, QTimer, QUrl, Signal)
from PySide6.QtGui import (QBrush, QColor, QDesktopServices, QFont, QFontDatabase,
                           QFontMetrics, QIcon, QKeySequence, QLinearGradient,
                           QPainter, QPainterPath, QPalette, QPen, QPixmap,
                           QShortcut)
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (QAbstractButton, QApplication, QButtonGroup, QFileDialog,
                               QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QLineEdit, QPlainTextEdit, QProgressBar, QPushButton,
                               QScrollArea, QSizePolicy, QToolButton, QVBoxLayout,
                               QWidget)

APP_NAME = "Kirei"
__version__ = "0.1.0"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_BIN = Path.home() / ".local/opt/realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan"
# The official Linux build of Real-ESRGAN, checked against its SHA-256 before installing.
ESRGAN_URL = ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
              "realesrgan-ncnn-vulkan-20220424-ubuntu.zip")
ESRGAN_SHA256 = "e5aa6eb131234b87c0c51f82b89390f5e3e642b7b70f2b9bbe95b6a285a40c96"
ESRGAN_SIZE_MB = 44

# id, title, description, allowed scales, short tag used in output names
MODELS = [
    ("realesrgan-x4plus-anime", "Anime · Strong",
     "Cleans line art and JPEG blur. Always 4×.", (4,), "anime"),
    ("realesr-animevideov3", "Anime · Light",
     "Faster, keeps more of the original texture.", (2, 3, 4), "animev3"),
    ("realesrgan-x4plus", "Photo",
     "For real-world photographs. Always 4×.", (4,), "photo"),
]
MODEL_BY_ID = {m[0]: m for m in MODELS}

C = {
    "bg": "#121317", "stage": "#0d0e11", "panel": "#181a20", "raised": "#23262e",
    "line": "#2a2e38", "line_hi": "#3a3f4b", "text": "#ecebe8", "muted": "#8a8f9c",
    "faint": "#5b606c", "accent": "#f0a35e", "accent_hi": "#f6b67a",
    "accent_ink": "#24170b", "danger": "#ef6b6b", "ok": "#82cf9d",
}

QSS = """
#Sidebar { background: @panel; border-right: 1px solid @line; }
#SidebarInner { background: transparent; }
#Footer { background: @panel; border-top: 1px solid @line; }
QScrollArea { background: transparent; border: none; }

#AppName { font-size: 19pt; font-weight: 700; }
#AppSub { color: @muted; font-size: 9pt; }
#Section { color: @faint; font-size: 8pt; font-weight: 700; letter-spacing: 1.6px; }
#Hint { color: @muted; font-size: 9pt; }
#FieldLabel { font-weight: 600; }
#Title { font-size: 12pt; font-weight: 600; }
#PathLabel { color: @text; }

#Drop { background: @bg; border: 1.5px dashed @line; border-radius: 14px; }
#Drop:hover { border-color: @line_hi; }
#Drop[filled="true"] { border-style: solid; }
#Drop[hover="true"] { border: 1.5px dashed @accent; background: rgba(240,163,94,0.07); }

#ModelCard { background: transparent; border: 1px solid @line; border-radius: 12px; }
#ModelCard:hover { border-color: @line_hi; }
#ModelCard[selected="true"] { border-color: @accent; background: rgba(240,163,94,0.07); }
#CardTitle { font-weight: 600; }
#CardDesc { color: @muted; font-size: 9pt; }

#Seg { background: @bg; border: 1px solid @line; border-radius: 10px; }
#SegBtn { background: transparent; border: none; border-radius: 7px; padding: 7px 0;
          color: @muted; font-weight: 600; }
#SegBtn:hover { color: @text; }
#SegBtn:checked { background: @raised; color: @text; }
#SegBtn:disabled { color: #3a3e48; }

QPushButton#Ghost { background: transparent; border: 1px solid @line; border-radius: 8px;
                    padding: 6px 12px; color: @text; }
QPushButton#Ghost:hover { border-color: @line_hi; background: @raised; }

QPushButton#Primary { background: @accent; color: @accent_ink; border: none; border-radius: 11px;
                      padding: 13px; font-size: 11pt; font-weight: 700; }
QPushButton#Primary:hover { background: @accent_hi; }
QPushButton#Primary:disabled { background: @raised; color: @faint; }
QPushButton#Primary[running="true"] { background: transparent; color: @text; border: 1px solid @line_hi; }
QPushButton#Primary[running="true"]:hover { border-color: @danger; color: @danger; }

QToolButton#Disclosure { background: transparent; border: none; color: @muted; font-weight: 600;
                         padding: 2px 0; }
QToolButton#Disclosure:hover { color: @text; }

QProgressBar { background: @raised; border: none; border-radius: 3px; min-height: 6px; max-height: 6px; }
QProgressBar::chunk { background: @accent; border-radius: 3px; }

#Status { color: @muted; font-size: 9pt; }
#Status[state="error"] { color: @danger; }
#Status[state="ok"] { color: @ok; }
#Elapsed { color: @faint; font-size: 9pt; }

#Chip { background: @raised; border-radius: 8px; padding: 4px 10px; color: @muted; font-size: 9pt; }

QLineEdit { background: @bg; border: 1px solid @line; border-radius: 8px; padding: 6px 9px;
            selection-background-color: @accent; selection-color: @accent_ink; }
QLineEdit:focus { border-color: @accent; }

QPlainTextEdit#Log { background: @stage; border: 1px solid @line; border-radius: 10px; padding: 6px;
                     color: #b9bdc7; font-family: "JetBrains Mono", "DejaVu Sans Mono", monospace;
                     font-size: 9pt; }

QScrollBar:vertical { background: transparent; width: 8px; margin: 2px; }
QScrollBar::handle:vertical { background: @line; border-radius: 3px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @line_hi; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

QToolTip { background: @raised; color: @text; border: 1px solid @line; padding: 4px 8px; }
"""


def build_qss() -> str:
    return re.sub(r"@(\w+)", lambda m: C[m.group(1)], QSS)


# ───────────────────────── helpers ─────────────────────────

def repolish(w: QWidget) -> None:
    w.style().unpolish(w)
    w.style().polish(w)
    w.update()


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


def human_time(ms: int) -> str:
    s = ms / 1000
    if s < 60:
        return f"{s:.1f} s"
    return f"{int(s // 60)} m {int(s % 60):02d} s"


def tilde(p: Path) -> str:
    s, home = str(p), str(Path.home())
    return "~" + s[len(home):] if s.startswith(home) else s


def list_images(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS)


def star_path(cx: float, cy: float, r: float) -> QPainterPath:
    """Four-point sparkle, the app's mark."""
    path = QPainterPath()
    k = r * 0.22
    path.moveTo(cx, cy - r)
    path.quadTo(cx + k, cy - k, cx + r, cy)
    path.quadTo(cx + k, cy + k, cx, cy + r)
    path.quadTo(cx - k, cy + k, cx - r, cy)
    path.quadTo(cx - k, cy - k, cx, cy - r)
    return path


def app_icon_pixmap(size: int) -> QPixmap:
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(scale, scale)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(C["accent_hi"]))
    grad.setColorAt(1, QColor("#e2774c"))
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.28, size * 0.28)
    p.setBrush(QColor(C["accent_ink"]))
    p.drawPath(star_path(size * 0.5, size * 0.5, size * 0.32))
    p.setBrush(QColor(C["accent_ink"]).lighter(160))
    p.drawPath(star_path(size * 0.76, size * 0.25, size * 0.09))
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


def rounded_thumb(src: QPixmap | None, size: int, radius: float = 10) -> QPixmap:
    scale = 2
    pm = QPixmap(size * scale, size * scale)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    p.scale(scale, scale)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    if src is not None and not src.isNull():
        p.setClipPath(clip)
        # cover-fit
        sw, sh = src.width(), src.height()
        s = max(size / sw, size / sh)
        w, h = sw * s, sh * s
        p.drawPixmap(QRectF((size - w) / 2, (size - h) / 2, w, h), src, QRectF(src.rect()))
        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 25), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(clip)
    else:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["raised"]))
        p.drawPath(clip)
        # upload arrow
        pen = QPen(QColor(C["muted"]), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        c = size / 2
        p.drawLine(QPointF(c, c + 9), QPointF(c, c - 9))
        p.drawLine(QPointF(c - 7, c - 2), QPointF(c, c - 9))
        p.drawLine(QPointF(c + 7, c - 2), QPointF(c, c - 9))
        p.drawLine(QPointF(c - 12, c + 14), QPointF(c + 12, c + 14))
    p.end()
    pm.setDevicePixelRatio(scale)
    return pm


def install_esrgan(data: bytes, dest: Path) -> None:
    """Unpack the Real-ESRGAN zip into dest, without its demo files."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            name = info.filename
            if name.startswith(("input", "README")) or name.endswith(".mp4"):
                continue
            target = (dest / name).resolve()
            if target != root and root not in target.parents:
                raise ValueError(f"unexpected path in archive: {name}")
            z.extract(info, dest)
    binary = dest / "realesrgan-ncnn-vulkan"
    binary.chmod(0o755)


# ───────────────────────── small widgets ─────────────────────────

class ElidedLabel(QLabel):
    def __init__(self, text: str = "", mode=Qt.ElideMiddle, parent=None):
        super().__init__(parent)
        self._full = ""
        self._mode = mode
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(10)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt naming)
        self._full = text
        self._apply()

    def fullText(self) -> str:  # noqa: N802
        return self._full

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._apply()

    def _apply(self):
        elided = self.fontMetrics().elidedText(self._full, self._mode, max(10, self.width()))
        super().setText(elided)
        self.setToolTip(self._full if elided != self._full else "")


class Segmented(QFrame):
    changed = Signal(object)

    def __init__(self, options: list[tuple[str, object]], parent=None):
        super().__init__(parent)
        self.setObjectName("Seg")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._btns: dict[object, QPushButton] = {}
        for label, value in options:
            b = QPushButton(label)
            b.setObjectName("SegBtn")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
            self.group.addButton(b)
            lay.addWidget(b)
            self._btns[value] = b

    def value(self):
        for v, b in self._btns.items():
            if b.isChecked():
                return v
        return None

    def set_value(self, value) -> None:
        b = self._btns.get(value)
        if b is not None:
            b.setChecked(True)

    def set_allowed(self, values) -> None:
        for v, b in self._btns.items():
            b.setEnabled(v in values)


class RadioDot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.on = False
        self.setFixedSize(18, 18)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1.5, 1.5, 15, 15)
        if self.on:
            p.setPen(QPen(QColor(C["accent"]), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C["accent"]))
            p.drawEllipse(r.adjusted(4, 4, -4, -4))
        else:
            p.setPen(QPen(QColor(C["line_hi"]), 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(r)


class ModelCard(QFrame):
    clicked = Signal()

    def __init__(self, title: str, desc: str, parent=None):
        super().__init__(parent)
        self.setObjectName("ModelCard")
        self.setProperty("selected", False)
        self.setCursor(Qt.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 9, 12, 9)
        lay.setSpacing(11)
        self.dot = RadioDot()
        lay.addWidget(self.dot, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("CardTitle")
        d = QLabel(desc)
        d.setObjectName("CardDesc")
        d.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(d)
        lay.addLayout(col, 1)

    def set_selected(self, on: bool) -> None:
        self.setProperty("selected", on)
        self.dot.on = on
        self.dot.update()
        repolish(self)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class Switch(QAbstractButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)

    def sizeHint(self):
        return QSize(36, 20)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, 35, 19)
        on = self.isChecked()
        p.setPen(Qt.NoPen if on else QPen(QColor(C["line_hi"]), 1))
        p.setBrush(QColor(C["accent"] if on else C["raised"]))
        p.drawRoundedRect(r, 9.5, 9.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["accent_ink"] if on else C["muted"]))
        x = 26 if on else 10
        p.drawEllipse(QPointF(x, 10), 6.5, 6.5)


class DropZone(QFrame):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Drop")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(112)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(14)
        self.thumb = QLabel()
        self.thumb.setFixedSize(76, 76)
        lay.addWidget(self.thumb)
        col = QVBoxLayout()
        col.setSpacing(3)
        col.addStretch()
        self.name = ElidedLabel(mode=Qt.ElideMiddle)
        self.name.setObjectName("CardTitle")
        self.meta = QLabel()
        self.meta.setObjectName("CardDesc")
        self.meta.setWordWrap(True)
        col.addWidget(self.name)
        col.addWidget(self.meta)
        col.addStretch()
        lay.addLayout(col, 1)
        self.set_empty()

    def set_empty(self):
        self.thumb.setPixmap(rounded_thumb(None, 76))
        self.name.setText("Drop an image or folder")
        self.meta.setText("or click to browse\nPNG · JPG · WEBP")
        self.setProperty("filled", False)
        repolish(self)

    def set_content(self, pix: QPixmap | None, name: str, meta: str):
        self.thumb.setPixmap(rounded_thumb(pix, 76))
        self.name.setText(name)
        self.meta.setText(meta)
        self.setProperty("filled", True)
        repolish(self)

    def set_hover(self, on: bool):
        self.setProperty("hover", on)
        repolish(self)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


# ───────────────────────── compare view ─────────────────────────

class CompareView(QWidget):
    """Before/after viewer: drag the divider, scroll to zoom, drag to pan."""
    emptyClicked = Signal()

    PAD = 28

    def __init__(self, parent=None):
        super().__init__(parent)
        self.before: QPixmap | None = None
        self.after: QPixmap | None = None
        self.after_label = "UPSCALED"
        self.split = 0.5
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.progress: float | None = None
        self._drag = None
        self.setMouseTracking(True)
        self.setMinimumSize(420, 320)
        dot = QPixmap(22, 22)
        dot.fill(QColor(C["stage"]))
        dp = QPainter(dot)
        dp.setPen(Qt.NoPen)
        dp.setBrush(QColor(255, 255, 255, 14))
        dp.drawEllipse(QPointF(11, 11), 1, 1)
        dp.end()
        self._grid = QBrush(dot)

    # state ---------------------------------------------------------
    def set_images(self, before: QPixmap | None, after: QPixmap | None = None,
                   after_label: str = "UPSCALED", reset_view: bool = True):
        self.before, self.after, self.after_label = before, after, after_label
        if reset_view:
            self.fit()
        self.update()

    def set_progress(self, value: float | None):
        self.progress = value
        self.update()

    def fit(self):
        self.zoom = 1.0
        self.pan = QPointF(0, 0)
        self.split = 0.5
        self.update()

    # geometry ------------------------------------------------------
    def _ref(self) -> QPixmap | None:
        return self.after or self.before

    def _fit_scale(self) -> float:
        ref = self._ref()
        avail_w = max(1, self.width() - 2 * self.PAD)
        avail_h = max(1, self.height() - 2 * self.PAD)
        return min(avail_w / ref.width(), avail_h / ref.height())

    def _scale(self) -> float:
        return self._fit_scale() * self.zoom

    def image_rect(self) -> QRectF:
        ref = self._ref()
        s = self._scale()
        w, h = ref.width() * s, ref.height() * s
        cx = self.width() / 2 + self.pan.x()
        cy = self.height() / 2 + self.pan.y()
        return QRectF(cx - w / 2, cy - h / 2, w, h)

    def _split_x(self) -> float:
        return self.width() * self.split

    def _near_split(self, pos: QPointF) -> bool:
        return self.after is not None and abs(pos.x() - self._split_x()) <= 14

    # painting ------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        stage = QPainterPath()
        stage.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 16, 16)
        p.setClipPath(stage)
        p.fillRect(self.rect(), self._grid)

        if self.before is None:
            self._paint_empty(p)
        else:
            r = self.image_rect()
            if self.after is not None:
                sx = self._split_x()
                p.save()
                p.setClipRect(QRectF(0, 0, sx, self.height()), Qt.IntersectClip)
                p.drawPixmap(r, self.before, QRectF(self.before.rect()))
                p.restore()
                p.save()
                p.setClipRect(QRectF(sx, 0, self.width() - sx, self.height()), Qt.IntersectClip)
                p.drawPixmap(r, self.after, QRectF(self.after.rect()))
                p.restore()
                self._paint_edge(p, r)
                self._paint_divider(p, sx, r)
                self._pill(p, "ORIGINAL", QPointF(16, 16))
                self._pill(p, self.after_label, QPointF(self.width() - 16, 16), right=True,
                           color=C["accent"])
            else:
                p.drawPixmap(r, self.before, QRectF(self.before.rect()))
                self._paint_edge(p, r)
                if self.progress is not None:
                    self._paint_scan(p, r)
            self._pill(p, f"{self._scale() * 100:.0f}%", QPointF(16, self.height() - 16),
                       bottom=True)

        p.setClipping(False)
        p.setPen(QPen(QColor(C["line"]), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(stage)

    def _paint_edge(self, p: QPainter, r: QRectF):
        p.setPen(QPen(QColor(255, 255, 255, 16), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(r.adjusted(-0.5, -0.5, 0.5, 0.5))

    def _paint_divider(self, p: QPainter, sx: float, r: QRectF):
        top, bottom = max(r.top(), 0), min(r.bottom(), self.height())
        if bottom > top:
            p.setPen(QPen(QColor(0, 0, 0, 90), 4))
            p.drawLine(QPointF(sx, top), QPointF(sx, bottom))
            p.setPen(QPen(QColor(C["accent"]), 2))
            p.drawLine(QPointF(sx, top), QPointF(sx, bottom))
        cy = min(max(self.height() / 2, top + 18), bottom - 18) if bottom - top > 36 else self.height() / 2
        p.setPen(QPen(QColor(C["accent"]), 2))
        p.setBrush(QColor(C["panel"]))
        p.drawEllipse(QPointF(sx, cy), 16, 16)
        pen = QPen(QColor(C["accent"]), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        for d in (-1, 1):
            x = sx + d * 4
            p.drawLine(QPointF(x, cy - 5), QPointF(x + d * 4, cy))
            p.drawLine(QPointF(x + d * 4, cy), QPointF(x, cy + 5))

    def _paint_scan(self, p: QPainter, r: QRectF):
        visible = r.intersected(QRectF(self.rect()))
        y = r.top() + r.height() * max(0.0, min(1.0, self.progress))
        done = QRectF(visible.left(), visible.top(), visible.width(), max(0, y - visible.top()))
        p.fillRect(done, QColor(240, 163, 94, 26))
        grad = QLinearGradient(0, y - 40, 0, y)
        grad.setColorAt(0, QColor(240, 163, 94, 0))
        grad.setColorAt(1, QColor(240, 163, 94, 70))
        p.fillRect(QRectF(visible.left(), y - 40, visible.width(), 40).intersected(visible), grad)
        p.setPen(QPen(QColor(C["accent_hi"]), 2))
        if visible.top() <= y <= visible.bottom():
            p.drawLine(QPointF(visible.left(), y), QPointF(visible.right(), y))

    def _paint_empty(self, p: QPainter):
        c = QPointF(self.width() / 2, self.height() / 2 - 24)
        box = QRectF(c.x() - 44, c.y() - 44, 88, 88)
        pen = QPen(QColor(C["line_hi"]), 1.5, Qt.DashLine)
        pen.setDashPattern([4, 4])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(box, 22, 22)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C["accent"]))
        p.drawPath(star_path(c.x(), c.y(), 18))
        p.setBrush(QColor(C["accent"]).darker(130))
        p.drawPath(star_path(c.x() + 19, c.y() - 17, 6))

        f = QFont(self.font())
        f.setPointSizeF(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(C["text"]))
        p.drawText(QRectF(0, box.bottom() + 22, self.width(), 26), Qt.AlignCenter,
                   "Drop an image to begin")
        f.setPointSizeF(9.5)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        p.setPen(QColor(C["muted"]))
        p.drawText(QRectF(0, box.bottom() + 50, self.width(), 20), Qt.AlignCenter,
                   "PNG, JPG or WEBP — or a whole folder.  Ctrl+O to browse.")

    def _pill(self, p: QPainter, text: str, anchor: QPointF, right=False, bottom=False,
              color: str | None = None):
        f = QFont(self.font())
        f.setPointSizeF(7.5)
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.2)
        p.setFont(f)
        fm = QFontMetrics(f)
        w = fm.horizontalAdvance(text) + 22
        h = fm.height() + 10
        x = anchor.x() - w if right else anchor.x()
        y = anchor.y() - h if bottom else anchor.y()
        rect = QRectF(x, y, w, h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(13, 14, 17, 215))
        p.drawRoundedRect(rect, h / 2, h / 2)
        p.setPen(QColor(color or C["muted"]))
        p.drawText(rect, Qt.AlignCenter, text)

    # interaction ---------------------------------------------------
    def mousePressEvent(self, e):
        if self.before is None:
            if e.button() == Qt.LeftButton:
                self.emptyClicked.emit()
            return
        pos = e.position()
        if e.button() == Qt.LeftButton and self._near_split(pos):
            self._drag = ("split",)
        elif e.button() in (Qt.LeftButton, Qt.MiddleButton):
            self._drag = ("pan", pos, QPointF(self.pan))
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        pos = e.position()
        if self._drag and self._drag[0] == "split":
            self.split = max(0.0, min(1.0, pos.x() / max(1, self.width())))
            self.update()
        elif self._drag and self._drag[0] == "pan":
            _, start, start_pan = self._drag
            self.pan = start_pan + (pos - start)
            self.update()
        else:
            self._hover_cursor(pos)

    def mouseReleaseEvent(self, e):
        self._drag = None
        self._hover_cursor(e.position())

    def _hover_cursor(self, pos: QPointF):
        if self.before is None:
            self.setCursor(Qt.PointingHandCursor)
        elif self._near_split(pos):
            self.setCursor(Qt.SplitHCursor)
        else:
            self.setCursor(Qt.OpenHandCursor)

    def mouseDoubleClickEvent(self, _):
        if self.before is not None:
            self.zoom = 1.0
            self.pan = QPointF(0, 0)
            self.update()

    def wheelEvent(self, e):
        if self.before is None:
            return
        steps = e.angleDelta().y() / 120
        if not steps:
            return
        old = self.image_rect()
        max_zoom = max(1.0, 8.0 / self._fit_scale())  # up to 800 % of output pixels
        self.zoom = max(0.5, min(max_zoom, self.zoom * (1.2 ** steps)))
        pos = e.position()
        fx = (pos.x() - old.left()) / old.width()
        fy = (pos.y() - old.top()) / old.height()
        ref = self._ref()
        s = self._scale()
        nw, nh = ref.width() * s, ref.height() * s
        left, top = pos.x() - fx * nw, pos.y() - fy * nh
        self.pan = QPointF(left + nw / 2 - self.width() / 2, top + nh / 2 - self.height() / 2)
        self.update()


# ───────────────────────── main window ─────────────────────────

PROGRESS_RE = re.compile(r"(\d+(?:\.\d+)?)%")


class MainWindow(QWidget):
    _dl: QNetworkReply | None = None
    _nam: QNetworkAccessManager | None = None

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — anime upscaler")
        self.setWindowIcon(QIcon(app_icon_pixmap(64)))
        self.resize(1360, 900)
        self.setMinimumSize(1040, 640)
        self.setAcceptDrops(True)

        self.settings = QSettings("kirei", "kirei")
        self.source: Path | None = None
        self.folder_images: list[Path] = []
        self.before_pix: QPixmap | None = None
        self.custom_out: Path | None = None
        self.proc: QProcess | None = None
        self.last_output: Path | None = None
        self._buf = ""
        self._cancelled = False
        self._file_idx = 0
        self._last_pct = 0.0
        self._clock = QElapsedTimer()
        self._ticker = QTimer(self)
        self._ticker.setInterval(100)
        self._ticker.timeout.connect(self._tick)

        self._build()
        self._load_settings()
        self._wire_shortcuts()
        self._refresh()

    # ── layout ──────────────────────────────────────────────
    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())
        root.addWidget(self._build_stage(), 1)

    def _section(self, lay: QVBoxLayout, text: str, first=False):
        if not first:
            lay.addSpacing(12)
        lbl = QLabel(text.upper())
        lbl.setObjectName("Section")
        lay.addWidget(lbl)
        lay.addSpacing(2)

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(384)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(0, 0, 0, 0)
        sv.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        inner = QWidget()
        inner.setObjectName("SidebarInner")
        self.sidebar_inner = inner
        il = QVBoxLayout(inner)
        il.setContentsMargins(24, 24, 24, 16)
        il.setSpacing(6)

        # header
        head = QHBoxLayout()
        head.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(app_icon_pixmap(40))
        head.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        name = QLabel(APP_NAME)
        name.setObjectName("AppName")
        sub = QLabel("Real-ESRGAN, without the terminal")
        sub.setObjectName("AppSub")
        titles.addWidget(name)
        titles.addWidget(sub)
        head.addLayout(titles, 1)
        il.addLayout(head)
        il.addSpacing(10)

        # source
        self._section(il, "Source")
        self.drop = DropZone()
        self.drop.clicked.connect(self.choose_image)
        il.addWidget(self.drop)
        row = QHBoxLayout()
        row.setSpacing(6)
        b_img = QPushButton("Choose image…")
        b_img.setObjectName("Ghost")
        b_img.clicked.connect(self.choose_image)
        b_dir = QPushButton("Choose folder…")
        b_dir.setObjectName("Ghost")
        b_dir.clicked.connect(self.choose_folder)
        for b in (b_img, b_dir):
            b.setCursor(Qt.PointingHandCursor)
            row.addWidget(b)
        il.addSpacing(4)
        il.addLayout(row)

        # model
        self._section(il, "Model")
        self.cards: dict[str, ModelCard] = {}
        for mid, title, desc, _scales, _tag in MODELS:
            card = ModelCard(title, desc)
            card.clicked.connect(lambda m=mid: self.set_model(m))
            il.addWidget(card)
            self.cards[mid] = card
        self.model_id = MODELS[0][0]

        # scale
        self._section(il, "Scale")
        self.seg_scale = Segmented([("2×", 2), ("3×", 3), ("4×", 4)])
        self.seg_scale.changed.connect(lambda _v: self._on_option_changed())
        il.addWidget(self.seg_scale)
        self.scale_hint = QLabel()
        self.scale_hint.setObjectName("Hint")
        il.addWidget(self.scale_hint)

        # format
        self._section(il, "Format")
        self.seg_fmt = Segmented([("PNG", "png"), ("WEBP", "webp"), ("JPG", "jpg")])
        self.seg_fmt.changed.connect(lambda _v: self._on_option_changed())
        il.addWidget(self.seg_fmt)

        # output
        self._section(il, "Save to")
        orow = QHBoxLayout()
        orow.setSpacing(6)
        self.out_label = ElidedLabel(mode=Qt.ElideLeft)
        self.out_label.setObjectName("PathLabel")
        orow.addWidget(self.out_label, 1)
        self.btn_out_reset = QPushButton("Reset")
        self.btn_out_reset.setObjectName("Ghost")
        self.btn_out_reset.clicked.connect(self.reset_output)
        b_out = QPushButton("Change…")
        b_out.setObjectName("Ghost")
        b_out.clicked.connect(self.choose_output)
        for b in (self.btn_out_reset, b_out):
            b.setCursor(Qt.PointingHandCursor)
            orow.addWidget(b)
        il.addLayout(orow)

        # advanced
        il.addSpacing(14)
        self.adv_toggle = QToolButton()
        self.adv_toggle.setObjectName("Disclosure")
        self.adv_toggle.setCheckable(True)
        self.adv_toggle.setCursor(Qt.PointingHandCursor)
        self.adv_toggle.toggled.connect(self._toggle_advanced)
        il.addWidget(self.adv_toggle)
        self.adv = QWidget()
        al = QVBoxLayout(self.adv)
        al.setContentsMargins(0, 6, 0, 0)
        al.setSpacing(6)

        tl = QLabel("Tile size")
        tl.setObjectName("FieldLabel")
        al.addWidget(tl)
        self.seg_tile = Segmented([("Auto", 0), ("512", 512), ("256", 256), ("128", 128)])
        self.seg_tile.changed.connect(lambda _v: self._save_settings())
        al.addWidget(self.seg_tile)
        th = QLabel("Smaller tiles use less GPU memory. Lower it if a run fails.")
        th.setObjectName("Hint")
        th.setWordWrap(True)
        al.addWidget(th)

        al.addSpacing(8)
        trow = QHBoxLayout()
        tcol = QVBoxLayout()
        tcol.setSpacing(1)
        ttl = QLabel("TTA mode")
        ttl.setObjectName("FieldLabel")
        tth = QLabel("8 passes per image: slower, slightly cleaner.")
        tth.setObjectName("Hint")
        tcol.addWidget(ttl)
        tcol.addWidget(tth)
        trow.addLayout(tcol, 1)
        self.tta = Switch()
        self.tta.toggled.connect(lambda _v: self._save_settings())
        trow.addWidget(self.tta, 0, Qt.AlignVCenter)
        al.addLayout(trow)

        al.addSpacing(8)
        bl = QLabel("Real-ESRGAN binary")
        bl.setObjectName("FieldLabel")
        al.addWidget(bl)
        brow = QHBoxLayout()
        brow.setSpacing(6)
        self.bin_edit = QLineEdit()
        self.bin_edit.setPlaceholderText(str(DEFAULT_BIN))
        self.bin_edit.editingFinished.connect(self._on_option_changed)
        brow.addWidget(self.bin_edit, 1)
        b_bin = QPushButton("Browse…")
        b_bin.setObjectName("Ghost")
        b_bin.setCursor(Qt.PointingHandCursor)
        b_bin.clicked.connect(self.choose_binary)
        brow.addWidget(b_bin)
        al.addLayout(brow)
        il.addWidget(self.adv)

        il.addStretch(1)
        scroll.setWidget(inner)
        sv.addWidget(scroll, 1)

        # footer
        foot = QFrame()
        foot.setObjectName("Footer")
        fl = QVBoxLayout(foot)
        fl.setContentsMargins(24, 16, 24, 22)
        fl.setSpacing(10)
        srow = QHBoxLayout()
        self.status = ElidedLabel(mode=Qt.ElideRight)
        self.status.setObjectName("Status")
        self.elapsed = QLabel()
        self.elapsed.setObjectName("Elapsed")
        srow.addWidget(self.status, 1)
        srow.addWidget(self.elapsed)
        fl.addLayout(srow)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        fl.addWidget(self.bar)
        self.get_btn = QPushButton(f"Download Real-ESRGAN  ·  {ESRGAN_SIZE_MB} MB")
        self.get_btn.setObjectName("Ghost")
        self.get_btn.setCursor(Qt.PointingHandCursor)
        self.get_btn.setToolTip(f"Installs the official Real-ESRGAN build to {tilde(DEFAULT_BIN.parent)}")
        self.get_btn.clicked.connect(self.download_esrgan)
        self.get_btn.hide()
        fl.addWidget(self.get_btn)
        self.run_btn = QPushButton("Upscale")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.run_or_cancel)
        fl.addWidget(self.run_btn)
        sv.addWidget(foot)
        return side

    def _build_stage(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.title = ElidedLabel(mode=Qt.ElideMiddle)
        self.title.setObjectName("Title")
        top.addWidget(self.title, 1)
        self.chip = QLabel()
        self.chip.setObjectName("Chip")
        top.addWidget(self.chip)
        self.btn_open_img = QPushButton("Open image")
        self.btn_open_img.setObjectName("Ghost")
        self.btn_open_img.clicked.connect(self.open_result)
        self.btn_open_dir = QPushButton("Show in folder")
        self.btn_open_dir.setObjectName("Ghost")
        self.btn_open_dir.clicked.connect(self.open_result_dir)
        for b in (self.btn_open_img, self.btn_open_dir):
            b.setCursor(Qt.PointingHandCursor)
            b.hide()
            top.addWidget(b)
        lay.addLayout(top)

        self.view = CompareView()
        self.view.emptyClicked.connect(self.choose_image)
        lay.addWidget(self.view, 1)

        bottom = QHBoxLayout()
        hint = QLabel("Scroll to zoom  ·  drag to pan  ·  drag the divider to compare  ·  double-click to fit")
        hint.setObjectName("Hint")
        bottom.addWidget(hint, 1)
        self.log_toggle = QToolButton()
        self.log_toggle.setObjectName("Disclosure")
        self.log_toggle.setCheckable(True)
        self.log_toggle.setCursor(Qt.PointingHandCursor)
        self.log_toggle.toggled.connect(self._toggle_log)
        bottom.addWidget(self.log_toggle)
        lay.addLayout(bottom)

        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setFixedHeight(150)
        self.log.setMaximumBlockCount(2000)
        lay.addWidget(self.log)
        self._toggle_log(False)
        return w

    def _wire_shortcuts(self):
        QShortcut(QKeySequence.Open, self, activated=self.choose_image)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self.run_or_cancel)
        QShortcut(QKeySequence("Ctrl+Enter"), self, activated=self.run_or_cancel)
        QShortcut(QKeySequence("Escape"), self, activated=self.cancel)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.view.fit)

    # ── settings ────────────────────────────────────────────
    def _load_settings(self):
        s = self.settings
        self.bin_edit.setText(s.value("binary", str(DEFAULT_BIN)))
        mid = s.value("model", MODELS[0][0])
        self.set_model(mid if mid in MODEL_BY_ID else MODELS[0][0], save=False)
        self.seg_scale.set_value(int(s.value("scale", 4)))
        self._apply_model_scales()
        self.seg_fmt.set_value(s.value("format", "png"))
        self.seg_tile.set_value(int(s.value("tile", 0)))
        self.tta.setChecked(s.value("tta", False, type=bool))
        out = s.value("output", "")
        self.custom_out = Path(out) if out else None
        adv = s.value("advanced_open", False, type=bool)
        self.adv_toggle.setChecked(adv)
        self._toggle_advanced(adv)

    def _save_settings(self):
        s = self.settings
        s.setValue("binary", self.bin_edit.text().strip())
        s.setValue("model", self.model_id)
        s.setValue("scale", self.seg_scale.value())
        s.setValue("format", self.seg_fmt.value())
        s.setValue("tile", self.seg_tile.value())
        s.setValue("tta", self.tta.isChecked())
        s.setValue("output", str(self.custom_out) if self.custom_out else "")
        s.setValue("advanced_open", self.adv_toggle.isChecked())

    # ── option handling ─────────────────────────────────────
    def set_model(self, mid: str, save: bool = True):
        self.model_id = mid
        for k, card in self.cards.items():
            card.set_selected(k == mid)
        self._apply_model_scales()
        if save:
            self._on_option_changed()

    def _apply_model_scales(self):
        allowed = MODEL_BY_ID[self.model_id][3]
        self.seg_scale.set_allowed(allowed)
        if self.seg_scale.value() not in allowed:
            self.seg_scale.set_value(allowed[-1])
        self.scale_hint.setText("This model always enlarges 4×." if len(allowed) == 1
                                else "How many times bigger each side gets.")

    def _on_option_changed(self):
        self._save_settings()
        self._refresh()

    def _toggle_advanced(self, on: bool):
        self.adv.setVisible(on)
        self.adv_toggle.setText(("▾" if on else "▸") + "  Advanced")
        self.settings.setValue("advanced_open", on)

    def _toggle_log(self, on: bool):
        self.log.setVisible(on)
        self.log_toggle.setText(("▾" if on else "▸") + "  Details")

    # ── derived values ──────────────────────────────────────
    @property
    def scale(self) -> int:
        return self.seg_scale.value() or 4

    @property
    def fmt(self) -> str:
        return self.seg_fmt.value() or "png"

    @property
    def is_folder(self) -> bool:
        return self.source is not None and self.source.is_dir()

    def binary(self) -> Path:
        text = self.bin_edit.text().strip()
        return Path(os.path.expanduser(text)) if text else DEFAULT_BIN

    def output_dir(self) -> Path | None:
        if self.custom_out:
            return self.custom_out
        if self.source is None:
            return None
        if self.is_folder:
            return self.source.parent / f"{self.source.name}_upscaled"
        return self.source.parent

    def output_file(self) -> Path:
        tag = MODEL_BY_ID[self.model_id][4]
        base = f"{self.source.stem}_x{self.scale}-{tag}"
        out = self.output_dir() / f"{base}.{self.fmt}"
        n = 2
        while out.exists():
            out = self.output_dir() / f"{base}-{n}.{self.fmt}"
            n += 1
        return out

    # ── source / output pickers ─────────────────────────────
    def _last_dir(self) -> str:
        return self.settings.value("last_dir", str(Path.home() / "Pictures"))

    def choose_image(self):
        if self.running:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose an image", self._last_dir(),
                                              "Images (*.png *.jpg *.jpeg *.webp)")
        if path:
            self.set_source(Path(path))

    def choose_folder(self):
        if self.running:
            return
        path = QFileDialog.getExistingDirectory(self, "Choose a folder of images", self._last_dir())
        if path:
            self.set_source(Path(path))

    def choose_output(self):
        start = str(self.output_dir() or self._last_dir())
        path = QFileDialog.getExistingDirectory(self, "Save upscaled images to", start)
        if path:
            self.custom_out = Path(path)
            self._on_option_changed()

    def reset_output(self):
        self.custom_out = None
        self._on_option_changed()

    def choose_binary(self):
        path, _ = QFileDialog.getOpenFileName(self, "Locate realesrgan-ncnn-vulkan",
                                              str(self.binary().parent))
        if path:
            self.bin_edit.setText(path)
            self._on_option_changed()

    def set_source(self, path: Path):
        if path.is_dir():
            images = list_images(path)
            if not images:
                self._set_status("That folder has no PNG, JPG or WEBP images.", "error")
                return
            pix = QPixmap(str(images[0]))
            self.source, self.folder_images = path, images
            self.before_pix = None if pix.isNull() else pix
            n = len(images)
            self.drop.set_content(self.before_pix, path.name + "/",
                                  f"{n} image{'s' if n != 1 else ''}\nPreviewing {images[0].name}")
            self.settings.setValue("last_dir", str(path.parent))
        elif path.suffix.lower() in IMAGE_EXTS:
            pix = QPixmap(str(path))
            if pix.isNull():
                self._set_status(f"Couldn't read {path.name}.", "error")
                return
            self.source, self.folder_images, self.before_pix = path, [], pix
            self.drop.set_content(pix, path.name,
                                  f"{pix.width()} × {pix.height()}\n{human_size(path.stat().st_size)}")
            self.settings.setValue("last_dir", str(path.parent))
        else:
            self._set_status("Only PNG, JPG and WEBP images are supported.", "error")
            return
        self.last_output = None
        self.view.set_images(self.before_pix)
        self.btn_open_img.hide()
        self.btn_open_dir.hide()
        self.bar.setValue(0)
        self.elapsed.clear()
        self._set_status("Ready.")
        self._refresh()

    # ── refresh ─────────────────────────────────────────────
    def _refresh(self):
        # output path label
        if self.source is None and not self.custom_out:
            self.out_label.setText("Next to the source")
        elif self.custom_out:
            self.out_label.setText(tilde(self.custom_out))
        elif self.is_folder:
            self.out_label.setText(tilde(self.output_dir()))
        else:
            self.out_label.setText("Next to the source")
        self.btn_out_reset.setVisible(self.custom_out is not None)

        # title + size chip
        if self.source is None:
            self.title.setText("No image yet")
            self.chip.hide()
        else:
            self.title.setText(tilde(self.source))
            if self.is_folder:
                n = len(self.folder_images)
                self.chip.setText(f"{n} images  ·  {self.scale}×  ·  {self.fmt.upper()}")
            elif self.before_pix is not None:
                w, h = self.before_pix.width(), self.before_pix.height()
                self.chip.setText(f"{w} × {h}  →  {w * self.scale} × {h * self.scale}")
            self.chip.show()

        if not self.running:
            problem = self._problem()
            self.run_btn.setEnabled(problem is None or problem == "")
            missing = not self.binary().is_file()
            self.get_btn.setVisible(missing or self._dl is not None)
            if self._dl is not None:
                pass  # the download reports its own progress
            elif problem and self.source is not None:
                self._set_status(problem, "error")
            elif missing:
                self._set_status("Real-ESRGAN isn't installed yet.", "error")

    def _problem(self) -> str | None:
        """None = ready, '' = nothing chosen yet, text = what's wrong."""
        b = self.binary()
        if not b.is_file():
            return "Real-ESRGAN isn't installed. Download it below, or set its path under Advanced."
        if not os.access(b, os.X_OK):
            return "The Real-ESRGAN binary isn't executable (chmod +x it)."
        model_file = self.model_id + (f"-x{self.scale}" if self.model_id == "realesr-animevideov3" else "")
        if not (b.parent / "models" / f"{model_file}.param").is_file():
            return f"Model files for {model_file} are missing from {tilde(b.parent / 'models')}."
        if self.source is None:
            return ""
        return None

    # ── getting Real-ESRGAN ─────────────────────────────────
    def download_esrgan(self):
        if self._dl is not None:
            return
        if self._nam is None:
            self._nam = QNetworkAccessManager(self)
        req = QNetworkRequest(QUrl(ESRGAN_URL))
        req.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy)
        self._dl = self._nam.get(req)
        self._dl.downloadProgress.connect(self._dl_progress)
        self._dl.finished.connect(self._dl_finished)
        self.get_btn.setEnabled(False)
        self.get_btn.setText("Downloading…")
        self.bar.setValue(0)
        self._set_status("Downloading Real-ESRGAN…")

    def _dl_progress(self, got: int, total: int):
        if total > 0:
            self.bar.setValue(int(1000 * got / total))
            self._set_status(f"Downloading Real-ESRGAN…  {100 * got / total:.0f}%")

    def _dl_finished(self):
        reply, self._dl = self._dl, None
        reply.deleteLater()
        self.get_btn.setEnabled(True)
        self.get_btn.setText(f"Download Real-ESRGAN  ·  {ESRGAN_SIZE_MB} MB")
        if reply.error() != QNetworkReply.NoError:
            self.bar.setValue(0)
            self._set_status("Couldn't download Real-ESRGAN. Check your connection and try again.", "error")
            return
        data = bytes(reply.readAll())
        if hashlib.sha256(data).hexdigest() != ESRGAN_SHA256:
            self.bar.setValue(0)
            self._set_status("The download wasn't the expected file, so it wasn't installed.", "error")
            return
        try:
            install_esrgan(data, DEFAULT_BIN.parent)
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            self.bar.setValue(0)
            self._set_status(f"Couldn't install Real-ESRGAN: {exc}", "error")
            return
        self.bin_edit.setText(str(DEFAULT_BIN))
        self._on_option_changed()
        self.bar.setValue(1000)
        self._set_status("Real-ESRGAN is installed. Ready.", "ok")

    # ── running ─────────────────────────────────────────────
    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    def run_or_cancel(self):
        if self.running:
            self.cancel()
        else:
            self.start()

    def start(self):
        if self.source is None:
            self.choose_image()
            return
        problem = self._problem()
        if problem:
            self._set_status(problem, "error")
            return

        out_dir = self.output_dir()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._set_status(f"Can't create {tilde(out_dir)}: {exc.strerror}", "error")
            return
        out = out_dir if self.is_folder else self.output_file()
        self.last_output = out

        b = self.binary()
        args = ["-i", str(self.source), "-o", str(out), "-n", self.model_id,
                "-s", str(self.scale), "-f", self.fmt, "-m", str(b.parent / "models")]
        if self.seg_tile.value():
            args += ["-t", str(self.seg_tile.value())]
        if self.tta.isChecked():
            args.append("-x")

        self.log.clear()
        self.log.appendPlainText("$ " + shlex.join([str(b), *args]))

        self.proc = QProcess(self)
        self.proc.setProgram(str(b))
        self.proc.setArguments(args)
        self.proc.setWorkingDirectory(str(b.parent))
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._on_output)
        self.proc.finished.connect(self._on_finished)
        self.proc.errorOccurred.connect(self._on_error)

        self._buf = ""
        self._cancelled = False
        self._file_idx = 0
        self._last_pct = 0.0
        self.bar.setValue(0)
        self.btn_open_img.hide()
        self.btn_open_dir.hide()
        self.view.set_images(self.before_pix, None, reset_view=False)
        self.view.set_progress(0.0)
        self._set_running(True)
        self._set_status("Warming up the GPU…")
        self._clock.start()
        self._ticker.start()
        self.proc.start()

    def cancel(self):
        if self.running:
            self._cancelled = True
            self.proc.kill()

    def _set_running(self, on: bool):
        self.run_btn.setProperty("running", on)
        self.run_btn.setText("Cancel" if on else "Upscale")
        self.run_btn.setEnabled(True)
        repolish(self.run_btn)
        self.sidebar_inner.setEnabled(not on)
        if on:
            eff = QGraphicsOpacityEffect(self.sidebar_inner)
            eff.setOpacity(0.45)
            self.sidebar_inner.setGraphicsEffect(eff)
        else:
            self.sidebar_inner.setGraphicsEffect(None)
        self.setAcceptDrops(not on)

    def _on_output(self):
        self._buf += bytes(self.proc.readAllStandardOutput()).decode(errors="replace")
        parts = re.split(r"[\r\n]", self._buf)
        self._buf = parts.pop()
        for line in parts:
            line = line.strip()
            if not line:
                continue
            m = PROGRESS_RE.fullmatch(line)
            if not m:
                self.log.appendPlainText(line)
                continue
            pct = float(m.group(1))
            if pct + 1 < self._last_pct:  # counter reset → next file
                self._file_idx += 1
            self._last_pct = pct
            total = max(1, len(self.folder_images)) if self.is_folder else 1
            idx = min(self._file_idx, total - 1)
            overall = (idx + pct / 100) / total
            self.bar.setValue(int(overall * 1000))
            if self.is_folder:
                self.view.set_progress(pct / 100 if idx == 0 else None)
                self._set_status(f"Image {idx + 1} of {total}  ·  {pct:.0f}%")
            else:
                self.view.set_progress(pct / 100)
                self._set_status(f"Upscaling…  {pct:.0f}%")

    def _on_finished(self, code: int, status: QProcess.ExitStatus):
        self._ticker.stop()
        took = human_time(self._clock.elapsed())
        self.elapsed.setText(took)
        self._set_running(False)
        self.view.set_progress(None)
        if self._buf.strip():
            self.log.appendPlainText(self._buf.strip())
            self._buf = ""

        if self._cancelled:
            self.bar.setValue(0)
            self._set_status("Cancelled.")
            return

        ok = code == 0 and status == QProcess.NormalExit
        if ok and not self.is_folder:
            ok = self.last_output is not None and self.last_output.is_file()

        if not ok:
            self.bar.setValue(0)
            self._set_status(f"Real-ESRGAN failed (exit {code}). See Details.", "error")
            self.log_toggle.setChecked(True)
            return

        self.bar.setValue(1000)
        label = f"UPSCALED · {self.scale}×"
        if self.is_folder:
            first = self.last_output / f"{self.folder_images[0].stem}.{self.fmt}"
            after = QPixmap(str(first)) if first.is_file() else None
            self.view.set_images(self.before_pix, after if after and not after.isNull() else None,
                                 label, reset_view=False)
            n = len(self.folder_images)
            self._set_status(f"Done — {n} images in {took}.", "ok")
            self.btn_open_dir.show()
        else:
            after = QPixmap(str(self.last_output))
            self.view.set_images(self.before_pix, after, label, reset_view=False)
            size = human_size(self.last_output.stat().st_size)
            self.chip.setText(f"{self.before_pix.width()} × {self.before_pix.height()}  →  "
                              f"{after.width()} × {after.height()}  ·  {size}")
            self._set_status(f"Saved {self.last_output.name}", "ok")
            self.btn_open_img.show()
            self.btn_open_dir.show()

    def _on_error(self, err: QProcess.ProcessError):
        if err == QProcess.FailedToStart:
            self._ticker.stop()
            self._set_running(False)
            self.view.set_progress(None)
            self._set_status("Couldn't start Real-ESRGAN. Check the binary under Advanced.", "error")
            self.log.appendPlainText(self.proc.errorString())
            self.log_toggle.setChecked(True)

    def _tick(self):
        self.elapsed.setText(human_time(self._clock.elapsed()))

    def _set_status(self, text: str, state: str = ""):
        self.status.setText(text)
        self.status.setProperty("state", state)
        repolish(self.status)

    # ── results ─────────────────────────────────────────────
    def open_result(self):
        if self.last_output and self.last_output.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output)))

    def open_result_dir(self):
        if self.last_output:
            target = self.last_output if self.last_output.is_dir() else self.last_output.parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    # ── drag & drop ─────────────────────────────────────────
    def dragEnterEvent(self, e):
        urls = e.mimeData().urls()
        if urls and urls[0].isLocalFile():
            e.acceptProposedAction()
            self.drop.set_hover(True)

    def dragLeaveEvent(self, _):
        self.drop.set_hover(False)

    def dropEvent(self, e):
        self.drop.set_hover(False)
        urls = e.mimeData().urls()
        if urls and urls[0].isLocalFile():
            self.set_source(Path(urls[0].toLocalFile()))

    def closeEvent(self, e):
        if self.running:
            self._cancelled = True
            self.proc.kill()
            self.proc.waitForFinished(2000)
        self._save_settings()
        super().closeEvent(e)


# ───────────────────────── entry point ─────────────────────────

def make_palette() -> QPalette:
    pal = QPalette()
    roles = {
        QPalette.Window: C["bg"], QPalette.WindowText: C["text"], QPalette.Base: C["bg"],
        QPalette.AlternateBase: C["panel"], QPalette.Text: C["text"], QPalette.Button: C["raised"],
        QPalette.ButtonText: C["text"], QPalette.Highlight: C["accent"],
        QPalette.HighlightedText: C["accent_ink"], QPalette.ToolTipBase: C["raised"],
        QPalette.ToolTipText: C["text"], QPalette.PlaceholderText: C["faint"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.Disabled, QPalette.WindowText, QColor(C["faint"]))
    pal.setColor(QPalette.Disabled, QPalette.Text, QColor(C["faint"]))
    return pal


def main() -> int:
    if "--version" in sys.argv:
        print(f"{APP_NAME} {__version__}")
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName("kirei")
    app.setStyle("Fusion")
    app.setPalette(make_palette())
    families = set(QFontDatabase.families())
    for fam in ("Inter", "Noto Sans", "Cantarell", "DejaVu Sans"):
        if fam in families:
            font = QFont(fam, 10)
            font.setHintingPreference(QFont.PreferNoHinting)
            app.setFont(font)
            break
    app.setStyleSheet(build_qss())
    win = MainWindow()
    files = [a for a in sys.argv[1:] if not a.startswith("-")]
    if files:
        win.set_source(Path(files[0]).expanduser())
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
