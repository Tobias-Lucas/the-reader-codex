from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase

from app.paths import ASSETS_DIR

# Nocturne Folio visual system (desktop Qt adaptation)
BG = "#0F1012"
SIDEBAR = "#16181B"
SURFACE = "#1E2024"
SURFACE_2 = "#181A1F"
SURFACE_3 = "#24272C"
SURFACE_4 = "#2B2E34"
BORDER = "#282B30"
BORDER_SOFT = "#1F2126"
TEXT = "#F4EFEA"
TEXT_MUTED = "#9E9B95"
TEXT_DIM = "#756E64"
AMBER = "#E5A93C"
AMBER_HOVER = "#F2BA58"
AMBER_DARK = "#2F271A"
SECONDARY = "#D97706"
GREEN = "#5B8266"
RED = "#B34045"
BLUE = "#617FA9"


def preferred_ui_font_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in ("Plus Jakarta Sans", "Segoe UI Variable", "Segoe UI", "Inter", "Noto Sans", "Arial"):
        if candidate in families:
            return candidate
    return "Sans Serif"


def preferred_display_font_family() -> str:
    families = set(QFontDatabase.families())
    for candidate in ("Newsreader", "Cormorant Garamond", "Georgia", "Palatino Linotype", "Times New Roman", "Noto Serif"):
        if candidate in families:
            return candidate
    return preferred_ui_font_family()


def preferred_font_family() -> str:
    """Backward-compatible alias for entry points from earlier 2.x builds."""
    return preferred_ui_font_family()


