import os
import tempfile
import unittest
from pathlib import Path

from app.paths import APP_DIR_NAME, PROJECT_DIR, resolve_data_dir


class PathResolutionTests(unittest.TestCase):
    def test_development_uses_project_data_directory(self):
        resolved = resolve_data_dir(is_frozen=False, env={})
        self.assertEqual(resolved, (PROJECT_DIR / "data").resolve())

    def test_frozen_build_uses_localappdata(self):
        with tempfile.TemporaryDirectory() as td:
            resolved = resolve_data_dir(is_frozen=True, env={"LOCALAPPDATA": td})
            self.assertEqual(resolved, (Path(td) / APP_DIR_NAME).resolve())

    def test_environment_override_wins(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "custom-profile"
            resolved = resolve_data_dir(
                is_frozen=True,
                env={"LOCALAPPDATA": str(Path(td) / "ignored"), "THE_READER_CODEX_DATA_DIR": str(target)},
            )
            self.assertEqual(resolved, target.resolve())


if __name__ == "__main__":
    unittest.main()
