"""Render the app icon to a PNG: python tools/export_icon.py OUT.png [SIZE]"""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

import main  # noqa: E402

app = QApplication([])
out = Path(sys.argv[1])
size = int(sys.argv[2]) if len(sys.argv) > 2 else 256
pm = main.app_icon_pixmap(size // 2)  # rendered at 2x internally
pm.setDevicePixelRatio(1)
out.parent.mkdir(parents=True, exist_ok=True)
if not pm.save(str(out)):
    sys.exit(f"could not write {out}")
print(f"wrote {out} ({pm.width()}x{pm.height()})")