def app_stylesheet() -> str:
    ui_family = preferred_ui_font_family().replace('"', '')
    display_family = preferred_display_font_family().replace('"', '')
    combo_arrow = (Path(ASSETS_DIR) / "icons" / "chevron-down.svg").as_posix()
    return f"""
    * {{
        font-family: \"{ui_family}\";
        font-size: 13px;
        color: {TEXT};
        outline: none;
    }}
    QMainWindow, QWidget#appRoot {{ background: {BG}; }}
    QWidget {{ background: transparent; }}

    QFrame#sidebar {{
        background: {SIDEBAR};
        border: none;
        border-right: 1px solid {BORDER_SOFT};
    }}
    QFrame#topbar {{
        background: {BG};
        border: none;
        border-bottom: 1px solid {BORDER_SOFT};
    }}
    QFrame#panel, QFrame#workCard, QFrame#metricCard, QFrame#releaseCard {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 4px;
    }}
    QFrame#subPanel {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        border-radius: 4px;
    }}
    QFrame#sidebarTile {{
        background: {SURFACE_2};
        border: 1px solid {BORDER_SOFT};
        border-radius: 4px;
    }}

    QLabel#brand {{
        font-family: \"{display_family}\";
        font-size: 18px;
        font-weight: 600;
        color: {TEXT};
        letter-spacing: -0.01em;
    }}
    QLabel#brandSub {{
        font-size: 10px;
        font-weight: 600;
        color: {TEXT_MUTED};
        letter-spacing: 1.5px;
    }}
    QLabel#pageEyebrow {{
        font-size: 11px;
        font-weight: 600;
        color: {TEXT_DIM};
        letter-spacing: 1.4px;
        text-transform: uppercase;
    }}
    QLabel#pageTitle {{
        font-family: \"{display_family}\";
        font-size: 44px;
        font-weight: 500;
        color: {TEXT};
        letter-spacing: -0.02em;
        line-height: 1.05em;
    }}
    QLabel#pageSubtitle {{
        font-family: \"{display_family}\";
        font-size: 18px;
        color: #D8CDBF;
        line-height: 1.4em;
    }}
    QLabel#sectionTitle {{
        font-family: \"{display_family}\";
        font-size: 18px;
        font-weight: 600;
        color: {TEXT};
    }}
    QLabel#fieldLabel {{
        font-size: 10px;
        font-weight: 700;
        color: {TEXT_DIM};
        letter-spacing: 1px;
    }}
    QLabel#muted {{ color: {TEXT_MUTED}; }}
    QLabel#dim {{ color: {TEXT_DIM}; }}
    QLabel#workTitle {{
        font-family: \"{display_family}\";
        font-size: 22px;
        font-weight: 600;
        color: {TEXT};
        letter-spacing: -0.01em;
    }}
    QLabel#publicationStatus {{ font-size: 11px; font-weight: 500; color: {TEXT_MUTED}; }}
    QLabel#progressCaption {{ font-size: 10px; font-weight: 700; color: {TEXT_DIM}; letter-spacing: 1px; }}
    QLabel#progressValue {{
        font-family: \"{display_family}\";
        font-size: 19px;
        font-weight: 600;
        color: {TEXT};
    }}
    QLabel#progressUnit {{ font-size: 13px; color: {TEXT_MUTED}; font-style: italic; }}
    QLabel#pending {{ color: {AMBER}; font-weight: 650; }}
    QLabel#danger {{ color: {RED}; font-weight: 650; }}
    QLabel#success {{ color: {GREEN}; font-weight: 650; }}
    QLabel#rating {{ color: {AMBER}; font-weight: 650; }}
    QLabel#heroStatValue {{
        font-family: \"{display_family}\";
        font-size: 32px;
        font-weight: 600;
        color: {TEXT};
    }}
    QLabel#heroStatLabel {{
        font-size: 11px;
        font-weight: 700;
        color: {TEXT_DIM};
        letter-spacing: 1px;
    }}

    QPushButton {{
        min-height: 36px;
        padding: 0 13px;
        border-radius: 4px;
        border: 1px solid {BORDER};
        background: {SURFACE_2};
        color: {TEXT};
        font-weight: 600;
    }}
    QPushButton:hover {{ background: {SURFACE_3}; border-color: #343840; }}
    QPushButton:pressed {{ background: #15181C; }}
    QPushButton:disabled {{ color: #5D5852; background: #121417; border-color: #1A1D22; }}
    QPushButton#primary {{ background: {AMBER}; color: #17130A; border-color: {AMBER}; font-weight: 750; }}
    QPushButton#primary:hover {{ background: {AMBER_HOVER}; border-color: {AMBER_HOVER}; }}
    QPushButton#ghost {{ background: transparent; border-color: transparent; color: {TEXT_MUTED}; }}
    QPushButton#ghost:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
    QPushButton#dangerButton {{ background: transparent; color: #E6B4B0; border-color: #5C3435; }}
    QPushButton#dangerButton:hover {{ background: #261719; border-color: #714143; }}
    QPushButton#favorite {{ min-width: 36px; max-width: 36px; padding: 0; background: transparent; border-color: transparent; }}
    QPushButton#favorite:hover {{ background: {SURFACE_2}; }}
    QPushButton#nav {{
        background: transparent;
        border: none;
        text-align: left;
        color: {TEXT_MUTED};
        min-height: 38px;
        padding-left: 12px;
        font-weight: 560;
        border-radius: 4px;
    }}
    QPushButton#nav:hover {{ background: {SURFACE}; color: {TEXT}; }}
    QPushButton#nav[active="true"] {{ background: {SURFACE_2}; color: {TEXT}; font-weight: 700; }}
    QPushButton#chip {{
        min-height: 24px;
        max-height: 24px;
        padding: 0 9px;
        border-radius: 999px;
        background: {SURFACE_3};
        color: {TEXT_MUTED};
        border: none;
        font-size: 10px;
        font-weight: 600;
    }}
    QPushButton#chip[accent="true"] {{ background: {AMBER_DARK}; color: {AMBER}; }}

    QLineEdit, QTextEdit, QPlainTextEdit, QDateEdit {{
        background: #111316;
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 8px 10px;
        min-height: 24px;
        selection-background-color: {AMBER};
        selection-color: #111;
    }}
    QComboBox {{
        background: #111316;
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 8px 38px 8px 10px;
        min-height: 24px;
        selection-background-color: {AMBER};
        selection-color: #111;
    }}
    QSpinBox, QDoubleSpinBox {{
        background: #111316;
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 8px 10px;
        min-height: 24px;
        selection-background-color: {AMBER};
        selection-color: #111;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
        border-color: {AMBER};
    }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 30px;
        border-left: 1px solid {BORDER};
        background: {SURFACE_2};
        border-top-right-radius: 4px;
        border-bottom-right-radius: 4px;
    }}
    QComboBox::down-arrow {{ image: url({combo_arrow}); width: 12px; height: 12px; }}
    QComboBox QAbstractItemView {{ background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {SURFACE_3}; }}
    QToolButton#stepperButton {{
        background: {SURFACE_2};
        border: 1px solid {BORDER};
        min-height: 38px;
        padding: 0;
        font-size: 14px;
        font-weight: 700;
        border-radius: 4px;
    }}
    QToolButton#stepperButton:hover {{ background: {SURFACE_3}; }}
    QToolButton#stepperButton:disabled {{ color: #5D5852; }}
    QLineEdit#stepperField {{
        background: #111316;
        border-top: 1px solid {BORDER};
        border-bottom: 1px solid {BORDER};
        border-left: none;
        border-right: none;
        border-radius: 0;
        padding: 8px 6px;
        min-height: 22px;
        font-size: 18px;
        font-weight: 700;
        qproperty-alignment: AlignCenter;
    }}
    QCheckBox {{ spacing: 7px; color: {TEXT_MUTED}; }}
    QCheckBox::indicator {{ width: 15px; height: 15px; border-radius: 3px; border: 1px solid #605A50; background: #111316; }}
    QCheckBox::indicator:checked {{ background: {AMBER}; border-color: {AMBER}; }}
    QProgressBar {{ border: none; border-radius: 2px; background: #121417; min-height: 6px; max-height: 6px; text-align: center; color: transparent; }}
    QProgressBar::chunk {{ border-radius: 2px; background: {AMBER}; }}
    QScrollArea {{ border: none; background: {BG}; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 3px; }}
    QScrollBar::handle:vertical {{ background: #2E3137; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ height: 9px; background: transparent; }}
    QScrollBar::handle:horizontal {{ background: #2E3137; border-radius: 4px; }}
    QSlider::groove:horizontal {{ border: none; height: 6px; background: #111316; border-radius: 3px; }}
    QSlider::sub-page:horizontal {{ background: {AMBER}; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {AMBER_HOVER}; width: 14px; margin: -4px 0; border-radius: 7px; }}
    QToolTip {{ background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px; }}
    QCalendarWidget QWidget {{ background: {SURFACE}; color: {TEXT}; }}
    QCalendarWidget QAbstractItemView {{ selection-background-color: {AMBER}; selection-color: #111; }}
    QTableWidget {{
        background: {SURFACE};
        alternate-background-color: {SURFACE_2};
        border: 1px solid {BORDER};
        border-radius: 4px;
        gridline-color: {BORDER};
    }}
    QHeaderView::section {{ background: {SURFACE_2}; color: {TEXT_MUTED}; border: none; padding: 8px; font-weight: 650; }}
    """
