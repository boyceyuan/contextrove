"""Synthetic multi-client placement and failure recovery; never touch real client homes."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared_memory_gateway.cli import (
    initialize,
    install_skill,
    setup_skill,
    skill_doctor,
)
from shared_memory_gateway.clients import CLIENTS, list_clients, skill_homes
from shared_memory_gateway.core import MemoryError


class ClientTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="shared-memory-clients-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.home = self.root / "home"
        self.home.mkdir()
        self.project = self.root / "project"
        self.project.mkdir()
        self.workspace = self.root / "workspace"
        self.home_patch = patch("pathlib.Path.home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.env_patch = patch.dict(os.environ, {"XDG_CONFIG_HOME": ""})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def assert_error(self, code, function):
        with self.assertRaises(MemoryError) as caught:
            function()
        self.assertEqual(code, caught.exception.code)

    def test_each_documented_client_installs_in_both_scopes_and_reuses(self):
        # Explicit expected paths detect accidental registry/installer drift together.
        paths = {
            "universal": (".agents/skills", ".agents/skills"),
            "codex": (".agents/skills", ".agents/skills"),
            "claude-code": (".claude/skills", ".claude/skills"),
            "opencode": (".opencode/skills", ".config/opencode/skills"),
            "cursor": (".cursor/skills", ".cursor/skills"),
            "github-copilot": (".github/skills", ".copilot/skills"),
            "gemini-cli": (".gemini/skills", ".gemini/skills"),
            "windsurf": (".windsurf/skills", ".codeium/windsurf/skills"),
            "cline": (".cline/skills", ".cline/skills"),
            "trae": (".trae/skills", ".trae/skills"),
            "qoder": (".qoder/skills", ".qoder/skills"),
            "qwen-code": (".qwen/skills", ".qwen/skills"),
            "codebuddy": (".codebuddy/skills", ".codebuddy/skills"),
        }
        self.assertEqual(set(CLIENTS), set(paths) | {"workbuddy"})
        initialize(self.workspace, self.project)
        for scope, index, base in [("project", 0, self.project), ("user", 1, self.home)]:
            output = install_skill(self.workspace, agents=list(paths), scope=scope,
                                   project_root=self.project)
            self.assertEqual(len(paths), len(output["installations"]))
            for item in output["installations"]:
                with self.subTest(scope=scope, agent=item["agent"]):
                    expected = base / paths[item["agent"]][index] / "shared-context/SKILL.md"
                    self.assertEqual(str(expected), item["skill"])
                    self.assertIn(str(self.workspace), expected.read_text())
                    self.assertNotIn("{{", expected.read_text())
            self.assertEqual("reused", install_skill(self.workspace, agents=list(paths),
                                                    scope=scope, project_root=self.project)["status"])

    def test_deduplication_aliases_and_legacy_custom_home(self):
        output = setup_skill(self.workspace, self.project,
                             agents=["codex", "codex", "universal", "claude-code"])
        self.assertEqual(["codex", "universal", "claude-code"],
                         [item["agent"] for item in output["installations"]])
        self.assertEqual(output["installations"][0]["skill"], output["installations"][1]["skill"])
        self.assertEqual("reused", output["installations"][1]["status"])
        custom = self.root / "custom"
        self.assertEqual(str(custom / "shared-context/SKILL.md"),
                         install_skill(self.workspace, custom)["skill"])

    def test_xdg_config_home_is_respected_and_relative_values_rejected(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "xdg")}):
            result = setup_skill(self.workspace, self.project, agents=["opencode"])
            self.assertEqual(str(self.root / "xdg/opencode/skills/shared-context/SKILL.md"), result["skill"])
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "relative"}):
            self.assert_error("INVALID_REQUEST", lambda: skill_homes(["opencode"], "user", None, None))

    def test_workbuddy_requires_explicit_target_without_initializing_workspace(self):
        self.assert_error("MANUAL_TARGET_REQUIRED", lambda: setup_skill(
            self.workspace, self.project, agents=["workbuddy"]))
        self.assertFalse(self.workspace.exists())
        confirmed = self.root / "confirmed-workbuddy-skills"
        result = setup_skill(self.workspace, self.project, confirmed, agents=["workbuddy"])
        self.assertEqual("workbuddy", result["installations"][0]["agent"])
        self.assertTrue((confirmed / "shared-context/SKILL.md").is_file())

    def test_invalid_selection_and_scope_leave_no_workspace_or_skills(self):
        for options, code in [({"agents": ["unknown"]}, "UNKNOWN_CLIENT"),
                              ({"scope": "other"}, "INVALID_REQUEST"),
                              ({"agents": ["codex", "cline"], "skill_home": self.root / "custom"},
                               "INVALID_REQUEST")]:
            with self.subTest(options=options):
                self.assert_error(code, lambda: setup_skill(self.workspace, self.project, **options))
                self.assertFalse(self.workspace.exists())
        self.assert_error("INVALID_PROJECT_ROOT", lambda: skill_homes(["codex"], "project", None, None))
        self.assert_error("INVALID_PROJECT_ROOT", lambda: skill_homes(
            ["codex"], "project", self.root / "missing", None))
        self.assertEqual([], list(self.home.iterdir()))

    def test_all_destinations_preflight_before_workspace_creation_or_project_registration(self):
        conflict = self.home / ".cline/skills/shared-context"
        conflict.mkdir(parents=True)
        (conflict / "SKILL.md").write_text("User-owned skill\n")
        self.assert_error("SKILL_EXISTS", lambda: setup_skill(
            self.workspace, self.project, agents=["codex", "cline"]))
        self.assertFalse(self.workspace.exists())
        self.assertFalse((self.home / ".agents").exists())
        initialize(self.workspace, self.project)
        original = (self.workspace / "memory.local.json").read_bytes()
        other = self.root / "other-project"
        other.mkdir()
        self.assert_error("SKILL_EXISTS", lambda: setup_skill(
            self.workspace, other, agents=["codex", "cline"]))
        self.assertEqual(original, (self.workspace / "memory.local.json").read_bytes())
        self.assertEqual("User-owned skill\n", (conflict / "SKILL.md").read_text())

    def test_parent_file_conflict_preflight(self):
        (self.home / ".claude").write_text("user file")
        self.assert_error("SKILL_EXISTS", lambda: setup_skill(
            self.workspace, self.project, agents=["codex", "claude-code"]))
        self.assertFalse(self.workspace.exists())
        self.assertFalse((self.home / ".agents").exists())

    def test_non_utf8_skill_is_reported_without_overwrite(self):
        initialize(self.workspace, self.project)
        target = self.home / ".agents/skills/shared-context/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"\xff")
        self.assert_error("SKILL_EXISTS", lambda: install_skill(self.workspace, agents=["codex"]))
        self.assertEqual("SKILL_EXISTS", skill_doctor(
            self.workspace, agents=["codex"])["installations"][0]["file_status"])
        self.assertEqual(b"\xff", target.read_bytes())

    def test_partial_failure_reports_and_retry_keeps_successful_target(self):
        initialize(self.workspace, self.project)
        real_open = os.open

        def fail_second(path, *args, **kwargs):
            if ".cline/skills/shared-context" in str(path):
                raise PermissionError("Synthetic install failure")
            return real_open(path, *args, **kwargs)

        with patch("shared_memory_gateway.cli.os.open", side_effect=fail_second):
            self.assert_error("INSTALL_PARTIAL", lambda: install_skill(
                self.workspace, agents=["codex", "cline"]))
        first = self.home / ".agents/skills/shared-context/SKILL.md"
        original = first.read_bytes()
        report = skill_doctor(self.workspace, agents=["codex", "cline"])
        self.assertEqual(["matches", "SKILL_EXISTS"],
                         [item["file_status"] for item in report["installations"]])
        # An empty directory from a failed open is not a valid existing Skill.
        (self.home / ".cline/skills/shared-context").rmdir()
        retried = install_skill(self.workspace, agents=["codex", "cline"])
        self.assertEqual(["reused", "installed"], [x["status"] for x in retried["installations"]])
        self.assertEqual(original, first.read_bytes())

    def test_doctor_is_read_only_for_missing_valid_and_modified_files(self):
        missing = self.root / "absent"
        self.assertFalse(skill_doctor(missing, agents=["codex"])["workspace_config_present"])
        self.assertFalse(missing.exists())
        self.assertEqual([], list(self.home.iterdir()))
        initialize(self.workspace, self.project)
        install_skill(self.workspace, agents=["codex", "cline"])
        altered = self.home / ".cline/skills/shared-context/SKILL.md"
        altered.write_text("User correction\n")
        before = {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        report = skill_doctor(self.workspace, agents=["codex", "cline", "cursor"])
        self.assertEqual(["matches", "SKILL_EXISTS", "missing"],
                         [item["file_status"] for item in report["installations"]])
        self.assertTrue(all(x["model_execution"] == "unverified" for x in report["installations"]))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertFalse((self.home / ".cursor").exists())

    def test_cli_multi_agent_options_and_mcp_option_guard(self):
        def invoke(*arguments):
            result = subprocess.run([sys.executable, "-m", "shared_memory_gateway.cli", *map(str, arguments)],
                                    capture_output=True, text=True)
            return result.returncode, json.loads(result.stdout)

        code, clients = invoke("skill", "clients")
        self.assertEqual(0, code)
        self.assertEqual(list_clients(), clients)
        code, output = invoke("setup", "--client", "skill", "--directory", self.workspace,
                              "--project-root", self.project, "--scope", "project",
                              "--agent", "codex", "--agent", "claude-code")
        self.assertEqual(0, code, output)
        code, report = invoke("skill", "doctor", "--workspace", self.workspace,
                              "--project-root", self.project, "--scope", "project", "--agent", "codex")
        self.assertEqual(0, code)
        self.assertEqual("matches", report["installations"][0]["file_status"])
        code, error = invoke("setup", "--client", "codex", "--agent", "codex",
                             "--directory", self.root / "forbidden", "--project-root", self.project)
        self.assertNotEqual(0, code)
        self.assertEqual("INVALID_REQUEST", error["error"]["code"])
        self.assertFalse((self.root / "forbidden").exists())


if __name__ == "__main__":
    unittest.main()
