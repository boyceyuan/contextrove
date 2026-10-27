"""One JSON request per invocation; also useful for independent-process tests."""

import argparse
import json
import stat
import sys
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
    }


def main():
    parser = argparse.ArgumentParser(description="Manage personal and project context for AI agents")
    subparsers = parser.add_subparsers(dest="method", required=True)
    init = subparsers.add_parser("init", help="Create a portable context workspace and local config")
    init.add_argument("--directory", default="~/.shared-memory-gateway")
    init.add_argument("--project-root", help="Optionally register the current project's absolute path")
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
