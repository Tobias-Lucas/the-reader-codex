
import os
import json
import customtkinter as ctk
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "config.json"


class LeituraApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("The Reader Codex")
        self.geometry("950x650")

        self.config_data = self.carregar_config()
        self.gc = None
        self.drive_service = None

        if not self.config_data or not os.path.exists("credentials.json"):
            self.abrir_tela_setup()
        else:
            self.conectar_servicos()
            self.inicializar_interface()

    def carregar_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def salvar_config(self, dados):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=4, ensure_ascii=False)

    def conectar_servicos(self):
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_file(
                "credentials.json",
                scopes=scopes,
            )
            self.gc = gspread.authorize(creds)
            self.drive_service = build(
                "drive",
                "v3",
                credentials=creds,
            )
            self.verificar_e_criar_abas_planilha()
        except Exception as e:
            print(f"Erro ao conectar com Google API: {e}")

    def verificar_e_criar_abas_planilha(self):
        try:
            sh = self.gc.open(self.config_data["planilha_nome"])
            abas_existentes = [ws.title for ws in sh.worksheets()]

            if "Categorias" not in abas_existentes:
                ws = sh.add_worksheet(title="Categorias", rows=100, cols=5)
                ws.append_row(["Nome", "Tipo"])
                ws.append_row(["Mangás", "Capitulo"])
                ws.append_row(["Livros", "Pagina"])

            if "Obras" not in abas_existentes:
                ws = sh.add_worksheet(title="Obras", rows=1000, cols=12)
                ws.append_row([
                    "ID",
                    "Nome",
                    "Categoria",
                    "ProgressoAtual",
                    "ProgressoTotal",
                    "Status",
                    "DiaLancamento",
                    "CapaID",
                    "UltimaAtualizacao",
                    "Sinopse",
                    "CreatedAt",
                    "UpdatedAt",
                ])

            if "Historico" not in abas_existentes:
                ws = sh.add_worksheet(title="Historico", rows=1000, cols=5)
                ws.append_row([
                    "IDObra",
                    "NomeObra",
                    "TextoAvanco",
                    "Data",
                    "CreatedAt",
                ])

        except Exception as e:
            print(f"Erro ao estruturar planilha: {e}")

    def abrir_tela_setup(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.title("Setup Inicial - The Reader Codex")

        frame = ctk.CTkFrame(self, width=600, height=500)
        frame.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            frame,
            text="Bem-vindo ao The Reader Codex!",
            font=("Arial", 20, "bold"),
        ).pack(pady=20)

        ctk.CTkLabel(
            frame,
            text=(
                "Configure seu perfil e suas credenciais da API do Google.\n"
                "Coloque o arquivo 'credentials.json' na pasta do programa."
            ),
            justify="left",
        ).pack(padx=20, pady=10)

        self.entry_nome = ctk.CTkEntry(
            frame,
            placeholder_text="Seu nome / perfil",
            width=350,
        )
        self.entry_nome.pack(pady=10)

        self.entry_planilha = ctk.CTkEntry(
            frame,
            placeholder_text="Nome da planilha no Google Sheets",
            width=350,
        )
        self.entry_planilha.pack(pady=10)

        self.entry_pasta = ctk.CTkEntry(
            frame,
            placeholder_text="ID da pasta do Google Drive",
            width=350,
        )
        self.entry_pasta.pack(pady=10)

        ctk.CTkButton(
            frame,
            text="Salvar e iniciar",
            command=self.salvar_setup,
        ).pack(pady=20)

    def salvar_setup(self):
        nome = self.entry_nome.get().strip()
        planilha = self.entry_planilha.get().strip()
        pasta = self.entry_pasta.get().strip()

        if not nome or not planilha or not pasta:
            return

        dados = {
            "perfil_nome": nome,
            "planilha_nome": planilha,
            "pasta_drive_id": pasta,
        }
        self.salvar_config(dados)
        self.config_data = dados
        self.conectar_servicos()
        self.inicializar_interface()

    def inicializar_interface(self):
        for widget in self.winfo_children():
            widget.destroy()

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")

        ctk.CTkLabel(
            self.sidebar,
            text=f"👤 {self.config_data.get('perfil_nome', 'Usuário')}",
            font=("Arial", 14, "bold"),
        ).pack(pady=20)

        ctk.CTkButton(
            self.sidebar,
            text="🏠 Início",
            command=lambda: self.tabview.set("Home"),
        ).pack(pady=8, padx=20)

        ctk.CTkButton(
            self.sidebar,
            text="⚙️ Configurações",
            command=self.abrir_tela_setup,
        ).pack(side="bottom", pady=20, padx=20)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(
            side="right",
            fill="both",
            expand=True,
            padx=10,
            pady=10,
        )

        for nome in ("Home", "Livros", "Mangás"):
            self.tabview.add(nome)

        ctk.CTkLabel(
            self.tabview.tab("Home"),
            text="Obras com lançamento programado para hoje aparecerão aqui.",
        ).pack(pady=20)


if __name__ == "__main__":
    app = LeituraApp()
    app.mainloop()
