import os
import subprocess
import sys
import threading
from datetime import datetime
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.components.work_card import WorkCard
from app.paths import APP_ICON_PATH, DATA_DIR
from app.repositories.sqlite_repository import SQLiteWorkRepository
from app.services.backup_service import BackupService
from app.services.settings_service import SettingsService
from app.services.statistics_service import StatisticsService
from app.services.sync_engine import SyncEngine
from app.ui.work_details_page import WorkDetailsPage
from app.ui.work_form_page import WorkFormPage
from app.ui.date_field import DateField
from app.ui.theme import (
    AMBER, AMBER_BRIGHT, BG, BLACK_TEXT, BORDER, GREEN, PURPLE_DARK,
    SIDEBAR, SURFACE, SURFACE_LOW, SURFACE_RAISED, TEXT, TEXT_DIM, TEXT_MUTED,
    sans, serif,
)
from app.version import __version__
from app.utils.dates import next_release_label


class MainWindow(ctk.CTk):
    GOAL_LABELS = {
        "books": "Obras concluídas",
        "pages": "Páginas lidas",
        "chapters": "Capítulos lidos",
    }
    GOAL_TYPES_BY_LABEL = {value: key for key, value in GOAL_LABELS.items()}

    def __init__(self):
        super().__init__()
        self.title(f"The Reader Codex {__version__}")
        self.geometry("1420x900")
        self.minsize(1100, 720)
        self.configure(fg_color=BG)
        if APP_ICON_PATH.is_file():
            try:
                self.iconbitmap(str(APP_ICON_PATH))
            except Exception:
                pass

        self.repo = SQLiteWorkRepository()
        self.settings_service = SettingsService()
        self.backup_service = BackupService(self.repo)
        self.statistics_service = StatisticsService(self.repo)
        self.sync_engine = SyncEngine(self.repo, self.settings_service)

        self.library_search_var = ctk.StringVar(value="")
        self.library_category_var = ctk.StringVar(value="Todas")
        self.library_status_var = ctk.StringVar(value="Todos")
        self.library_tag_var = ctk.StringVar(value="Todas")
        self.library_results = None
        self.global_search_var = ctk.StringVar(value="")
        self.current_view = "home"
        self.current_work_id = None
        self.previous_view = "library"
        self.category_editing_name = None
        self.goal_editing = None
        self.nav_buttons = {}
        self._sync_running = False
        self._sync_debounce_job = None
        self._periodic_sync_job = None

        self._build_shell()
        self.show_home()
        self._update_sync_label_from_status()

        settings = self.settings_service.load()
        if settings.get("sync_enabled"):
            self.after(1500, self.sync_in_background)
        self._schedule_periodic_sync()
        self.after(2500, self._startup_backup)

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.sidebar = ctk.CTkFrame(
            self, width=250, corner_radius=0, fg_color=SIDEBAR, border_width=0
        )
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")
        self.sidebar.grid_propagate(False)

        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=20, pady=(22, 18))
        ctk.CTkLabel(
            brand, text="▣", width=34, height=34, corner_radius=7,
            fg_color=SURFACE_RAISED, text_color=AMBER, font=sans(17, "bold")
        ).pack(side="left")
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=(10, 0))
        ctk.CTkLabel(
            brand_text, text="The Reader Codex", font=sans(18, "bold"),
            text_color=AMBER_BRIGHT, anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand_text, text="BIBLIOTECA PESSOAL", font=sans(9, "bold"),
            text_color=TEXT_MUTED, anchor="w"
        ).pack(anchor="w")

        self._sidebar_section("MENU PRINCIPAL")
        for key, text, command in [
            ("library", "▤  Biblioteca", self.show_library),
            ("reading", "▥  Lendo Agora", self.show_reading_now),
            ("goals", "♜  Metas & Desafios", self.show_goals),
            ("statistics", "⌁  Estatísticas", self.show_statistics),
            ("history", "◴  Histórico de Sessões", self.show_history),
        ]:
            self._sidebar_button(key, text, command)

        self._sidebar_section("COLEÇÕES & ORGANIZAÇÃO")
        for key, text, command in [
            ("favorites", "★  Favoritos", self.show_favorites),
            ("categories", "◈  Categorias", self.show_categories),
            ("calendar", "□  Calendário", self.show_calendar),
        ]:
            self._sidebar_button(key, text, command)

        self._sidebar_section("CATEGORIAS")
        self.sidebar_categories = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.sidebar_categories.pack(fill="x", padx=12)
        self._refresh_sidebar_categories()

        utilities = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        utilities.pack(side="bottom", fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(
            utilities, text="⚙  Configurações", anchor="w", command=self.show_settings,
            height=32, fg_color="transparent", hover_color=SURFACE_RAISED,
            text_color=TEXT_MUTED
        ).pack(fill="x", pady=2)
        ctk.CTkButton(
            utilities, text="▣  Backup", anchor="w", command=self.show_backup,
            height=32, fg_color="transparent", hover_color=SURFACE_RAISED,
            text_color=TEXT_MUTED
        ).pack(fill="x", pady=2)

        self.sync_label = ctk.CTkLabel(
            utilities, text="", text_color=TEXT_DIM, wraplength=210, font=sans(9)
        )
        self.sync_label.pack(fill="x", pady=(8, 4))
        self.sync_button = ctk.CTkButton(
            utilities, text="☁  Sincronizar agora",
            command=lambda: self.sync_in_background(show_dialog=True),
            height=34, fg_color=SURFACE_RAISED, hover_color=BORDER,
            border_width=1, border_color=BORDER, text_color=TEXT,
        )
        self.sync_button.pack(fill="x")

        self.topbar = ctk.CTkFrame(self, height=68, fg_color=BG, corner_radius=0)
        self.topbar.grid(row=0, column=1, sticky="ew", padx=18, pady=(8, 0))
        self.topbar.grid_columnconfigure(0, weight=1)
        search = ctk.CTkEntry(
            self.topbar, textvariable=self.global_search_var,
            placeholder_text="⌕  Buscar por título, categoria, tag ou status...",
            height=42, corner_radius=10, font=sans(13),
        )
        search.grid(row=0, column=0, sticky="ew", padx=(0, 14), pady=8)
        search.bind("<Return>", lambda _event: self._run_global_search())
        ctk.CTkButton(
            self.topbar, text="＋  Nova Obra", command=self.open_new_work,
            height=42, width=128, fg_color=AMBER, hover_color=AMBER_BRIGHT,
            text_color=BLACK_TEXT, font=sans(12, "bold"),
        ).grid(row=0, column=1, pady=8)

        self.content = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
            scrollbar_button_color=SURFACE_RAISED, scrollbar_button_hover_color=BORDER
        )
        self.content.grid(row=1, column=1, sticky="nsew", padx=18, pady=(0, 14))

    def _sidebar_section(self, text):
        ctk.CTkLabel(
            self.sidebar, text=text, font=sans(10, "bold"), text_color=TEXT_DIM, anchor="w"
        ).pack(fill="x", padx=22, pady=(14, 6))

    def _sidebar_button(self, key, text, command):
        button = ctk.CTkButton(
            self.sidebar, text=text, anchor="w", command=command, height=38,
            corner_radius=9, fg_color="transparent", hover_color=SURFACE_RAISED,
            text_color=TEXT_MUTED, font=sans(12),
        )
        button.pack(fill="x", padx=12, pady=2)
        self.nav_buttons[key] = button

    def _sync_nav_state(self):
        active = self.current_view
        for key, button in self.nav_buttons.items():
            selected = key == active or (active in ("home", "library", "work_form", "work_details") and key == "library")
            button.configure(
                fg_color=AMBER if selected else "transparent",
                hover_color=AMBER_BRIGHT if selected else SURFACE_RAISED,
                text_color=BLACK_TEXT if selected else TEXT_MUTED,
                font=sans(12, "bold" if selected else "normal"),
            )

    def _refresh_sidebar_categories(self):
        if not hasattr(self, "sidebar_categories"):
            return
        for child in self.sidebar_categories.winfo_children():
            child.destroy()
        for item in self.repo.list_categories()[:6]:
            name = item["name"]
            ctk.CTkButton(
                self.sidebar_categories, text=f"•  {name}", anchor="w", height=28,
                fg_color="transparent", hover_color=SURFACE_RAISED, text_color=TEXT_MUTED,
                font=sans(10), command=lambda n=name: self._open_category_filter(n),
            ).pack(fill="x", pady=1)
        if not self.repo.list_categories():
            ctk.CTkLabel(
                self.sidebar_categories, text="Nenhuma categoria", text_color=TEXT_DIM,
                font=sans(9), anchor="w"
            ).pack(fill="x", padx=10, pady=3)

    def _open_category_filter(self, category):
        self.library_category_var.set(category)
        self.library_status_var.set("Todos")
        self.show_library()

    def _open_status_filter(self, status):
        self.library_status_var.set(status)
        self.show_library()

    def _run_global_search(self):
        self.library_search_var.set(self.global_search_var.get().strip())
        self.show_library()

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.library_results = None
        self._sync_nav_state()
        self._refresh_sidebar_categories()

    def _header(self, title, subtitle):
        ctk.CTkLabel(
            self.content, text=title, font=sans(32, "bold"), text_color=TEXT, anchor="w"
        ).pack(fill="x", padx=6, pady=(8, 0))
        ctk.CTkLabel(
            self.content, text=subtitle, text_color=TEXT_MUTED, font=sans(12), anchor="w"
        ).pack(fill="x", padx=6, pady=(4, 20))

    @staticmethod
    def _plural_progress_unit(unit):
        return "páginas" if unit == "Página" else "capítulos" if unit == "Capítulo" else unit.lower()

    @staticmethod
    def _format_date(value):
        if not value:
            return ""
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return value

    @staticmethod
    def _format_datetime(value):
        if not value:
            return ""
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo:
                dt = dt.astimezone()
            return dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return value

    def _render_work(self, work, parent=None):
        parent = parent or self.content
        total = work.progress_total or 0
        percent = work.progress_current / total if total and total > 0 else 0
        unit_plural = self._plural_progress_unit(work.progress_unit)
        if work.progress_total:
            progress_text = f"{work.progress_current} / {work.progress_total} {unit_plural} ({min(percent * 100, 100):.0f}%)"
        elif work.progress_unit == "Capítulo":
            progress_text = f"Último capítulo lido: {work.progress_current}  •  Em lançamento"
        else:
            progress_text = f"Página atual: {work.progress_current}  •  total não informado"
        tags = self.repo.get_tags(work.id)
        dates = []
        if work.start_date:
            dates.append(f"Início: {self._format_date(work.start_date)}")
        if work.end_date:
            dates.append(f"Fim: {self._format_date(work.end_date)}")
        if work.progress_unit == "Capítulo" and work.progress_total is None and work.release_day:
            prediction = next_release_label(work.release_day)
            if prediction:
                dates.append(f"Próximo lançamento: {prediction}")

        WorkCard(
            parent,
            title=work.name,
            category=work.category,
            progress_text=progress_text,
            status=work.status,
            percent=percent,
            on_increment=lambda wid=work.id: self._change_progress(wid, 1),
            on_decrement=lambda wid=work.id: self._change_progress(wid, -1),
            on_details=lambda wid=work.id: self.open_details(wid),
            on_favorite=lambda wid=work.id: self._toggle_favorite_from_card(wid),
            tags_text=", ".join(tags[:4]),
            dates_text=" | ".join(dates),
            favorite=work.favorite,
            rating=work.rating,
            cover_path=work.cover_path,
        ).pack(fill="x", pady=7)

    def _change_progress(self, work_id, amount):
        try:
            self.repo.increment_progress(work_id, amount)
        except Exception as exc:
            messagebox.showerror("Progresso", str(exc), parent=self)
            return
        self.refresh_current_view()
        self._data_changed()

    def refresh_current_view(self):
        if self.current_view == "work_details" and self.current_work_id:
            self.open_details(self.current_work_id)
            return
        if self.current_view == "work_form":
            return
        views = {
            "home": self.show_home,
            "library": self.show_library,
            "reading": self.show_reading_now,
            "favorites": self.show_favorites,
            "categories": self.show_categories,
            "calendar": self.show_calendar,
            "statistics": self.show_statistics,
            "goals": self.show_goals,
            "history": self.show_history,
            "backup": self.show_backup,
            "settings": self.show_settings,
        }
        views.get(self.current_view, self.show_library)()

    def open_new_work(self):
        self.previous_view = self.current_view if self.current_view not in ("work_form", "work_details") else "library"
        self.current_view = "work_form"
        self.current_work_id = None
        self._clear_content()
        WorkFormPage(
            self.content, self.repo, work=None,
            on_saved=self._after_work_saved,
            on_cancel=self._return_from_work_page,
            on_deleted=self.show_library,
        ).pack(fill="x", expand=True)

    def open_edit_work(self, work_id):
        work = self.repo.get_by_id(work_id)
        if work is None:
            messagebox.showwarning("Obra", "Essa obra não está mais disponível.", parent=self)
            return
        self.current_view = "work_form"
        self.current_work_id = work_id
        self._clear_content()
        WorkFormPage(
            self.content, self.repo, work=work,
            on_saved=self._after_work_saved,
            on_cancel=lambda: self.open_details(work_id),
            on_deleted=self._after_work_deleted,
        ).pack(fill="x", expand=True)

    def open_details(self, work_id):
        work = self.repo.get_by_id(work_id)
        if work is None:
            messagebox.showwarning("Obra", "Essa obra não está mais disponível.", parent=self)
            return
        if self.current_view not in ("work_form", "work_details"):
            self.previous_view = self.current_view
        self.current_work_id = work_id
        self.current_view = "work_details"
        self._clear_content()
        WorkDetailsPage(
            self.content, self.repo, work_id,
            on_back=self._return_from_work_page,
            on_edit=self.open_edit_work,
            on_changed=self._details_changed,
        ).pack(fill="x", expand=True)

    def _return_from_work_page(self):
        target = self.previous_view
        views = {
            "home": self.show_home,
            "library": self.show_library,
            "reading": self.show_reading_now,
            "favorites": self.show_favorites,
            "calendar": self.show_calendar,
            "statistics": self.show_statistics,
            "goals": self.show_goals,
            "history": self.show_history,
        }
        views.get(target, self.show_library)()

    def _after_work_saved(self, work_id):
        self._data_changed()
        self.open_details(work_id)

    def _after_work_deleted(self):
        self._data_changed()
        self.show_library()

    def _details_changed(self):
        self._data_changed()
        self._refresh_sidebar_categories()

    def _toggle_favorite_from_card(self, work_id):
        work = self.repo.get_by_id(work_id)
        if work is None:
            return
        try:
            self.repo.update_work(
                work.id, name=work.name, category=work.category,
                progress_unit=work.progress_unit, progress_current=work.progress_current,
                progress_total=work.progress_total, status=work.status, release_day=work.release_day,
                synopsis=work.synopsis, rating=work.rating, favorite=not work.favorite,
                personal_notes=work.personal_notes, start_date=work.start_date, end_date=work.end_date,
            )
        except Exception as exc:
            messagebox.showerror("Favorito", str(exc), parent=self)
            return
        self._data_changed()
        self.refresh_current_view()

    def show_home(self):
        self.current_view = "home"
        self._clear_content()
        self._header("Biblioteca Pessoal", "Seu acervo, progresso e ritmo de leitura em um só lugar.")
        summary = self.statistics_service.summary()

        cards = ctk.CTkFrame(self.content, fg_color="transparent")
        cards.pack(fill="x", pady=(0, 18))
        metrics = [
            ("OBRAS NO ACERVO", summary["total_works"], "▤"),
            ("LENDO AGORA", summary["reading"], "◉"),
            ("CONCLUÍDAS", summary["completed"], "✓"),
            ("FAVORITAS", summary["favorites"], "★"),
        ]
        for label, value, icon in metrics:
            box = ctk.CTkFrame(
                cards, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=14
            )
            box.pack(side="left", expand=True, fill="both", padx=6)
            ctk.CTkLabel(box, text=icon, font=sans(16, "bold"), text_color=AMBER).pack(
                anchor="w", padx=16, pady=(14, 0)
            )
            ctk.CTkLabel(box, text=str(value), font=sans(27, "bold"), text_color=TEXT).pack(
                anchor="w", padx=16, pady=(2, 0)
            )
            ctk.CTkLabel(box, text=label, font=sans(9, "bold"), text_color=TEXT_MUTED).pack(
                anchor="w", padx=16, pady=(0, 14)
            )

        reading = self.repo.list_filtered(status="Lendo")
        if reading:
            ctk.CTkLabel(
                self.content, text="Continue lendo", font=sans(22, "bold"),
                text_color=TEXT, anchor="w"
            ).pack(fill="x", padx=6, pady=(10, 8))
            ctk.CTkLabel(
                self.content, text="Retome rapidamente as obras em andamento.",
                font=sans(11), text_color=TEXT_MUTED, anchor="w"
            ).pack(fill="x", padx=6, pady=(0, 8))
            for work in reading[:3]:
                self._render_work(work)
        elif self.repo.list_all():
            ctk.CTkLabel(
                self.content, text="Nenhuma obra está marcada como 'Lendo'.",
                text_color=TEXT_MUTED, anchor="w"
            ).pack(fill="x", padx=6, pady=12)
        else:
            empty = ctk.CTkFrame(
                self.content, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=16
            )
            empty.pack(fill="x", padx=6, pady=20)
            ctk.CTkLabel(empty, text="Sua biblioteca está vazia", font=sans(22, "bold")).pack(
                pady=(32, 6)
            )
            ctk.CTkLabel(
                empty, text="Comece seu acervo cadastrando a primeira obra.", text_color=TEXT_MUTED
            ).pack(pady=(0, 14))
            ctk.CTkButton(
                empty, text="＋ Adicionar primeira obra", command=self.open_new_work,
                fg_color=AMBER, hover_color=AMBER_BRIGHT, text_color=BLACK_TEXT
            ).pack(pady=(0, 30))

    def show_reading_now(self):
        self.current_view = "reading"
        self._clear_content()
        self._header("Lendo Agora", "Obras em andamento, com acesso rápido ao progresso e aos detalhes.")
        works = self.repo.list_filtered(status="Lendo")
        if not works:
            empty = ctk.CTkFrame(self.content, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=14)
            empty.pack(fill="x", padx=6, pady=16)
            ctk.CTkLabel(empty, text="Nenhuma obra em leitura", font=sans(20, "bold"), text_color=TEXT).pack(pady=(24, 5))
            ctk.CTkLabel(empty, text="Altere o status de uma obra para 'Lendo' e ela aparecerá aqui.", font=sans(12), text_color=TEXT_MUTED).pack(pady=(0, 22))
            return
        for work in works:
            self._render_work(work)

    def show_library(self):
        self.current_view = "library"
        self._clear_content()
        self._header("Biblioteca", "Explore seu acervo por título, categoria, status ou marcador.")

        filters = ctk.CTkFrame(
            self.content, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=14
        )
        filters.pack(fill="x", padx=6, pady=(0, 16))
        for column in range(4):
            filters.grid_columnconfigure(column, weight=1)

        search = ctk.CTkEntry(
            filters, textvariable=self.library_search_var,
            placeholder_text="⌕  Buscar no acervo...", height=42, corner_radius=10
        )
        search.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(14, 7), pady=(14, 8))
        search.bind("<KeyRelease>", lambda _event: self._render_library_results())

        categories = ["Todas"] + [item["name"] for item in self.repo.list_categories()]
        if self.library_category_var.get() not in categories:
            self.library_category_var.set("Todas")
        ctk.CTkOptionMenu(
            filters, values=categories, variable=self.library_category_var, height=42,
            command=lambda _value: self._render_library_results(),
        ).grid(row=0, column=2, sticky="ew", padx=7, pady=(14, 8))

        statuses = ["Todos"] + list(self.repo.STATUS_OPTIONS)
        if self.library_status_var.get() not in statuses:
            self.library_status_var.set("Todos")
        ctk.CTkOptionMenu(
            filters, values=statuses, variable=self.library_status_var, height=42,
            command=lambda _value: self._render_library_results(),
        ).grid(row=0, column=3, sticky="ew", padx=(7, 14), pady=(14, 8))

        tags = ["Todas"] + self.repo.list_tags()
        if self.library_tag_var.get() not in tags:
            self.library_tag_var.set("Todas")
        ctk.CTkOptionMenu(
            filters, values=tags, variable=self.library_tag_var, height=36,
            command=lambda _value: self._render_library_results(),
        ).grid(row=1, column=0, sticky="ew", padx=(14, 7), pady=(0, 14))
        ctk.CTkLabel(
            filters, text="Filtro de tag", anchor="w", text_color=TEXT_DIM, font=sans(10)
        ).grid(row=1, column=1, sticky="w", padx=7, pady=(0, 14))
        ctk.CTkButton(
            filters, text="Limpar filtros", command=self._clear_library_filters,
            fg_color="transparent", hover_color=SURFACE_RAISED, border_width=1,
            border_color=BORDER, text_color=TEXT_MUTED, height=36
        ).grid(row=1, column=3, sticky="e", padx=14, pady=(0, 14))

        self.library_results = ctk.CTkFrame(self.content, fg_color="transparent")
        self.library_results.pack(fill="x", padx=6)
        self._render_library_results()

    def _clear_library_filters(self):
        self.library_search_var.set("")
        self.library_category_var.set("Todas")
        self.library_status_var.set("Todos")
        self.library_tag_var.set("Todas")
        self._render_library_results()

    def _render_library_results(self):
        if self.library_results is None or not self.library_results.winfo_exists():
            return
        for child in self.library_results.winfo_children():
            child.destroy()
        works = self.repo.list_filtered(
            search=self.library_search_var.get(),
            category=self.library_category_var.get(),
            status=self.library_status_var.get(),
            tag=self.library_tag_var.get(),
        )
        if not works:
            ctk.CTkLabel(
                self.library_results,
                text="Nenhuma obra encontrada com os filtros atuais.",
                anchor="w",
            ).pack(fill="x", pady=18)
            return
        ctk.CTkLabel(
            self.library_results,
            text=f"{len(works)} obra(s) encontrada(s)",
            anchor="w",
            text_color=("gray35", "gray70"),
        ).pack(fill="x", pady=(0, 4))
        for work in works:
            self._render_work(work, self.library_results)

    def show_favorites(self):
        self.current_view = "favorites"
        self._clear_content()
        self._header("Favoritos", "Obras marcadas como favoritas, independentemente da nota.")
        favorites = self.repo.list_filtered(favorites_only=True)
        if not favorites:
            ctk.CTkLabel(self.content, text="Nenhuma obra favorita.").pack(anchor="w")
            return
        for work in favorites:
            self._render_work(work)

    def show_categories(self):
        self.current_view = "categories"
        self._clear_content()
        editing = self.category_editing_name
        self._header("Categorias", "Crie e renomeie categorias diretamente nesta página.")
        form = ctk.CTkFrame(self.content, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=12)
        form.pack(fill="x", pady=(0, 16))
        self.new_category_entry = ctk.CTkEntry(
            form, placeholder_text="Nova categoria: Livro, Mangá, HQ, Artigo...", height=40, font=sans(12)
        )
        self.new_category_entry.pack(side="left", expand=True, fill="x", padx=(12, 8), pady=12)
        if editing:
            self.new_category_entry.insert(0, editing)
        self.new_category_entry.bind("<Return>", lambda _event: self._save_category_form())
        ctk.CTkButton(
            form, text="Salvar nome" if editing else "Adicionar categoria",
            command=self._save_category_form, height=40, font=sans(12, "bold")
        ).pack(side="right", padx=(0, 8), pady=12)
        if editing:
            ctk.CTkButton(
                form, text="Cancelar", command=self._cancel_category_edit, height=40,
                fg_color=SURFACE_RAISED, hover_color=BORDER, text_color=TEXT
            ).pack(side="right", padx=(0, 8), pady=12)

        categories = self.repo.list_categories()
        if not categories:
            ctk.CTkLabel(
                self.content,
                text="Ainda não há categorias. Você também pode digitar uma categoria ao cadastrar uma obra.",
                anchor="w", wraplength=760, font=sans(12), text_color=TEXT_MUTED,
            ).pack(fill="x", pady=12)
            return
        for item in categories:
            row = ctk.CTkFrame(self.content, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=10)
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=item["name"], font=sans(14, "bold"), anchor="w").pack(
                side="left", padx=12, pady=12
            )
            ctk.CTkLabel(row, text=f"{item['work_count']} obra(s)", text_color=TEXT_MUTED, font=sans(11)).pack(
                side="left", padx=8
            )
            ctk.CTkButton(
                row, text="Excluir", width=70, fg_color="transparent", border_width=1,
                command=lambda name=item["name"]: self._delete_category(name),
            ).pack(side="right", padx=(6, 12), pady=8)
            ctk.CTkButton(
                row, text="Renomear", width=85, command=lambda name=item["name"]: self._start_category_edit(name),
            ).pack(side="right", padx=6, pady=8)

    def _save_category_form(self):
        try:
            if self.category_editing_name:
                self.repo.rename_category(self.category_editing_name, self.new_category_entry.get())
                self.category_editing_name = None
            else:
                self.repo.create_category(self.new_category_entry.get())
        except Exception as exc:
            messagebox.showerror("Categoria", str(exc), parent=self)
            return
        self._data_changed()
        self.show_categories()

    def _start_category_edit(self, old_name):
        self.category_editing_name = old_name
        self.show_categories()

    def _cancel_category_edit(self):
        self.category_editing_name = None
        self.show_categories()

    def _delete_category(self, name):
        if not messagebox.askyesno("Excluir categoria", f"Deseja excluir a categoria '{name}'?", parent=self):
            return
        try:
            self.repo.delete_category(name)
        except Exception as exc:
            messagebox.showerror("Categoria", str(exc), parent=self)
            return
        if self.category_editing_name == name:
            self.category_editing_name = None
        self._data_changed()
        self.show_categories()

    def show_calendar(self):
        self.current_view = "calendar"
        self._clear_content()
        self._header("Calendário", "Datas de leitura e próximas previsões semanais de lançamento.")
        events = self.repo.list_calendar_events()
        if not events:
            ctk.CTkLabel(self.content, text="Nenhum evento de leitura registrado.").pack(anchor="w")
            return
        current_date = None
        for event in events:
            if event["date"] != current_date:
                current_date = event["date"]
                ctk.CTkLabel(
                    self.content,
                    text=self._format_date(current_date),
                    font=sans(16, "bold"),
                    anchor="w",
                ).pack(fill="x", pady=(14, 4))
            button = ctk.CTkButton(
                self.content,
                text=f"{event['type']}: {event['title']}",
                anchor="w",
                fg_color="transparent",
                border_width=1,
                command=lambda wid=event["work_id"]: self.open_details(wid),
            )
            button.pack(fill="x", padx=8, pady=3)

    def show_statistics(self):
        self.current_view = "statistics"
        self._clear_content()
        self._header("Estatísticas", "Visão geral da sua biblioteca e do progresso de leitura.")
        summary = self.statistics_service.summary()
        rows = [
            ("Obras cadastradas", summary["total_works"]),
            ("Lendo agora", summary["reading"]),
            ("Obras concluídas", summary["completed"]),
            ("Favoritas", summary["favorites"]),
            ("Páginas registradas como lidas", summary["pages_read"]),
            ("Capítulos registrados como lidos", summary["chapters_read"]),
            ("Avaliação média", str(summary["average_rating"]).replace(".", ",")),
            ("Categoria mais concluída", summary["top_category"]),
            ("Progresso médio das obras com total definido", f"{summary['average_progress']}%".replace(".", ",")),
        ]
        for label, value in rows:
            row = ctk.CTkFrame(self.content)
            row.pack(fill="x", pady=5)
            ctk.CTkLabel(row, text=label, anchor="w").pack(side="left", padx=12, pady=10)
            ctk.CTkLabel(row, text=str(value), font=sans(14, "bold")).pack(side="right", padx=12, pady=10)

    def show_goals(self):
        self.current_view = "goals"
        self._clear_content()
        editing = self.goal_editing
        self._header("Metas", "Crie e edite objetivos diretamente nesta página. O progresso é atualizado automaticamente.")

        form = ctk.CTkFrame(self.content, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=12)
        form.pack(fill="x", pady=(0, 16))
        form.grid_columnconfigure(0, weight=2)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(2, weight=1)
        form.grid_columnconfigure(3, weight=1)
        self.goal_title = ctk.CTkEntry(form, placeholder_text="Ex.: Ler 12 obras no ano", height=40, font=sans(12))
        self.goal_title.grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=(12, 6))
        self.goal_target = ctk.CTkEntry(form, placeholder_text="Meta", height=40, font=sans(12))
        self.goal_target.grid(row=0, column=1, sticky="ew", padx=6, pady=(12, 6))
        self.goal_type = ctk.CTkOptionMenu(form, values=list(self.GOAL_TYPES_BY_LABEL), height=40, font=sans(12), dropdown_font=sans(12))
        self.goal_type.set("Obras concluídas")
        self.goal_type.grid(row=0, column=2, sticky="ew", padx=6, pady=(12, 6))
        ctk.CTkButton(
            form, text="Salvar alterações" if editing else "Adicionar meta",
            command=self._save_goal_form, height=40, font=sans(12, "bold")
        ).grid(row=0, column=3, sticky="ew", padx=(6, 12), pady=(12, 6))
        self.goal_start = DateField(form, placeholder="Início DD/MM/AAAA (opcional)")
        self.goal_start.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(12, 6), pady=(6, 12))
        self.goal_end = DateField(form, placeholder="Fim DD/MM/AAAA (opcional)")
        self.goal_end.grid(row=1, column=2, sticky="ew", padx=(6, 6), pady=(6, 12))
        if editing:
            self.goal_title.insert(0, editing["title"])
            self.goal_target.insert(0, str(editing["target_value"]))
            self.goal_type.set(self.GOAL_LABELS.get(editing["goal_type"], editing["goal_type"]))
            self.goal_start.set_iso(editing.get("start_date"))
            self.goal_end.set_iso(editing.get("end_date"))
            ctk.CTkButton(
                form, text="Cancelar edição", command=self._cancel_goal_edit, height=40,
                fg_color=SURFACE_RAISED, hover_color=BORDER, text_color=TEXT
            ).grid(row=1, column=3, sticky="ew", padx=(6, 12), pady=(6, 12))

        goals = self.repo.list_goals()
        if not goals:
            ctk.CTkLabel(self.content, text="Nenhuma meta cadastrada.", font=sans(12), text_color=TEXT_MUTED).pack(anchor="w")
            return
        for goal in goals:
            current = int(goal["current_value"] or 0)
            target = int(goal["target_value"] or 1)
            percent = min(current / target, 1)
            card = ctk.CTkFrame(self.content, fg_color=SURFACE, border_width=1, border_color=BORDER, corner_radius=10)
            card.pack(fill="x", pady=6)
            header = ctk.CTkFrame(card, fg_color="transparent")
            header.pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(header, text=goal["title"], font=sans(15, "bold"), anchor="w").pack(side="left", expand=True, fill="x")
            ctk.CTkButton(header, text="Editar", width=70, command=lambda item=goal: self._start_goal_edit(item)).pack(side="right", padx=(6, 0))
            ctk.CTkButton(
                header, text="Excluir", width=70, fg_color="transparent", border_width=1,
                command=lambda gid=goal["id"], title=goal["title"]: self._delete_goal(gid, title),
            ).pack(side="right", padx=6)
            progress = ctk.CTkProgressBar(card)
            progress.set(percent)
            progress.pack(fill="x", padx=12, pady=4)
            period = ""
            if goal.get("start_date") or goal.get("end_date"):
                period = f" • {self._format_date(goal.get('start_date')) or '...'} a {self._format_date(goal.get('end_date')) or '...'}"
            label = self.GOAL_LABELS.get(goal["goal_type"], goal["goal_type"])
            ctk.CTkLabel(card, text=f"{current} / {target} • {label}{period}", anchor="w", font=sans(11)).pack(
                fill="x", padx=12, pady=(0, 10)
            )

    def _save_goal_form(self):
        try:
            goal_type = self.GOAL_TYPES_BY_LABEL[self.goal_type.get()]
            kwargs = dict(
                title=self.goal_title.get(), goal_type=goal_type, target_value=self.goal_target.get(),
                start_date=self.goal_start.get_iso("Data inicial"), end_date=self.goal_end.get_iso("Data final"),
            )
            if self.goal_editing:
                self.repo.update_goal(self.goal_editing["id"], **kwargs)
                self.goal_editing = None
            else:
                self.repo.create_goal(**kwargs)
        except Exception as exc:
            messagebox.showwarning("Meta inválida", str(exc), parent=self)
            return
        self._data_changed()
        self.show_goals()

    def _start_goal_edit(self, goal):
        self.goal_editing = dict(goal)
        self.show_goals()

    def _cancel_goal_edit(self):
        self.goal_editing = None
        self.show_goals()

    def _delete_goal(self, goal_id, title):
        if not messagebox.askyesno("Excluir meta", f"Deseja excluir a meta '{title}'?", parent=self):
            return
        self.repo.delete_goal(goal_id)
        if self.goal_editing and self.goal_editing.get("id") == goal_id:
            self.goal_editing = None
        self._data_changed()
        self.show_goals()

    def show_history(self):
        self.current_view = "history"
        self._clear_content()
        self._header("Histórico", "Alterações de progresso e status registradas automaticamente.")
        rows = self.repo.list_history()
        if not rows:
            ctk.CTkLabel(self.content, text="Ainda não há registros.").pack(anchor="w")
            return
        for row in rows:
            frame = ctk.CTkFrame(self.content)
            frame.pack(fill="x", pady=3)
            ctk.CTkLabel(frame, text=row["name"], font=sans(13, "bold"), anchor="w").pack(
                side="left", padx=(12, 8), pady=8
            )
            ctk.CTkLabel(frame, text=row["description"], anchor="w").pack(side="left", padx=8, pady=8)
            ctk.CTkLabel(
                frame,
                text=self._format_datetime(row["created_at"]),
                text_color=("gray35", "gray70"),
            ).pack(side="right", padx=12, pady=8)

    def show_backup(self):
        self.current_view = "backup"
        self._clear_content()
        self._header("Backup e dados", "Exporte dados em JSON ou um backup completo com as capas.")
        buttons = [
            ("Exportar dados para JSON", self.export_json),
            ("Importar dados de JSON", self.import_json),
            ("Exportar backup completo (.zip)", self.export_full_backup),
            ("Importar backup completo (.zip)", self.import_full_backup),
            ("Criar backup automático agora", self.manual_backup),
        ]
        for label, command in buttons:
            ctk.CTkButton(self.content, text=label, command=command).pack(anchor="w", pady=6)
        ctk.CTkLabel(
            self.content,
            text="O JSON contém metadados. O ZIP é a opção indicada para transferir a biblioteca entre computadores porque inclui as capas.",
            wraplength=820,
            justify="left",
            anchor="w",
            text_color=("gray35", "gray70"),
        ).pack(fill="x", pady=(14, 0))

    def export_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="the-reader-codex-export.json",
        )
        if not path:
            return
        try:
            self.backup_service.export_json(path)
        except Exception as exc:
            messagebox.showerror("Exportação", str(exc), parent=self)
            return
        messagebox.showinfo("Exportação concluída", f"Dados exportados para:\n{path}", parent=self)

    def import_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        if not messagebox.askyesno("Importar dados", "A importação substituirá os dados locais atuais. Continuar?", parent=self):
            return
        try:
            self.backup_service.create_automatic_backup()
            self.backup_service.import_json(path)
        except Exception as exc:
            messagebox.showerror("Importação", str(exc), parent=self)
            return
        self._data_changed()
        messagebox.showinfo("Importação concluída", "Os dados foram importados com sucesso.", parent=self)
        self.show_library()

    def export_full_backup(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Backup ZIP", "*.zip")],
            initialfile="the-reader-codex-backup.zip",
        )
        if not path:
            return
        try:
            result = self.backup_service.export_full_backup(path)
        except Exception as exc:
            messagebox.showerror("Backup", str(exc), parent=self)
            return
        messagebox.showinfo("Backup concluído", f"Backup completo criado em:\n{result}", parent=self)

    def import_full_backup(self):
        path = filedialog.askopenfilename(filetypes=[("Backup ZIP", "*.zip")])
        if not path:
            return
        if not messagebox.askyesno("Restaurar backup", "A restauração substituirá os dados locais atuais. Continuar?", parent=self):
            return
        try:
            self.backup_service.create_automatic_backup()
            self.backup_service.import_full_backup(path)
        except Exception as exc:
            messagebox.showerror("Restauração", str(exc), parent=self)
            return
        self._data_changed()
        messagebox.showinfo("Restauração concluída", "Biblioteca e capas restauradas.", parent=self)
        self.show_library()

    def manual_backup(self):
        try:
            result = self.backup_service.create_automatic_backup()
        except Exception as exc:
            messagebox.showerror("Backup", str(exc), parent=self)
            return
        messagebox.showinfo("Backup criado", f"Backup completo:\n{result['zip']}", parent=self)

    def _startup_backup(self):
        try:
            self.backup_service.create_automatic_backup()
        except Exception as exc:
            print(f"Falha ao criar backup automático: {exc}")

    def show_settings(self):
        self.current_view = "settings"
        self._clear_content()
        self._header("Configurações", "Configure a sincronização opcional com Google Sheets e Google Drive.")
        settings = self.settings_service.load()
        google = settings.get("google", {})

        form = ctk.CTkFrame(self.content)
        form.pack(fill="x", pady=(0, 16))
        form.grid_columnconfigure(1, weight=1)
        self.settings_sync_var = ctk.BooleanVar(value=bool(settings.get("sync_enabled")))
        ctk.CTkCheckBox(
            form,
            text="Ativar sincronização Google",
            variable=self.settings_sync_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(14, 10))

        def field(row, label, value, browse=False):
            ctk.CTkLabel(form, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=12, pady=7)
            entry = ctk.CTkEntry(form)
            entry.insert(0, value or "")
            entry.grid(row=row, column=1, sticky="ew", padx=8, pady=7)
            if browse:
                ctk.CTkButton(form, text="Selecionar", width=90, command=lambda: self._browse_credentials(entry)).grid(
                    row=row, column=2, padx=(0, 12), pady=7
                )
            return entry

        self.settings_credentials = field(1, "credentials.json", google.get("credentials_file", ""), browse=True)
        self.settings_sheet_name = field(2, "Nome da planilha", google.get("spreadsheet_name", "The Reader Codex"))
        self.settings_sheet_id = field(3, "ID da planilha (opcional)", google.get("spreadsheet_id", ""))
        self.settings_drive_folder = field(4, "ID da pasta do Drive (opcional)", google.get("drive_folder_id", ""))

        actions = ctk.CTkFrame(form, fg_color="transparent")
        actions.grid(row=5, column=0, columnspan=3, sticky="e", padx=12, pady=(8, 14))
        ctk.CTkButton(actions, text="Salvar configurações", command=self.save_settings).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Testar conexão", command=self.test_google_connection).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Sincronizar agora", command=lambda: self.sync_in_background(show_dialog=True)).pack(side="left", padx=4)

        pending = self.repo.pending_sync_count()
        ctk.CTkLabel(
            self.content,
            text=f"Alterações locais aguardando sincronização: {pending}",
            font=sans(14, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(4, 8))
        data_box = ctk.CTkFrame(self.content)
        data_box.pack(fill="x", pady=(4, 12))
        ctk.CTkLabel(
            data_box,
            text=f"Dados locais: {DATA_DIR}",
            anchor="w",
            justify="left",
            wraplength=760,
        ).pack(side="left", fill="x", expand=True, padx=12, pady=10)
        ctk.CTkButton(
            data_box,
            text="Abrir pasta de dados",
            width=150,
            command=self.open_data_folder,
        ).pack(side="right", padx=12, pady=10)

        ctk.CTkLabel(
            self.content,
            text=(
                "A aplicação funciona normalmente sem Google. Para uso pessoal, prefira credenciais OAuth de aplicativo "
                "Desktop: no primeiro teste o navegador abrirá para você autorizar a conta e o token ficará salvo apenas "
                "neste computador. Também é possível usar uma conta de serviço; nesse caso, compartilhe a planilha e a "
                "pasta/Shared Drive com o e-mail da conta de serviço. Se o ID da planilha ficar vazio, o sistema procura "
                "pelo nome informado e tenta criar uma nova quando a credencial permitir."
            ),
            wraplength=860,
            justify="left",
            anchor="w",
            text_color=("gray35", "gray70"),
        ).pack(fill="x", pady=(4, 12))

    def open_data_folder(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(DATA_DIR))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(DATA_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(DATA_DIR)])
        except Exception as exc:
            messagebox.showerror("Pasta de dados", f"Não foi possível abrir a pasta:\n{exc}", parent=self)

    def _browse_credentials(self, entry):
        path = filedialog.askopenfilename(parent=self, filetypes=[("JSON", "*.json"), ("Todos os arquivos", "*.*")])
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _collect_settings(self):
        return {
            "sync_enabled": bool(self.settings_sync_var.get()),
            "profile_name": self.settings_service.load().get("profile_name", ""),
            "google": {
                "credentials_file": self.settings_credentials.get().strip(),
                "spreadsheet_name": self.settings_sheet_name.get().strip() or "The Reader Codex",
                "spreadsheet_id": self.settings_sheet_id.get().strip(),
                "drive_folder_id": self.settings_drive_folder.get().strip(),
            },
        }

    def save_settings(self, notify=True, schedule_sync=True):
        if not hasattr(self, "settings_sync_var"):
            return
        self.settings_service.save(self._collect_settings())
        self._update_sync_label_from_status()
        self._schedule_periodic_sync()
        if schedule_sync and self.sync_engine.status().get("status") == "ready":
            if self._sync_debounce_job is not None:
                try:
                    self.after_cancel(self._sync_debounce_job)
                except Exception:
                    pass
            self._sync_debounce_job = self.after(1000, self._run_debounced_sync)
        if notify:
            messagebox.showinfo("Configurações", "Configurações salvas.", parent=self)

    def test_google_connection(self):
        self.save_settings(notify=False, schedule_sync=False)
        self.sync_label.configure(text="☁ Testando conexão...")

        def worker():
            try:
                info = self.sync_engine.test_connection()
                result = {"ok": True, "info": info}
            except Exception as exc:
                result = {"ok": False, "message": str(exc)}
            self.after(0, lambda: self._apply_connection_test(result))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_connection_test(self, result):
        self._update_sync_label_from_status()
        if result["ok"]:
            if self.current_view == "settings":
                self.show_settings()
            messagebox.showinfo(
                "Google",
                f"Conexão realizada. Planilha: {result['info'].get('spreadsheet_name', 'The Reader Codex')}",
                parent=self,
            )
        else:
            messagebox.showerror("Google", result["message"], parent=self)

    def _update_sync_label_from_status(self):
        result = self.sync_engine.status()
        pending = result.get("pending", 0)
        if result["status"] == "not_configured":
            self.sync_label.configure(text=f"○ Nuvem não configurada\n{pending} alteração(ões) local(is)")
        else:
            self.sync_label.configure(text=f"☁ Google configurado\n{pending} alteração(ões) pendente(s)")

    def _data_changed(self):
        """Refresh sync state and debounce cloud upload after a local mutation."""
        self._update_sync_label_from_status()
        if self.sync_engine.status().get("status") != "ready":
            return
        if self._sync_debounce_job is not None:
            try:
                self.after_cancel(self._sync_debounce_job)
            except Exception:
                pass
        self._sync_debounce_job = self.after(3000, self._run_debounced_sync)

    def _run_debounced_sync(self):
        self._sync_debounce_job = None
        self.sync_in_background(show_dialog=False)

    def _schedule_periodic_sync(self):
        if self._periodic_sync_job is not None:
            try:
                self.after_cancel(self._periodic_sync_job)
            except Exception:
                pass
        self._periodic_sync_job = self.after(300000, self._periodic_sync)

    def _periodic_sync(self):
        self._periodic_sync_job = None
        if self.sync_engine.status().get("status") == "ready":
            self.sync_in_background(show_dialog=False)
        self._schedule_periodic_sync()

    def sync_in_background(self, show_dialog=False):
        if self._sync_running:
            if show_dialog:
                messagebox.showinfo("Sincronização", "Uma sincronização já está em andamento.", parent=self)
            return
        status = self.sync_engine.status()
        if status["status"] == "not_configured":
            self._update_sync_label_from_status()
            if show_dialog:
                messagebox.showinfo(
                    "Sincronização",
                    "A sincronização Google não está configurada. Use Configurações para ativá-la.",
                    parent=self,
                )
            return
        self._sync_running = True
        self.sync_button.configure(state="disabled")
        self.sync_label.configure(text="☁ Sincronizando...")

        def worker():
            result = self.sync_engine.sync()
            self.after(0, lambda: self._apply_sync_result(result, show_dialog))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_sync_result(self, result, show_dialog=False):
        self._sync_running = False
        self.sync_button.configure(state="normal")
        status = result.get("status")
        if status == "synced":
            self.sync_label.configure(text="☁ Sincronizado\n0 alterações pendentes")
            if result.get("downloaded"):
                self.refresh_current_view()
            if show_dialog:
                messagebox.showinfo(
                    "Sincronização concluída",
                    f"Alterações locais processadas: {result.get('uploaded', 0)}\n"
                    f"Registros recebidos/atualizados: {result.get('downloaded', 0)}\n"
                    f"Capas enviadas: {result.get('covers_uploaded', 0)}\n"
                    f"Capas baixadas: {result.get('covers_downloaded', 0)}",
                    parent=self,
                )
            return
        pending = result.get("pending", self.repo.pending_sync_count())
        if status == "not_configured":
            self.sync_label.configure(text=f"○ Nuvem não configurada\n{pending} alteração(ões) local(is)")
        else:
            self.sync_label.configure(text=f"⚠ Falha na sincronização\n{pending} alteração(ões) protegida(s) localmente")
            if show_dialog:
                messagebox.showerror("Sincronização", result.get("message", "Falha desconhecida."), parent=self)
