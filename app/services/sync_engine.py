
import json
import os
import socket
from datetime import datetime, timezone


class SyncEngine:
    """
    Motor de sincronização desacoplado.

    Nesta versão de portfólio o transporte remoto padrão é um arquivo JSON
    simulando a nuvem. A classe foi desenhada para receber futuramente
    um adaptador Google Sheets/Drive sem alterar a UI.
    """

    def __init__(
        self,
        repository,
        remote_path="data/remote_simulated.json",
    ):
        self.repository = repository
        self.remote_path = remote_path
        os.makedirs(os.path.dirname(remote_path), exist_ok=True)

    def has_network(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=1).close()
            return True
        except OSError:
            return False

    def sync(self):
        if not self.has_network():
            return {
                "status": "offline",
                "uploaded": 0,
                "downloaded": 0,
            }

        remote = self._load_remote()
        by_id = {item["id"]: item for item in remote}

        uploaded = 0
        for row in self.repository.get_pending_works():
            payload = dict(row)
            local_updated = payload["updated_at"]
            remote_item = by_id.get(payload["id"])

            if remote_item is None or local_updated >= remote_item["updated_at"]:
                payload["sync_status"] = "SYNCED"
                by_id[payload["id"]] = payload
                self.repository.mark_work_synced(payload["id"])
                uploaded += 1

        downloaded = 0
        for payload in by_id.values():
            self.repository.upsert_remote(payload)
            downloaded += 1

        self._save_remote(list(by_id.values()))

        return {
            "status": "synced",
            "uploaded": uploaded,
            "downloaded": downloaded,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def _load_remote(self):
        if not os.path.exists(self.remote_path):
            return []

        with open(self.remote_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_remote(self, data):
        with open(self.remote_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
