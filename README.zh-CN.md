# Shared Memory Gateway

**多种 Agent 共用一份 Markdown 知识，能修订旧结论，而不只是追加记忆。**

这是一个小型、可验证的开源原型：规范知识保留在 Markdown／Obsidian，
通过统一 CLI 或 MCP stdio 接口读取和受控更新。核心不调用模型、不联网，
也不要求向量数据库。完整参数和边界见 [英文 README](README.md)。

> Alpha，不是已经接通全部客户端的成品。Agent 负责理解、归纳与判断，
> 服务负责文件范围、版本和写入机制。先用合成样例测试，不要直接接生产笔记。

## 核心思路

共享访问、及时读取、持续整合是三个不同问题：MCP 提供共同入口；客户端
规则／hook 负责在新会话、项目切换与压缩后读取；Agent 根据证据维护规范主题。

```text
Agent + 规则／Hook
      ↓
CLI / MCP Gateway
      ↓
读取旧正文 → 预览最小修改 → 校验版本 → 更新原主题
      ↓
唯一规范 Markdown 正文
```

已有结论从“待验证”变成“已验证”时，应该修改原结论并保留必要依据，
而不是让两种状态长期并存。版本已被其他进程更新时，拒绝覆盖，重新读取合并。

## 当前支持

- 明确文件白名单、原文字节 SHA-256 版本；拒绝越界路径和符号链接。
- 单段精确替换、diff 预览；无关内容及换行字节不改动。
- 同一状态目录下的跨进程写锁与原子替换；旧版本请求会被拒绝。
- 实时读取文件的子串检索，支持中文；不是语义检索。
- 显式项目路径匹配，不猜测未匹配／有歧义的项目。
- 精确遗忘一段文字；不保留第二份正文或服务侧历史。
- 可选 MCP SDK 适配，六个工具，以及独立进程与协议测试。

## 快速验证

macOS／Linux，Python 3.11+：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mcp]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_mcp.py
```

自动测试只创建临时合成笔记库并自行清理。配置示例为
[`examples/memory.json`](examples/memory.json)；真实配置不要提交到 Git。
所有访问同一笔记库的 writer 必须共用同一个 `state_dir`。

MCP 启动命令为 `.venv/bin/shared-memory-mcp --config /绝对路径/memory.local.json`。
将其配置进客户端支持的 MCP 入口，再按 [Agent 规则](docs/AGENT_RULES.md)验证
实际工具调用；“已连接”不等于模型会及时使用记忆。

## 重要边界

- 不自动抽取事实、不保证语义正确、不自动识别隐私，不代替用户授权。
- 普通笔记是数据，不能被当成任意执行指令；来源字段也不等于已验证证据。
- 目前无向量索引、知识图谱、后台归纳、自动创建笔记与客户端 hook。
- 外部编辑器不遵守服务锁，检查与替换之间仍有竞争窗口，不能保证所有外部
  并发编辑不丢失；目前也未保留恢复快照。重要笔记请独立备份。
- 服务只协调受同一协议管理的 writer；不是多租户或恶意本地用户隔离机制。
- 遗忘不清除 Git 历史、备份、客户端会话和云端模型留存。
- 本地存储不意味着检索内容不会通过你的 Agent 发送到云模型。

验证证据与未验证范围见 [VALIDATION](docs/VALIDATION.md)，安全说明见
[SECURITY](SECURITY.md)。欢迎贡献，采用 MIT 许可。
