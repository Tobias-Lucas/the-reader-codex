import json
import os
import shutil
import sys
from pathlib import Path

APP_NAME = "The Reader Codex"
APP_DIR_NAME = "TheReaderCodex"
PROJECT_DIR = Path(__file__).resolve().parents[1]
IS_FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_DIR)).resolve()


def _default_local_appdata(env=None):
    env = env or os.environ
    configured = env.get("LOCALAPPDATA")
    if configured:
        return Path(configured).expanduser()
    if os.name == "nt":
        return Path.home() / "AppData" / "Local"
    xdg_data_home = env.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home).expanduser()
    return Path.home() / ".local" / "share"


def resolve_data_dir(is_frozen=None, env=None):
    """Return the writable user-data directory.

    During development the project-local ``data`` directory is kept for convenience.
    A packaged/frozen build stores mutable files outside the installation directory so
    it works under Windows Program Files / LocalAppData Programs and survives updates.
    ``THE_READER_CODEX_DATA_DIR`` is supported for tests and advanced portable setups.
    """

    env = env or os.environ
    override = env.get("THE_READER_CODEX_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    frozen = IS_FROZEN if is_frozen is None else bool(is_frozen)
    if frozen:
        return (_default_local_appdata(env) / APP_DIR_NAME).resolve()
    return (PROJECT_DIR / "data").resolve()


DATA_DIR = resolve_data_dir()
DB_PATH = DATA_DIR / "reader.db"
COVERS_DIR = DATA_DIR / "covers"
BACKUPS_DIR = DATA_DIR / "backups"
LOGS_DIR = DATA_DIR / "logs"
SETTINGS_PATH = DATA_DIR / "settings.json"
DEFAULT_CREDENTIALS_PATH = DATA_DIR / "credentials.json"
ASSETS_DIR = RESOURCE_DIR / "assets"
APP_ICON_PATH = ASSETS_DIR / "TheReaderCodex.ico"


def ensure_data_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    COVERS_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _legacy_portable_root():
    if not IS_FROZEN:
        return None
    try:
        return Path(sys.executable).resolve().parent
    except Exception:
        return None


def migrate_legacy_portable_data():
    """Migrate a legacy portable install once, without overwriting current user data.

    Older builds stored ``data`` and optionally ``credentials.json`` next to the app.
    Packaged builds now use ``%LOCALAPPDATA%\\TheReaderCodex``. If the destination is
    still empty, copy the old data and repair the credentials path in settings.
    """

    root = _legacy_portable_root()
    if root is None:
        return False

    legacy_data = root / "data"
    if not legacy_data.is_dir() or legacy_data.resolve() == DATA_DIR.resolve():
        return False

    # Do not merge automatically into an already initialized profile.
    meaningful_targets = [DB_PATH, SETTINGS_PATH, COVERS_DIR, BACKUPS_DIR]
    if DB_PATH.exists() or SETTINGS_PATH.exists() or any(COVERS_DIR.glob("*")) or any(BACKUPS_DIR.glob("*")):
        return False

    ensure_data_dirs()
    migrated = False

    for filename in ("reader.db", "reader.db-wal", "reader.db-shm", "settings.json"):
        source = legacy_data / filename
        destination = DATA_DIR / filename
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
            migrated = True

    for folder_name in ("covers", "backups"):
        source_dir = legacy_data / folder_name
        destination_dir = DATA_DIR / folder_name
        if source_dir.is_dir():
            shutil.copytree(source_dir, destination_dir, dirs_exist_ok=True)
            migrated = True

    for token_file in legacy_data.glob("google_token_*.json"):
        destination = DATA_DIR / token_file.name
        if token_file.is_file() and not destination.exists():
            shutil.copy2(token_file, destination)
            migrated = True

    legacy_credentials = root / "credentials.json"
    if legacy_credentials.is_file() and not DEFAULT_CREDENTIALS_PATH.exists():
        shutil.copy2(legacy_credentials, DEFAULT_CREDENTIALS_PATH)
        migrated = True

    # If the copied settings referenced the old portable credentials, point it to the
    # migrated copy. Invalid/other custom paths are intentionally left untouched.
    if SETTINGS_PATH.is_file() and DEFAULT_CREDENTIALS_PATH.is_file():
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            google = settings.get("google") if isinstance(settings.get("google"), dict) else {}
            current = str(google.get("credentials_file", "")).strip()
            old_default = str(legacy_credentials)
            if not current or Path(current).expanduser() == legacy_credentials or current == old_default:
                google["credentials_file"] = str(DEFAULT_CREDENTIALS_PATH)
                settings["google"] = google
                SETTINGS_PATH.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass

    return migrated
