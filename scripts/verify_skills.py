"""Isolated discovery checks using installed clients; no model calls or MCP.

Pass absolute --codex and --opencode executable paths. Only this script's
temporary HOME/XDG/CODEX directories and synthetic notes are used.
"""

import argparse
import json
import os
import selectors
import subprocess
import tempfile
import time
from pathlib import Path

from shared_memory_gateway.cli import install_skill, setup_skill


def codex_discovery(command, project, env, skill_path):
    with tempfile.TemporaryFile(mode="w+") as errors:
        process = subprocess.Popen([command, "app-server", "--stdio"], cwd=project,
                                   env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=errors, text=True, bufsize=1)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)

        def request(identifier, method, params):
            process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": identifier,
                                            "method": method, "params": params}) + "\n")
            process.stdin.flush()
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if not selector.select(timeout=1):
                    continue
                line = process.stdout.readline()
                if not line:
                    raise RuntimeError("Codex app-server exited before response")
                message = json.loads(line)
                if message.get("id") == identifier:
                    if "error" in message:
                        raise RuntimeError(message["error"])
                    return message["result"]
            raise TimeoutError(f"Codex {method} timed out")

        try:
            request(1, "initialize", {"clientInfo": {"name": "shared-memory-skill-check",
                                                    "version": "0.1.0"}})
            process.stdin.write('{"jsonrpc":"2.0","method":"initialized"}\n')
            process.stdin.flush()
            result = request(2, "skills/list", {"cwds": [str(project)], "forceReload": True})
            skills = [skill for item in result["data"] for skill in item["skills"]
                      if skill["name"] == "shared-context"]
            if len(skills) != 1 or Path(skills[0]["path"]).resolve() != skill_path.resolve():
                raise RuntimeError("Codex did not discover the installed Skill")
            if not skills[0].get("enabled", True):
                raise RuntimeError("Codex Skill is disabled")
            return "PASS"
        finally:
            selector.close()
            process.terminate()
            process.communicate(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--opencode", required=True)
    args = parser.parse_args()
    # Allow only platform essentials; do not inherit production credentials,
    # client configuration, provider endpoints or telemetry configuration.
    env = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TMPDIR", "SHELL")
           if key in os.environ}
    with tempfile.TemporaryDirectory(prefix="shared-memory-skills-") as temporary:
        base = Path(temporary).resolve()
        home, project = base / "home", base / "project"
        home.mkdir()
        project.mkdir()
        env.update(HOME=str(home), CODEX_HOME=str(home / ".codex"),
                   XDG_CONFIG_HOME=str(home / ".config"), XDG_DATA_HOME=str(home / ".local/share"),
                   XDG_CACHE_HOME=str(home / ".cache"), XDG_STATE_HOME=str(home / ".local/state"))
        (home / ".codex").mkdir()
        output = setup_skill(base / "workspace", project, home / ".agents" / "skills")
        skill_path = Path(output["skill"])
        result = {"scope": "Client discovery only; no model execution",
                  "codex_version": subprocess.check_output([args.codex, "--version"], env=env, text=True).strip(),
                  "opencode_version": subprocess.check_output([args.opencode, "--version"], env=env, text=True).strip(),
                  "codex_discovery": codex_discovery(args.codex, project, env, skill_path)}
        def opencode_skills():
            response = subprocess.run([args.opencode, "api", "get", "/api/skill", "--standalone",
                                       "--param", "location=" + json.dumps({"directory": str(project)})],
                                      cwd=project, env=env, capture_output=True, text=True, timeout=45)
            if response.returncode:
                raise RuntimeError(f"OpenCode skill query failed: {response.stderr[-2000:]}")
            payload = json.loads(response.stdout)
            if Path(payload["location"]["directory"]).resolve() != project.resolve():
                raise RuntimeError("OpenCode queried a different project location")
            return [item for item in payload["data"]
                    if item["id"] == "shared-context"]

        matched = opencode_skills()
        result["opencode_shared_directory"] = "PASS" if matched else "NOT_DISCOVERED"
        if not matched:
            native = install_skill(base / "workspace", home / ".config/opencode/skills")
            skill_path = Path(native["skill"])
            matched = opencode_skills()
            result["opencode_native_directory"] = "PASS" if matched else "NOT_DISCOVERED"
        if not matched:
            (project / "opencode.json").write_text(json.dumps({
                "$schema": "https://opencode.ai/config.json",
                "skills": [str(home / ".agents/skills")],
            }))
            skill_path = Path(output["skill"])
            matched = opencode_skills()
            result["opencode_explicit_source"] = "PASS" if matched else "NOT_DISCOVERED"
            config_response = subprocess.run(
                [args.opencode, "api", "get", "/api/config", "--standalone", "--param",
                 "location=" + json.dumps({"directory": str(project)})],
                cwd=project, env=env, capture_output=True, text=True, timeout=45)
            config_response.check_returncode()
            entries = json.loads(config_response.stdout)
            if not any(str(home / ".agents/skills") in entry.get("info", {}).get("skills", [])
                       for entry in entries):
                raise RuntimeError("OpenCode did not load the explicit Skill source config")
            result["opencode_explicit_config_loaded"] = "PASS"
        if matched:
            if Path(matched[0]["path"]).resolve() != skill_path.resolve():
                raise RuntimeError("OpenCode loaded a different Skill")
            if not matched[0].get("autoinvoke", True) or not matched[0].get("description"):
                raise RuntimeError("OpenCode Skill is not advertised")
        result["opencode_discovery"] = "PASS" if matched else "NOT_DISCOVERED"
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
