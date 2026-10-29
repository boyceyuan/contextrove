"""One JSON request per invocation; also useful for independent-process tests."""

import argparse
import fcntl
import json
import os
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


def _skill_target(workspace: Path, skill_home: str | Path | None) -> tuple[Path, str]:
    """Render and preflight without changing the workspace or an existing skill."""
    source = Path(__file__).parent / "skills" / "shared-context" / "SKILL.md"
    if not source.is_file():
        raise MemoryError("SKILL_NOT_FOUND", "The shared-context skill is missing from this installation")
    destination = (Path(skill_home).expanduser() if skill_home else
                   Path.home() / ".agents" / "skills") / "shared-context"
    destination = destination.absolute()
    # Prefer this Python environment over another installation on PATH.
    command = Path(sys.executable).absolute().parent / "shared-memory"
    if not command.is_file():
        raise MemoryError("CLI_NOT_FOUND", f"Install the CLI in the current Python environment: {command}")
    rendered = source.read_text(encoding="utf-8")
    rendered = rendered.replace("{{SHARED_MEMORY}}", shlex.quote(str(command)))
    rendered = rendered.replace("{{WORKSPACE}}", shlex.quote(str(workspace)))
    skill_file = destination / "SKILL.md"
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not skill_file.is_file() or skill_file.is_symlink():
            raise MemoryError("SKILL_EXISTS", f"Refusing to overwrite existing skill: {destination}")
        if skill_file.read_text(encoding="utf-8") != rendered:
            raise MemoryError("SKILL_EXISTS", f"A different skill already exists: {destination}")
    return skill_file, rendered


