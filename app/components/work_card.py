from pathlib import Path

import customtkinter as ctk
from PIL import Image

from app.ui.theme import (
    AMBER,
    AMBER_BRIGHT,
    BLACK_TEXT,
    BORDER,
    GREEN,
    PURPLE_DARK,
    SURFACE,
    SURFACE_LOW,
    SURFACE_RAISED,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    sans,
    serif,
)


class WorkCard(ctk.CTkFrame):
    """Editorial library row inspired by the Stitch Obsidian Archive card."""

    STATUS_COLORS = {
        "Lendo": AMBER,
        "Concluído": GREEN,
        "Quero ler": TEXT_MUTED,
        "Pausado": "#C7A5FF",
        "Abandonado": "#E63946",
    }

    def __init__(
        self,
        master,
        title,
        category,
        progress_text,
        status,
        percent=0,
        on_increment=None,
        on_decrement=None,
        on_details=None,
        on_favorite=None,
        tags_text="",
        dates_text="",
        favorite=False,
        rating=None,
        cover_path=None,
    ):
        super().__init__(
            master,
            fg_color=SURFACE,
            border_width=1,
            border_color=BORDER,
            corner_radius=16,
        )
        self.grid_columnconfigure(1, weight=1)
        self._cover_image = None

        cover = ctk.CTkFrame(
            self,
            width=104,
            height=150,
            fg_color=SURFACE_LOW,
            border_width=1,
            border_color=BORDER,
            corner_radius=8,
        )
        cover.grid(row=0, column=0, rowspan=7, padx=16, pady=16, sticky="n")
        cover.grid_propagate(False)
        cover_label = ctk.CTkLabel(cover, text="CAPA", text_color=TEXT_DIM, font=sans(10, "bold"))
        cover_label.place(relx=0.5, rely=0.5, anchor="center")
        self._load_cover(cover_label, cover_path)

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(0, 16), pady=(16, 0))
        top.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text=title, font=sans(21, "bold"), anchor="w", text_color=TEXT).grid(
            row=0, column=0, sticky="ew"
        )
        ctk.CTkButton(
            top, text="★" if favorite else "☆", width=38, height=32,
            command=on_favorite, fg_color=SURFACE_RAISED, hover_color=BORDER,
            border_width=1, border_color=BORDER,
            text_color=AMBER if favorite else TEXT_MUTED, font=sans(18, "bold"),
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        meta = ctk.CTkFrame(self, fg_color="transparent")
        meta.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, 16), pady=(4, 0))
        self._badge(meta, status or "Sem status", self.STATUS_COLORS.get(status, TEXT_MUTED)).pack(side="left")
        if category:
            self._badge(meta, category.upper(), PURPLE_DARK).pack(side="left", padx=(7, 0))

        rating_text = self._rating_text(rating)
        ctk.CTkLabel(
            self,
            text=rating_text,
            font=sans(12, "bold"),
            text_color=AMBER if rating is not None else TEXT_DIM,
            anchor="w",
        ).grid(row=2, column=1, sticky="w", padx=(0, 16), pady=(9, 0))

        progress = ctk.CTkProgressBar(self, height=7, corner_radius=99, progress_color=AMBER, fg_color=SURFACE_LOW)
        progress.set(max(0, min(float(percent or 0), 1)))
        progress.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 16), pady=(10, 4))
        ctk.CTkLabel(
            self,
            text=progress_text,
            anchor="w",
            font=sans(12, "bold"),
            text_color=TEXT_MUTED,
        ).grid(row=4, column=1, sticky="w", padx=(0, 16), pady=(0, 2))

        detail_text = "  •  ".join(part for part in [tags_text, dates_text] if part)
        if detail_text:
            ctk.CTkLabel(
                self,
                text=detail_text,
                anchor="w",
                text_color=TEXT_DIM,
                font=sans(11),
                wraplength=650,
                justify="left",
            ).grid(row=5, column=1, columnspan=2, sticky="w", padx=(0, 16), pady=(2, 4))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=6, column=1, columnspan=2, sticky="ew", padx=(0, 16), pady=(7, 16))
        ctk.CTkButton(
            controls,
            text="−1",
            width=42,
            height=32,
            command=on_decrement,
            fg_color=SURFACE_RAISED,
            hover_color=BORDER,
            text_color=TEXT,
            border_width=1,
            border_color=BORDER,
        ).pack(side="left", padx=(0, 5))
        ctk.CTkButton(
            controls,
            text="+1",
            width=42,
            height=32,
            command=on_increment,
            fg_color=SURFACE_RAISED,
            hover_color=BORDER,
            text_color=TEXT,
            border_width=1,
            border_color=BORDER,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            controls,
            text="Ver detalhes",
            width=112,
            height=32,
            command=on_details,
            fg_color=AMBER,
            hover_color=AMBER_BRIGHT,
            text_color=BLACK_TEXT,
            font=sans(12, "bold"),
        ).pack(side="left")

    @staticmethod
    def _badge(master, text, color):
        return ctk.CTkLabel(
            master,
            text=f"  {text}  ",
            height=24,
            corner_radius=12,
            fg_color=color,
            text_color=BLACK_TEXT if color in (AMBER, GREEN) else TEXT,
            font=sans(10, "bold"),
        )

    def _load_cover(self, label, cover_path):
        if not cover_path:
            return
        try:
            path = Path(cover_path)
            if not path.is_file():
                return
            with Image.open(path) as image:
                image = image.convert("RGB")
                image.thumbnail((96, 142))
                rendered = image.copy()
            self._cover_image = ctk.CTkImage(
                light_image=rendered,
                dark_image=rendered,
                size=rendered.size,
            )
            label.configure(image=self._cover_image, text="")
        except Exception:
            return

    @staticmethod
    def _rating_text(rating):
        if rating is None:
            return "☆ Sem avaliação"
        value = float(rating)
        full = int(value)
        half = abs(value - full - 0.5) < 1e-9
        remaining = 5 - full - (1 if half else 0)
        stars = "★" * full + ("½" if half else "") + "☆" * max(remaining, 0)
        number = f"{value:.1f}".replace(".", ",")
        return f"{stars}   {number} / 5"
