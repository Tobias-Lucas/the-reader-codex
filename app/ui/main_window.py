import threading
import customtkinter as ctk
from tkinter import filedialog, messagebox

from app.components.work_card import WorkCard
from app.repositories.sqlite_repository import SQLiteWorkRepository
from app.services.backup_service import BackupService
from app.services.sync_engine import SyncEngine
from app.ui.work_details_dialog import WorkDetailsDialog


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("The Reader Codex")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.repo = SQLiteWorkRepository()
        self.sync_engine = SyncEngine(self.repo)
        self.backup_service = BackupService(self.repo)

        self._seed_demo()
        self._build_shell()
        self.show_home()

        self.after(1500, self.sync_in_background)
        self.after(2500, self._startup_backup)

    def _seed_demo(self):
        if self.repo.list_all():
            return

        duna = self.repo.create(
            name="Duna",
            category="Livro",
            progress_unit="Página",
            progress_current=241,
            progress_total=412,
            status="Lendo",
            rating=5,
            favorite=True,
            personal_notes="Excelente construção de mundo.",
        )
        self.repo.set_tags(
            duna.id,
            ["ficção científica", "clássico"],
        )

        frieren = self.repo.create(
            name="Frieren",
            category="Mangá",
            progress_unit="Capítulo",
            progress_current=128,
            progress_total=140,
            status="Lendo",
            release_day="Terça-feira",
            rating=4,
        )
        self.repo.set_tags(
            frieren.id,
            ["fantasia", "mangá"],
        )

    def _build_shell(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(
            self,
            width=220,
            corner_radius=0,
        )
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
            ("⭐  Favoritos", self.show_favorites),
            ("🕘  Histórico", self.show_history),
            ("💾  Backup", self.show_backup),
        ]:
            ctk.CTkButton(
                self.sidebar,
                text=text,
                anchor="w",
                command=command,
                height=42,
            ).pack(fill="x", padx=14, pady=6)

        self.sync_label = ctk.CTkLabel(
            self.sidebar,
            text="☁ Verificando sincronização...",
            text_color=("gray35", "gray70"),
            wraplength=180,
        )
        self.sync_label.pack(
            side="bottom",
            pady=(0, 18),
        )

        self.content = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self.content.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=24,
            pady=20,
        )

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
        ).pack(
            fill="x",
            pady=(4, 18),
        )

    def _render_work(self, work):
        total = work.progress_total or 0
        percent = (
            work.progress_current / total
            if total and total > 0
            else 0
        )

        progress_text = (
            f"{work.progress_current} / "
            f"{work.progress_total} "
            f"{work.progress_unit.lower()}s"
            if work.progress_total
            else f"{work.progress_unit}: {work.progress_current}"
        )

        tags = self.repo.get_tags(work.id)
        rating = f"{'★' * (work.rating or 0)}"
        favorite = "⭐ " if work.favorite else ""
        extra = " • ".join(
            part
            for part in [
                favorite + rating if rating else favorite.strip(),
                ", ".join(tags[:3]),
            ]
            if part
        )

        frame = WorkCard(
            self.content,
            title=work.name,
            category=work.category,
            progress_text=progress_text,
            status=work.status,
            percent=percent,
            on_increment=lambda wid=work.id: self._increment(wid),
            extra_text=extra,
        )
        frame.pack(fill="x", pady=7)

        ctk.CTkButton(
            frame,
            text="Detalhes",
            width=86,
            command=lambda w=work: self.open_details(w),
        ).grid(
            row=3,
            column=2,
            padx=14,
            pady=(0, 8),
        )

    def _increment(self, work_id):
        self.repo.increment_progress(work_id)
        self.show_library()

    def open_details(self, work):
        WorkDetailsDialog(
            self,
            self.repo,
            work,
            on_saved=self.show_library,
        )

    def show_home(self):
        self._clear_content()
        self._header(
            "Início",
            "Sua leitura, organizada do seu jeito.",
        )

        works = self.repo.list_all()
        if works:
            self._render_work(works[0])

    def show_library(self):
        self._clear_content()
        self._header(
            "Biblioteca",
            "Tags, avaliações, favoritos e notas pessoais.",
        )

        for work in self.repo.list_all():
            self._render_work(work)

    def show_favorites(self):
        self._clear_content()
        self._header(
            "Favoritos",
            "Obras marcadas como favoritas.",
        )

        favorites = [
            work
            for work in self.repo.list_all()
            if work.favorite
        ]

        if not favorites:
            ctk.CTkLabel(
                self.content,
                text="Nenhuma obra favorita ainda.",
            ).pack(anchor="w")
            return

        for work in favorites:
            self._render_work(work)

    def show_history(self):
        self._clear_content()
        self._header("Histórico", "Avanços recentes.")

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
                text="Ainda não há registros.",
            ).pack(anchor="w")
            return

        for row in rows:
            ctk.CTkLabel(
                self.content,
                text=f"{row['name']} • {row['description']}",
                anchor="w",
            ).pack(fill="x", pady=4)

    def show_backup(self):
        self._clear_content()
        self._header(
            "Backup e dados",
            "Importação, exportação e cópias de segurança.",
        )

        ctk.CTkButton(
            self.content,
            text="Exportar biblioteca para JSON",
            command=self.export_json,
        ).pack(anchor="w", pady=6)

        ctk.CTkButton(
            self.content,
            text="Importar biblioteca de JSON",
            command=self.import_json,
        ).pack(anchor="w", pady=6)

        ctk.CTkButton(
            self.content,
            text="Criar backup agora",
            command=self.manual_backup,
        ).pack(anchor="w", pady=6)

    def export_json(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="the-reader-codex-export.json",
        )
        if not path:
            return

        self.backup_service.export_json(path)
        messagebox.showinfo(
            "Exportação concluída",
            f"Dados exportados para:\n{path}",
        )

    def import_json(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON", "*.json")]
        )
        if not path:
            return

        if not messagebox.askyesno(
            "Importar dados",
            "A importação substituirá os dados locais atuais. Continuar?",
        ):
            return

        self.backup_service.create_automatic_backup()
        self.backup_service.import_json(path)
        messagebox.showinfo(
            "Importação concluída",
            "Os dados foram importados com sucesso.",
        )
        self.show_library()

    def manual_backup(self):
        result = self.backup_service.create_automatic_backup()
        messagebox.showinfo(
            "Backup criado",
            f"Backup JSON:\n{result['json']}",
        )

    def _startup_backup(self):
        try:
            self.backup_service.create_automatic_backup()
        except Exception as exc:
            print(f"Falha ao criar backup automático: {exc}")

    def sync_in_background(self):
        self.sync_label.configure(text="☁ Sincronizando...")

        def worker():
            result = self.sync_engine.sync()
            self.after(
                0,
                lambda: self._apply_sync_result(result),
            )

        threading.Thread(
            target=worker,
            daemon=True,
        ).start()

    def _apply_sync_result(self, result):
        if result["status"] == "offline":
            self.sync_label.configure(
                text="○ Offline\nDados protegidos localmente."
            )
            return

        self.sync_label.configure(
            text="☁ Sincronizado"
        )
