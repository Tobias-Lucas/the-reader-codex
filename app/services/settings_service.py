import json
from pathlib import Path

from app.paths import DEFAULT_CREDENTIALS_PATH, SETTINGS_PATH


class SettingsService:
    DEFAULTS = {
        "sync_enabled": False,
        "profile_name": "",
        "google": {
            "credentials_file": str(DEFAULT_CREDENTIALS_PATH),
            "spreadsheet_id": "",
            "spreadsheet_name": "The Reader Codex",
            "drive_folder_id": "",
        },
    }

    def __init__(self, settings_path=None):
        self.settings_path = Path(settings_path or SETTINGS_PATH)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self):
        data = {}
        if self.settings_path.exists():
            try:
                with self.settings_path.open("r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    data = loaded
            except (OSError, json.JSONDecodeError):
                data = {}
        merged = {
            "sync_enabled": bool(data.get("sync_enabled", self.DEFAULTS["sync_enabled"])),
            "profile_name": str(data.get("profile_name", self.DEFAULTS["profile_name"])),
            "google": dict(self.DEFAULTS["google"]),
        }
        google = data.get("google") if isinstance(data.get("google"), dict) else {}
        merged["google"].update({
            key: str(google.get(key, default) or "")
            for key, default in self.DEFAULTS["google"].items()
        })
        return merged

    def save(self, settings):
        google = settings.get("google") if isinstance(settings.get("google"), dict) else {}
        normalized = {
            "sync_enabled": bool(settings.get("sync_enabled", False)),
            "profile_name": str(settings.get("profile_name", "")).strip(),
            "google": {
                "credentials_file": str(google.get("credentials_file", "")).strip(),
                "spreadsheet_id": str(google.get("spreadsheet_id", "")).strip(),
                "spreadsheet_name": str(google.get("spreadsheet_name", "The Reader Codex")).strip() or "The Reader Codex",
                "drive_folder_id": str(google.get("drive_folder_id", "")).strip(),
            },
        }
        temp = self.settings_path.with_suffix(self.settings_path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as f:
            json.dump(normalized, f, indent=2, ensure_ascii=False)
        temp.replace(self.settings_path)
        return normalized

    def update_google_identifiers(self, spreadsheet_id=None):
        settings = self.load()
        if spreadsheet_id:
            settings["google"]["spreadsheet_id"] = spreadsheet_id
        return self.save(settings)
