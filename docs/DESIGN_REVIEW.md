# Name and design review

Status: recommendation, not a rename or a feature claim. Reviewed 2026-10-27.
The product records personal and project context for reuse across agent clients.
Markdown is the current canonical format, not the product category.

## Name

**Recommendation: Shared Context** as the product-facing description; retain
`shared-memory-gateway` as the repository, Python package and MCP server name for
now. "Shared" identifies the cross-client use case, and "Context" covers both
personal preferences and project knowledge without promising automatic recall.
The phrase is descriptive rather than a distinct brand. A later public rename
would need package/repository name checks and a compatibility plan; GitHub search
alone is not a trademark or package-availability check.

| Candidate | Fit | Decision |
|---|---|---|
| Shared Memory Gateway | Accurate for the current local CLI/MCP access boundary, but "gateway" suggests a proxy or network edge; "memory" can imply automatic capture | Keep as the existing technical identifier, not the product promise |
| Shared Context | Describes cross-client personal/project context with few extra promises; generic phrase already used by other projects | Use as the product description, not a claim of exclusive naming |
| Context Ledger | Suggests durable audit/history and often compaction tracking, neither implemented here | Do not adopt |
| Context Anchor | Suggests session anchoring or automatic prompt injection, which the server cannot ensure | Do not adopt |

GitHub searches for `shared-context`, `context-ledger` and `context-anchor` found
existing uses, including [Ultracontext](https://github.com/ultracontext/ultracontext)
and [context-ledger](https://github.com/wiztek-llc/context-ledger). This is a
collision signal, not an exhaustive availability search. Avoid renaming code,
MCP tool names or installed workspaces merely to change positioning text.

## Open-source design comparison

The table describes published behavior in the linked projects, not an assertion
that their approaches have been independently certified here.

| Project / source | Relevant design | Decision for this project |
|---|---|---|
| [Basic Memory](https://github.com/basicmachines-co/basic-memory/blob/main/NOTE-FORMAT.md) | Markdown as canonical files; frontmatter, observations and relations form a richer indexed graph. Its [README](https://github.com/basicmachines-co/basic-memory) documents client-native setup and sync. | Keep files authoritative and improve per-client onboarding. Do not impose frontmatter or a graph grammar on an existing Obsidian library; the pinned compatibility probe observed formatting changes and a short-process external-edit visibility limit ([validation](VALIDATION.md)). |
| [MCP Memory Server](https://github.com/modelcontextprotocol/servers/blob/main/src/memory/README.md) | Explicit entities, atomic observations and relations, add/delete tools, and a shared-file locking protocol. | Make corrections explicit and coordinate cooperating processes. Its discrete observation model is not a substitute for hierarchical context topics; its locking does not solve this project's external-editor race. |
| [OpenLore](https://github.com/aakarim/OpenLore/blob/main/README.md) | Serves Markdown through several transports with identity-specific views and conflict-aware whole-file writes. | Retain the simple local allowlist and revision check. If remote/team access is requested, design authentication and authorization explicitly before adding transports; project search filtering is not an ACL. |
| [Mem0](https://github.com/mem0ai/mem0/blob/main/README.md) | Separates user/session/agent memory; model-backed extraction and retrieval, with version-specific update semantics. | Retain personal/project separation and evaluate retrieval with sourced questions before adopting extraction. Do not assume its latest algorithm reconciles existing Markdown topics automatically. |
| [Letta](https://github.com/letta-ai/letta-code) | Stateful agent runtime manages memory alongside sessions and agent execution. | Keep lifecycle responsibility with each client. MCP access alone cannot guarantee startup reads or compaction recovery. |

## Priorities and acceptance

1. **P0, make onboarding repeatable:** test `init` output with actual client
   configuration formats and model tool calls. Codex-to-OpenCode correction/read
   passed on synthetic context; autonomous startup retrieval, project switching,
   model stale-write reconciliation, and compaction recovery still need separate
   runs. Keep unsupported clients and policies explicit.
2. **P1, make edits recoverable:** define snapshots, backup ownership, and crash
   recovery before expanding real-data use. Preserve the file as the only current
   authority and retain the explicit external-editor race limitation.
3. **P2, evaluate discovery:** collect sourced English/Chinese retrieval tasks,
   including project boundaries and stale facts. Compare the current literal
   search to simple full-text indexing before adding embedding/model pipelines.
4. **P3, optional synthesis:** allow proposals with source, rationale and diff;
   establish privacy and correction policy before model-backed ingestion. Never
   silently append a contradictory fact as if both are current.

No reviewed project establishes a generally correct choice of memory format,
retrieval engine, or automatic capture policy for this codebase. Each adoption
requires a targeted test against the actual personal/project context workflow.
