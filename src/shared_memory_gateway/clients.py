"""Documented local Skill entry points, not a claim of client execution support."""

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .core import MemoryError


@dataclass(frozen=True)
class Client:
    name: str
    project_path: str | None
    user_path: str | None
    documentation: str
    note: str = "Local Skill placement only; client execution has not been verified."


CLIENTS = {
    "universal": Client("Agent Skills-compatible client", ".agents/skills", ".agents/skills",
                        "https://agentskills.io", "Choose only if your client reads this directory."),
    "codex": Client("Codex", ".agents/skills", ".agents/skills",
                    "https://developers.openai.com/codex/skills",
                    "Isolated CLI discovery passed; model execution and lifecycle remain unverified."),
    "claude-code": Client("Claude Code", ".claude/skills", ".claude/skills",
                          "https://code.claude.com/docs/en/skills"),
    "opencode": Client("OpenCode V2", ".opencode/skills", ".config/opencode/skills",
                       "https://opencode.ai/v2/docs/skills",
                       "2.2.0 isolated API discovery returned no Skills; placement is not execution evidence."),
    "cursor": Client("Cursor", ".cursor/skills", ".cursor/skills",
                     "https://cursor.com/docs/context/skills"),
    "github-copilot": Client("GitHub Copilot", ".github/skills", ".copilot/skills",
                             "https://docs.github.com/en/copilot/concepts/agents/about-agent-skills",
                             "CLI, IDE and cloud surfaces need separate discovery/execution checks."),
    "gemini-cli": Client("Gemini CLI", ".gemini/skills", ".gemini/skills",
                         "https://geminicli.com/docs/cli/skills/"),
    "windsurf": Client("Windsurf / Cascade", ".windsurf/skills", ".codeium/windsurf/skills",
                       "https://docs.windsurf.com/windsurf/cascade/skills",
                       "Legacy-compatible paths; current docs redirect to Devin Desktop. Verify your version."),
    "cline": Client("Cline", ".cline/skills", ".cline/skills",
                    "https://docs.cline.bot/customization/skills"),
    "trae": Client("TRAE", ".trae/skills", ".trae/skills",
                   "https://docs.trae.ai/ide/skills"),
    "qoder": Client("Qoder", ".qoder/skills", ".qoder/skills",
                    "https://docs.qoder.com/extensions/skills"),
    "qwen-code": Client("Qwen Code", ".qwen/skills", ".qwen/skills",
                        "https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/"),
    "codebuddy": Client("CodeBuddy Code", ".codebuddy/skills", ".codebuddy/skills",
                        "https://www.codebuddy.ai/docs/cli/skills",
                        "Non-built-in Skills require explicit client-side trust/enablement; verify with /skills."),
    "workbuddy": Client("WorkBuddy", None, None,
                        "https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market",
                        "Use an explicitly confirmed --skill-home; desktop import and local paths vary. "
                        "Do not infer compatibility from CodeBuddy Code."),
}


def list_clients() -> dict:
    return {"scope": "Local macOS/Linux Skill placement; not model or cloud certification",
            "documentation_checked": "2026-10-29",
            "clients": [{"id": identifier, **asdict(client)}
                        for identifier, client in CLIENTS.items()]}


def skill_homes(agents: list[str] | None, scope: str, project_root: str | Path | None,
                skill_home: str | Path | None) -> list[tuple[str, Path]]:
    selected = list(dict.fromkeys(agents or ["universal"]))
    if scope not in ("user", "project"):
        raise MemoryError("INVALID_REQUEST", "scope must be user or project")
    if skill_home is not None and len(selected) != 1:
        raise MemoryError("INVALID_REQUEST", "--skill-home requires exactly one agent")
    root = Path(project_root).expanduser().resolve() if project_root else None
    if scope == "project" and (root is None or not root.is_dir()):
        raise MemoryError("INVALID_PROJECT_ROOT", "Project scope requires an existing --project-root")
    targets = []
    for identifier in selected:
        if identifier not in CLIENTS:
            raise MemoryError("UNKNOWN_CLIENT", f"Unknown agent: {identifier}; run skill clients")
        client = CLIENTS[identifier]
        relative = client.project_path if scope == "project" else client.user_path
        if skill_home is not None:
            target = Path(skill_home).expanduser().absolute()
        elif relative is None:
            raise MemoryError("MANUAL_TARGET_REQUIRED",
                              f"{identifier} requires a confirmed --skill-home; see {client.documentation}")
        else:
            # Respect OpenCode's native XDG config location.
            if identifier == "opencode" and scope == "user":
                value = os.environ.get("XDG_CONFIG_HOME", "")
                config = Path(value) if value else Path.home() / ".config"
                if not config.is_absolute():
                    raise MemoryError("INVALID_REQUEST", "XDG_CONFIG_HOME must be an absolute path")
                target = config / "opencode" / "skills"
            else:
                target = (root if scope == "project" else Path.home()) / relative
        targets.append((identifier, target.absolute()))
    return targets
