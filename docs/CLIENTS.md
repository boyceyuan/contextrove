# Local client compatibility / 本地客户端兼容

Checked against linked documentation on 2026-10-29. These are **installer targets**
for the bundled `shared-context` workflow, not certifications of every product,
version or surface. The same CLI and canonical context are used in every target.

下表表示内置工作流的安装目标，不代表每个产品／版本／形态都已通过执行验收。
用户／项目作用域只选择安装位置，不构成上下文访问隔离。

| `--agent` | Project Skill home / 项目目录 | User Skill home / 用户目录 | Documentation and limits / 依据与边界 |
|---|---|---|---|
| `universal` (default) | `.agents/skills` | `~/.agents/skills` | [Agent Skills](https://agentskills.io); select only if the client reads this directory |
| `codex` | `.agents/skills` | `~/.agents/skills` | [Codex](https://developers.openai.com/codex/skills); CLI discovery passed, model execution of this Skill unverified |
| `claude-code` | `.claude/skills` | `~/.claude/skills` | [Claude Code](https://code.claude.com/docs/en/skills); execution unverified |
| `opencode` | `.opencode/skills` | `$XDG_CONFIG_HOME/opencode/skills`, default `~/.config/opencode/skills` | [OpenCode V2](https://opencode.ai/v2/docs/skills); 2.2.0 isolated Skill API returned no entries |
| `cursor` | `.cursor/skills` | `~/.cursor/skills` | [Cursor](https://cursor.com/docs/context/skills); local and cloud surfaces need separate validation |
| `github-copilot` | `.github/skills` | `~/.copilot/skills` | [Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills); CLI, IDE and cloud differ |
| `gemini-cli` | `.gemini/skills` | `~/.gemini/skills` | [Gemini CLI](https://geminicli.com/docs/cli/skills/); execution unverified |
| `windsurf` | `.windsurf/skills` | `~/.codeium/windsurf/skills` | [Windsurf/Cascade](https://docs.windsurf.com/windsurf/cascade/skills); legacy paths, docs now redirect to Devin Desktop; verify installed version |
| `cline` | `.cline/skills` | `~/.cline/skills` | [Cline](https://docs.cline.bot/customization/skills); execution unverified |
| `trae` | `.trae/skills` | `~/.trae/skills` | [TRAE](https://docs.trae.ai/ide/skills); execution unverified |
| `qoder` | `.qoder/skills` | `~/.qoder/skills` | [Qoder](https://docs.qoder.com/extensions/skills); execution unverified |
| `qwen-code` | `.qwen/skills` | `~/.qwen/skills` | [Qwen Code](https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/); execution unverified |
| `codebuddy` | `.codebuddy/skills` | `~/.codebuddy/skills` | [CodeBuddy Code](https://www.codebuddy.ai/docs/cli/skills); external Skills require client-side trust/enablement; check `/skills` |
| `workbuddy` | Explicit `--skill-home` | Explicit `--skill-home` | [WorkBuddy](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market); confirm desktop import/path for the installed version; CodeBuddy results are not WorkBuddy evidence |

All homes receive `shared-context/SKILL.md`. Some clients read several aliases
with different precedence; this installer selects one native source per client.
Conflicting or disabled Skills elsewhere can still override or hide the installed
file. WorkBuddy has no assumed default, and `universal` does not mean all agents
support that directory. `skill clients` returns machine-readable paths and notes.

各目录下创建 `shared-context/SKILL.md`。客户端的其他同名 Skill、优先级、禁用开关或信任
设置仍可能影响发现结果；安装器不会修改这些配置。WorkBuddy 必须提供确认过的路径。

## Examples / 示例

```bash
contextrove setup --client skill --agent codex --agent claude-code --directory /absolute/context --project-root /absolute/project
contextrove skill install --workspace /absolute/context --agent cursor --agent cline --scope project --project-root /absolute/project
contextrove skill doctor --workspace /absolute/context --agent cursor --agent cline --scope project --project-root /absolute/project
contextrove skill install --workspace /absolute/context --agent workbuddy --skill-home /confirmed/workbuddy/skills
```

`setup --client codex|opencode` retains its original meaning: **MCP registration**.
To install a Skill for those clients use `--client skill --agent codex|opencode`.
Skill-specific options are rejected by the MCP setup path.

`setup --client codex|opencode` 仍表示 MCP 注册；Skill 安装需使用
`--client skill --agent codex|opencode`，避免混用参数。

## Acceptance levels / 验收层次

| Level / 层次 | Evidence / 证据 |
|---|---|
| Documented placement | The official docs list a source directory; manual targets remain explicit |
| Installation | Synthetic tests check rendered files, reuse, conflicts and failure reporting |
| Discovery | A specific client/version lists the enabled Skill; Codex passed, OpenCode probe did not |
| Execution | A model actually follows this Skill and invokes the intended CLI; unverified for this workflow |
| Cross-client visibility | Two clients observe a correction; existing MCP evidence does not validate Skill execution |
| Lifecycle | Startup reads, project switching and compaction recovery each need their own observations |

`skill doctor` is read-only and reports local file matches/missing/conflicts,
plus whether a basic workspace config is present. It leaves discovery and model
execution **unverified**, even when files match. See [validation](VALIDATION.md).

doctor 不创建锁或修改客户端配置；文件匹配不代表客户端已发现、启用或执行。

## Environments and future coverage / 环境与后续覆盖

- The core requires Python 3.11+ and POSIX `fcntl`: macOS/Linux are tested;
  native Windows is unsupported. WSL/container paths need environment-specific checks.
- Remote SSH and cloud agents cannot use a laptop's absolute CLI/vault paths.
  No cloud upload, sync, remote API or credentials distribution is implemented.
  Generated project Skills are machine-local; exclude them from shared commits.
- Roo/Kilo, Continue, Amp, Kiro, Amazon Q, Aider and other products remain future
  targets. Verify their current native Skill/rule support before adding adapters;
  a third-party installer's path list is not sufficient evidence.
- This installer ships one maintenance Skill. General business SOP Skill packaging
  and automatic extraction remain future work; canonical methods can already be
  maintained as approved context notes.

当前交付优先覆盖可本地验证的安装链路。远程／云端、操作系统与客户端版本分开验收；
后续新增适配按官方能力和实际需求推进，不能从目录支持推断模型行为。
