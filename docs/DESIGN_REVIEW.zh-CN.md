# 命名与设计对照

状态：建议，不代表已更名或已实现新功能。审阅日期：2026-10-27。
产品目的是记录个人与项目上下文，供多个 Agent 客户端复用。Markdown 是当前的
规范存储格式，不是产品类别。

## 命名判断

**建议使用 Shared Context 作为对外定位**；暂保留 `shared-memory-gateway` 仓库、
Python 包和 MCP 服务的技术标识。“Shared” 指跨客户端复用，“Context” 同时包含
个人偏好和项目知识，也不暗示自动记忆。它是通用描述，不是独占品牌。正式更名之前
还需检查包名、仓库名和兼容迁移；单靠 GitHub 搜索不能证明商标或包名可用。

| 候选 | 适配与风险 | 判断 |
|---|---|---|
| Shared Memory Gateway | 准确描述当前本地 CLI／MCP 访问边界，但 gateway 容易被理解为代理或网络入口，memory 也可能暗示自动捕获 | 保留现有技术标识，不把它当产品承诺 |
| Shared Context | 准确覆盖个人／项目上下文跨客户端复用；是已有项目也使用的通用词 | 作为产品定位，不宣称名称独占 |
| Context Ledger | 暗示持久审计历史／变更账本，当前没有实现 | 不采用 |
| Context Anchor | 易暗示会话锚定或自动注入提示词，当前服务不能保证 | 不采用 |

在 GitHub 检索 `shared-context`、`context-ledger`、`context-anchor` 可找到已有用途，
如 [Ultracontext](https://github.com/ultracontext/ultracontext) 和
[context-ledger](https://github.com/wiztek-llc/context-ledger)。这是重名信号，
不是完整的名称可用性调查。仅改变产品定位时不应贸然改动代码、MCP 工具名或已有工作区。

## 开源设计对照

下表依据链接项目公开的设计描述，不代表独立验证了对方全部实现。

| 项目／来源 | 值得参考的机制 | 本项目取舍 |
|---|---|---|
| [Basic Memory](https://github.com/basicmachines-co/basic-memory/blob/main/NOTE-FORMAT.md) | Markdown 为规范文件，借助 frontmatter、观察与关系建立索引图谱；[README](https://github.com/basicmachines-co/basic-memory) 提供客户端接入与同步说明 | 保留文件权威性，改进各客户端接入。不要强迫既有 Obsidian 文件转成新语法；本项目固定版本探测观察到格式变化及短进程外部编辑可见性边界（见[验证记录](VALIDATION.md)） |
| [MCP Memory Server](https://github.com/modelcontextprotocol/servers/blob/main/src/memory/README.md) | 实体、原子观察与关系，增删工具和共享文件写入锁 | 借鉴显式修订及协作进程锁；离散观察模型不能直接替代分层上下文主题，也不宣称锁解决外部编辑器竞争 |
| [OpenLore](https://github.com/aakarim/OpenLore/blob/main/README.md) | Markdown 多传输访问、按身份区分视图、冲突感知的整文件写入 | 当前保持本地白名单和版本校验。引入远程／团队协作前先设计认证授权；项目过滤并非 ACL |
| [Mem0](https://github.com/mem0ai/mem0/blob/main/README.md) | 区分用户／会话／Agent 记忆，模型驱动提取与检索，更新语义依版本而异 | 保留个人与项目分层，先用带来源问题评测检索再考虑自动提取；不假定当前算法能自动修订既有 Markdown 主题 |
| [Letta](https://github.com/letta-ai/letta-code) | 带状态 Agent 运行时统一管理记忆、会话及执行 | 生命周期交给客户端；单靠 MCP 连接不能保证启动读取或压缩恢复 |

## 优先级与验收

1. **P0：可复现接入。** 用实际客户端配置和模型工具调用验收 `init` 输出。合成库
   上 Codex → OpenCode 修订／读取已通过；无提示启动读取、项目切换、模型处理旧版本
   冲突、压缩恢复仍需分别验证。明确标注未覆盖客户端和审批策略。
2. **P1：可恢复更新。** 扩大真实数据应用前明确快照、备份归属与崩溃恢复；文件仍是
   唯一当前规范来源，保留外部编辑器竞态限制。
3. **P2：有评测的检索。** 建立有来源的中英文检索任务，覆盖项目边界和过期事实；
   比较现有子串搜索与简单全文索引，再决定是否添加嵌入与模型管线。
4. **P3：可选知识整合。** 输出含来源、理由和 diff 的提案；模型驱动摄取前明确隐私
   与纠错政策，不能静默追加与现有事实矛盾的新条目。

这些开源项目没有替本项目证明某种记忆格式、检索引擎或自动捕获政策一定正确；
每项借鉴都应回到个人／项目上下文实际工作流进行针对性验证。
