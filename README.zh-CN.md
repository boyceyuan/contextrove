# Shared Memory Gateway

[English](README.md) | 简体中文

**多个 Agent 共用一份 Markdown 知识，修订旧记忆，而不只是不断追加。**

这是一个小型、本地优先的开源原型，让多个 Agent 通过 CLI 或 MCP stdio
共享同一份规范 Markdown 笔记（可使用现有 Obsidian 库）。核心不调用模型、
不发送遥测，也不要求向量数据库。

[Agent 使用规则](docs/AGENT_RULES.md) · [安全说明](SECURITY.md) · [验证记录](docs/VALIDATION.md)

> **Alpha／概念验证。** 语义理解与知识整合由调用方负责。本项目不是自动记忆
> 提取引擎、Mem0 替代品，也不是经过认证的并发编辑器。请先使用合成笔记库，
> 不要直接接入生产笔记。

## 为什么做这个项目

Agent 共享记忆有三个不同问题：

1. **共同访问**：每个客户端都能读取同一批获准笔记。
2. **及时读取**：在项目切换、上下文压缩等时机重新加载相关背景。
3. **持续维护**：新信息修订已有主题，而不是累积互相矛盾的片段。

MCP 解决共同访问，但不保证客户端会在正确时机读取，也不保证事实质量。
本项目提供精简的文件写入边界和可复现测试，借鉴记忆系统的设计，但不让
不透明数据库成为规范知识的唯一来源。

```text
Agent 客户端 + 规则／Hook
          │
       CLI / MCP stdio
          │
      明确的笔记白名单
读取 → 预览修改 → 校验版本 → 应用修改
          │
    规范 Markdown 文件
```

## 已实现

- 仅访问明确列入白名单的 UTF-8 Markdown 文件，不递归扫描整个笔记库。
- 使用原始字节 SHA-256 版本、修改预览和精确的单段替换。
- 使用 POSIX 跨进程 `flock`、原子替换，并尽力检测外部编辑。
- 保留无关内容、换行字节和普通文件权限位。
- 每次直接读取文件的大小写不敏感子串搜索，可搜索中文；不等同于语义检索
  或中文分词。
- 显式映射项目根目录；未匹配或有歧义时不猜测项目。
- 精确删除指定段落；服务状态中不保留第二份笔记历史。
- 可选 MCP SDK 适配器，暴露六个工具。

## 尚未实现

- 自动事实提取、事实核验、密钥扫描、用户审批、向量检索、图推理、后台索引，
  或完整对话采集。
- 保证所有客户端生命周期 Hook 生效，或 Codex、Claude Code、OpenCode、
  WorkBuddy 的模型级集成测试。
- 与任意外部编辑器协作的事务协议、多用户安全隔离、Windows 支持、笔记新建／
  移动或完整备份管理。
- 持久化幂等回执：重复应用已完成的修改会收到版本冲突；写入结果不确定时，
  应先重新读取再处理。

## 后续方向与开发计划

这是一个**按验证结果推进的建议路线图**，不是交付承诺。功能只有在实现、测试，
并同步更新上方状态后，才算完成。

### P0：验证真实客户端工作流

- 使用隔离笔记库，在两个真实 Agent 客户端验证启动上下文、项目切换、修订旧笔记、
  旧版本冲突处理，以及上下文压缩后的恢复。
- 逐个验证客户端的 MCP 配置与生命周期 Hook 后，再编写对应接入说明。
- 验收标准：跨客户端读取与修订有效；明确记录不支持的 Hook 和模型级限制；不使用
  生产笔记库做测试。

### P1：加强文件更新可靠性

- 评估恢复快照／备份、进程异常后的恢复、更严格的外部编辑协调，以及文件系统元数据
  的处理方式。
- 在扩大系统支持范围前，为每个声明支持的操作系统和文件系统增加相应测试。
- 验收标准：中断写入有明确恢复路径；冲突与部分失败会明确报告。若外部编辑器不参与
  协议，不宣称能够与其实现严格原子协调。

### P2：根据评测改进检索

- 建立一组带规范来源的中英文评测问题，覆盖别名、代码标识、项目隔离、过期事实和
  无答案查询。
- 将当前子串搜索与 SQLite 全文检索进行比较；只有评测显示召回不足时，才考虑语义检索
  或重排，并衡量新增运行时、模型依赖和数据流复杂度。
- 验收标准：结果可复现地提升来源支持的召回，且没有跨项目泄漏，延迟与上下文增长
  在可接受范围内。

### P3：可选的知识整合适配器

- 探索 Mem0／Hindsight 作为候选事实提取或归纳适配器，不建立第二份规范知识库；输出
  可审阅的主题修改差异。
- 启用任何模型处理前，先定义来源、用户维护规则、纠错、删除和对外发送的数据范围。
- 验收标准：纠正能够替换旧结论或明确限定其范围；冲突与过期事实不会被静默累积或
  升格为事实；删除影响范围清楚。

### 初期明确不做

在没有明确需求与安全模型前，不计划提供托管多用户服务、全量对话自动导入、图数据库，
或自主重写长期记忆。可根据实际使用与验证结果调整优先级。

