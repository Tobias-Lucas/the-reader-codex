from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from app.paths import ASSETS_DIR

ICON_DIR = Path(ASSETS_DIR) / "icons"


@lru_cache(maxsize=256)
def _render_svg_icon(path_str: str, color: str, size: int) -> QIcon:
    svg_path = Path(path_str)
    try:
        svg_text = svg_path.read_text(encoding="utf-8")
    except OSError:
        return QIcon()
    svg_text = re.sub(r'stroke="[^"]+"', f'stroke="{color}"', svg_text)
    svg_text = re.sub(r'fill="(?!none)[^"]+"', f'fill="{color}"', svg_text)
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def icon(name: str, color: str | None = None, size: int = 24) -> QIcon:
    path = ICON_DIR / f"{name}.svg"
    if not path.is_file():
        return QIcon()
    if color:
        return _render_svg_icon(str(path), color, size)
    return QIcon(str(path))
