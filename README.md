# Shared Memory Gateway

English | [简体中文](README.zh-CN.md)

**Personal and project context, shared across agents. Corrections instead of append-only memory.**

A small, local-first proof of concept for recording and maintaining personal and
project context, then sharing it across agents through CLI or MCP stdio. Markdown
is the current portable, human-readable storage format, not the product's purpose.
The core has no runtime dependencies, model calls, telemetry, or vector database.

[Agent rules](docs/AGENT_RULES.md) · [Security](SECURITY.md) · [Validation](docs/VALIDATION.md) · [Name and design](docs/DESIGN_REVIEW.md)

[Quick start](#quick-start) · [Architecture](#architecture) · [Context model](#context-and-responsibility) · [MCP integration](#mcp-integration) · [Roadmap](#roadmap--development-plan)

> **Alpha / proof of concept.** The caller performs semantic synthesis. This is
> not an autonomous memory extraction engine, a Mem0 replacement, or a certified
> concurrent editor. Start with a synthetic vault, not your production notes.

## Why another component?

Shared context has three separate problems:

1. **Access:** every client can reach the same approved notes.
2. **Lifecycle:** clients read them at the right time, including after compaction.
3. **Maintenance:** new knowledge corrects existing topics instead of accumulating
   mutually contradictory fragments.

The goal is to preserve useful personal preferences and project understanding
across tools and sessions, with clear boundaries between the two. Markdown is used
because people can inspect, edit, move, and version it with ordinary tools. MCP
provides a common access path; it does not itself guarantee timely retrieval or
factual quality. This project adds a small write boundary and reproducible tests.

## Architecture

![Architecture: independent client processes share canonical Markdown, config and locks; corrections read, propose and recheck before applying](docs/assets/context-architecture.svg)

Each connected client launches its own MCP stdio server process, with its own
core instance. Other MCP clients can use the adapter but have not been validated.
The CLI uses the same core implementation. All processes use the same local
config, Markdown files, and state directory; the state holds
locks, not a second copy of context. A human editor works on the files directly
and does not participate in the gateway lock. Project filtering selects relevant
content; it is **not** an access-control boundary. A client configured with this
workspace can read every allowlisted file.

### Context and responsibility

| Layer | Responsibility | Where it lives |
|---|---|---|
| Agent client | Decide when to load context, assess source and meaning, review diffs, enforce user policy | Client rules or hooks; outside this server |
| MCP / CLI adapter | Expose the same core operations to multiple processes | `server.py` (optional `mcp` extra), `cli.py` |
| Shared core | Check allowlist, resolve an explicit project root, read/search current files, compare revisions and apply an exact edit | `core.py` |
| Canonical context | Separate personal and project topics, edited in place and portable as files | UTF-8 Markdown under configured `vault` |
| Machine-local metadata | List approved files, bootstrap entries, project mappings and coordinated locks | `memory.local.json` and `.state/`; not knowledge copies |

`init` creates `context/personal-context.md` and
`context/projects/current-project.md`. It bootstraps only the personal file;
when a registered root matches, `bootstrap(project_root)` returns the project's
file path in `entries`, which the agent then reads explicitly. Additional
topics require both an existing Markdown file and an explicit allowlist entry.
Neither a project match nor a search result proves a fact is true. The client
must keep personal preferences distinct from project claims and their evidence.

For larger workspaces, organize context by **personal preferences**, **collaboration
rules**, and **project knowledge**. Within project knowledge, link domain → system →
topic → evidence; keep dates, environments and verification status in the relevant
topic. These are authoring conventions, not a schema enforced by the core. The
starter puts collaboration rules in the personal template; split them into a
separate allowlisted file when useful. Obsidian is an optional editor, not a runtime
dependency.

### Read and correction paths

1. **Discover:** a client calls `bootstrap` with its actual absolute project
   directory; the core returns a small global context and matching project
   paths, or an explicit unmatched/ambiguous status. `search` rereads allowlisted
   files and returns literal-match snippets; `read` returns the full selected file
   and its raw-byte SHA-256 revision.
2. **Propose:** for a stable, sourced correction, the client supplies the exact
   old and new passages, revision, reason and source. `propose_update` requires a
   unique old passage and returns a unified diff without writing anything.
3. **Apply:** after reviewing the diff under its own policy, the client calls
   `apply_update`. The core rechecks the revision under a cooperative file lock,
   writes a temporary file, checks for an external change and atomically replaces
   the file. A stale revision fails; the client must reread and reconcile.
   `forget` uses the same exact-passage update path and cannot erase Git history,
   backups or past model conversations.

Each core instance reads the same files; there is no central daemon. Atomic
replacement prevents partial file contents; the final external-edit check is
best effort. A failure after replacement can return `WRITE_UNCERTAIN`, so read
the file before deciding whether to retry.

This is a **file-first, local single-user design**, not an automatic fact
extractor or an agent runtime. MCP makes operations available; it does not
trigger startup reads or compaction recovery. The lock coordinates gateway
processes only: direct editor writes can still race between the final check
and replacement. Recovery snapshots and better retrieval are [planned](#roadmap--development-plan),
not components of the diagram. See [validation](docs/VALIDATION.md) for tested
cross-client behavior and [security](SECURITY.md) for filesystem limits.

## Implemented

- `shared-memory init` creates separate personal and project context templates,
  an allowlisted workspace, and a machine-local config without overwriting files.
- `shared-memory demo` checks a disposable local correction; `setup --client`
  creates or reuses a project workspace and registers OpenCode or Codex via its CLI.
- Exact allowlisted UTF-8 Markdown files; no recursive vault crawling.
- Raw-byte SHA-256 revisions, diff previews and exact single-passage replacements.
- Cross-process POSIX `flock`, atomic replacement and best-effort external-edit checks.
- Preservation of unrelated bytes / line endings and ordinary permission bits.
- Literal case-insensitive substring search, rereading disk every time; supports
  Chinese substrings without implying semantic retrieval or word segmentation.
- Explicit project-root mapping; unmatched/ambiguous projects are not guessed.
- Exact passage deletion, without keeping a second note history in service state.
- Optional MCP SDK adapter with six tools.
- Synthetic cross-agent model-session acceptance: OpenCode read `pending`; Codex
  read, previewed and applied `verified`; a fresh OpenCode session read `verified`
  through MCP (see [validation](docs/VALIDATION.md)).

## Not implemented

- Automatic fact extraction, truth checking, secret scanning, user approvals,
  embeddings, graph reasoning, background indexing or full conversation capture.
- Guaranteed lifecycle hooks, autonomous startup retrieval, project-switching and
  compaction recovery; Claude Code and WorkBuddy model sessions remain untested.
- A transactional protocol with arbitrary external editors, a multi-user security
  boundary, native Windows support, automatic context discovery, or full backup management.
- Durable idempotency receipts: replaying an applied proposal returns a revision
  conflict; reread before retrying an uncertain operation.

## Quick start

Python 3.11+ on macOS or Linux. Install from a checkout:

```bash
git clone https://github.com/boyceyuan/shared-memory-gateway.git
cd shared-memory-gateway
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mcp]'
```

Still in this checkout, register an installed client for the project you want
to keep context for (replace the one absolute project path):

```bash
.venv/bin/shared-memory setup --client opencode --project-root /absolute/path/to/your/project
# or: .venv/bin/shared-memory setup --client codex --project-root /absolute/path/to/your/project
```

`setup` creates `~/.shared-memory-gateway/` with separate personal/project
Markdown, registers the local MCP server using the chosen client's CLI, and
prints the note paths. Edit the project note, restart the client, then ask it
to `bootstrap` this project's absolute path and `read` the returned project
entry. **A successful registration is not proof that the model used the tool.**
For a second client in the *same project*, run `setup` again with its `--client`
and the same `--project-root`; it reuses the existing notes. OpenCode
registration is global; Codex uses its MCP CLI scope. An unrelated existing
context directory is rejected. For a different project, a new `--directory`
alone is insufficient because `setup` uses a fixed MCP server name. Configure
additional projects and server names manually using [MCP integration](#mcp-integration).
If registration fails after workspace creation, the error includes a retry
command; rerunning `setup` with the same project also reuses the workspace.

Want a no-client self-check first? Run `.venv/bin/shared-memory demo`. It
prints `before: pending`, `after: verified`, and
`fresh_read: PASS` using disposable files. **This only checks the local core.**
The previous [Codex → OpenCode model-session test](docs/VALIDATION.md#real-client-model-sessions-cross-client-correction-passed)
used synthetic notes; startup retrieval without prompting remains unverified.

For manual setup, existing workspaces, migration, and protocol checks, see
[MCP integration](#mcp-integration) and [validation](docs/VALIDATION.md).

## Context workspace configuration

See [`examples/memory.json`](examples/memory.json) or generate one with `init`.
Paths for `vault` and `state_dir` are relative to the config file; absolute paths
also work. `state_dir` must be outside the context directory and **identical for
all writers sharing that context**. It stores
empty lock files only. Keep configuration and the filesystem under trusted local
control; paths are not authorization for arbitrary machine access.

The starter workspace separates `personal-context.md` from
`projects/current-project.md`; project-specific contexts can be added and explicitly
allowlisted. `notes` is an explicit list of existing relative `.md` files, not a glob.
Symlinks are rejected. The server does not change frontmatter or impose a template.
Use a small bootstrap list to avoid injecting all context. Project roots are
absolute explicit paths; nested roots matching multiple projects are ambiguous.
Project filtering is retrieval convenience, not tenant-level authorization: every
client attached to a config can read every note allowlisted by that config.

## MCP integration

The initializer prints `opencode_v2_config`, `codex_mcp_add`, and `mcp_config`,
all using the active Python executable and absolute config path. For OpenCode V2,
merge this shape into your project or global `opencode.json(c)`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "shared-memory-gateway": {
        "type": "local",
        "command": ["/absolute/path/to/python", "-m", "shared_memory_gateway.server", "--config", "/absolute/path/to/memory.local.json"]
      }
    }
  }
}
```

For Codex, execute the `codex_mcp_add` array as a command, or use this shape
with the paths printed by `init`:

```bash
codex mcp add shared-memory-gateway -- /absolute/path/to/python -m shared_memory_gateway.server --config /absolute/path/to/memory.local.json
```

The `mcp_config` output uses `mcpServers` for clients that support that shape.
The generated interpreter belongs to the environment where the package was
installed. If you move/recreate that environment, rerun `init` or update the
command. Client-specific configuration formats differ; add the suggested
[client rules](docs/AGENT_RULES.md) and verify actual tool use. The initializer
does not install an agent client or edit its configuration.

| Tool | Purpose |
|---|---|
| `bootstrap(project_root)` | Load configured global context and exact project entries |
| `search(query, project?, limit?)` | Literal search of current allowlisted files |
| `read(note)` | Return content and full raw-byte revision |
| `propose_update(note, expected_revision, old, new, reason, source)` | Preview one unambiguous replacement |
| `apply_update(proposal)` | Revalidate and apply the exact proposal |
| `forget(note, expected_revision, text, reason, source)` | Remove one exact passage |

The proposal digest binds request arguments. **It is not a signature, an approval,
or proof of truth.** Source / reason fields require nonempty strings, not verified
evidence. The caller must make and enforce semantic / privacy decisions. Source
and rationale are returned but not automatically persisted: put lasting evidence
in the topic's replacement text when appropriate.

## Name and design

The product name is under discussion; the published identifiers remain
`shared-memory-gateway`. The [design review](docs/DESIGN_REVIEW.md) compares
Basic Memory, MCP Memory Server, OpenLore, Mem0 and Letta by storage, update
behavior, scope and client integration. This README also draws on the
[Hindsight README](https://github.com/vectorize-io/hindsight#readme)'s separation
of concepts, operations and integrations, and
[OpenLore](https://github.com/aakarim/OpenLore#readme)'s explanation of read/write
ownership. The diagram above describes this repository's implementation.

## Roadmap / Development plan

The cross-client baseline below is complete. The remaining stages are
validation-gated plans, not delivery commitments.

### Completed baseline — Cross-client correction and read

- On isolated synthetic context, OpenCode and Codex model sessions called the
  MCP tools. Codex revised a prior status after reviewing the diff, and a new
  OpenCode session read the revised status. This verifies cross-client tool use
  and write visibility, **not** automatic lifecycle behavior; see
  [validation](docs/VALIDATION.md) for the exact scope and Codex approval policy.

### P0 — Validate client lifecycle and scope

- Test automatic retrieval at session start without an explicit tool-use prompt,
  project switching with distinct synthetic contexts, stale-write reconciliation
  by the model, and retrieval after compaction. Fresh-session reading with an
  explicit tool-use prompt is already covered by the baseline above.
- Document client-specific MCP setup and lifecycle hooks only where observed.
- Acceptance: record the actual tool calls and content for each scenario, including
  failures and unsupported hooks; do not use production context.

### P1 — Harden file updates

- Evaluate recovery snapshots / backups, crash recovery, stricter external-edit
  coordination, and filesystem metadata behavior.
- Add tests for each supported operating system and filesystem before expanding
  the support claim.
- Acceptance: interrupted writes have a documented recovery path; conflict and
  partial-failure outcomes remain explicit. Do not claim atomic coordination with
  arbitrary external editors without a protocol they participate in.

### P2 — Improve retrieval when evaluations justify it

- Build a small, source-annotated context evaluation set for Chinese, English, aliases,
  code identifiers, project isolation, stale facts, and no-answer queries.
- Compare current literal search with SQLite full-text search; consider semantic
  retrieval or reranking only if measured recall gaps justify the added runtime,
  model, and data-flow complexity.
- Acceptance: reproducible evaluation shows source-grounded retrieval improves
  without cross-project leakage or unacceptable latency / context growth.

### P3 — Optional synthesis integrations

- Explore Mem0 / Hindsight as candidate extraction or synthesis adapters, not as a
  second canonical store. Produce reviewable diffs against existing topics.
- Define provenance, user policy, correction, deletion, and outbound-data behavior
  before enabling any model-backed processing.
- Acceptance: corrections replace or qualify old claims; stale/conflicting facts
  are not silently accumulated or promoted to truth; deletion scope is explicit.

### Explicitly out of scope for the initial release

No hosted multi-user service, automatic full-conversation ingestion, graph database,
or autonomous memory rewriting is planned until a concrete need and security model
justify it. Contributions and issue reports can help reprioritize this roadmap.

## Concurrency boundaries

Two gateway processes using the same config/state coordinate with a per-note
lock and compare the expected revision *inside* that lock. A stale writer is
rejected rather than merged automatically. A proposal is not a write reservation.

External editors do not follow these locks. The final hash check catches many
external edits but leaves a check-to-replace race. Atomic rename prevents partial
file contents, not all lost updates from uncooperative editors. There are no
retained recovery snapshots yet: keep your own backups, and do not use this alpha
for concurrent edits of important notes. Cross-file changes are not transactions.
Filesystem metadata beyond ordinary permission bits (ACLs, xattrs, ownership,
hardlink identity) is not preserved or managed.

## Related systems

- [Basic Memory](https://github.com/basicmachines-co/basic-memory): a richer
  Markdown knowledge system. An optional isolated compatibility probe is included;
  it is not a dependency or certified backend.
- [Mem0](https://github.com/mem0ai/mem0): fact extraction and retrieval; check the
  current algorithm/version before assuming automatic update/delete behavior.
- [Hindsight](https://github.com/vectorize-io/hindsight): retain/recall/reflect and
  consolidated knowledge, with different canonical-store semantics.
- [Graphiti](https://github.com/getzep/graphiti): temporal context graphs.

No source code from these projects is bundled. Product benchmarks are not evidence
that this proof of concept works in real agent sessions.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Use synthetic fixtures only. Improvements
should preserve canonical file ownership and explicitly document concurrency,
privacy and evidence boundaries. MIT licensed.
