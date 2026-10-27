from pathlib import Path

from app.paths import COVERS_DIR
from app.services.google_sync_adapter import (
    GoogleSyncAdapter,
    GoogleSyncConfigurationError,
    GoogleSyncError,
)


class SyncEngine:
    def __init__(self, repository, settings_service, adapter_factory=GoogleSyncAdapter):
        self.repository = repository
        self.settings_service = settings_service
        self.adapter_factory = adapter_factory
        self.covers_dir = Path(getattr(repository, "covers_dir", COVERS_DIR)).resolve()

    def status(self):
        settings = self.settings_service.load()
        if not settings.get("sync_enabled"):
            return {"status": "not_configured", "pending": self.repository.pending_sync_count()}
        google = settings.get("google", {})
        credentials = str(google.get("credentials_file", "")).strip()
        if not credentials or not Path(credentials).expanduser().is_file():
            return {"status": "not_configured", "pending": self.repository.pending_sync_count()}
        return {"status": "ready", "pending": self.repository.pending_sync_count()}

    def test_connection(self):
        settings = self.settings_service.load()
        adapter = self.adapter_factory(settings.get("google", {}))
        info = adapter.connect()
        if info.get("spreadsheet_id") and info.get("spreadsheet_id") != settings.get("google", {}).get("spreadsheet_id"):
            self.settings_service.update_google_identifiers(info["spreadsheet_id"])
        return info

    def sync(self):
        settings = self.settings_service.load()
        pending_before = self.repository.pending_sync_count()
        if not settings.get("sync_enabled"):
            return {
                "status": "not_configured",
                "uploaded": 0,
                "downloaded": 0,
                "pending": pending_before,
            }

        adapter = self.adapter_factory(settings.get("google", {}))
        try:
            info = adapter.connect()
            if info.get("spreadsheet_id") and info.get("spreadsheet_id") != settings.get("google", {}).get("spreadsheet_id"):
                self.settings_service.update_google_identifiers(info["spreadsheet_id"])

            remote_payload = adapter.download_payload()
            merge_result = self.repository.merge_remote_payload(remote_payload)

            covers_uploaded = 0
            covers_downloaded = 0
            covers_deleted = 0
            for row in self.repository.get_work_sync_rows():
                work_id = row["id"]
                remote_id = row.get("cover_remote_id")
                local_path = row.get("cover_path")
                local_exists = bool(local_path and Path(local_path).is_file())
                pending = row.get("sync_status") != "SYNCED"
                deleted = bool(row.get("deleted_at"))
                cover_deleted = bool(row.get("cover_deleted"))

                if deleted:
                    if local_exists:
                        try:
                            Path(local_path).unlink(missing_ok=True)
                        except OSError:
                            pass
                        self.repository.clear_local_cover_from_remote(work_id)
                    if pending and remote_id:
                        adapter.delete_cover(remote_id)
                        self.repository.update_cover_remote(work_id, None, None, None)
                        covers_deleted += 1
                    continue

                if pending and cover_deleted:
                    if remote_id:
                        adapter.delete_cover(remote_id)
                        covers_deleted += 1
                    self.repository.update_cover_remote(work_id, None, None, None)
                    continue

                if pending and local_exists:
                    upload_result = adapter.upload_cover(local_path, remote_id=remote_id)
                    if len(upload_result) == 2:
                        new_id, remote_name = upload_result
                        remote_modified = None
                    else:
                        new_id, remote_name, remote_modified = upload_result
                    self.repository.update_cover_remote(work_id, new_id, remote_name, remote_modified)
                    covers_uploaded += 1
                    continue

                if remote_id and not local_exists and not cover_deleted:
                    remote_name = row.get("cover_remote_name") or f"{work_id}.jpg"
                    safe_name = Path(remote_name).name
                    destination = self.covers_dir / safe_name
                    downloaded_path = adapter.download_cover(remote_id, destination)
                    if downloaded_path:
                        self.repository.set_local_cover_from_remote(work_id, downloaded_path)
                        covers_downloaded += 1

            merged_payload = self.repository.export_sync_payload()
            adapter.upload_payload(merged_payload)
            self.repository.mark_all_synced()
            self.repository.prune_orphan_covers()

            return {
                "status": "synced",
                "uploaded": pending_before,
                "downloaded": int(merge_result.get("downloaded", 0)),
                "pending": 0,
                "covers_uploaded": covers_uploaded,
                "covers_downloaded": covers_downloaded,
                "covers_deleted": covers_deleted,
                "spreadsheet_id": adapter.spreadsheet_id,
            }
        except GoogleSyncConfigurationError as exc:
            return {
                "status": "configuration_error",
                "message": str(exc),
                "uploaded": 0,
                "downloaded": 0,
                "pending": self.repository.pending_sync_count(),
            }
        except GoogleSyncError as exc:
            return {
                "status": "error",
                "message": str(exc),
                "uploaded": 0,
                "downloaded": 0,
                "pending": self.repository.pending_sync_count(),
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": f"Falha inesperada na sincronização: {exc}",
                "uploaded": 0,
                "downloaded": 0,
                "pending": self.repository.pending_sync_count(),
            }
