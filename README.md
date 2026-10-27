# Shared Memory Gateway

**One Markdown knowledge base. Multiple agents. Corrections instead of append-only memory.**<br>
**一份 Markdown 知识库，多个 Agent 共享。修订旧记忆，而不只是不断追加。**

A small, local-first proof of concept for agents sharing canonical Markdown
notes (including an existing Obsidian vault) through a CLI or MCP stdio server.
The core has no runtime dependencies, model calls, telemetry, or vector database.

这是一个小型、本地优先的开源原型，让多个 Agent 通过 CLI 或 MCP stdio
共享同一份规范 Markdown 笔记（可使用现有 Obsidian 库）。核心没有运行时
第三方依赖，不调用模型、不发送遥测，也不要求向量数据库。

[Agent rules / Agent 使用规则](docs/AGENT_RULES.md) · [Security / 安全](SECURITY.md) · [Validation / 验证](docs/VALIDATION.md) · [Contributing / 贡献](CONTRIBUTING.md)

> **Alpha / proof of concept.** The caller performs semantic synthesis. This is
> not an autonomous memory extraction engine, a Mem0 replacement, or a certified
> concurrent editor. Start with a synthetic vault, not your production notes.
>
> **Alpha／概念验证。** 语义理解与知识整合由调用方负责。本项目不是自动记忆
> 提取引擎、Mem0 替代品，也不是经过认证的并发编辑器。请先使用合成笔记库，
> 不要直接接入生产笔记。

## Why this project / 为什么做这个项目

Shared agent memory has three distinct problems:

1. **Access:** every client can reach the same approved notes.
2. **Lifecycle:** clients read them at the right time, including after project
   switches or context compaction.
3. **Maintenance:** new knowledge corrects existing topics instead of
   accumulating contradictory fragments.

MCP addresses access, but does not guarantee lifecycle behavior or factual
quality. This project provides a small file-first write boundary and reproducible
tests. It borrows ideas from memory systems without making an opaque database the
canonical knowledge source.

Agent 共享记忆有三个不同问题：

1. **共同访问**：每个客户端都能读取同一批获准笔记。
2. **及时读取**：在项目切换、上下文压缩等时机重新加载相关背景。
3. **持续维护**：新信息修订已有主题，而不是累积互相矛盾的片段。

MCP 解决共同访问，但不保证客户端会在正确时机读取，也不保证事实质量。
本项目提供精简的文件写入边界和可复现测试，借鉴记忆系统的设计，但不让
不透明数据库成为规范知识的唯一来源。

```text
Agent clients + their rules / hooks  |  Agent 客户端 + 规则／Hook
                    │
             CLI or MCP stdio  |  CLI 或 MCP stdio
                    │
          Explicit note allowlist  |  明确的笔记白名单
     Read → Propose diff → Check revision → Apply
   读取 → 预览修改 → 校验版本 → 应用修改
                    │
        Canonical Markdown files  |  规范 Markdown 文件
```

## Implemented / 已实现

- Exact allowlisted UTF-8 Markdown files; no recursive vault crawling.
- Raw-byte SHA-256 revisions, diff previews and exact single-passage replacements.
- Cross-process POSIX `flock`, atomic replacement and best-effort external-edit checks.
- Preservation of unrelated bytes, line endings and ordinary permission bits.
- Literal case-insensitive substring search, rereading disk each time; supports
  Chinese substrings without implying semantic retrieval or word segmentation.
- Explicit project-root mapping; unmatched/ambiguous projects are not guessed.
- Exact passage deletion, without keeping a second note history in service state.
- Optional MCP SDK adapter with six tools.

- 仅访问明确列入白名单的 UTF-8 Markdown 文件，不递归扫描整个笔记库。
- 使用原始字节 SHA-256 版本、修改预览和精确的单段替换。
- 使用 POSIX 跨进程 `flock`、原子替换，并尽力检测外部编辑。
- 保留无关内容、换行字节和普通文件权限位。
- 每次直接读取文件的大小写不敏感子串搜索，可搜索中文；不等同于语义检索
  或中文分词。
- 显式映射项目根目录；未匹配或有歧义时不猜测项目。
- 精确删除指定段落；服务状态中不保留第二份笔记历史。
- 可选 MCP SDK 适配器，暴露六个工具。

## Not implemented / 尚未实现

- Automatic fact extraction, truth checking, secret scanning, user approvals,
  embeddings, graph reasoning, background indexing or full conversation capture.
