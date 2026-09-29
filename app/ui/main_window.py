
import customtkinter as ctk
from app.components.work_card import WorkCard


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("The Reader Codex")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self._build_shell()
        self.show_home()

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
            ("📅  Agenda", self.show_schedule),
            ("🕘  Histórico", self.show_history),
        ]:
            ctk.CTkButton(
                self.sidebar,
                text=text,
                anchor="w",
                command=command,
                height=42,
            ).pack(fill="x", padx=14, pady=6)

        ctk.CTkButton(
            self.sidebar,
            text="⚙️  Configurações",
            anchor="w",
            command=self.show_settings,
            height=42,
        ).pack(side="bottom", fill="x", padx=14, pady=18)

        self.content = ctk.CTkFrame(self, fg_color="transparent")
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

    def show_home(self):
        self._clear_content()
        self._header(
            "Início",
            "Continue de onde parou e acompanhe seus próximos lançamentos.",
        )

        ctk.CTkLabel(
            self.content,
            text="Continue lendo",
            font=("Arial", 18, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(8, 10))

        WorkCard(
            self.content,
            title="Duna",
            category="Livro",
            progress_text="241 / 412 páginas",
            status="Lendo",
            percent=0.58,
        ).pack(fill="x", pady=8)

        ctk.CTkLabel(
            self.content,
            text="Lançamentos de hoje",
            font=("Arial", 18, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(24, 10))

        empty = ctk.CTkFrame(self.content)
        empty.pack(fill="x")
        ctk.CTkLabel(
            empty,
            text="Nenhum lançamento programado para hoje.",
        ).pack(pady=24)

    def show_library(self):
        self._clear_content()
        self._header(
            "Biblioteca",
            "Pesquise, filtre e atualize o progresso das suas leituras.",
        )

        toolbar = ctk.CTkFrame(self.content, fg_color="transparent")
        toolbar.pack(fill="x", pady=(0, 14))

        ctk.CTkEntry(
            toolbar,
            placeholder_text="🔍 Buscar na biblioteca...",
            width=360,
        ).pack(side="left")

        ctk.CTkButton(
            toolbar,
            text="+ Adicionar obra",
            width=150,
        ).pack(side="right")

        for data in [
            ("Frieren", "Mangá", "128 / 140 capítulos", "Lendo", 0.91),
            ("Duna", "Livro", "241 / 412 páginas", "Lendo", 0.58),
            ("Berserk", "Mangá", "241 / 380 capítulos", "Pausado", 0.63),
        ]:
            WorkCard(
                self.content,
                title=data[0],
                category=data[1],
                progress_text=data[2],
                status=data[3],
                percent=data[4],
            ).pack(fill="x", pady=7)

    def show_schedule(self):
        self._clear_content()
        self._header("Agenda", "Visualize os próximos lançamentos.")
        ctk.CTkLabel(
            self.content,
            text="Terça-feira\n• Frieren\n\nQuinta-feira\n• Kaiju No. 8",
            justify="left",
            anchor="w",
        ).pack(fill="x")

    def show_history(self):
        self._clear_content()
        self._header("Histórico", "Acompanhe seus avanços recentes.")
        ctk.CTkLabel(
            self.content,
            text="Hoje  • Duna: página 230 → 241\nOntem • Frieren: capítulo 127 → 128",
            justify="left",
            anchor="w",
        ).pack(fill="x")

    def show_settings(self):
        self._clear_content()
        self._header("Configurações", "Preferências do aplicativo.")
        ctk.CTkLabel(
            self.content,
            text="Persistência local e sincronização serão introduzidas na próxima versão.",
        ).pack(anchor="w")
