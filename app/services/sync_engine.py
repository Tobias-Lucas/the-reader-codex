import socket
from datetime import datetime, timezone


class SyncEngine:
    def __init__(self, repository):
        self.repository = repository

    def has_network(self):
        try:
            socket.create_connection(
                ("8.8.8.8", 53),
                timeout=1,
            ).close()
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

        return {
            "status": "synced",
            "uploaded": 0,
            "downloaded": 0,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
