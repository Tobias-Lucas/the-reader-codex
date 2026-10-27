from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image

from app.ui.date_field import DateField
from app.ui.theme import (
    AMBER, AMBER_BRIGHT, BLACK_TEXT, BORDER, RED, SURFACE, SURFACE_LOW,
    SURFACE_RAISED, TEXT, TEXT_DIM, TEXT_MUTED, sans,
)
from app.utils.dates import WEEKDAYS_PT, normalize_weekday


class WorkFormPage(ctk.CTkFrame):
    RATING_OPTIONS = [
        "Sem avaliação", "0,5", "1,0", "1,5", "2,0", "2,5",
        "3,0", "3,5", "4,0", "4,5", "5,0",
    ]

    def __init__(self, master, repository, on_saved, on_cancel, on_deleted=None, work=None):
        super().__init__(master, fg_color="transparent")
        self.repository = repository
        self.work = work
        self.on_saved = on_saved
        self.on_cancel = on_cancel
        self.on_deleted = on_deleted or on_cancel
        self._selected_cover_source = None
        self._remove_cover = False
        self._cover_image = None
        self.grid_columnconfigure(0, weight=1)
        self._build(work is not None)
        self._fill_existing_values()
        self._refresh_progress_preview()
        self._refresh_rating_preview(self.rating_menu.get())

    def _build(self, editing):
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 10))
        ctk.CTkButton(
            nav, text="← Voltar", width=90, height=34, command=self.on_cancel,
            fg_color="transparent", hover_color=SURFACE_RAISED, border_width=1,
            border_color=BORDER, text_color=TEXT_MUTED, font=sans(12, "bold"),
        ).pack(side="left")
        ctk.CTkLabel(
            nav, text="EDITAR OBRA" if editing else "NOVA OBRA",
            font=sans(11, "bold"), text_color=AMBER,
        ).pack(side="left", padx=12)

        header = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        header.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 14))
        ctk.CTkLabel(
            header, text="Editar obra" if editing else "Cadastrar nova obra",
            font=sans(30, "bold"), text_color=TEXT, anchor="w",
        ).pack(fill="x", padx=24, pady=(20, 4))
        ctk.CTkLabel(
            header,
            text="Mantenha capa, classificação, progresso, lançamento e organização da obra em um único cadastro.",
            font=sans(13), text_color=TEXT_MUTED, anchor="w",
        ).pack(fill="x", padx=24, pady=(0, 20))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=6)
        body.grid_columnconfigure(0, minsize=280)
        body.grid_columnconfigure(1, weight=1)
        self._build_left(body)
        self._build_right(body)
        self._build_actions()

    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        left.grid(row=0, column=0, sticky="new", padx=(0, 10))
        left.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(left, text="CAPA", font=sans(11, "bold"), text_color=TEXT_MUTED).grid(
            row=0, column=0, sticky="w", padx=20, pady=(18, 8)
        )
        cover = ctk.CTkFrame(left, width=220, height=310, fg_color="#0B0A10", border_width=1, border_color=BORDER, corner_radius=10)
        cover.grid(row=1, column=0, padx=24, pady=(0, 12))
        cover.grid_propagate(False)
        self.cover_preview = ctk.CTkLabel(
            cover, text="Adicionar capa\nPNG, JPG, WEBP ou GIF", justify="center",
            font=sans(12, "bold"), text_color=TEXT_MUTED,
        )
        self.cover_preview.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkButton(left, text="Selecionar capa", command=self._select_cover, height=38, font=sans(12, "bold")).grid(
            row=2, column=0, sticky="ew", padx=20, pady=(0, 7)
        )
        ctk.CTkButton(
            left, text="Remover capa", command=self._mark_cover_for_removal, height=34,
            fg_color="transparent", hover_color=SURFACE_RAISED, border_width=1,
            border_color=BORDER, text_color=TEXT_MUTED,
        ).grid(row=3, column=0, sticky="ew", padx=20, pady=(0, 18))

        favorite = ctk.CTkFrame(left, fg_color=SURFACE_LOW, corner_radius=10)
        favorite.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 18))
        favorite.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(favorite, text="★ Favorito", font=sans(12, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 2)
        )
        ctk.CTkLabel(favorite, text="Também pode ser alterado no card.", font=sans(10), text_color=TEXT_DIM, anchor="w").grid(
            row=1, column=0, sticky="w", padx=14, pady=(0, 12)
        )
        self.favorite_var = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(favorite, text="", variable=self.favorite_var, width=44).grid(row=0, column=1, rowspan=2, padx=14)

    def _label(self, parent, text, row, column=0, span=1, padx=18):
        ctk.CTkLabel(parent, text=text, font=sans(10, "bold"), text_color=TEXT_MUTED, anchor="w").grid(
            row=row, column=column, columnspan=span, sticky="ew", padx=padx, pady=(9, 5)
        )

    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_columnconfigure(1, weight=1)
        row = 0
        self._label(right, "TÍTULO DA OBRA *", row, 0, 2)
        self.name_entry = ctk.CTkEntry(right, placeholder_text="Ex.: Nano Machine", height=44, font=sans(14, "bold"))
        self.name_entry.grid(row=row + 1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 8))
        row += 2
        self._label(right, "CATEGORIA", row, 0)
        self._label(right, "STATUS DA LEITURA", row, 1)
        categories = [item["name"] for item in self.repository.list_categories()]
        self.category_combo = ctk.CTkComboBox(right, values=categories or [""], height=40, font=sans(12), dropdown_font=sans(12))
        self.category_combo.grid(row=row + 1, column=0, sticky="ew", padx=(18, 7), pady=(0, 8))
        self.status_menu = ctk.CTkOptionMenu(right, values=list(self.repository.STATUS_OPTIONS), height=40, font=sans(12), dropdown_font=sans(12))
        self.status_menu.grid(row=row + 1, column=1, sticky="ew", padx=(7, 18), pady=(0, 8))
        row += 2
        self._label(right, "TAGS", row, 0, 2)
        self.tags_entry = ctk.CTkEntry(right, placeholder_text="ação, fantasia, manhwa", height=40, font=sans(12))
        self.tags_entry.grid(row=row + 1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))
        row += 2

        progress = ctk.CTkFrame(right, fg_color=SURFACE_LOW, corner_radius=12)
        progress.grid(row=row, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))
        progress.grid_columnconfigure(0, weight=1)
        progress.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(progress, text="RASTREAMENTO DE PROGRESSO", font=sans(12, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=14, pady=(12, 6)
        )
        self.unit_menu = ctk.CTkSegmentedButton(progress, values=list(self.repository.PROGRESS_UNITS), height=31, command=lambda _v: self._refresh_progress_preview())
        self.unit_menu.grid(row=0, column=1, sticky="e", padx=14, pady=(10, 6))
        self._label(progress, "ÚLTIMO REGISTRO LIDO", 1, 0, padx=14)
        self._label(progress, "TOTAL PREVISTO (OPCIONAL)", 1, 1, padx=14)
        self.current_var = ctk.StringVar(value="0")
        self.total_var = ctk.StringVar(value="")
        self.current_entry = ctk.CTkEntry(progress, textvariable=self.current_var, height=40, font=sans(12))
        self.current_entry.grid(row=2, column=0, sticky="ew", padx=(14, 6), pady=(0, 7))
        self.total_entry = ctk.CTkEntry(progress, textvariable=self.total_var, placeholder_text="Deixe vazio se ainda estiver em lançamento", height=40, font=sans(12))
        self.total_entry.grid(row=2, column=1, sticky="ew", padx=(6, 14), pady=(0, 7))
        self.current_var.trace_add("write", lambda *_: self._refresh_progress_preview())
        self.total_var.trace_add("write", lambda *_: self._refresh_progress_preview())
        self.progress_bar = ctk.CTkProgressBar(progress, height=7, fg_color="#0B0A10", progress_color=AMBER)
        self.progress_bar.grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(5, 4))
        self.progress_text = ctk.CTkLabel(progress, text="", font=sans(11, "bold"), text_color=AMBER, anchor="e")
        self.progress_text.grid(row=4, column=0, columnspan=2, sticky="e", padx=14, pady=(0, 12))
        row += 1

        rating = ctk.CTkFrame(right, fg_color=SURFACE_LOW, corner_radius=12)
        rating.grid(row=row, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))
        rating.grid_columnconfigure(0, weight=1)
        self.rating_preview = ctk.CTkLabel(rating, text="☆☆☆☆☆  Sem avaliação", font=sans(16, "bold"), text_color=TEXT_DIM, anchor="w")
        self.rating_preview.grid(row=0, column=0, sticky="w", padx=14, pady=12)
        self.rating_menu = ctk.CTkOptionMenu(rating, values=self.RATING_OPTIONS, width=155, command=self._refresh_rating_preview, font=sans(12), dropdown_font=sans(12))
        self.rating_menu.grid(row=0, column=1, sticky="e", padx=14, pady=12)
        row += 1

        self._label(right, "DATA DE INÍCIO", row, 0)
        self._label(right, "DATA DE CONCLUSÃO", row, 1)
        self.start_date = DateField(right)
        self.start_date.grid(row=row + 1, column=0, sticky="ew", padx=(18, 7), pady=(0, 8))
        self.end_date = DateField(right)
        self.end_date.grid(row=row + 1, column=1, sticky="ew", padx=(7, 18), pady=(0, 8))
        row += 2

        self._label(right, "DIA DE LANÇAMENTO / PUBLICAÇÃO", row, 0, 2)
        self.release_day = ctk.CTkOptionMenu(
            right, values=["Sem dia fixo", *WEEKDAYS_PT], height=40, font=sans(12), dropdown_font=sans(12)
        )
        self.release_day.grid(row=row + 1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 10))
        row += 2
        self._label(right, "SINOPSE", row, 0, 2)
        self.synopsis_text = ctk.CTkTextbox(right, height=105, corner_radius=9, border_width=1, font=sans(12))
        self.synopsis_text.grid(row=row + 1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 10))
        row += 2
        self._label(right, "NOTAS PESSOAIS", row, 0, 2)
        self.notes_text = ctk.CTkTextbox(right, height=105, corner_radius=9, border_width=1, font=sans(12))
        self.notes_text.grid(row=row + 1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18))

    def _build_actions(self):
        actions = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=14, border_width=1, border_color=BORDER)
        actions.grid(row=3, column=0, sticky="ew", padx=6, pady=(14, 20))
        if self.work is not None:
            ctk.CTkButton(
                actions, text="Excluir obra", command=self._delete, fg_color="transparent",
                hover_color="#3A1B22", border_width=1, border_color=RED,
                text_color="#FFB4AB", height=40,
            ).pack(side="left", padx=16, pady=14)
        ctk.CTkButton(
            actions, text="Cancelar", command=self.on_cancel, fg_color=SURFACE_RAISED,
            hover_color=BORDER, text_color=TEXT, height=40, width=110,
        ).pack(side="right", padx=(7, 16), pady=14)
        ctk.CTkButton(
            actions, text="Salvar obra", command=self.save, fg_color=AMBER,
            hover_color=AMBER_BRIGHT, text_color=BLACK_TEXT, font=sans(12, "bold"),
            height=40, width=135,
        ).pack(side="right", pady=14)

    def _fill_existing_values(self):
        if self.work is None:
            self.status_menu.set("Quero ler")
            self.unit_menu.set("Página")
            self.rating_menu.set("Sem avaliação")
            self.release_day.set("Sem dia fixo")
            return
        work = self.work
        self.name_entry.insert(0, work.name)
        self.category_combo.set(work.category or "")
        self.status_menu.set(work.status)
        self.unit_menu.set(work.progress_unit)
        self.current_var.set(str(work.progress_current))
        if work.progress_total is not None:
            self.total_var.set(str(work.progress_total))
        self.rating_menu.set("Sem avaliação" if work.rating is None else f"{work.rating:.1f}".replace(".", ","))
        self.favorite_var.set(work.favorite)
        self.start_date.set_iso(work.start_date)
        self.end_date.set_iso(work.end_date)
        normalized = normalize_weekday(work.release_day)
        values = ["Sem dia fixo", *WEEKDAYS_PT]
        if normalized and normalized not in values:
            values.append(normalized)
            self.release_day.configure(values=values)
        self.release_day.set(normalized or "Sem dia fixo")
        self.tags_entry.insert(0, ", ".join(self.repository.get_tags(work.id)))
        self.synopsis_text.insert("1.0", work.synopsis or "")
        self.notes_text.insert("1.0", work.personal_notes or "")
        if work.cover_path:
            self._show_cover(work.cover_path)

    def _select_cover(self):
        path = filedialog.askopenfilename(
            parent=self.winfo_toplevel(), title="Selecionar capa",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.gif"), ("Todos os arquivos", "*.*")],
        )
        if not path:
            return
        try:
            with Image.open(Path(path)) as image:
                image.verify()
        except Exception:
            messagebox.showerror("Capa inválida", "O arquivo selecionado não é uma imagem válida.", parent=self.winfo_toplevel())
            return
        self._selected_cover_source = path
        self._remove_cover = False
        self._show_cover(path)

    def _show_cover(self, path):
        try:
            with Image.open(Path(path)) as image:
                image = image.convert("RGB")
                image.thumbnail((210, 300))
                rendered = image.copy()
            self._cover_image = ctk.CTkImage(light_image=rendered, dark_image=rendered, size=rendered.size)
            self.cover_preview.configure(image=self._cover_image, text="")
        except Exception:
            self.cover_preview.configure(image=None, text="Capa indisponível")
            self._cover_image = None

    def _mark_cover_for_removal(self):
        self._selected_cover_source = None
        self._remove_cover = True
        self._cover_image = None
        self.cover_preview.configure(image=None, text="Adicionar capa\nPNG, JPG, WEBP ou GIF")

    def _refresh_progress_preview(self):
        if not hasattr(self, "progress_bar"):
            return
        try:
            current = max(int(self.current_var.get() or 0), 0)
        except ValueError:
            current = 0
        try:
            total = int(self.total_var.get()) if self.total_var.get().strip() else 0
        except ValueError:
            total = 0
        ratio = min(current / total, 1.0) if total > 0 else 0.0
        self.progress_bar.set(ratio)
        unit = self.unit_menu.get() if hasattr(self, "unit_menu") else "Página"
        if total > 0:
            plural = "páginas" if unit == "Página" else "capítulos"
            self.progress_text.configure(text=f"{ratio * 100:.1f}% concluído • {current} / {total} {plural}")
        elif unit == "Capítulo":
            self.progress_text.configure(text=f"Último capítulo lido: {current} • Em lançamento")
        else:
            self.progress_text.configure(text=f"Página atual: {current} • total ainda não informado")

    def _refresh_rating_preview(self, value):
        if not hasattr(self, "rating_preview"):
            return
        if value == "Sem avaliação":
            self.rating_preview.configure(text="☆☆☆☆☆  Sem avaliação", text_color=TEXT_DIM)
            return
        rating = float(value.replace(",", "."))
        full = int(rating)
        half = abs(rating - full - 0.5) < 1e-9
        remaining = 5 - full - (1 if half else 0)
        stars = "★" * full + ("½" if half else "") + "☆" * max(remaining, 0)
        self.rating_preview.configure(text=f"{stars}   {value} / 5", text_color=AMBER)

    @staticmethod
    def _parse_int(value, field_name, allow_blank=False):
        value = value.strip()
        if not value and allow_blank:
            return None
        try:
            return int(value or "0")
        except ValueError as exc:
            raise ValueError(f"{field_name} deve ser um número inteiro.") from exc

    def _rating_value(self):
        value = self.rating_menu.get()
        return None if value == "Sem avaliação" else float(value.replace(",", "."))

    def save(self):
        try:
            current = self._parse_int(self.current_entry.get(), "Quantidade lida")
            total = self._parse_int(self.total_entry.get(), "Total", allow_blank=True)
            start_date = self.start_date.get_iso("Data de início")
            end_date = self.end_date.get_iso("Data de conclusão")
            if start_date and end_date and end_date < start_date:
                raise ValueError("A data de conclusão não pode ser anterior à data de início.")
            release = self.release_day.get()
            data = dict(
                name=self.name_entry.get().strip(), category=self.category_combo.get().strip(),
                progress_unit=self.unit_menu.get(), progress_current=current, progress_total=total,
                status=self.status_menu.get(), release_day=None if release == "Sem dia fixo" else release,
                synopsis=self.synopsis_text.get("1.0", "end").strip(), rating=self._rating_value(),
                favorite=self.favorite_var.get(), personal_notes=self.notes_text.get("1.0", "end").strip(),
                start_date=start_date, end_date=end_date,
            )
            if self.work is None:
                saved = self.repository.create(**data)
                work_id = saved.id
            else:
                self.repository.update_work(self.work.id, **data)
                work_id = self.work.id
            tags = [x.strip() for x in self.tags_entry.get().split(",") if x.strip()]
            self.repository.set_tags(work_id, tags)
            if self._remove_cover:
                self.repository.remove_cover(work_id)
            elif self._selected_cover_source:
                self.repository.set_cover(work_id, self._selected_cover_source)
        except Exception as exc:
            messagebox.showerror("Não foi possível salvar", str(exc), parent=self.winfo_toplevel())
            return
        self.on_saved(work_id)

    def _delete(self):
        if self.work is None:
            return
        if not messagebox.askyesno("Excluir obra", f"Deseja excluir '{self.work.name}'?", parent=self.winfo_toplevel()):
            return
        self.repository.delete_work(self.work.id)
        self.on_deleted()
