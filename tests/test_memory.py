import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared_memory_gateway.core import Memory, MemoryError

ROOT = Path(__file__).resolve().parents[1]


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="shared-memory-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.note = self.vault / "decision.md"
        self.note.write_bytes(b"# Decision\r\n\r\nStatus: pending\r\nKeep this line.\r\n")
        self.config = self.root / "config.json"
        self.config.write_text(json.dumps({
            "vault": "vault", "state_dir": "state", "notes": ["decision.md"],
            "bootstrap": [], "projects": {
                "demo": {"roots": [str(self.root / "demo")], "notes": ["decision.md"]},
            },
        }))
        self.memory = Memory(self.config)

    def proposal(self, new="verified"):
        return self.memory.propose_update(
            "decision.md", self.memory.read("decision.md")["revision"],
            "pending", new, "Synthetic correction", "Synthetic user statement",
        )

    def assert_code(self, code, operation):
        with self.assertRaises(MemoryError) as caught:
            operation()
        self.assertEqual(code, caught.exception.code)

    def child(self, method, args):
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        return subprocess.Popen(
            [sys.executable, "-m", "shared_memory_gateway.cli", "--config", str(self.config), method],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env,
        )

    def invoke(self, method, args):
        process = self.child(method, args)
        out, err = process.communicate(json.dumps(args), timeout=20)
        self.assertFalse(err, err)
        return process.returncode, json.loads(out)

    def test_proposal_does_not_write_and_update_replaces_old_memory(self):
        before = self.note.read_bytes()
        proposal = self.proposal()
        self.assertEqual(before, self.note.read_bytes())
        self.assertIn("-Status: pending", proposal["diff"])
        self.memory.apply_update(proposal)
        self.assertEqual(before.replace(b"pending", b"verified"), self.note.read_bytes())
        self.assertEqual(1, self.note.read_bytes().count(b"verified"))
        self.assertNotIn(b"pending", self.note.read_bytes())

    def test_stale_revision_rejected(self):
        first = self.proposal("first")
        stale = self.proposal("second")
        self.memory.apply_update(first)
        self.assert_code("VERSION_CONFLICT", lambda: self.memory.apply_update(stale))
        self.assertIn(b"first", self.note.read_bytes())

    def test_independent_process_reads_correction(self):
        code, result = self.invoke("apply_update", {"proposal": self.proposal()})
        self.assertEqual(0, code, result)
        code, read = self.invoke("read", {"note": "decision.md"})
        self.assertEqual(0, code)
        self.assertIn("verified", read["content"])
        self.assertNotIn("pending", read["content"])

    def test_two_process_writers_one_wins_one_conflicts(self):
        proposals = [self.proposal("writer-A"), self.proposal("writer-B")]
        children = [self.child("apply_update", {}) for _ in proposals]
        for child, proposal in zip(children, proposals):
            child.stdin.write(json.dumps({"proposal": proposal}))
            child.stdin.flush()
        results = []
        for child in children:
            out, err = child.communicate(timeout=20)
            self.assertFalse(err)
            results.append((child.returncode, json.loads(out)))
        self.assertEqual([0, 1], sorted(code for code, _ in results))
        loser = next(result for code, result in results if code)
        self.assertEqual("VERSION_CONFLICT", loser["error"]["code"])
        content = self.note.read_text()
        self.assertNotIn("pending", content)
        self.assertEqual(1, content.count("writer-"))

    def test_external_edit_invalidates_proposal_and_search_reads_disk(self):
        proposal = self.proposal()
        self.note.write_text("# Decision\n外部纠正，生产尚未验证。\n")
        self.assert_code("VERSION_CONFLICT", lambda: self.memory.apply_update(proposal))
        result = self.memory.search("生产尚未验证")
        self.assertEqual("decision.md", result["results"][0]["note"])
        self.assertEqual([], self.memory.search("pending")["results"])

    def test_replay_is_rejected_not_appended(self):
        proposal = self.proposal()
        self.memory.apply_update(proposal)
        self.assert_code("VERSION_CONFLICT", lambda: self.memory.apply_update(proposal))
        self.assertEqual(1, self.note.read_bytes().count(b"verified"))

    def test_unrelated_content_and_permissions_preserved(self):
        self.note.chmod(0o640)
        self.memory.apply_update(self.proposal())
        self.assertEqual(0o640, self.note.stat().st_mode & 0o777)
        self.assertIn(b"Keep this line.\r\n", self.note.read_bytes())

    def test_ambiguous_empty_and_unsourced_edits_rejected(self):
        self.note.write_text("pending pending")
        self.assert_code("AMBIGUOUS_EDIT", self.proposal)
        rev = self.memory.read("decision.md")["revision"]
        self.assert_code("INVALID_EDIT", lambda: self.memory.propose_update(
            "decision.md", rev, "", "x", "reason", "source"))
        self.assert_code("SOURCE_REQUIRED", lambda: self.memory.propose_update(
            "decision.md", rev, "pending", "x", "", ""))

    def test_tampered_proposal_rejected(self):
        proposal = self.proposal()
        proposal["arguments"]["new"] = "tampered"
        self.assert_code("INVALID_PROPOSAL", lambda: self.memory.apply_update(proposal))
        self.assertIn(b"pending", self.note.read_bytes())

    def test_allowlist_traversal_absolute_and_symlinks_rejected(self):
        for note in ("../outside.md", str(self.note), "secret.md", "./decision.md"):
            self.assert_code("OUT_OF_SCOPE", lambda n=note: self.memory.read(n))
        self.note.unlink()
        (self.root / "outside.md").write_text("not allowed")
        self.note.symlink_to(self.root / "outside.md")
        self.assert_code("OUT_OF_SCOPE", lambda: self.memory.read("decision.md"))

    def test_symlink_parent_rejected(self):
        external = self.root / "outside"
        external.mkdir()
        (external / "note.md").write_text("secret")
        (self.vault / "linked").symlink_to(external, target_is_directory=True)
        config = json.loads(self.config.read_text())
        config["notes"].append("linked/note.md")
        self.config.write_text(json.dumps(config))
        self.assert_code("OUT_OF_SCOPE", lambda: Memory(self.config).read("linked/note.md"))

    def test_oversize_and_invalid_utf8_rejected(self):
        self.note.write_bytes(b"x" * 262145)
        self.assert_code("TOO_LARGE", lambda: self.memory.read("decision.md"))
        self.note.write_bytes(b"\xff")
        self.assert_code("INVALID_ENCODING", lambda: self.memory.read("decision.md"))

    def test_bootstrap_no_guessing_and_scope(self):
        matched = self.memory.bootstrap(str(self.root / "demo" / "src"))
        self.assertEqual("matched", matched["status"])
        self.assertEqual(["decision.md"], matched["entries"])
        self.assertEqual("unmatched", self.memory.bootstrap(str(self.root / "demo-other"))["status"])
        self.assert_code("UNMATCHED_PROJECT", lambda: self.memory.search("pending", "unknown"))
        self.assertEqual(1, len(self.memory.search("pending", "demo")["results"]))
        config = json.loads(self.config.read_text())
        config["projects"]["overlap"] = config["projects"]["demo"]
        self.config.write_text(json.dumps(config))
        result = Memory(self.config).bootstrap(str(self.root / "demo"))
        self.assertEqual("ambiguous", result["status"])
        self.assertEqual([], result["entries"])

    def test_forget_removes_passage_and_search_has_no_ghost(self):
        self.note.write_text("# Decision\nkeep\nforget-marker-742\n")
        rev = self.memory.read("decision.md")["revision"]
        self.memory.forget("decision.md", rev, "forget-marker-742\n", "User request", "User")
        self.assertEqual("# Decision\nkeep\n", self.note.read_text())
        self.assertEqual([], self.memory.search("forget-marker-742")["results"])
        # Only lock files, not old note bodies, are retained in private state.
        for path in self.memory.state.iterdir():
            self.assertEqual(b"", path.read_bytes())

    def test_failure_before_replace_leaves_original_and_cleans_temporary(self):
        proposal = self.proposal()
        original = self.note.read_bytes()
        with patch("shared_memory_gateway.core.os.replace", side_effect=OSError("injected")):
            with self.assertRaises(OSError):
                self.memory.apply_update(proposal)
        self.assertEqual(original, self.note.read_bytes())
        self.assertEqual([], list(self.vault.glob(".memory-*")))

    def test_failure_after_replace_reports_uncertain_not_false_success(self):
        proposal = self.proposal()
        real_fsync = os.fsync
        calls = 0

        def fail_directory_sync(fd):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected directory sync failure")
            return real_fsync(fd)

        with patch("shared_memory_gateway.core.os.fsync", side_effect=fail_directory_sync):
            self.assert_code("WRITE_UNCERTAIN", lambda: self.memory.apply_update(proposal))
        self.assertIn(b"verified", self.note.read_bytes())
        self.assertEqual([], list(self.vault.glob(".memory-*")))

    def test_external_change_detected_immediately_before_replace(self):
        proposal = self.proposal()
        real_fsync = os.fsync

        def mutate(fd):
            real_fsync(fd)
            self.note.write_bytes(b"external-wins\n")

        with patch("shared_memory_gateway.core.os.fsync", side_effect=mutate):
            self.assert_code("VERSION_CONFLICT", lambda: self.memory.apply_update(proposal))
        self.assertEqual(b"external-wins\n", self.note.read_bytes())

    def test_state_inside_vault_rejected(self):
        config = json.loads(self.config.read_text())
        config["state_dir"] = "vault/state"
        self.config.write_text(json.dumps(config))
        self.assert_code("INVALID_CONFIG", lambda: Memory(self.config))


if __name__ == "__main__":
    unittest.main()