- Guaranteed lifecycle hooks across clients, or model-level integration tests
  for Codex, Claude Code, OpenCode or WorkBuddy.
- A transactional protocol with arbitrary external editors, a multi-user security
  boundary, Windows support, note creation/moves, or full backup management.
- Durable idempotency receipts: replaying an applied proposal returns a revision
  conflict; reread before retrying an uncertain operation.

- 自动事实提取、事实核验、密钥扫描、用户审批、向量检索、图推理、后台索引，
  或完整对话采集。
- 保证所有客户端生命周期 Hook 生效，或 Codex、Claude Code、OpenCode、
  WorkBuddy 的模型级集成测试。
- 与任意外部编辑器协作的事务协议、多用户安全隔离、Windows 支持、笔记新建／
  移动或完整备份管理。
- 持久化幂等回执：重复应用已完成的修改会收到版本冲突；写入结果不确定时，
  应先重新读取再处理。

## Quick start / 快速开始

Python 3.11+ on macOS or Linux / macOS 或 Linux 上的 Python 3.11+：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mcp]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_mcp.py
```

Optional `uv` equivalent / 可选的 `uv` 命令：
`uv sync --extra mcp` and `uv run python scripts/verify_mcp.py`。

Read a bundled synthetic note / 读取项目自带的合成样例：

```bash
echo '{"note":"demo.md"}' | .venv/bin/shared-memory --config examples/memory.json read
```

Demonstrate a correction with the core / 使用核心接口演示如何修订旧结论：

```python
from shared_memory_gateway.core import Memory

