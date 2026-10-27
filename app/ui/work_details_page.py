from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from app.ui.theme import (
    AMBER, AMBER_BRIGHT, BLACK_TEXT, BORDER, GREEN, PURPLE_DARK, RED,
    SURFACE, SURFACE_LOW, SURFACE_RAISED, TEXT, TEXT_DIM, TEXT_MUTED, sans,
)
from app.utils.dates import iso_to_br, next_release_label, normalize_weekday


class WorkDetailsPage(ctk.CTkFrame):
    STATUS_COLORS = {
        "Lendo": AMBER, "Concluído": GREEN, "Quero ler": TEXT_MUTED,
        "Pausado": "#C7A5FF", "Abandonado": RED,
    }

    def __init__(self, master, repository, work_id, on_back, on_edit, on_changed):
        super().__init__(master, fg_color="transparent")
        self.repository = repository
        self.work_id = work_id
        self.on_back = on_back
        self.on_edit = on_edit
        self.on_changed = on_changed
        self._cover_image = None
        self.grid_columnconfigure(0, weight=1)
        self.render()

    def render(self):
        for child in self.winfo_children():
            child.destroy()
        work = self.repository.get_by_id(self.work_id)
        if work is None:
            self.on_back()
            return
        self.work = work
        self._render_nav()
        self._render_hero()
        self._render_progress()
        self._render_content()

    def _render_nav(self):
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 10))
        ctk.CTkButton(
            nav, text="← Biblioteca", command=self.on_back, width=105, height=34,
            fg_color="transparent", hover_color=SURFACE_RAISED, border_width=1,
            border_color=BORDER, text_color=TEXT_MUTED, font=sans(12, "bold"),
        ).pack(side="left")
        ctk.CTkButton(
            nav, text="Editar cadastro", command=lambda: self.on_edit(self.work_id), width=120, height=34,
            fg_color=SURFACE_RAISED, hover_color=BORDER, border_width=1,
            border_color=BORDER, text_color=TEXT, font=sans(12, "bold"),
        ).pack(side="right")

    def _render_hero(self):
        work = self.work
        hero = ctk.CTkFrame(self, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=16)
        hero.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 12))
        hero.grid_columnconfigure(1, weight=1)

        cover = ctk.CTkFrame(hero, width=220, height=310, fg_color="#0B0A10", border_width=1, border_color=BORDER, corner_radius=10)
        cover.grid(row=0, column=0, rowspan=7, padx=22, pady=22, sticky="n")
        cover.grid_propagate(False)
        label = ctk.CTkLabel(cover, text="CAPA\nINDISPONÍVEL", font=sans(11, "bold"), text_color=TEXT_DIM)
        label.place(relx=0.5, rely=0.5, anchor="center")
        if work.cover_path:
            try:
                path = Path(work.cover_path)
                if path.is_file():
                    with Image.open(path) as image:
                        image = image.convert("RGB")
                        image.thumbnail((210, 300))
                        rendered = image.copy()
                    self._cover_image = ctk.CTkImage(light_image=rendered, dark_image=rendered, size=rendered.size)
                    label.configure(image=self._cover_image, text="")
            except Exception:
                pass

        top = ctk.CTkFrame(hero, fg_color="transparent")
        top.grid(row=0, column=1, sticky="ew", padx=(0, 22), pady=(24, 0))
        top.grid_columnconfigure(0, weight=1)
        status_color = self.STATUS_COLORS.get(work.status, TEXT_MUTED)
        ctk.CTkLabel(
            top, text=f"  {work.status.upper()}  ", fg_color=status_color,
            text_color=BLACK_TEXT if status_color in (AMBER, GREEN) else TEXT,
            corner_radius=10, height=26, font=sans(10, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            top, text="★" if work.favorite else "☆", width=42, height=34,
            command=self._toggle_favorite, fg_color=SURFACE_RAISED, hover_color=BORDER,
            border_width=1, border_color=BORDER, text_color=AMBER if work.favorite else TEXT_MUTED,
            font=sans(18, "bold"),
        ).grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(hero, text=work.name, font=sans(31, "bold"), text_color=TEXT, anchor="w", wraplength=720, justify="left").grid(
            row=1, column=1, sticky="ew", padx=(0, 22), pady=(12, 5)
        )
        meta = []
        if work.category:
            meta.append(work.category)
        if work.start_date:
            meta.append(f"Início: {iso_to_br(work.start_date)}")
        if work.end_date:
            meta.append(f"Conclusão: {iso_to_br(work.end_date)}")
        ctk.CTkLabel(hero, text="  •  ".join(meta) or "Sem metadados adicionais", font=sans(12), text_color=TEXT_MUTED, anchor="w").grid(
            row=2, column=1, sticky="ew", padx=(0, 22), pady=(0, 8)
        )

        chips = ctk.CTkFrame(hero, fg_color="transparent")
        chips.grid(row=3, column=1, sticky="w", padx=(0, 22), pady=(0, 9))
        if work.category:
            self._chip(chips, work.category.upper(), AMBER).pack(side="left", padx=(0, 6))
        for tag in self.repository.get_tags(work.id)[:6]:
            self._chip(chips, tag, PURPLE_DARK).pack(side="left", padx=(0, 6))

        rating_text, rating_color = self._rating_display(work.rating)
        ctk.CTkLabel(hero, text=rating_text, font=sans(16, "bold"), text_color=rating_color, anchor="w").grid(
            row=4, column=1, sticky="w", padx=(0, 22), pady=(4, 8)
        )

        pub_text = self._publication_text(work)
        if pub_text:
            ctk.CTkLabel(hero, text=pub_text, font=sans(12, "bold"), text_color=AMBER, anchor="w").grid(
                row=5, column=1, sticky="w", padx=(0, 22), pady=(0, 10)
            )

    def _publication_text(self, work):
        if work.progress_unit != "Capítulo" or work.progress_total is not None:
            return ""
        day = normalize_weekday(work.release_day)
        if day:
            prediction = next_release_label(day)
            return f"Em lançamento • publicação: {day} • próximo: {prediction}"
        return "Em lançamento • dia de publicação não informado"

    def _render_progress(self):
        work = self.work
        panel = ctk.CTkFrame(self, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=14)
        panel.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 12))
        panel.grid_columnconfigure(0, weight=1)
        total = work.progress_total or 0
        ratio = min(work.progress_current / total, 1.0) if total else 0.0
        if work.progress_unit == "Capítulo" and work.progress_total is None:
            amount = f"Último capítulo lido: {work.progress_current}"
            side = "Em lançamento"
        elif work.progress_unit == "Página" and work.progress_total is None:
            amount = f"Página atual: {work.progress_current}"
            side = "Total não informado"
        else:
            plural = "páginas" if work.progress_unit == "Página" else "capítulos"
            amount = f"{work.progress_current} de {work.progress_total} {plural}"
            side = f"{ratio * 100:.1f}% concluído"
        ctk.CTkLabel(panel, text="PROGRESSO DA LEITURA", font=sans(11, "bold"), text_color=TEXT_MUTED, anchor="w").grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 4)
        )
        ctk.CTkLabel(panel, text=amount, font=sans(18, "bold"), text_color=TEXT, anchor="w").grid(
            row=1, column=0, sticky="w", padx=18
        )
        ctk.CTkLabel(panel, text=side, font=sans(15, "bold"), text_color=AMBER).grid(
            row=1, column=1, sticky="e", padx=18
        )
        bar = ctk.CTkProgressBar(panel, height=7, fg_color="#0B0A10", progress_color=AMBER)
        bar.set(ratio)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(10, 10))
        buttons = ctk.CTkFrame(panel, fg_color="transparent")
        buttons.grid(row=3, column=0, columnspan=2, sticky="w", padx=18, pady=(0, 16))
        for amount_delta in (-1, 1, 5, 10):
            ctk.CTkButton(
                buttons, text=str(amount_delta) if amount_delta < 0 else f"+{amount_delta}",
                width=50, height=32, command=lambda a=amount_delta: self._increment(a),
                fg_color=SURFACE_RAISED, hover_color=BORDER, border_width=1,
                border_color=BORDER, text_color=TEXT,
            ).pack(side="left", padx=(0, 6))

    def _render_content(self):
        work = self.work
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 22))
        grid.grid_columnconfigure(0, weight=3)
        grid.grid_columnconfigure(1, weight=2)

        synopsis = ctk.CTkFrame(grid, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=14)
        synopsis.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        ctk.CTkLabel(synopsis, text="SINOPSE", font=sans(11, "bold"), text_color=AMBER, anchor="w").pack(fill="x", padx=18, pady=(16, 6))
        ctk.CTkLabel(
            synopsis, text=work.synopsis or "Nenhuma sinopse cadastrada.", font=sans(13),
            text_color=TEXT, justify="left", anchor="nw", wraplength=660,
        ).pack(fill="both", expand=True, padx=18, pady=(0, 18))

        quick = ctk.CTkFrame(grid, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=14)
        quick.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        quick.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(quick, text="EDIÇÃO RÁPIDA", font=sans(11, "bold"), text_color=AMBER, anchor="w").grid(
            row=0, column=0, sticky="ew", padx=16, pady=(16, 5)
        )
        ctk.CTkLabel(quick, text="Status da leitura", font=sans(10, "bold"), text_color=TEXT_MUTED, anchor="w").grid(
            row=1, column=0, sticky="ew", padx=16, pady=(5, 4)
        )
        self.status_menu = ctk.CTkOptionMenu(quick, values=list(self.repository.STATUS_OPTIONS), height=38, font=sans(12), dropdown_font=sans(12))
        self.status_menu.set(work.status)
        self.status_menu.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        ctk.CTkLabel(quick, text="Notas pessoais", font=sans(10, "bold"), text_color=TEXT_MUTED, anchor="w").grid(
            row=3, column=0, sticky="ew", padx=16, pady=(5, 4)
        )
        self.notes_text = ctk.CTkTextbox(quick, height=125, border_width=1, font=sans(12))
        self.notes_text.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 10))
        self.notes_text.insert("1.0", work.personal_notes or "")
        ctk.CTkButton(
            quick, text="Salvar status e notas", command=self._save_quick_edit,
            height=38, fg_color=AMBER, hover_color=AMBER_BRIGHT,
            text_color=BLACK_TEXT, font=sans(12, "bold"),
        ).grid(row=5, column=0, sticky="ew", padx=16, pady=(0, 16))

    @staticmethod
    def _chip(master, text, color):
        return ctk.CTkLabel(
            master, text=f"  {text}  ", height=24, corner_radius=12, fg_color=color,
            text_color=BLACK_TEXT if color == AMBER else TEXT, font=sans(9, "bold"),
        )

    @staticmethod
    def _rating_display(rating):
        if rating is None:
            return "☆☆☆☆☆  Sem avaliação", TEXT_DIM
        value = float(rating)
        full = int(value)
        half = abs(value - full - 0.5) < 1e-9
        remaining = 5 - full - (1 if half else 0)
        stars = "★" * full + ("½" if half else "") + "☆" * max(remaining, 0)
        return f"{stars}   {str(f'{value:.1f}').replace('.', ',')} / 5", AMBER

    def _update_work(self, **changes):
        work = self.work
        data = dict(
            name=work.name, category=work.category, progress_unit=work.progress_unit,
            progress_current=work.progress_current, progress_total=work.progress_total,
            status=work.status, release_day=work.release_day, synopsis=work.synopsis,
            rating=work.rating, favorite=work.favorite, personal_notes=work.personal_notes,
            start_date=work.start_date, end_date=work.end_date,
        )
        data.update(changes)
        self.repository.update_work(work.id, **data)
        self.on_changed()
        self.render()

    def _toggle_favorite(self):
        try:
            self._update_work(favorite=not self.work.favorite)
        except Exception as exc:
            messagebox.showerror("Favorito", str(exc), parent=self.winfo_toplevel())

    def _increment(self, amount):
        try:
            self.repository.increment_progress(self.work.id, amount)
            self.on_changed()
            self.render()
        except Exception as exc:
            messagebox.showerror("Progresso", str(exc), parent=self.winfo_toplevel())

    def _save_quick_edit(self):
        try:
            self._update_work(
                status=self.status_menu.get(),
                personal_notes=self.notes_text.get("1.0", "end").strip(),
            )
        except Exception as exc:
            messagebox.showerror("Detalhes da obra", str(exc), parent=self.winfo_toplevel())
