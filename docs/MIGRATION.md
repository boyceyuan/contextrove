# ContextRove migration / 更名与迁移

ContextRove 0.2.0 was previously Shared Memory Gateway 0.1.0. Install from source
until a separately verified package release exists. A name check is not a PyPI
publication. This change does not move or rewrite a context vault.

ContextRove 0.2.0 原名 Shared Memory Gateway 0.1.0。当前使用源码安装；包名检查
不表示已经发布 PyPI。更名不自动迁移或改写上下文库。

| Identifier / 标识 | Before / 之前 | After / 之后 |
|---|---|---|
| Product / 产品 | Shared Memory Gateway | ContextRove |
| Repository / 仓库 | `boyceyuan/shared-memory-gateway` | `boyceyuan/contextrove` |
| Python distribution / 分发包 | `shared-memory-gateway` | `contextrove` |
| Primary CLI / 主命令 | `shared-memory`, `shared-memory-mcp` | `contextrove`, `contextrove-mcp`; old commands retained as aliases |
| Python imports / 模块 | `shared_memory_gateway` | Unchanged / 保留 |
| MCP server ID / 服务 ID | `shared-memory-gateway` | Unchanged / 保留 |
| Workspace default / 默认工作区 | `~/.shared-memory-gateway` | Unchanged / 保留 |
| Skill ID | `shared-context` | Unchanged / 保留 |

## Existing installs / 已有安装

1. Keep the existing vault and `memory.local.json`. Stop client processes using
   the environment while replacing its installed package.
2. Do not co-install the old and new distributions in one environment: they own
   the same module and compatibility scripts. For an in-place source upgrade,
   uninstall the old distribution first, then install this checkout. Choose the
   optional MCP extra only if needed:

   ```bash
   .venv/bin/python -m pip uninstall shared-memory-gateway
   .venv/bin/python -m pip install -e '.[mcp]'
   .venv/bin/contextrove demo
   ```

3. Existing MCP config continues to use `shared_memory_gateway.server` and the
   same server ID. If the environment path changes, update the Python command in
   that config. Do not reinitialize or delete the vault.
4. Old generated Skills reference the old CLI path. The compatibility alias
   remains usable when that environment still exists. New Skill templates bind
   `contextrove`; installer comparison will refuse an old/different Skill. Read
   it, preserve local customizations, and remove only the confirmed generated
   Skill before reinstalling. There is no forced overwrite or automatic migration.
5. Restart the client and inspect its discovery and actual CLI calls. File matches
   alone do not validate model execution or lifecycle behavior.

升级时保留笔记与配置。同一环境内先卸载旧分发包再装新包，避免两个包拥有相同模块。
旧 MCP 标识、模块路径及命令别名保留；如果换虚拟环境，仍需更新绝对路径。新版 Skill
会因模板变化拒绝覆盖旧文件，先阅读并保留手动修改，再只移除确认属于生成物的 Skill
并重新安装。不要删除上下文库，也不要把修改过的业务 Skill 当作生成物处理。

## Repository remotes / 仓库远端

After the GitHub repository rename, existing links normally redirect; update
your own remote explicitly:

```bash
git remote set-url origin git@github.com:boyceyuan/contextrove.git
```

The local checkout directory can retain its old name. Renaming it may invalidate
editable-install or client absolute paths, so it is not part of this migration.
No PyPI/npm publication or client-global config changes are performed here.

本地目录可继续使用旧名字，避免影响 editable 安装与客户端绝对路径。仓库更名、分支
合并和包发布是分别可核对的动作；以实际 GitHub PR／验证记录为准。
