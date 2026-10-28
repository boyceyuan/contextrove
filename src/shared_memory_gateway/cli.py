"""One JSON request per invocation; also useful for independent-process tests."""

import argparse
import json
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from .core import Memory, MemoryError

METHODS = ("read", "search", "bootstrap", "propose_update", "apply_update", "forget")


def initialize(directory: str | Path, project_root: str | Path | None = None) -> dict:
    """Create a private personal/project context workspace and local MCP config."""
    root = Path(directory).expanduser().absolute()
    if root.exists():
        raise MemoryError("TARGET_EXISTS", f"Refusing to use an existing path: {root}")
    vault = root / "context"
    personal = vault / "personal-context.md"
    project = vault / "projects" / "current-project.md"
    for path in (personal, project):
        if path.exists():
            raise MemoryError("TARGET_EXISTS", f"Refusing to overwrite {path}")

    resolved_project = Path(project_root).expanduser().resolve() if project_root else None
    if resolved_project and not resolved_project.is_dir():
        raise MemoryError("INVALID_PROJECT_ROOT", "project_root must be an existing directory")
    notes = ["personal-context.md", "projects/current-project.md"]
    config = {
        "vault": "context",
        "state_dir": ".state",
        "notes": notes,
        "bootstrap": ["personal-context.md"],
        "projects": ({"current-project": {
            "roots": [str(resolved_project)],
            "notes": ["projects/current-project.md"],
        }} if resolved_project else {}),
        "max_bytes": 262144,
    }

    root.mkdir(mode=0o700, parents=True)
    root.chmod(stat.S_IRWXU)
    personal.parent.mkdir(parents=True, exist_ok=True)
    project.parent.mkdir(parents=True, exist_ok=True)
    vault.chmod(stat.S_IRWXU)
    personal.parent.chmod(stat.S_IRWXU)
    project.parent.chmod(stat.S_IRWXU)
    personal.write_text(
        "# Personal context\n\n"
        "## Stable preferences\n\n"
        "## Collaboration rules\n\n"
        "## Explicit boundaries\n\n"
        "Only add information explicitly confirmed by the user. Do not store credentials.\n",
        encoding="utf-8",
    )
    project.write_text(
        "# Current project context\n\n"
        "## Goal and scope\n\n"
        "## Architecture and key concepts\n\n"
        "## Decisions and rationale\n\n"
        "## Current status and evidence\n\n"
        "## Open questions\n",
        encoding="utf-8",
    )
    config_path = root / "memory.local.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    for path in (personal, project, config_path):
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    (root / ".gitignore").write_text("memory.local.json\n.state/\n", encoding="utf-8")
    config_resolved = str(config_path.resolve())
    # Preserve the venv launcher path; resolving its symlink can escape the
    # environment where this package and its optional MCP dependency are installed.
    command_resolved = str(Path(sys.executable).absolute())
    server_args = ["-m", "shared_memory_gateway.server", "--config", config_resolved]
    return {
        "workspace": str(root.resolve()),
        "config": config_resolved,
        "vault": str(vault.resolve()),
        "project_root": str(resolved_project) if resolved_project else None,
        "mcp_command": command_resolved,
        "mcp_args": server_args,
        "mcp_config": {
            "mcpServers": {
                "shared-memory-gateway": {
                    "command": command_resolved,
                    "args": server_args,
                }
            }
        },
        "opencode_v2_config": {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "servers": {
                    "shared-memory-gateway": {
                        "type": "local",
                        "command": [command_resolved, *server_args],
                    }
                }
            },
        },
        "codex_mcp_add": [
            "codex", "mcp", "add", "shared-memory-gateway", "--",
            command_resolved, *server_args,
        ],
    }


def demo() -> dict:
    """Run a disposable, local correction without touching user context."""
    with tempfile.TemporaryDirectory(prefix="shared-memory-demo-") as temporary:
        base = Path(temporary)
        project_root = base / "project"
        project_root.mkdir()
        setup = initialize(base / "workspace", project_root)
        note = Path(setup["vault"]) / "projects" / "current-project.md"
        note.write_text(note.read_text(encoding="utf-8") + "\nStatus: pending.\n", encoding="utf-8")

        writer = Memory(setup["config"])
        matched = writer.bootstrap(str(project_root))
        before = writer.read("projects/current-project.md")
        proposal = writer.propose_update(
            note="projects/current-project.md", expected_revision=before["revision"],
            old="Status: pending.", new="Status: verified.",
            reason="Correct the synthetic status", source="Synthetic demo",
        )
        writer.apply_update(proposal)
        after = Memory(setup["config"]).read("projects/current-project.md")
        if (matched["status"] != "matched"
                or "projects/current-project.md" not in matched["entries"]
                or "Status: pending." not in before["content"]
                or "Status: verified." not in after["content"]
                or "Status: pending." in after["content"]
                or before["revision"] == after["revision"]):
            raise MemoryError("DEMO_FAILED", "Synthetic correction did not persist")
        return {"scope": "Local core only; no agent or MCP session",
                "project": matched["status"], "before": "pending", "after": "verified",
                "fresh_read": "PASS"}


