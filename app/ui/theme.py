"""Visual tokens for the Obsidian Archive inspired desktop UI.

The project intentionally uses system fonts instead of bundling third-party font
files. Segoe UI is used consistently for headings and interface text on Windows,
with Tk fallback on other systems. This avoids the low-legibility serif rendering
seen in the previous desktop build.
"""

import customtkinter as ctk

# Core palette derived from the Stitch reference.
BG = "#0D0C13"
SIDEBAR = "#121118"
SURFACE_LOW = "#161420"
SURFACE = "#1A1824"
SURFACE_RAISED = "#242132"
SURFACE_HIGH = "#2A2736"
BORDER = "#2F2B42"
BORDER_WARM = "#4B3C23"
TEXT = "#F7F4EB"
TEXT_MUTED = "#A7A2B6"
TEXT_DIM = "#7E7892"
AMBER = "#F0B429"
AMBER_BRIGHT = "#FFC857"
AMBER_SOFT = "#FFD481"
AMBER_DARK = "#C98E12"
PURPLE = "#845EC2"
PURPLE_DARK = "#573093"
GREEN = "#38B000"
RED = "#E63946"
BLACK_TEXT = "#121118"

SERIF = "Segoe UI"
SANS = "Segoe UI"


def serif(size: int, weight: str = "normal", slant: str = "roman"):
    return ctk.CTkFont(family=SERIF, size=size, weight=weight, slant=slant)


def sans(size: int, weight: str = "normal"):
    return ctk.CTkFont(family=SANS, size=size, weight=weight)


def apply_obsidian_theme():
    """Apply a dark amber theme to default CustomTkinter widgets.

    Only existing keys are changed so the code remains compatible across
    CustomTkinter minor versions.
    """
    ctk.set_appearance_mode("dark")
    theme = ctk.ThemeManager.theme

    patches = {
        "CTk": {"fg_color": BG},
        "CTkToplevel": {"fg_color": BG},
        "CTkFrame": {"fg_color": SURFACE, "border_color": BORDER},
        "CTkScrollableFrame": {"fg_color": SURFACE, "label_fg_color": SURFACE_RAISED},
        "CTkLabel": {"text_color": TEXT},
        "CTkButton": {
            "fg_color": AMBER,
            "hover_color": AMBER_BRIGHT,
            "border_color": AMBER_DARK,
            "text_color": BLACK_TEXT,
            "text_color_disabled": TEXT_DIM,
        },
        "CTkEntry": {
            "fg_color": SURFACE_LOW,
            "border_color": BORDER,
            "text_color": TEXT,
            "placeholder_text_color": TEXT_DIM,
        },
        "CTkTextbox": {
            "fg_color": SURFACE_LOW,
            "border_color": BORDER,
            "text_color": TEXT,
            "scrollbar_button_color": SURFACE_RAISED,
            "scrollbar_button_hover_color": SURFACE_HIGH,
        },
        "CTkOptionMenu": {
            "fg_color": SURFACE_RAISED,
            "button_color": SURFACE_HIGH,
            "button_hover_color": BORDER,
            "text_color": TEXT,
            "dropdown_fg_color": SURFACE_RAISED,
            "dropdown_hover_color": SURFACE_HIGH,
            "dropdown_text_color": TEXT,
        },
        "CTkComboBox": {
            "fg_color": SURFACE_LOW,
            "border_color": BORDER,
            "button_color": SURFACE_RAISED,
            "button_hover_color": SURFACE_HIGH,
            "text_color": TEXT,
            "dropdown_fg_color": SURFACE_RAISED,
            "dropdown_hover_color": SURFACE_HIGH,
            "dropdown_text_color": TEXT,
        },
        "CTkCheckBox": {
            "fg_color": AMBER,
            "hover_color": AMBER_BRIGHT,
            "border_color": BORDER,
            "text_color": TEXT,
        },
        "CTkSwitch": {
            "button_color": TEXT_MUTED,
            "button_hover_color": TEXT,
            "progress_color": AMBER,
            "fg_color": SURFACE_RAISED,
            "text_color": TEXT,
        },
        "CTkProgressBar": {
            "fg_color": SURFACE_LOW,
            "progress_color": AMBER,
            "border_color": BORDER,
        },
        "CTkSegmentedButton": {
            "fg_color": SURFACE_LOW,
            "selected_color": AMBER,
            "selected_hover_color": AMBER_BRIGHT,
            "unselected_color": SURFACE_LOW,
            "unselected_hover_color": SURFACE_RAISED,
            "text_color": TEXT,
            "text_color_disabled": TEXT_DIM,
        },
    }
    for widget, values in patches.items():
        bucket = theme.get(widget)
        if not isinstance(bucket, dict):
            continue
        for key, value in values.items():
            if key in bucket:
                bucket[key] = value
