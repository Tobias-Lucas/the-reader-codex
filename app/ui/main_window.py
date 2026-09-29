
import customtkinter as ctk
from app.components.work_card import WorkCard
from app.repositories.sqlite_repository import SQLiteWorkRepository


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("The Reader Codex")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.repo = SQLiteWorkRepository()
        self._seed_demo()

        self._build_shell()
        self.show_home()

    def _seed_demo(self):
        if self.repo.list_all():
            return

        self.repo.create(
            name="Duna",
            category="Livro",
            progress_unit="Página",
            progress_current=241,
            progress_total=412,
            status="Lendo",
        )
        self.repo.create(
            name="Frieren",
            category="Mangá",
            progress_unit="Capítulo",
            progress_current=128,
            progress_total=140,
            status="Lendo",
            release_day="Terça-feira",
        )

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsw")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="The Reader Codex",
            font=("Arial", 20, "bold"),
        ).pack(padx=20, pady=(24, 28))

        for text, command in [
            ("🏠  Início", self.show_home),
            ("📚  Biblioteca", self.show_library),
            ("🕘  Histórico", self.show_history),
        ]:
            ctk.CTkButton(
                self.sidebar,
                text=text,
                anchor="w",
                command=command,
                height=42,
            ).pack(fill="x", padx=14, pady=6)

        ctk.CTkLabel(
            self.sidebar,
            text="● Modo local",
            text_color=("gray35", "gray70"),
        ).pack(side="bottom", pady=18)

        self.content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=24, pady=20)

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def _header(self, title, subtitle):
        ctk.CTkLabel(
            self.content,
            text=title,
            font=("Arial", 28, "bold"),
            anchor="w",
        ).pack(fill="x")
        ctk.CTkLabel(
            self.content,
            text=subtitle,
            text_color=("gray35", "gray70"),
            anchor="w",
        ).pack(fill="x", pady=(4, 18))

    def _render_work(self, work):
        total = work.progress_total or 0
        percent = (
            work.progress_current / total
            if total and total > 0
            else 0
        )
        progress_text = (
            f"{work.progress_current} / {work.progress_total} {work.progress_unit.lower()}s"
            if work.progress_total
            else f"{work.progress_unit}: {work.progress_current}"
        )

        WorkCard(
            self.content,
            title=work.name,
            category=work.category,
            progress_text=progress_text,
            status=work.status,
            percent=percent,
            on_increment=lambda wid=work.id: self._increment(wid),
        ).pack(fill="x", pady=7)

    def _increment(self, work_id):
        self.repo.increment_progress(work_id)
        self.show_library()

    def show_home(self):
        self._clear_content()
        self._header(
            "Início",
            "Sua biblioteca agora funciona mesmo sem internet.",
        )

        ctk.CTkLabel(
            self.content,
            text="Continue lendo",
            font=("Arial", 18, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(8, 10))

        works = self.repo.list_all()
        if works:
            self._render_work(works[0])

    def show_library(self):
        self._clear_content()
        self._header(
            "Biblioteca",
            "Dados carregados do SQLite local.",
        )

        for work in self.repo.list_all():
            self._render_work(work)

    def show_history(self):
        self._clear_content()
        self._header("Histórico", "Avanços registrados localmente.")

        with self.repo._connect() as conn:
            rows = conn.execute("""
                SELECT h.created_at, h.description, w.name
                FROM history h
                JOIN works w ON w.id = h.work_id
                ORDER BY h.created_at DESC
            """).fetchall()

        if not rows:
            ctk.CTkLabel(
                self.content,
                text="Ainda não há registros de progresso.",
            ).pack(anchor="w")
            return

        for row in rows:
            ctk.CTkLabel(
                self.content,
                text=f"{row['name']} • {row['description']}",
                anchor="w",
            ).pack(fill="x", pady=4)