def setup(client: str, directory: str | Path, project_root: str | Path) -> dict:
    """Initialize context and explicitly register one installed agent client."""
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise MemoryError("INVALID_PROJECT_ROOT", "project_root must be an existing directory")
    target = Path(directory).expanduser().absolute()
    existing = target.exists()
    if target.is_symlink():
        raise MemoryError("WORKSPACE_MISMATCH", f"Refusing symlink workspace: {target}")
    if existing:
        config_path = target / "memory.local.json"
        try:
            if config_path.is_symlink():
                raise ValueError("Config must not be a symlink")
            config = json.loads(config_path.read_text(encoding="utf-8"))
            matches = [p for p in config["projects"].values()
                       if p["roots"] == [str(root)]
                       and p["notes"] == ["projects/current-project.md"]]
            if (config["vault"] != "context" or config["state_dir"] != ".state"
                    or "personal-context.md" not in config["notes"] or len(matches) != 1
                    or (target / "context").is_symlink()):
                raise ValueError("Workspace does not match this project")
            memory = Memory(config_path)
            memory.read("personal-context.md")
            memory.read("projects/current-project.md")
            config_path = config_path.resolve()
        except (OSError, ValueError, KeyError, TypeError, MemoryError) as exc:
            raise MemoryError("WORKSPACE_MISMATCH",
                              f"Existing workspace at {target} is not initialized for {root}") from exc
    executable = shutil.which(client)
    if executable is None:
        raise MemoryError("CLIENT_NOT_FOUND", f"Install {client} before running setup")
    initialized = (initialize(target, root) if not existing else {
        "workspace": str(target.resolve()), "vault": str(memory.vault),
        "config": str(config_path), "mcp_command": str(Path(sys.executable).absolute()),
        "mcp_args": ["-m", "shared_memory_gateway.server", "--config", str(config_path)],
    })
    command = [executable, "mcp", "add", "shared-memory-gateway",
               *(["--global"] if client == "opencode" else []), "--",
               initialized["mcp_command"], *initialized["mcp_args"]]
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True,
                                check=False, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MemoryError("CLIENT_SETUP_FAILED",
                          f"Workspace available at {target}, but {client} registration failed: {exc}. "
                          f"Retry with: {shlex.join(command)}") from exc
    if result.returncode != 0:
        raise MemoryError("CLIENT_SETUP_FAILED",
                          f"Workspace {'reused' if existing else 'created'} at {target}, but "
                          f"{client} registration failed. "
                          f"Fix the client and retry setup or run: {shlex.join(command)}")
    return {"status": "registered", "client": client, "project_root": str(root),
            "workspace": initialized["workspace"], "config": initialized["config"],
            "workspace_reused": existing,
            "personal_note": str(Path(initialized["vault"]) / "personal-context.md"),
            "project_note": str(Path(initialized["vault"]) / "projects/current-project.md"),
            "next": "Restart the client and ask it to bootstrap this project, then read the project note",
            "verified": "Client command succeeded; model tool use not yet checked"}


def main():
    parser = argparse.ArgumentParser(description="Manage personal and project context for AI agents")
    subparsers = parser.add_subparsers(dest="method", required=True)
    init = subparsers.add_parser("init", help="Create a portable context workspace and local config")
    init.add_argument("--directory", default="~/.shared-memory-gateway")
    init.add_argument("--project-root", help="Optionally register the current project's absolute path")
    subparsers.add_parser("demo", help="Run a disposable local correction and fresh read")
    setup_parser = subparsers.add_parser("setup", help="Initialize context and register an agent client")
    setup_parser.add_argument("--client", choices=("opencode", "codex"), required=True)
    setup_parser.add_argument("--directory", default="~/.shared-memory-gateway")
    setup_parser.add_argument("--project-root", default=".")
    for method in METHODS:
        command = subparsers.add_parser(method)
        command.add_argument("--config", required=True)
    args = parser.parse_args()
    try:
        if args.method == "init":
            result = initialize(args.directory, args.project_root)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            print("Context workspace initialized. Review the generated templates and MCP command.", file=sys.stderr)
            return
        if args.method == "demo":
            print(json.dumps(demo()))
            return
        if args.method == "setup":
            print(json.dumps(setup(args.client, args.directory, args.project_root), ensure_ascii=False, indent=2))
            return
        parameters = json.load(sys.stdin)
        result = getattr(Memory(args.config), args.method)(**parameters)
        print(json.dumps(result, ensure_ascii=False))
    except MemoryError as exc:
        print(json.dumps({"error": {"code": exc.code, "message": str(exc)}}))
        raise SystemExit(1)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"error": {"code": "INVALID_REQUEST_OR_CONFIG", "type": type(exc).__name__}}))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
