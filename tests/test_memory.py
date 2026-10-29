import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared_memory_gateway.cli import (
    agent_action,
    initialize,
    install_skill,
    setup,
    setup_skill,
)
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
            [sys.executable, "-m", "shared_memory_gateway.cli", method, "--config", str(self.config)],
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

    def test_demo_command_corrects_and_cleans_isolated_workspace(self):
        with tempfile.TemporaryDirectory(prefix="shared-memory-demo-parent-") as parent:
            env = dict(os.environ, TMPDIR=parent, PYTHONPATH=str(ROOT / "src"))
            result = subprocess.run(
                [sys.executable, "-m", "shared_memory_gateway.cli", "demo"],
                capture_output=True, text=True, env=env, check=True,
            )
            output = json.loads(result.stdout)
            self.assertEqual("matched", output["project"])
            self.assertEqual("pending", output["before"])
            self.assertEqual("verified", output["after"])
            self.assertEqual("PASS", output["fresh_read"])
            self.assertIn("no agent or MCP", output["scope"])
            self.assertEqual([], list(Path(parent).iterdir()))

    def test_setup_registers_global_opencode_without_editing_project(self):
        project = self.root / "project"
        project.mkdir()
        with patch("shared_memory_gateway.cli.shutil.which", return_value="/usr/bin/opencode"), \
             patch("shared_memory_gateway.cli.subprocess.run") as run:
            run.return_value.returncode = 0
            output = setup("opencode", self.root / "workspace", project)
        self.assertEqual("registered", output["status"])
        self.assertEqual([], list(project.iterdir()))
        self.assertEqual("opencode", output["client"])
        args = run.call_args.args[0]
        self.assertEqual(["/usr/bin/opencode", "mcp", "add", "shared-memory-gateway",
                          "--global", "--"], args[:6])
        self.assertEqual(output["config"], args[-1])
        self.assertTrue(Path(output["project_note"]).is_file())

    def test_setup_fails_before_writing_without_client_or_on_unrelated_target(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        with patch("shared_memory_gateway.cli.shutil.which", return_value=None):
            self.assert_code("CLIENT_NOT_FOUND", lambda: setup("codex", workspace, project))
        self.assertFalse(workspace.exists())
        workspace.mkdir()
        with patch("shared_memory_gateway.cli.subprocess.run") as run:
            self.assert_code("WORKSPACE_MISMATCH", lambda: setup("codex", workspace, project))
            run.assert_not_called()

    def test_setup_reuses_context_for_second_client_without_overwriting_notes(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        with patch("shared_memory_gateway.cli.shutil.which", side_effect=lambda x: f"/usr/bin/{x}"), \
             patch("shared_memory_gateway.cli.subprocess.run") as run:
            run.return_value.returncode = 0
            first = setup("opencode", workspace, project)
            note = Path(first["project_note"])
            note.write_text("# Confirmed context\n", encoding="utf-8")
            second = setup("codex", workspace, project)
        self.assertTrue(second["workspace_reused"])
        self.assertEqual(first["config"], second["config"])
        self.assertEqual("# Confirmed context\n", note.read_text(encoding="utf-8"))
        self.assertEqual(["/usr/bin/codex", "mcp", "add", "shared-memory-gateway", "--"],
                         run.call_args.args[0][:5])

    def test_setup_rejects_workspace_initialized_for_another_project(self):
        first_project = self.root / "first"
        second_project = self.root / "second"
        first_project.mkdir()
        second_project.mkdir()
        workspace = self.root / "workspace"
        first = initialize(workspace, first_project)
        original_config = Path(first["config"]).read_bytes()
        with patch("shared_memory_gateway.cli.subprocess.run") as run:
            self.assert_code("WORKSPACE_MISMATCH", lambda: setup("codex", workspace, second_project))
            run.assert_not_called()
        self.assertEqual(original_config, Path(first["config"]).read_bytes())

    def test_setup_reports_partial_registration_failure(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        with patch("shared_memory_gateway.cli.shutil.which", return_value="/usr/bin/codex"), \
             patch("shared_memory_gateway.cli.subprocess.run") as run:
            run.return_value.returncode = 1
            self.assert_code("CLIENT_SETUP_FAILED", lambda: setup("codex", workspace, project))
            self.assertEqual("--", run.call_args.args[0][4])
        self.assertTrue((workspace / "memory.local.json").is_file())

    def test_setup_cli_reports_registered_without_claiming_model_tool_use(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        with patch("shared_memory_gateway.cli.shutil.which", return_value="/usr/bin/opencode"), \
             patch("shared_memory_gateway.cli.subprocess.run") as run, \
             patch("sys.argv", ["shared-memory", "setup", "--client", "opencode",
                                "--directory", str(workspace), "--project-root", str(project)]), \
             patch("sys.stdout", new_callable=io.StringIO) as stdout:
            from shared_memory_gateway.cli import main

            run.return_value.returncode = 0
            main()
        output = json.loads(stdout.getvalue())
        self.assertEqual("registered", output["status"])
        self.assertIn("model tool use not yet checked", output["verified"])

    def test_skill_install_renders_shared_skill_for_opencode_and_codex(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        initialize(workspace, project)
        skill_home = self.root / ".agents" / "skills"
        output = install_skill(workspace, skill_home)
        skill = Path(output["skill"]).read_text(encoding="utf-8")
        self.assertTrue(output["skill"].endswith("shared-context/SKILL.md"))
        self.assertIn("name: shared-context", skill)
        self.assertIn(str(Path(sys.executable).absolute().parent / "contextrove"), skill)
        self.assertIn(str(workspace.resolve()), skill)
        self.assertNotIn("{{WORKSPACE}}", skill)
        self.assertEqual("reused", install_skill(workspace, skill_home)["status"])

    def test_skill_setup_reuses_workspace_shares_personal_context_and_adds_projects(self):
        first = self.root / "first-project"
        second = self.root / "second-project"
        first.mkdir()
        second.mkdir()
        workspace = self.root / "workspace"
        skill_home = self.root / ".agents" / "skills"
        initial = setup_skill(workspace, first, skill_home)
        personal = Path(initial["workspace"]) / "context" / "personal-context.md"
        personal.write_text("# Personal\nConfirmed preference\n", encoding="utf-8")
        second_setup = setup_skill(workspace, second, skill_home)
        self.assertEqual("reused", second_setup["status"])
        self.assertEqual(initial["skill"], second_setup["skill"])
        self.assertEqual("# Personal\nConfirmed preference\n", personal.read_text(encoding="utf-8"))
        config = json.loads(Path(second_setup["config"]).read_text(encoding="utf-8"))
        self.assertEqual({"current-project", "second-project"}, set(config["projects"]))
        self.assertTrue((Path(second_setup["workspace"]) / "context" / "projects" / "second-project.md").is_file())

    def test_agent_skill_actions_bootstrap_review_apply_and_re_read(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        initialized = initialize(workspace, project)
        note_path = Path(initialized["vault"]) / "projects" / "current-project.md"
        note_path.write_text("# Project\nStatus: pending.\n", encoding="utf-8")
        bootstrap = agent_action("bootstrap", workspace, str(project))
        self.assertEqual("matched", bootstrap["status"])
        before = agent_action("read", workspace, note="projects/current-project.md")
        proposal_args = dict(workspace=workspace, note="projects/current-project.md",
                             expected_revision=before["revision"], old="Status: pending.",
                             new="Status: verified.", reason="Confirmed status",
                             source="User confirmation")
        proposal = agent_action("propose", **proposal_args)
        self.assertIn("-Status: pending.", proposal["diff"])
        self.assertIn("Status: pending.", note_path.read_text(encoding="utf-8"))
        applied = agent_action("apply", **proposal_args)
        self.assertTrue(applied["updated"])
        after = agent_action("read", workspace, note="projects/current-project.md")
        self.assertIn("Status: verified.", after["content"])

    def test_setup_skill_initializes_workspace_and_installs_once(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        skill_home = self.root / ".agents" / "skills"
        with patch("shared_memory_gateway.cli.Path.home", return_value=self.root), \
             patch("sys.argv", ["shared-memory", "setup", "--client", "skill",
                                "--directory", str(workspace), "--project-root", str(project)]), \
             patch("sys.stdout", new_callable=io.StringIO) as stdout:
            from shared_memory_gateway.cli import main

            main()
        result = json.loads(stdout.getvalue())
        self.assertEqual("installed", result["status"])
        self.assertTrue(Path(result["skill"]).is_file())
        self.assertTrue(Path(result["config"]).is_file())
        self.assertEqual(skill_home / "shared-context" / "SKILL.md", Path(result["skill"]))
        self.assertEqual("reused", setup_skill(workspace, project, skill_home)["status"])

    def test_skill_conflict_is_detected_before_workspace_mutation(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        skill_home = self.root / ".agents" / "skills"
        skill = skill_home / "shared-context" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("Existing user skill\n")
        self.assert_code("SKILL_EXISTS", lambda: setup_skill(workspace, project, skill_home))
        self.assertFalse(workspace.exists())
        self.assertEqual("Existing user skill\n", skill.read_text())

    def test_skill_install_validates_custom_workspace_notes_and_reports_paths(self):
        project = self.root / "project"
        project.mkdir()
        workspace = self.root / "workspace"
        initialized = initialize(workspace, project)
        config = json.loads(Path(initialized["config"]).read_text())
        config["projects"]["current-project"]["notes"] = ["missing.md"]
        config["notes"].append("missing.md")
        Path(initialized["config"]).write_text(json.dumps(config))
        self.assert_code("WORKSPACE_MISMATCH", lambda: install_skill(workspace, self.root / "skills"))

        config["notes"].remove("missing.md")
        config["projects"]["current-project"]["notes"] = ["projects/current-project.md"]
        Path(initialized["config"]).write_text(json.dumps(config))
        output = install_skill(workspace, self.root / "skills")
        self.assertEqual(0o600, Path(output["skill"]).stat().st_mode & 0o777)

    def test_new_project_setup_rejects_symlink_parent_and_overlapping_root(self):
        first, second = self.root / "first", self.root / "second"
        first.mkdir()
        second.mkdir()
        workspace, skill_home = self.root / "workspace", self.root / "skills"
        output = setup_skill(workspace, first, skill_home)
        config = Path(output["config"])
        original = config.read_bytes()
        nested = first / "nested"
        nested.mkdir()
        self.assert_code("WORKSPACE_MISMATCH", lambda: setup_skill(workspace, nested, skill_home))
        projects = workspace / "context" / "projects"
        projects.rename(workspace / "original-projects")
        projects.symlink_to(workspace / "original-projects", target_is_directory=True)
        self.assert_code("WORKSPACE_MISMATCH", lambda: setup_skill(workspace, second, skill_home))
        self.assertEqual(original, config.read_bytes())
        self.assertFalse((projects / "second.md").exists())

    def test_setup_does_not_follow_symlinked_workspace_ancestor(self):
        project = self.root / "project"
        project.mkdir()
        actual = self.root / "actual"
        alias = self.root / "alias"
        actual.mkdir()
        alias.symlink_to(actual, target_is_directory=True)
        self.assert_code("WORKSPACE_MISMATCH",
                         lambda: setup_skill(alias / "workspace", project, self.root / "skills"))
        self.assertEqual([], list(actual.iterdir()))

    def test_failed_project_publish_preserves_config_and_allows_retry(self):
        first, second = self.root / "first", self.root / "second"
        first.mkdir()
        second.mkdir()
        workspace, skill_home = self.root / "workspace", self.root / "skills"
        output = setup_skill(workspace, first, skill_home)
        config = Path(output["config"])
        original = config.read_bytes()
        with patch("shared_memory_gateway.cli.os.replace", side_effect=OSError("injected")):
            self.assert_code("WORKSPACE_MISMATCH", lambda: setup_skill(workspace, second, skill_home))
        self.assertEqual(original, config.read_bytes())
        self.assertFalse((workspace / "context" / "projects" / "second.md").exists())
        self.assertEqual([], list(workspace.glob(".setup-*")))
        retried = setup_skill(workspace, second, skill_home)
        self.assertEqual("matched", agent_action("bootstrap", workspace, str(second))["status"])
        self.assertEqual([str(workspace.resolve() / "context" / "projects" / "second.md")], retried["project_notes"])

    def test_installed_skill_command_quotes_paths_and_runs_from_other_project(self):
        project = self.root / "项目"
        project.mkdir()
        workspace = self.root / "memory ' $() `backticks`"
        output = setup_skill(workspace, project, self.root / "skills")
        skill = Path(output["skill"]).read_text()
        command = next(line for line in skill.splitlines() if " agent bootstrap " in line)
        self.assertIn(shlex.quote(str(workspace.resolve())), command)
        result = subprocess.run(command, shell=True, cwd=project, capture_output=True,
                                text=True, check=True, env=dict(os.environ, PWD=str(project)))
        self.assertEqual("matched", json.loads(result.stdout)["status"])

    def test_incomplete_skill_edit_returns_structured_error_and_stale_apply_rejected(self):
        workspace = self.root / "workspace"
        initialize(workspace, self.root)
        self.assert_code("INVALID_REQUEST", lambda: agent_action("apply", workspace))
        before = agent_action("read", workspace, note="projects/current-project.md")
        arguments = dict(workspace=workspace, note=before["note"], expected_revision=before["revision"],
                         old="Current project context", new="Confirmed project context",
                         reason="Confirmed", source="User")
        agent_action("propose", **arguments)
        note = workspace / "context" / before["note"]
        note.write_text(note.read_text() + "External edit\n")
        self.assert_code("VERSION_CONFLICT", lambda: agent_action("apply", **arguments))
        self.assertIn("External edit", note.read_text())

    def test_skill_edit_requires_explicit_replacement_but_allows_forget(self):
        workspace = self.root / "workspace"
        initialize(workspace, self.root)
        before = agent_action("read", workspace, note="projects/current-project.md")
        arguments = dict(workspace=workspace, note=before["note"],
                         expected_revision=before["revision"], old="Current project context",
                         reason="User requested deletion", source="User")
        for action in ("propose", "apply"):
            with self.subTest(action=action):
                self.assert_code("INVALID_REQUEST", lambda: agent_action(action, **arguments))
        self.assertEqual(before, agent_action("read", workspace, note=before["note"]))
        self.assertTrue(agent_action("forget", **arguments)["updated"])
        self.assertNotIn(arguments["old"], agent_action("read", workspace, note=before["note"])["content"])

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

    def test_init_creates_relocatable_context_workspace(self):
        workspace = self.root / "portable-context"
        project_root = self.root / "demo"
        project_root.mkdir()
        result = initialize(workspace, project_root)
        config_path = Path(result["config"])
        config = json.loads(config_path.read_text())
        memory = Memory(config_path)
        personal = memory.read("personal-context.md")
        project = memory.read("projects/current-project.md")
        self.assertIn("Stable preferences", personal["content"])
        self.assertIn("Decisions and rationale", project["content"])
        self.assertEqual("matched", memory.bootstrap(str(project_root / "src"))["status"])
        self.assertEqual("unmatched", memory.bootstrap(str(self.root / "other"))["status"])
        self.assertEqual(".state", config["state_dir"])
        self.assertTrue((workspace / ".gitignore").exists())
        self.assertTrue(Path(result["mcp_command"]).is_absolute())
        entry = result["mcp_config"]["mcpServers"]["shared-memory-gateway"]
        self.assertEqual(result["mcp_command"], entry["command"])
        self.assertEqual(str(Path(sys.executable).absolute()), entry["command"])
        self.assertTrue(Path(entry["command"]).exists())
        self.assertEqual(result["mcp_args"], entry["args"])
        self.assertEqual(result["config"], entry["args"][-1])
        opencode = result["opencode_v2_config"]["mcp"]["servers"]["shared-memory-gateway"]
        self.assertEqual("local", opencode["type"])
        self.assertEqual([entry["command"], *entry["args"]], opencode["command"])
        self.assertEqual(["codex", "mcp", "add", "shared-memory-gateway", "--", *opencode["command"]],
                         result["codex_mcp_add"])
        self.assertEqual(0o700, workspace.stat().st_mode & 0o777)
        self.assertEqual(0o700, Path(result["vault"]).stat().st_mode & 0o777)
        self.assertEqual(0o600, Path(result["config"]).stat().st_mode & 0o777)
        self.assertEqual(0o600, (Path(result["vault"]) / "personal-context.md").stat().st_mode & 0o777)

    def test_init_refuses_nonempty_target_without_modifying_it(self):
        target = self.root / "existing"
        target.mkdir()
        marker = target / "keep.txt"
        marker.write_text("user data")
        self.assert_code("TARGET_EXISTS", lambda: initialize(target))
        self.assertEqual("user data", marker.read_text())

    def test_init_without_project_is_personal_context_only(self):
        workspace = self.root / "personal-only"
        result = initialize(workspace)
        memory = Memory(result["config"])
        self.assertEqual("unmatched", memory.bootstrap(str(self.root))["status"])
        self.assertEqual([], memory.bootstrap(str(self.root))["entries"])


if __name__ == "__main__":
    unittest.main()
