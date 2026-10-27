# Shared Memory Gateway

English | [简体中文](README.zh-CN.md)

**Personal and project context, shared across agents. Corrections instead of append-only memory.**

A small, local-first proof of concept for recording and maintaining personal and
project context, then sharing it across agents through CLI or MCP stdio. Markdown
is the current portable, human-readable storage format, not the product's purpose.
The core has no runtime dependencies, model calls, telemetry, or vector database.

[Agent rules](docs/AGENT_RULES.md) · [Security](SECURITY.md) · [Validation](docs/VALIDATION.md)

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

```text
Agent clients + their rules / hooks
                │
         CLI or MCP stdio
                │
         Explicit note allowlist
         Read → Propose diff → Check revision → Apply
                │
       Personal + project context
       stored as portable Markdown
```

## Implemented

- `shared-memory init` creates separate personal and project context templates,
  an allowlisted workspace, and a machine-local config without overwriting files.
- Exact allowlisted UTF-8 Markdown files; no recursive vault crawling.
- Raw-byte SHA-256 revisions, diff previews and exact single-passage replacements.
- Cross-process POSIX `flock`, atomic replacement and best-effort external-edit checks.
- Preservation of unrelated bytes / line endings and ordinary permission bits.
- Literal case-insensitive substring search, rereading disk every time; supports
  Chinese substrings without implying semantic retrieval or word segmentation.
- Explicit project-root mapping; unmatched/ambiguous projects are not guessed.
- Exact passage deletion, without keeping a second note history in service state.
- Optional MCP SDK adapter with six tools.

## Not implemented

- Automatic fact extraction, truth checking, secret scanning, user approvals,
  embeddings, graph reasoning, background indexing or full conversation capture.
- Guaranteed lifecycle hooks across clients, or model-level integration tests
  for Codex, Claude Code, OpenCode or WorkBuddy.
- A transactional protocol with arbitrary external editors, a multi-user security
  boundary, native Windows support, automatic context discovery, or full backup management.
- Durable idempotency receipts: replaying an applied proposal returns a revision
  conflict; reread before retrying an uncertain operation.

## Roadmap / Development plan

This is a proposed, validation-gated roadmap, not a delivery commitment. Items
remain **planned** until implemented, tested, and reflected in the status above.

### P0 — Validate real client workflows

- Test two real agent clients against a disposable context workspace: startup bootstrap,
  project switching, correction of an existing note, stale-write handling, and
  recovery after context compaction.
- Document per-client MCP setup and lifecycle hooks only after verifying them.
- Acceptance: cross-client reads and corrections work; unsupported hooks and
  model-level limitations are explicitly documented; no production vault is used.

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

## Future directions / 后续方向

See the stage-gated [development plan](#roadmap--development-plan). Near term,
priorities are real-client validation and file-update recovery; retrieval and
model-backed synthesis remain conditional on evaluation results.

## Quick start

Python 3.11+ on macOS or Linux. From a local checkout:

```bash
git clone https://github.com/boyceyuan/shared-memory-gateway.git
cd shared-memory-gateway
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mcp]'
.venv/bin/shared-memory init --project-root /absolute/path/to/your/project
```

Copy the `mcp_config` object printed by `init` into the chosen agent client's MCP
settings. Restart that client and ask it to call `bootstrap` for the repository.
The command below verifies the project code, not that an agent app has been configured.

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_mcp.py
```

Optional `uv` equivalent: `uv sync --extra mcp` and `uv run python scripts/verify_mcp.py`.

Initialization creates a private `~/.shared-memory-gateway/` context workspace by
default and prints its config path plus the MCP server command. Use `--directory`
to choose another location. It refuses an existing target. Review the generated
personal/project context templates, then copy the generated `mcp_config` JSON
into your agent's MCP settings (adapt the outer key to the client's format).
The initializer does not edit client settings. Direct JSON output is also available
from Python as `shared_memory_gateway.cli.initialize(...)`.
For clients using the common `mcpServers` shape, the generated entry is ready to
paste as-is. Agent apps and runtime dependencies still need to be installed
separately.

Create a portable workspace without machine-specific project mapping by omitting
`--project-root`. To use project bootstrap on another machine, run `init` there
with that machine's checkout path. The context Markdown can be copied or versioned
independently; `memory.local.json` and `.state/` are machine-local and ignored.
The initializer creates private directories/files on POSIX systems; store the
workspace in a location covered by your own backups. `--project-root` must point
to the project whose context you want to load, not this gateway's checkout. Omit
it for a personal-only workspace.

Read a bundled example context:

```bash
echo '{"note":"demo.md"}' | .venv/bin/shared-memory read --config examples/memory.json
```

Demonstrate correction using the core:

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
print(proposal["diff"])       # preview does not modify the note
memory.apply_update(proposal) # apply only if the caller's policy permits it
```

Running this changes the example file. To experiment repeatedly, copy the examples
to a disposable directory first. Automated tests create and clean up their own
temporary context workspaces and do not touch the bundled examples or personal data.

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

The initializer prints an `mcp_config` JSON object containing the active Python
executable and absolute config path. Copy it into a client that accepts the common
`mcpServers` shape. For example:

```json
{
  "mcpServers": {
    "shared-memory-gateway": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "shared_memory_gateway.server", "--config", "/absolute/path/to/memory.local.json"]
    }
  }
}
```

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
