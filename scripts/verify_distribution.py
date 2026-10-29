"""Install a built wheel in a fresh environment and exercise its packaged Skill."""

import argparse
import json
import os
import shlex
import subprocess
import tempfile
import venv
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="shared-memory-wheel-") as temporary:
        base = Path(temporary).resolve()
        environment = base / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / "bin" / "python"
        cli = environment / "bin" / "contextrove"
        env = {key: value for key, value in os.environ.items()
               if key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
        subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps",
                        str(wheel)], cwd=base, env=env, check=True)
        # Old console names remain aliases; the Python module and MCP ID stay stable.
        for name in ("shared-memory", "shared-memory-mcp", "contextrove-mcp"):
            assert (environment / "bin" / name).is_file(), name
        alias = subprocess.run([str(environment / "bin/shared-memory"), "demo"],
                               cwd=base, env=env, capture_output=True, text=True, check=True)
        assert json.loads(alias.stdout)["after"] == "verified"
        project = base / "project"
        project.mkdir()
        workspace = base / "context with ' quotes"
        skill_home = base / "skills"

        def invoke(*arguments, failure=None):
            result = subprocess.run([str(cli), *map(str, arguments)], cwd=project,
                                    env=env, capture_output=True, text=True)
            output = json.loads(result.stdout)
            if failure:
                assert result.returncode != 0, result
                assert output["error"]["code"] == failure, output
            else:
                assert result.returncode == 0, result.stderr or result.stdout
            return output

        installed = invoke("setup", "--client", "skill", "--directory", workspace,
                           "--project-root", project, "--skill-home", skill_home)
        skill = Path(installed["skill"]).read_text(encoding="utf-8")
        assert "{{SHARED_MEMORY}}" not in skill and "{{WORKSPACE}}" not in skill
        assert shlex.quote(str(cli)) in skill
        clients = invoke("skill", "clients")
        assert {"codex", "claude-code", "cursor", "workbuddy"} <= {
            item["id"] for item in clients["clients"]}, clients
        options = ["--workspace", workspace, "--scope", "project", "--project-root", project,
                   "--agent", "codex", "--agent", "claude-code", "--agent", "cline"]
        installed_clients = invoke("skill", "install", *options)
        assert len(installed_clients["installations"]) == 3, installed_clients
        for item in installed_clients["installations"]:
            assert Path(item["skill"]).read_text(encoding="utf-8") == skill, item
        checked = invoke("skill", "doctor", *options)
        assert all(item["file_status"] == "matches"
                   and item["model_execution"] == "unverified" for item in checked["installations"]), checked
        assert invoke("skill", "install", *options)["status"] == "reused"
        bootstrap = invoke("agent", "bootstrap", "--workspace", workspace,
                           "--project-root", project)
        assert bootstrap["status"] == "matched", bootstrap
        note = bootstrap["entries"][0]
        before = invoke("agent", "read", "--workspace", workspace, "--note", note)
        edit = ["--workspace", workspace, "--note", note,
                "--expected-revision", before["revision"],
                "--old", "Current project context", "--new", "Verified wheel context",
                "--reason", "Synthetic package check", "--source", "Distribution smoke test"]
        proposal = invoke("agent", "propose", *edit)
        assert "-# Current project context" in proposal["diff"], proposal
        assert invoke("agent", "read", "--workspace", workspace, "--note", note) == before
        assert invoke("agent", "apply", *edit)["updated"]
        invoke("agent", "apply", *edit, failure="VERSION_CONFLICT")
        after = invoke("agent", "read", "--workspace", workspace, "--note", note)
        assert "Verified wheel context" in after["content"], after
        assert invoke("agent", "search", "--workspace", workspace,
                      "--query", "Verified wheel context")["results"]
        assert invoke("agent", "forget", "--workspace", workspace, "--note", note,
                      "--expected-revision", after["revision"],
                      "--old", "Verified wheel context", "--reason", "Synthetic cleanup",
                      "--source", "Distribution smoke test")["updated"]
        assert not invoke("agent", "search", "--workspace", workspace,
                          "--query", "Verified wheel context")["results"]
        assert invoke("demo")["after"] == "verified"
        print(json.dumps({"wheel": wheel.name, "fresh_environment": "PASS",
                          "packaged_skill": "PASS", "cli_workflow": "PASS",
                          "multi_client_install_and_doctor": "PASS",
                          "scope": "Synthetic local CLI; no agent model calls"}, indent=2))


if __name__ == "__main__":
    main()