memory = Memory("examples/memory.json")
before = memory.read("demo.md")
proposal = memory.propose_update(
    note="demo.md", expected_revision=before["revision"],
    old="Status: pending", new="Status: verified",
    reason="Replace the previous status, do not add another status",
    source="Synthetic verification",
)
print(proposal["diff"])       # Preview only; does not modify the note.
memory.apply_update(proposal) # Apply only if the caller's policy permits it.
```

The example modifies a bundled file. Copy the examples to a disposable directory
before experimenting repeatedly. Automated tests create and clean up their own
temporary vaults and do not touch the bundled examples or personal notes.

上面的示例会修改项目自带文件。反复试验前请先将 `examples` 复制到临时目录。
自动化测试会自行创建并清理临时笔记库，不会触碰项目样例或个人笔记。

## Configuration / 配置

See [`examples/memory.json`](examples/memory.json). `vault` and `state_dir` paths
are relative to the config file; absolute paths also work. `state_dir` must be
outside the vault and **identical for all writers sharing that vault**. It stores
empty lock files only. Keep the config and filesystem under trusted local control.

配置示例见 [`examples/memory.json`](examples/memory.json)。`vault` 和
`state_dir` 默认相对配置文件解析，也可以使用绝对路径。`state_dir` 必须位于
笔记库外，并且**所有共享该笔记库的写入进程必须使用同一个目录**。其中只保存
空锁文件。请确保配置与文件系统位于可信的本机控制范围内。

`notes` is an explicit list of existing relative `.md` files, not a glob.
Symlinks are rejected. The server does not change frontmatter or impose a note
template. Use a small bootstrap list to avoid injecting the whole vault. Project
roots are absolute explicit paths; nested roots matching multiple projects are
ambiguous. Project filtering is retrieval convenience, not tenant authorization:
each client using a config can read every note allowlisted by that config.

`notes` 必须逐个列出已存在的相对 `.md` 文件，不支持 glob；拒绝符号链接。服务
不会自动修改 frontmatter 或强制笔记模板。请用小型 `bootstrap` 列表，避免把整座
笔记库注入上下文。项目根路径必须显式使用绝对路径；嵌套路径匹配多个项目时会
返回歧义。项目过滤只是检索范围，不是租户级授权：使用同一配置的客户端都能读取
该配置白名单中的全部笔记。

## MCP integration / MCP 接入

Configure a client to launch / 在客户端配置中启动：

```text
command: /absolute/path/to/.venv/bin/shared-memory-mcp
args: ["--config", "/absolute/path/to/memory.local.json"]
```

Client-specific configuration formats differ, so this process specification is
not a universal config snippet. Add the suggested [client rules](docs/AGENT_RULES.md)
and verify that the model actually uses the tools.

各客户端的 MCP 配置格式不同，因此以上是进程启动参数，不是适用于所有客户端的
完整配置片段。请添加建议的[客户端规则](docs/AGENT_RULES.md)，并验证模型实际
调用工具；显示“已连接”不代表模型会及时读取记忆。

| Tool / 工具 | Purpose / 作用 |
|---|---|
| `bootstrap(project_root)` | Load configured context and project entries / 加载启动上下文与项目入口 |
| `search(query, project?, limit?)` | Literal search of current allowlisted files / 在白名单文件中实时子串搜索 |
| `read(note)` | Return content and full raw-byte revision / 返回正文和完整原始字节版本 |
| `propose_update(note, expected_revision, old, new, reason, source)` | Preview one unambiguous replacement / 预览一处无歧义的替换 |
| `apply_update(proposal)` | Revalidate and apply the exact proposal / 重新校验并应用原提案 |
| `forget(note, expected_revision, text, reason, source)` | Remove one exact passage / 删除一段精确匹配的正文 |

The proposal digest binds request arguments. **It is not a signature, approval,
or proof of truth.** Source and reason fields require nonempty strings; evidence
is not verified. The caller must make and enforce semantic and privacy decisions.
Source and rationale are returned but not automatically persisted: include lasting
evidence in the replacement text when appropriate.

提案摘要只绑定请求参数，**不是数字签名、用户批准或事实属实的证明**。来源和
理由字段只检查非空，不验证证据。语义与隐私决策仍由调用方负责。来源与理由会在
结果中返回，但不会自动另存；需要长期保留的依据应在合适时整合进替换正文。

## Concurrency boundaries / 并发边界

Two gateway processes using the same config/state coordinate with a per-note
lock and compare the expected revision *inside* that lock. A stale writer is
rejected rather than merged automatically. A proposal is not a write reservation.

使用相同配置和状态目录的 Gateway 进程通过逐笔记锁协调，并在锁内校验预期版本。
旧版本写入会被拒绝，不会自动合并。生成提案并不等于预留了写入权。

External editors do not follow these locks. The final hash check catches many
external edits but leaves a check-to-replace race. Atomic rename prevents partial
file contents, not all lost updates from uncooperative editors. No recovery
snapshots are retained yet: keep your own backups, and do not use this alpha for
concurrent edits of important notes. Cross-file changes are not transactions.
ACLs, xattrs, ownership and hardlink identity are not managed.

外部编辑器不会遵守这些锁。最后的版本检查可以发现许多外部修改，但检查与替换
之间仍有竞争窗口。原子重命名可以避免半写入文件，不能避免所有非协作编辑造成的
覆盖。目前不保留恢复快照，请自行备份；不要将此 Alpha 用于重要笔记的并发编辑。
跨文件修改也不是事务。ACL、扩展属性、所有者和硬链接身份均不由本工具管理。

## Related systems / 相关项目

- [Basic Memory](https://github.com/basicmachines-co/basic-memory): a richer
  Markdown knowledge system. This repository includes an isolated compatibility
  probe; it is not a dependency or certified backend.
- [Mem0](https://github.com/mem0ai/mem0): fact extraction and retrieval; check its
  current algorithm before assuming automatic update/delete behavior.
- [Hindsight](https://github.com/vectorize-io/hindsight): retain/recall/reflect
  and consolidated knowledge, with different canonical-store semantics.
- [Graphiti](https://github.com/getzep/graphiti): temporal context graphs.

- [Basic Memory](https://github.com/basicmachines-co/basic-memory)：功能更完整的
  Markdown 知识管理系统。本项目包含隔离兼容性探测脚本，但不依赖它，也没有将其
  认证为兼容后端。
- [Mem0](https://github.com/mem0ai/mem0)：事实提取与检索；不要在未核实当前算法
  版本前假定它会自动更新或删除旧事实。
- [Hindsight](https://github.com/vectorize-io/hindsight)：通过 retain／recall／
  reflect 处理记忆并形成整合知识，其规范存储语义与本项目不同。
- [Graphiti](https://github.com/getzep/graphiti)：时序上下文图。

No source code from these projects is bundled. Their benchmarks do not establish
that this proof of concept works in real agent sessions.

本项目不包含上述项目的源代码。它们公开的基准成绩也不能证明本原型已在真实
Agent 会话中有效。

## Contributing / 参与贡献

See [CONTRIBUTING.md](CONTRIBUTING.md). Use synthetic fixtures only. Improvements
should preserve canonical file ownership and document concurrency, privacy and
evidence boundaries. MIT licensed.

请先阅读[贡献指南](CONTRIBUTING.md)，仅使用合成测试数据。改进应保持规范文件的
唯一权威地位，并明确记录并发、隐私和证据边界。本项目采用 MIT 许可证。
