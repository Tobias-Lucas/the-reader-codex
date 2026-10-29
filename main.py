import logging
import sys

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

        from PySide6.QtWidgets import QApplication, QMessageBox
        from PySide6.QtCore import Qt
        from app.ui.main_window import MainWindow
        from app.ui.theme import preferred_ui_font_family

        app = QApplication(sys.argv)
        app.setApplicationName("The Reader Codex")
        app.setOrganizationName("The Reader Codex")
        app.setStyle("Fusion")
        font = app.font()
        font.setFamily(preferred_ui_font_family())
        font.setPointSize(10)
        app.setFont(font)

        window = MainWindow()
        window.show()
        return app.exec()
    except Exception as exc:
        logging.exception("Falha fatal ao iniciar The Reader Codex")
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(
                None,
                "The Reader Codex",
                "O aplicativo não conseguiu iniciar. Um log foi salvo na pasta de dados locais.\n\n"
                f"Detalhes: {exc}",
            )
        except Exception:
            print(f"The Reader Codex não conseguiu iniciar: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
