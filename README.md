# Shared Memory Gateway

English | [简体中文](README.zh-CN.md)

**One Markdown knowledge base. Multiple agents. Corrections instead of append-only memory.**

A small, local-first proof of concept for agents sharing canonical Markdown notes
(including an existing Obsidian vault) through a CLI or MCP stdio server.
The core has no runtime dependencies, model calls, telemetry, or vector database.

[Agent rules](docs/AGENT_RULES.md) · [Security](SECURITY.md) · [Validation](docs/VALIDATION.md)

> **Alpha / proof of concept.** The caller performs semantic synthesis. This is
> not an autonomous memory extraction engine, a Mem0 replacement, or a certified
> concurrent editor. Start with a synthetic vault, not your production notes.

## Why another component?

Shared memory has three separate problems:

1. **Access:** every client can reach the same approved notes.
2. **Lifecycle:** clients read them at the right time, including after compaction.
3. **Maintenance:** new knowledge corrects existing topics instead of accumulating
   mutually contradictory fragments.

MCP addresses access, but does not guarantee lifecycle behavior or factual quality.
This project provides a deliberately small file-first write boundary and
reproducible tests. It borrows ideas from memory systems without copying their
implementations or making an opaque database the canonical knowledge source.

```text
Agent clients + their rules / hooks
                │
         CLI or MCP stdio
                │
         Explicit note allowlist
         Read → Propose diff → Check revision → Apply
                │
       Canonical Markdown files
```

## Implemented

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
  boundary, Windows support, note creation / moves, or full backup management.
- Durable idempotency receipts: replaying an applied proposal returns a revision
  conflict; reread before retrying an uncertain operation.

## Roadmap / Development plan

This is a proposed, validation-gated roadmap, not a delivery commitment. Items
remain **planned** until implemented, tested, and reflected in the status above.

### P0 — Validate real client workflows

- Test two real agent clients against a disposable vault: startup bootstrap,
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

- Build a small, source-annotated evaluation set for Chinese, English, aliases,
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

Python 3.11+ on macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[mcp]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_mcp.py
```

Optional `uv` equivalent: `uv sync --extra mcp` and `uv run python scripts/verify_mcp.py`.

Read a bundled synthetic note:

```bash
echo '{"note":"demo.md"}' | .venv/bin/shared-memory --config examples/memory.json read
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
temporary vaults and do not touch the bundled examples or personal notes.

## Configuration

See [`examples/memory.json`](examples/memory.json). Paths for `vault` and `state_dir`
are relative to the config file; absolute paths also work. `state_dir` must be
outside the vault and **identical for all writers sharing that vault**. It stores
empty lock files only. Keep configuration and the filesystem under trusted local
control; paths are not authorization for arbitrary machine access.

`notes` is an explicit list of existing relative `.md` files, not a glob. Symlinks
are rejected. The server does not change frontmatter or impose a note template.
Use a small bootstrap list to avoid injecting the whole vault. Project roots are
absolute explicit paths; nested roots matching multiple projects are ambiguous.
Project filtering is retrieval convenience, not tenant-level authorization: every
client attached to a config can read every note allowlisted by that config.

## MCP integration

Configure the client to launch:

```text
command: /absolute/path/to/.venv/bin/shared-memory-mcp
args: ["--config", "/absolute/path/to/memory.local.json"]
```

Client-specific configuration formats differ; this is a process specification,
not a complete configuration to paste into every client. Add the suggested
[client rules](docs/AGENT_RULES.md), then verify actual tool use.

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
