import hashlib
import io
import json
from pathlib import Path

from app.paths import DATA_DIR


class GoogleSyncError(RuntimeError):
    pass


class GoogleSyncConfigurationError(GoogleSyncError):
    pass


class GoogleSyncAdapter:
    """Google Sheets + Drive provider used by the local-first SyncEngine.

    Sheets stores structured metadata. Drive stores cover image binaries. Imports are
    lazy so the application still opens locally if Google dependencies are missing.
    """

    WORKS_HEADERS = [
        "id", "name", "category", "progress_unit", "progress_current",
        "progress_total", "status", "release_day", "synopsis", "rating",
        "favorite", "personal_notes", "start_date", "end_date",
        "cover_remote_id", "cover_filename", "cover_remote_modified", "created_at", "updated_at",
        "deleted_at", "tags_json",
    ]
    CATEGORIES_HEADERS = ["id", "name", "created_at", "updated_at", "deleted_at"]
    GOALS_HEADERS = [
        "id", "title", "goal_type", "target_value", "current_value",
        "start_date", "end_date", "created_at", "updated_at", "deleted_at",
    ]
    HISTORY_HEADERS = [
        "id", "work_id", "description", "event_type", "delta",
        "progress_unit", "created_at",
    ]
    META_HEADERS = ["key", "value"]

    def __init__(self, google_settings):
        self.settings = dict(google_settings or {})
        self.credentials_file = str(self.settings.get("credentials_file", "")).strip()
        self.spreadsheet_id = str(self.settings.get("spreadsheet_id", "")).strip()
        self.spreadsheet_name = str(self.settings.get("spreadsheet_name", "The Reader Codex")).strip() or "The Reader Codex"
        self.drive_folder_id = str(self.settings.get("drive_folder_id", "")).strip()
        self._sheets = None
        self._drive = None

    @staticmethod
    def _load_discovery_builder():
        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleSyncConfigurationError(
                "Dependências do Google não instaladas. Execute: pip install -r requirements.txt"
            ) from exc
        return build

    def _read_credentials_config(self):
        credentials_path = Path(self.credentials_file).expanduser()
        if not credentials_path.is_file():
            raise GoogleSyncConfigurationError(f"Credenciais não encontradas: {credentials_path}")
        try:
            raw = credentials_path.read_bytes()
            config = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GoogleSyncConfigurationError("O arquivo de credenciais não contém um JSON válido.") from exc
        if not isinstance(config, dict):
            raise GoogleSyncConfigurationError("Formato de credenciais Google não reconhecido.")
        return credentials_path, raw, config

    @staticmethod
    def _credentials_kind(config):
        if config.get("type") == "service_account":
            return "service_account"
        if isinstance(config.get("installed"), dict) or isinstance(config.get("web"), dict):
            return "oauth"
        return "unknown"

    @staticmethod
    def _oauth_token_path(credentials_path, raw_credentials):
        fingerprint = hashlib.sha256(
            str(credentials_path.resolve()).encode("utf-8") + b"\0" + raw_credentials
        ).hexdigest()[:16]
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        return DATA_DIR / f"google_token_{fingerprint}.json"

    def _build_credentials(self, scopes):
        credentials_path, raw, config = self._read_credentials_config()
        kind = self._credentials_kind(config)

        if kind == "service_account":
            try:
                from google.oauth2.service_account import Credentials
            except ImportError as exc:
                raise GoogleSyncConfigurationError(
                    "Dependências do Google não instaladas. Execute: pip install -r requirements.txt"
                ) from exc
            return Credentials.from_service_account_file(str(credentials_path), scopes=scopes)

        if kind == "oauth":
            try:
                from google.auth.transport.requests import Request
                from google.oauth2.credentials import Credentials as UserCredentials
                from google_auth_oauthlib.flow import InstalledAppFlow
            except ImportError as exc:
                raise GoogleSyncConfigurationError(
                    "Suporte OAuth não instalado. Execute: pip install -r requirements.txt"
                ) from exc

            token_path = self._oauth_token_path(credentials_path, raw)
            creds = None
            if token_path.is_file():
                try:
                    creds = UserCredentials.from_authorized_user_file(str(token_path), scopes=scopes)
                except Exception:
                    token_path.unlink(missing_ok=True)
                    creds = None

            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    token_path.unlink(missing_ok=True)
                    creds = None

            if not creds or not creds.valid:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), scopes=scopes)
                    creds = flow.run_local_server(port=0, open_browser=True)
                except Exception as exc:
                    raise GoogleSyncConfigurationError(
                        "Não foi possível concluir o login OAuth do Google. Verifique o cliente OAuth Desktop e tente novamente."
                    ) from exc
                token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds

        raise GoogleSyncConfigurationError(
            "Formato de credentials.json não reconhecido. Use credenciais OAuth de aplicativo Desktop "
            "ou uma conta de serviço do Google Cloud."
        )

    def connect(self):
        if not self.credentials_file:
            raise GoogleSyncConfigurationError("Selecione o arquivo de credenciais do Google.")

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        try:
            creds = self._build_credentials(scopes)
            build = self._load_discovery_builder()
            self._sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
            self._drive = build("drive", "v3", credentials=creds, cache_discovery=False)
            self.spreadsheet_id = self._resolve_spreadsheet()
            self._ensure_worksheets()
        except GoogleSyncError:
            raise
        except Exception as exc:
            raise GoogleSyncError(f"Falha ao conectar ao Google: {exc}") from exc
        return {
            "spreadsheet_id": self.spreadsheet_id,
            "spreadsheet_name": self.spreadsheet_name,
        }

    def _resolve_spreadsheet(self):
        if self.spreadsheet_id:
            try:
                info = self._sheets.spreadsheets().get(
                    spreadsheetId=self.spreadsheet_id,
                    fields="spreadsheetId,properties.title",
                ).execute()
                self.spreadsheet_name = info.get("properties", {}).get("title", self.spreadsheet_name)
                return info["spreadsheetId"]
            except Exception as exc:
                raise GoogleSyncConfigurationError(
                    "Não foi possível abrir a planilha pelo ID informado. Verifique o ID e as permissões da conta Google usada."
                ) from exc

        escaped_name = self.spreadsheet_name.replace("'", "\\'")
        query = (
            "mimeType='application/vnd.google-apps.spreadsheet' "
            f"and name='{escaped_name}' and trashed=false"
        )
        if self.drive_folder_id:
            query += f" and '{self.drive_folder_id}' in parents"
        result = self._drive.files().list(
            q=query,
            spaces="drive",
            fields="files(id,name)",
            pageSize=20,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()
        files = result.get("files", [])
        if files:
            return files[0]["id"]

        try:
            created = self._sheets.spreadsheets().create(
                body={"properties": {"title": self.spreadsheet_name}},
                fields="spreadsheetId",
            ).execute()
        except Exception as exc:
            raise GoogleSyncConfigurationError(
                "Não encontrei a planilha e a conta de serviço não conseguiu criar uma nova. "
                "Crie uma planilha no Google Sheets, compartilhe-a com o e-mail da conta de serviço e informe o ID nas configurações."
            ) from exc
        spreadsheet_id = created["spreadsheetId"]
        if self.drive_folder_id:
            try:
                meta = self._drive.files().get(
                    fileId=spreadsheet_id, fields="parents", supportsAllDrives=True
                ).execute()
                previous = ",".join(meta.get("parents", []))
                kwargs = {
                    "fileId": spreadsheet_id,
                    "addParents": self.drive_folder_id,
                    "fields": "id,parents",
                    "supportsAllDrives": True,
                }
                if previous:
                    kwargs["removeParents"] = previous
                self._drive.files().update(**kwargs).execute()
            except Exception as exc:
                raise GoogleSyncConfigurationError(
                    "A planilha foi criada, mas não pôde ser movida para a pasta do Drive. "
                    "Conceda acesso à pasta/Shared Drive para a conta usada ou deixe o ID da pasta vazio."
                ) from exc
        return spreadsheet_id

    def _ensure_worksheets(self):
        info = self._sheets.spreadsheets().get(
            spreadsheetId=self.spreadsheet_id,
            fields="sheets.properties.title",
        ).execute()
        existing = {sheet["properties"]["title"] for sheet in info.get("sheets", [])}
        required = ["Works", "Categories", "Goals", "History", "Meta"]
        requests = []
        for title in required:
            if title not in existing:
                requests.append({"addSheet": {"properties": {"title": title, "gridProperties": {"rowCount": 1000, "columnCount": 26}}}})
        if requests:
            self._sheets.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={"requests": requests},
            ).execute()

    @staticmethod
    def _as_text(value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        return str(value)

    @staticmethod
    def _as_int(value, default=0):
        if value in (None, ""):
            return default
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_optional_int(value):
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_optional_float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _as_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).strip().casefold() in {"1", "true", "yes", "sim", "verdadeiro"}

    def _get_rows(self, title, headers):
        response = self._sheets.spreadsheets().values().get(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{title}'!A:Z",
        ).execute()
        values = response.get("values", [])
        if not values:
            return []
        first = [str(value).strip() for value in values[0]]
        # If a user changed headers, map only the columns that still exist.
        indices = {name: first.index(name) for name in headers if name in first}
        rows = []
        for raw in values[1:]:
            item = {}
            for header in headers:
                index = indices.get(header)
                item[header] = raw[index] if index is not None and index < len(raw) else ""
            if any(str(value).strip() for value in item.values()):
                rows.append(item)
        return rows

    def _replace_rows(self, title, headers, rows):
        self._sheets.spreadsheets().values().clear(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{title}'!A:Z",
            body={},
        ).execute()
        values = [headers] + [[self._as_text(row.get(header)) for header in headers] for row in rows]
        self._sheets.spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id,
            range=f"'{title}'!A1",
            valueInputOption="RAW",
            body={"values": values},
        ).execute()

    def download_payload(self):
        if not self._sheets:
            self.connect()
        works = []
        for row in self._get_rows("Works", self.WORKS_HEADERS):
            if not row.get("id"):
                continue
            try:
                tags = json.loads(row.get("tags_json") or "[]")
                if not isinstance(tags, list):
                    tags = []
            except json.JSONDecodeError:
                tags = []
            works.append({
                "id": row["id"],
                "name": row.get("name", ""),
                "category": row.get("category", ""),
                "progress_unit": row.get("progress_unit") or "Página",
                "progress_current": self._as_int(row.get("progress_current"), 0),
                "progress_total": self._as_optional_int(row.get("progress_total")),
                "status": row.get("status") or "Quero ler",
                "release_day": row.get("release_day") or None,
                "synopsis": row.get("synopsis", ""),
                "rating": self._as_optional_float(row.get("rating")),
                "favorite": self._as_bool(row.get("favorite")),
                "personal_notes": row.get("personal_notes", ""),
                "start_date": row.get("start_date") or None,
                "end_date": row.get("end_date") or None,
                "cover_remote_id": row.get("cover_remote_id") or None,
                "cover_filename": row.get("cover_filename") or None,
                "cover_remote_modified": row.get("cover_remote_modified") or None,
                "created_at": row.get("created_at") or "",
                "updated_at": row.get("updated_at") or "",
                "deleted_at": row.get("deleted_at") or None,
                "tags": [str(tag).strip() for tag in tags if str(tag).strip()],
            })

        categories = []
        for row in self._get_rows("Categories", self.CATEGORIES_HEADERS):
            if row.get("id") and row.get("name"):
                categories.append({
                    "id": row["id"], "name": row["name"],
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                    "deleted_at": row.get("deleted_at") or None,
                })

        goals = []
        for row in self._get_rows("Goals", self.GOALS_HEADERS):
            if row.get("id"):
                goals.append({
                    "id": row["id"], "title": row.get("title", "Meta"),
                    "goal_type": row.get("goal_type") or "books",
                    "target_value": self._as_int(row.get("target_value"), 1),
                    "current_value": self._as_int(row.get("current_value"), 0),
                    "start_date": row.get("start_date") or None,
                    "end_date": row.get("end_date") or None,
                    "created_at": row.get("created_at") or "",
                    "updated_at": row.get("updated_at") or "",
                    "deleted_at": row.get("deleted_at") or None,
                })

        history = []
        for row in self._get_rows("History", self.HISTORY_HEADERS):
            if row.get("id") and row.get("work_id"):
                history.append({
                    "id": row["id"], "work_id": row["work_id"],
                    "description": row.get("description", ""),
                    "event_type": row.get("event_type") or "progress",
                    "delta": self._as_optional_int(row.get("delta")),
                    "progress_unit": row.get("progress_unit") or None,
                    "created_at": row.get("created_at") or "",
                })
        return {
            "schema_version": 5,
            "works": works,
            "categories": categories,
            "goals": goals,
            "history": history,
        }

    def upload_payload(self, payload):
        if not self._sheets:
            self.connect()
        works = []
        for item in payload.get("works", []):
            row = dict(item)
            row["tags_json"] = json.dumps(item.get("tags", []), ensure_ascii=False, separators=(",", ":"))
            works.append(row)
        self._replace_rows("Works", self.WORKS_HEADERS, works)
        self._replace_rows("Categories", self.CATEGORIES_HEADERS, payload.get("categories", []))
        self._replace_rows("Goals", self.GOALS_HEADERS, payload.get("goals", []))
        self._replace_rows("History", self.HISTORY_HEADERS, payload.get("history", []))
        self._replace_rows("Meta", self.META_HEADERS, [
            {"key": "schema_version", "value": payload.get("schema_version", 5)},
            {"key": "application", "value": "The Reader Codex"},
        ])

    def upload_cover(self, local_path, remote_id=None):
        if not self._drive:
            self.connect()
        try:
            from googleapiclient.http import MediaFileUpload
            from googleapiclient.errors import HttpError
        except ImportError as exc:
            raise GoogleSyncConfigurationError("Dependências do Google não instaladas.") from exc

        path = Path(local_path)
        if not path.is_file():
            raise GoogleSyncError(f"Capa local não encontrada: {path}")
        media = MediaFileUpload(str(path), resumable=False)
        body = {"name": path.name}
        if remote_id:
            try:
                result = self._drive.files().update(
                    fileId=remote_id,
                    body=body,
                    media_body=media,
                    fields="id,name,modifiedTime",
                    supportsAllDrives=True,
                ).execute()
                return result["id"], result.get("name", path.name), result.get("modifiedTime")
            except HttpError as exc:
                if getattr(exc.resp, "status", None) != 404:
                    raise GoogleSyncError(f"Falha ao atualizar capa no Drive: {exc}") from exc
        if self.drive_folder_id:
            body["parents"] = [self.drive_folder_id]
        try:
            result = self._drive.files().create(
                body=body, media_body=media, fields="id,name,modifiedTime", supportsAllDrives=True
            ).execute()
            return result["id"], result.get("name", path.name), result.get("modifiedTime")
        except Exception as exc:
            raise GoogleSyncError(f"Falha ao enviar capa ao Drive: {exc}") from exc

    def delete_cover(self, remote_id):
        if not remote_id:
            return
        if not self._drive:
            self.connect()
        try:
            from googleapiclient.errors import HttpError
            self._drive.files().delete(fileId=remote_id, supportsAllDrives=True).execute()
        except HttpError as exc:
            if getattr(exc.resp, "status", None) != 404:
                raise GoogleSyncError(f"Falha ao excluir capa do Drive: {exc}") from exc

    def download_cover(self, remote_id, destination):
        if not remote_id:
            return None
        if not self._drive:
            self.connect()
        try:
            from googleapiclient.http import MediaIoBaseDownload
        except ImportError as exc:
            raise GoogleSyncConfigurationError("Dependências do Google não instaladas.") from exc
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        request = self._drive.files().get_media(fileId=remote_id, supportsAllDrives=True)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        try:
            while not done:
                _, done = downloader.next_chunk()
            destination.write_bytes(buffer.getvalue())
        except Exception as exc:
            raise GoogleSyncError(f"Falha ao baixar capa do Drive: {exc}") from exc
        return str(destination.resolve())