def install_skill(workspace: str | Path, skill_home: str | Path | None = None) -> dict:
    """Install the packaged portable skill for compatible local agent clients."""
    workspace_path = Path(workspace).expanduser().resolve()
    skill_file, rendered = _skill_target(workspace_path, skill_home)
    config_path = workspace_path / "memory.local.json"
    try:
        memory = Memory(config_path)
        for note in memory.notes:
            memory.read(note)
    except (OSError, ValueError, KeyError, TypeError, MemoryError) as exc:
        raise MemoryError("WORKSPACE_MISMATCH", f"Not an initialized shared-memory workspace: {workspace_path}") from exc
    reused = skill_file.exists()
    if not reused:
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(skill_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(rendered)
    return {"status": "reused" if reused else "installed", "skill": str(skill_file),
            "workspace": str(workspace_path), "config": str(config_path),
            "next": "Start a new compatible agent session and invoke shared-context"}


def _add_project(target: Path, root: Path) -> None:
    """Serialize setup writers and atomically publish an expanded allowlist."""
    config_path = target / "memory.local.json"
    if not target.is_dir():
        raise ValueError("Workspace must be an existing directory")
    if (config_path.is_symlink() or (target / "context").is_symlink()
            or (target / ".state").is_symlink()):
        raise ValueError("Workspace must not use symlinks")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if (config["vault"] != "context" or config["state_dir"] != ".state"
            or "personal-context.md" not in config["notes"]):
        raise ValueError("Unexpected workspace format")
    memory = Memory(config_path)
    with (memory.state / "setup.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        memory = Memory(config_path)
        if config.get("vault") != "context" or config.get("state_dir") != ".state":
            raise ValueError("Unexpected workspace format")
        if not isinstance(config.get("projects"), dict) or not isinstance(config.get("notes"), list):
            raise ValueError("Invalid project configuration")
        for note in memory.notes:
            memory.read(note)
        if not set(memory.notes) <= set(config["notes"]):
            raise ValueError("Invalid note allowlist")
        matched = memory.bootstrap(str(root))
        # Only an exact root may be reused; a nested project needs its own entry.
        names = [name for name, item in config["projects"].items()
                 if str(root) in item.get("roots", [])]
        if len(names) > 1 or matched["status"] == "ambiguous":
            raise ValueError("Ambiguous project mapping")
        if names:
            return
        if matched["status"] == "matched" or any(
                root in Path(registered).resolve().parents
                for project in config["projects"].values() for registered in project["roots"]):
            raise ValueError("Overlapping project roots require explicit manual configuration")
        project_name = root.name or "project"
        if project_name in config["projects"]:
            raise ValueError("Project name already maps to a different root")
        project_note = f"projects/{project_name}.md"
        Memory._validate_name(project_note)
        project_path = memory.vault / project_note
        if (project_note in memory.notes or project_path.exists() or project_path.is_symlink()
                or project_path.parent.is_symlink()):
            raise ValueError("Project note path already exists or uses a symlink")
        if not project_path.parent.exists():
            missing_parent = project_path.parent
            while not missing_parent.parent.exists():
                missing_parent = missing_parent.parent
            if missing_parent.parent.is_symlink():
                raise ValueError("Project note path must not contain symlink directories")
            missing_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        config["notes"].append(project_note)
        config["projects"][project_name] = {"roots": [str(root)], "notes": [project_note]}
        # Validate the prospective config before creating a new note.
        fd, temporary = tempfile.mkstemp(prefix=".setup-", dir=target)
        created = False
        published = False
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(config, stream, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            validated = Memory(temporary)
            for note in validated.notes:
                if note != project_note:
                    validated.read(note)
            fd = os.open(project_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            created = True
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(
                    f"# {project_name} context\n\n## Goal and scope\n\n"
                    "## Architecture and key concepts\n\n## Decisions and rationale\n\n"
                    "## Current status and evidence\n\n## Open questions\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, config_path)
            published = True
            directory_fd = os.open(target, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            exc = sys.exc_info()[1]
            if created and not published:
                project_path.unlink()
            if published and isinstance(exc, OSError):
                raise MemoryError("WRITE_UNCERTAIN",
                                  "Project config was published but directory sync failed") from exc
            raise
        finally:
            Path(temporary).unlink(missing_ok=True)


def setup_skill(directory: str | Path, project_root: str | Path,
                skill_home: str | Path | None = None) -> dict:
    """Create or safely reuse a matching workspace, then install the shared skill."""
    root = Path(project_root).expanduser().resolve()
    target = Path(directory).expanduser().absolute()
    if not root.is_dir():
        raise MemoryError("INVALID_PROJECT_ROOT", "project_root must be an existing directory")
    existing_parent = target
    while not existing_parent.exists() and not existing_parent.is_symlink():
        existing_parent = existing_parent.parent
    if target.is_symlink() or existing_parent.is_symlink():
        raise MemoryError("WORKSPACE_MISMATCH", f"Refusing symlink workspace: {target}")
    _skill_target(target.resolve(), skill_home)
    existing = target.exists()
    if not target.exists():
        try:
            initialized = initialize(target, root)
        except FileExistsError:
            # Another setup process may have initialized the same workspace.
            initialized = None
        if initialized is None:
            try:
                _add_project(target, root)
                initialized = {"workspace": str(target.resolve())}
            except (OSError, ValueError, KeyError, TypeError, MemoryError) as exc:
                raise MemoryError("WORKSPACE_MISMATCH",
                                  f"Existing workspace at {target} is not a valid shared-memory workspace") from exc
    else:
        try:
            _add_project(target, root)
            initialized = {"workspace": str(target.resolve())}
        except (OSError, ValueError, KeyError, TypeError, MemoryError) as exc:
            if isinstance(exc, MemoryError) and exc.code == "WRITE_UNCERTAIN":
                raise
            raise MemoryError("WORKSPACE_MISMATCH",
                              f"Existing workspace at {target} is not a valid shared-memory workspace") from exc
    installed = install_skill(initialized["workspace"], skill_home)
    memory = Memory(installed["config"])
    matched = memory.bootstrap(str(root))
    return {**initialized, **installed, "workspace_reused": existing,
            "project_root": str(root), "vault": str(memory.vault),
            "personal_note": str(memory.vault / "personal-context.md"),
            "project_notes": [str(memory.vault / note) for note in matched["entries"]]}


def agent_action(action: str, workspace: str | Path, project_root: str | None = None,
                 note: str | None = None, query: str | None = None,
                 project: str | None = None, limit: int = 10,
                 expected_revision: str | None = None, old: str | None = None,
                 new: str | None = None, reason: str | None = None,
                 source: str | None = None) -> dict:
    """Small argument-based interface intended for agent skill scripts."""
    try:
        memory = Memory(Path(workspace).expanduser() / "memory.local.json")
    except (OSError, ValueError, KeyError, TypeError, MemoryError) as exc:
        raise MemoryError("WORKSPACE_MISMATCH", "Workspace config is missing or invalid") from exc
    if action == "bootstrap":
        return memory.bootstrap(project_root or str(Path.cwd()))
    if action == "read":
        if not note:
            raise MemoryError("INVALID_REQUEST", "read requires --note")
        return memory.read(note)
    if action == "search":
        if not query:
            raise MemoryError("INVALID_REQUEST", "search requires --query")
        if project is not None and project not in memory.projects:
            raise MemoryError("INVALID_REQUEST", "project must match one bootstrap project ID")
        return memory.search(query, project, limit)
    if action == "propose":
        _require_edit(note, expected_revision, old, new, reason, source)
        return memory.propose_update(note, expected_revision, old, new, reason, source)
    if action == "apply":
        _require_edit(note, expected_revision, old, new, reason, source)
        proposal = memory.propose_update(note, expected_revision, old, new, reason, source)
        return memory.apply_update(proposal)
    if action == "forget":
        _require_edit(note, expected_revision, old, "", reason, source)
        return memory.forget(note, expected_revision, old, reason, source)
    raise MemoryError("INVALID_REQUEST", f"Unsupported agent action: {action}")


def _require_edit(note, expected_revision, old, new, reason, source):
    if not all(isinstance(value, str) for value in (note, expected_revision, old, new, reason, source)):
        raise MemoryError("INVALID_REQUEST", "Edit requires --note, --expected-revision, --old, "
                          "--new (except forget), --reason and --source")


def main():
    parser = argparse.ArgumentParser(description="Manage personal and project context for AI agents")
    subparsers = parser.add_subparsers(dest="method", required=True)
    init = subparsers.add_parser("init", help="Create a portable context workspace and local config")
    init.add_argument("--directory", default="~/.shared-memory-gateway")
    init.add_argument("--project-root", help="Optionally register the current project's absolute path")
    subparsers.add_parser("demo", help="Run a disposable local correction and fresh read")
    setup_parser = subparsers.add_parser("setup", help="Initialize context and install a Skill or register MCP")
    setup_parser.add_argument("--client", choices=("skill", "opencode", "codex"), required=True)
    setup_parser.add_argument("--directory", default="~/.shared-memory-gateway")
    setup_parser.add_argument("--project-root", default=".")
    setup_parser.add_argument("--skill-home", help="Override the Skill source directory (Skill setup only)")
    skill_parser = subparsers.add_parser("skill", help="Install the shared-context agent skill")
    skill_parser.add_argument("install", choices=("install",))
    skill_parser.add_argument("--workspace", default="~/.shared-memory-gateway")
    skill_parser.add_argument("--skill-home")
    agent_parser = subparsers.add_parser("agent", help="Run a context action for agent skills")
    agent_parser.add_argument("action", choices=("bootstrap", "read", "search", "propose", "apply", "forget"))
    agent_parser.add_argument("--workspace", default="~/.shared-memory-gateway")
    agent_parser.add_argument("--project-root")
    agent_parser.add_argument("--note")
    agent_parser.add_argument("--query")
    agent_parser.add_argument("--project")
    agent_parser.add_argument("--limit", type=int, default=10)
    agent_parser.add_argument("--expected-revision")
    agent_parser.add_argument("--old")
    agent_parser.add_argument("--new")
    agent_parser.add_argument("--reason")
    agent_parser.add_argument("--source")
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
            if args.client == "skill":
                result = setup_skill(args.directory, args.project_root, args.skill_home)
            else:
                result = setup(args.client, args.directory, args.project_root)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if args.method == "skill":
            output = install_skill(args.workspace, args.skill_home)
            memory = Memory(output["config"])
            output.update(personal_note=str(memory.vault / "personal-context.md"),
                          project_notes=[str(memory.vault / note)
                                         for project in memory.projects.values()
                                         for note in project["notes"]])
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return
        if args.method == "agent":
            result = agent_action(**{key: getattr(args, key) for key in (
                "action", "workspace", "project_root", "note", "query", "project", "limit",
                "expected_revision", "old", "new", "reason", "source")})
            print(json.dumps(result, ensure_ascii=False, indent=2))
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
