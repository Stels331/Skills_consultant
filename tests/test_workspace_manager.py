import json
import tempfile
import unittest
from pathlib import Path

from app.state.workspace_manager import WorkspaceManager


class WorkspaceManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.manager = WorkspaceManager(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _read_json(self, rel: str):
        with (self.root / rel).open("r", encoding="utf-8") as f:
            return json.load(f)

    def test_create_workspace_creates_required_structure(self):
        ref = self.manager.create_workspace("case_20260228_001")

        self.assertTrue(ref.path.is_dir())
        required_dirs = [
            "raw",
            "parsed",
            "extracted",
            "model",
            "analysis",
            "dialogue",
            "evidence",
            "quality",
            "reports",
            "state",
            "versions",
        ]
        for d in required_dirs:
            self.assertTrue((ref.path / d).is_dir(), d)

        self.assertTrue((ref.path / "workspace_metadata.json").is_file())
        self.assertTrue((ref.path / "state" / "session_state.json").is_file())
        self.assertTrue((ref.path / "state" / "version_changelog.json").is_file())

    def test_create_workspace_is_idempotent_for_existing_workspace(self):
        ref1 = self.manager.create_workspace("case_20260228_001")
        ref2 = self.manager.create_workspace("case_20260228_001")
        self.assertEqual(ref1.workspace_id, ref2.workspace_id)
        self.assertEqual(ref1.path, ref2.path)

    def test_load_workspace_fails_when_required_file_is_missing(self):
        ref = self.manager.create_workspace("case_20260228_001")
        (ref.path / "state" / "session_state.json").unlink()

        with self.assertRaises(FileNotFoundError):
            self.manager.load_workspace("case_20260228_001")

    def test_state_transition_and_changelog(self):
        self.manager.create_workspace("case_20260228_001")
        self.manager.set_workspace_state("case_20260228_001", "ACTIVE", "start work")

        metadata = self._read_json("cases/case_20260228_001/workspace_metadata.json")
        self.assertEqual(metadata["state"], "ACTIVE")

        changelog = self._read_json("cases/case_20260228_001/state/version_changelog.json")
        event_types = [e["event_type"] for e in changelog["events"]]
        self.assertIn("LIFECYCLE_STATE_CHANGED", event_types)

    def test_invalid_transition_raises(self):
        self.manager.create_workspace("case_20260228_001")
        with self.assertRaises(ValueError):
            self.manager.set_workspace_state("case_20260228_001", "REPORTING")

    def test_checkpoint_created(self):
        self.manager.create_workspace("case_20260228_001")
        self.manager.set_workspace_state("case_20260228_001", "ACTIVE")
        vpath = self.manager.create_checkpoint(
            "case_20260228_001", reason="manual checkpoint", structural=True
        )
        self.assertTrue(vpath.is_dir())
        self.assertTrue((vpath / "version_metadata.json").is_file())

        version = self._read_json("cases/case_20260228_001/model/model_version.json")
        self.assertEqual(version["current_version"], 1)


if __name__ == "__main__":
    unittest.main()
