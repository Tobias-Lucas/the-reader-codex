import logging
from tkinter import messagebox

from app.paths import LOGS_DIR, ensure_data_dirs, migrate_legacy_portable_data


def _configure_logging():
    ensure_data_dirs()
    logging.basicConfig(
        filename=LOGS_DIR / "the-reader-codex.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        encoding="utf-8",
    )


def main():
    _configure_logging()
    try:
        if migrate_legacy_portable_data():
            logging.info("Dados de uma instalação portátil anterior foram migrados para o perfil do usuário.")

        import customtkinter as ctk
        from app.ui.theme import apply_obsidian_theme

        ctk.set_default_color_theme("dark-blue")
        apply_obsidian_theme()
        from app.ui.main_window import MainWindow

        app = MainWindow()
        app.mainloop()
    except Exception as exc:
        logging.exception("Falha fatal ao iniciar The Reader Codex")
        try:
            messagebox.showerror(
                "The Reader Codex",
                "O aplicativo não conseguiu iniciar. Um log foi salvo na pasta de dados locais.\n\n"
                f"Detalhes: {exc}",
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    main()
