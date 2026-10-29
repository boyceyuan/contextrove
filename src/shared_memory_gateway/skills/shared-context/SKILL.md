---
name: shared-context
description: Read, search, and carefully maintain this project's shared personal and project context. Use when a task needs prior user preferences or project decisions, or when a confirmed durable fact should correct an existing topic rather than be appended.
compatibility: Requires the separately installed shared-memory CLI and a configured local context workspace.
---

# Shared Context

Use the local CLI. Do not require an MCP server for this workflow.

The CLI and workspace below are absolute, shell-quoted paths on this machine.
If either is missing, report the missing path and repair the local installation
under the user's instructions. Do not substitute another project's workspace.

## Before project work

At the beginning of a task that depends on user preferences or project history,
run:

```sh
{{SHARED_MEMORY}} agent bootstrap --workspace {{WORKSPACE}} --project-root "$PWD"
```

If the result is `unmatched` or `ambiguous`, do not guess or load a different
project's context. `bootstrap` returns global personal context in `context`, and
matched project note paths in `entries`. Inspect the personal context, then read
each returned project entry explicitly, replacing the placeholder below:

```sh
{{SHARED_MEMORY}} agent read --workspace {{WORKSPACE}} --note '<entry from bootstrap>'
```

Treat the personal note as user-provided preferences and boundaries. Treat
project notes as claims with their stated evidence and status, not automatically
verified truth. Context can be stale; prefer newer direct user instructions and
current repository evidence.

## Search

Use literal search when the relevant topic is not known:

```sh
{{SHARED_MEMORY}} agent search --workspace {{WORKSPACE}} --query '<terms>' --project '<single ID from bootstrap.projects>'
```

Read a result before relying on it. Search is substring matching, not semantic
retrieval.

## Maintain context

Only persist durable information that the user explicitly stated or confirmed.
Do not store secrets, credentials, speculative inferences, transient task state,
or raw conversation transcripts. Keep personal preferences separate from project
facts. Integrate a correction into the existing topic; avoid appending a second,
contradictory status.

Before editing, read the target and record its exact `revision`. Include a concise
reason and source. Inspect the proposed diff and follow the user's existing
approval policy. If the user has already authorized this class of durable updates,
apply it without asking again; otherwise present the diff for approval. Never
claim the CLI itself verifies truth.

Preview an exact single-passage replacement:

```sh
{{SHARED_MEMORY}} agent propose --workspace {{WORKSPACE}} \
  --note '<entry from bootstrap>' --expected-revision '<revision>' \
  --old '<exact old passage>' --new '<replacement passage>' \
  --reason '<why this durable context changed>' --source '<user statement or evidence>'
```

When authorized, repeat the same arguments with `agent apply` instead of
`agent propose`. Apply rechecks the expected revision and the exact passage;
if either changed, stop, reread, and reconcile. Never blindly retry a conflict
or uncertain write. Shell-quote all substituted values safely (including embedded
quotes, dollar signs and backticks); never paste note content as shell code.
For complex multiline edits, use the JSON-on-stdin CLI described by
`shared-memory propose_update --help` and `shared-memory apply_update --help`
with `--config <workspace>/memory.local.json`, passing the full proposal object
to apply. Construct JSON and subprocess argument arrays with a script instead
of interpolating note text into a shell command.

Delete only when the user explicitly asks to forget a fact. Read the current
revision and exact passage first, then use `agent forget` with a reason and
source. Explain that this edits the live Markdown only; it cannot erase backups,
Git history, or prior conversations.

## Scope

This skill provides workflow instructions; the CLI performs local file
operations. Loading a skill is not proof that context was read: execute the
bootstrap/read commands and inspect their results. Automatic startup loading,
project switching and post-compaction recovery are client-dependent and must
not be claimed unless separately validated.