## 路线图状态说明

当前最近的优先事项是 P0：验证两个真实客户端的模型会话。检索增强和模型驱动的知识整合
均为条件性方向，需先有评测证据；它们目前都不是已实现能力。

## 快速开始

macOS／Linux，Python 3.11+：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mcp]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_mcp.py
```

可选 `uv` 命令：`uv sync --extra mcp`，然后运行
`uv run python scripts/verify_mcp.py`。

读取项目自带的合成样例：

```bash
echo '{"note":"demo.md"}' | .venv/bin/shared-memory --config examples/memory.json read
```

使用核心接口演示如何修订旧结论：

```python
from shared_memory_gateway.core import Memory

memory = Memory("examples/memory.json")
before = memory.read("demo.md")
proposal = memory.propose_update(
    note="demo.md", expected_revision=before["revision"],
    old="Status: pending", new="Status: verified",
    reason="替换旧状态，不再追加一个状态",
    source="合成验证",
)
print(proposal["diff"])       # 只预览，不修改笔记
memory.apply_update(proposal) # 仅在调用方政策允许时应用
```

该示例会修改项目自带文件。反复试验前请先将 `examples` 复制到临时目录。
自动化测试会自行创建并清理临时笔记库，不会触碰项目样例或个人笔记。

## 配置

配置示例见 [`examples/memory.json`](examples/memory.json)。`vault` 和
`state_dir` 默认相对配置文件解析，也可以使用绝对路径。`state_dir` 必须位于
笔记库外，并且**所有共享该笔记库的写入进程必须使用同一个目录**。其中只保存
空锁文件。请确保配置与文件系统位于可信的本机控制范围内。

`notes` 必须逐个列出已存在的相对 `.md` 文件，不支持 glob；拒绝符号链接。服务
不会自动修改 frontmatter 或强制笔记模板。请用小型 `bootstrap` 列表，避免把整座
笔记库注入上下文。项目根路径必须显式使用绝对路径；嵌套路径匹配多个项目时会
返回歧义。项目过滤只是检索范围，不是租户级授权：使用同一配置的客户端都能读取
该配置白名单中的全部笔记。

## MCP 接入

在客户端配置中启动：

```text
command: /absolute/path/to/.venv/bin/shared-memory-mcp
args: ["--config", "/absolute/path/to/memory.local.json"]
```

各客户端的 MCP 配置格式不同，因此以上是进程启动参数，不是适用于所有客户端的
完整配置片段。请添加建议的[客户端规则](docs/AGENT_RULES.md)，并验证模型实际
调用工具；显示“已连接”不代表模型会及时读取记忆。

| 工具 | 作用 |
|---|---|
| `bootstrap(project_root)` | 加载启动上下文与项目入口 |
| `search(query, project?, limit?)` | 在白名单文件中实时子串搜索 |
| `read(note)` | 返回正文和完整原始字节版本 |
| `propose_update(note, expected_revision, old, new, reason, source)` | 预览一处无歧义的替换 |
| `apply_update(proposal)` | 重新校验并应用原提案 |
| `forget(note, expected_revision, text, reason, source)` | 删除一段精确匹配的正文 |

提案摘要只绑定请求参数，**不是数字签名、用户批准或事实属实的证明**。来源和
理由字段只检查非空，不验证证据。语义与隐私决策仍由调用方负责。来源与理由会在
结果中返回，但不会自动另存；需要长期保留的依据应在合适时整合进替换正文。

## 并发边界

使用相同配置和状态目录的 Gateway 进程通过逐笔记锁协调，并在锁内校验预期版本。
旧版本写入会被拒绝，不会自动合并。生成提案并不等于预留了写入权。

外部编辑器不会遵守这些锁。最后的版本检查可以发现许多外部修改，但检查与替换
之间仍有竞争窗口。原子重命名可以避免半写入文件，不能避免所有非协作编辑造成的
覆盖。目前不保留恢复快照，请自行备份；不要将此 Alpha 用于重要笔记的并发编辑。
跨文件修改也不是事务。ACL、扩展属性、所有者和硬链接身份均不由本工具管理。

## 相关项目

- [Basic Memory](https://github.com/basicmachines-co/basic-memory)：功能更完整的
  Markdown 知识管理系统。本项目包含隔离兼容性探测脚本，但不依赖它，也没有将其
  认证为兼容后端。
- [Mem0](https://github.com/mem0ai/mem0)：事实提取与检索；不要在未核实当前算法
  版本前假定它会自动更新或删除旧事实。
- [Hindsight](https://github.com/vectorize-io/hindsight)：通过 retain／recall／
  reflect 处理记忆并形成整合知识，其规范存储语义与本项目不同。
- [Graphiti](https://github.com/getzep/graphiti)：时序上下文图。

本项目不包含上述项目的源代码。它们公开的基准成绩也不能证明本原型已在真实
Agent 会话中有效。

## 参与贡献

请先阅读[贡献指南](CONTRIBUTING.md)，仅使用合成测试数据。改进应保持规范文件的
唯一权威地位，并明确记录并发、隐私和证据边界。本项目采用 MIT 许可证。
