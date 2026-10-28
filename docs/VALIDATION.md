# Validation and evidence boundaries

Date: 2026-10-27. All local runs used synthetic context, not personal notes or
production client configuration. Automated tests clean up their temporary vaults;
model-session acceptance used a separate temporary workspace. No global
OpenCode/Codex/Claude Code/WorkBuddy settings were changed.

## Core: 21 automated tests passed

Locally exercised on macOS arm64, Python 3.15.1 and Python 3.13.18. Reproduce from an installed
checkout with:

```bash
python -m unittest discover -s tests -v
```

The suite verifies:

- A preview does not write; applying changes the old passage in place, once.
- Unrelated content, CRLF bytes and ordinary permission bits are preserved.
- Stale revisions and repeated application are rejected, without appending.
- Independent processes observe updates, and two competing gateway writers have
  exactly one successful write and one `VERSION_CONFLICT`.
- A detected external edit invalidates a proposal and is visible to fresh search.
- Repeated/empty replacement targets, missing provenance and changed proposal
  arguments are rejected.
- Absolute/traversal/nonallowlisted paths, symlink files and symlink parents are
  rejected; oversized and non-UTF-8 notes are rejected.
- Project boundaries, unknown and ambiguous matches behave explicitly.
- Forget removes an exact passage and it is no longer returned by live search;
  state retains empty locks only, not old note bodies.
- A failure before replacement leaves the original file; a failure after
  replacement reports `WRITE_UNCERTAIN` rather than false success.
- An injected external change before the last check is detected and preserved.
- A state directory inside the vault is rejected.
- Workspace initialization creates separate personal/project context templates,
  portable relative vault paths, an explicit project mapping when requested,
  owner-only POSIX permissions, and client-specific MCP setup data using the active
  Python environment. It refuses existing targets without modifying them.

This does NOT prove safety in the remaining check-to-replace race against an
arbitrary editor, malicious local filesystem changes, disk power loss, or every
filesystem. Tests of injected errors are not exhaustive crash certification.

## MCP: two independent stdio sessions passed

Python 3.13.18, official `mcp==1.30.0`; server adapter uses the SDK 1.x FastMCP
module, so the optional dependency is intentionally bounded to `<2`.

```bash
python scripts/verify_mcp.py
```

Observed output:

```json
{
  "protocol": "MCP stdio",
  "sessions": 2,
  "tools": 6,
  "A_write_B_read": "PASS",
  "B_correct_A_refresh": "PASS",
  "stale_write_rejected": "PASS",
  "path_escape_rejected": "PASS"
}
```

The two SDK clients launched separate server processes sharing one config and
state directory. This establishes protocol-level access and update visibility,
not actual model behavior in any named agent client. Client lifecycle/compaction
behavior, model factual accuracy and autonomous synthesis remain unverified.

## Real client model sessions: cross-client correction passed

On macOS, OpenCode V2 CLI 2.0.32 and Codex CLI 0.164.0 used separate model
sessions and MCP processes against the same initialized synthetic workspace.
The project-local OpenCode V2 `mcp.servers` configuration and Codex invocation
overrides pointed to one machine-local config; no production vault or global MCP
settings were modified.

1. OpenCode model called `bootstrap` and `read` via MCP and identified the
   synthetic marker `cobalt-otter-41` with `Status: pending.`
2. Codex model called `bootstrap`, `read`, `propose_update`, inspected the exact
   diff, then called `apply_update`; it replaced `Status: pending.` with
   `Status: verified.` without changing the marker.
3. A **fresh** OpenCode model session called MCP `read` and returned the marker
   with `Status: verified.` (revision changed from `758b8596…` to `94c1dc66…`).

The first Codex run was blocked by its MCP approval policy (`never`); a second
isolated run with `--approve-for-me` succeeded. This is genuine model tool use,
not a protocol-only simulation. The prompts explicitly requested tool use;
autonomous startup retrieval, project switching, stale-write reconciliation by
the model, compaction recovery, other clients and long-term reliability remain
unverified. Approval behavior depends on the user's Codex policy.

## Optional Basic Memory compatibility probe

This is a separate experiment, not a dependency or implementation copied into
the gateway. Pinned release: `basic-memory==0.24.1`, Python 3.13.18, macOS arm64.
Run with `uv` from the project root:

```bash
uv run --with basic-memory==0.24.1 python scripts/probe_basic_memory.py
```

The script isolates HOME/config/vault, uses synthetic English/Chinese notes,
removes credential-like environment variables, disables configured Logfire,
and sets Hugging Face offline flags. These configuration choices are **not** a
network-capture proof of zero outbound requests from every dependency.

Final probe uses Basic Memory's official `run_with_cleanup`, which drains queued
file materialization and background work before closing the event loop.
Observed in the corrected local run:

| Observation | Result |
|---|---|
| Existing preformatted note imported byte-for-byte | No: permalink/format changed |
| Plain Markdown imported byte-for-byte | No: frontmatter added, formatting changed |
| Fresh tool process sees the accepted correction | Yes: `Status: verified` |
| Old checksum update rejected | Yes: `NOTE_REVISION_CONFLICT` |
| Disk after official short-process cleanup matches accepted content | Yes: old status replaced by `Status: verified` |
| Direct external file edit visible in next tool read without explicit sync | No |
| External file contents preserved after that read | Yes, at the sampled moment |

An earlier probe used a raw async call and exited without this official cleanup;
it observed accepted content ahead of disk. That was an incomplete invocation,
not evidence of a Basic Memory durability bug. The corrected probe verifies both
tool-level replacement and disk-level replacement. Its direct external edit also
uses an asserted, genuinely different sentinel, avoiding a no-op test.

Formatting changes and the unsynchronized external edit are reasons not to plug
this configuration straight into a byte-preserving file-first gateway. They are
**not** evidence that Basic Memory cannot synchronize files, loses data generally,
or fails under its recommended long-running deployment. Watcher convergence,
explicit sync, recovery, timing, alternate settings and semantic retrieval were
not certified here.

## CI and future acceptance

The repository includes a macOS/Linux Python 3.11/3.13 CI matrix, but local runs
do not prove that remote GitHub Actions has run. Once published, confirm CI
independently. Follow-up acceptance should use real client sessions, unique
non-sensitive markers, project switching and compaction recovery; remove the
markers and inspect current files afterwards.

## Quick-start CLI checks (2026-10-28)

The `demo` command uses a disposable synthetic project and workspace. It reads
`pending`, applies a revision-checked correction, and reads `verified` using a
fresh core instance; the temporary workspace is removed. This is a local-core
check, not a model session or MCP protocol check.

The MCP `setup` tests cover registering OpenCode globally and Codex through
their CLI argument shapes. Client commands are mocked and do not establish
connection or model behavior.

## Skill-first validation (2026-10-28)

The implementation tests cover shared personal context across projects,
idempotent installation, refusal to overwrite a different Skill, safe handling
of conflicting project names and overlapping roots, atomic config publication,
retry after injected failure, shell-quoted installation paths, live CLI actions,
and stale revision rejection. They use synthetic temporary workspaces.

The completed local suite has **40 passing tests** on macOS arm64 / Python
3.13.18. It also verifies that propose/apply reject a missing `--new` with a
structured `INVALID_REQUEST`, leave the note unchanged, and allow explicit forget.

`scripts/verify_skills.py --codex <path> --opencode <path>` runs in temporary
HOME/XDG/CODEX directories, with no provider credentials and no model calls. It
uses Codex 0.165.0's app-server `skills/list` and OpenCode 2.2.0's isolated API
skill list. The observed results were:

| Client | Discovery result |
|---|---|
| Codex 0.165.0 | Pass: `shared-context` returned enabled with the installed path |
| OpenCode 2.2.0, documented global `~/.agents/skills` | Not discovered by isolated API query |
| OpenCode 2.2.0, documented `~/.config/opencode/skills` | Not discovered by isolated API query |
| OpenCode 2.2.0, explicit project `skills` source | Not discovered by isolated API query |

The 2026-10-28 rerun confirmed that each OpenCode query returned the requested
synthetic project location and that `/api/config` loaded the explicit `skills`
source. Its Skill list was still empty. This rules out querying the wrong
location or silently missing that config in this probe; it does not establish
the cause of the missing registration or certify the TUI behavior.

The OpenCode probe is a negative discovery observation in this CLI/API setup,
not proof its TUI cannot load the compatibility path. Therefore the README's
shared-directory claim is documented as a client-version caveat rather than
passing cross-client acceptance. Neither client was asked to run Skill instructions or invoke the
CLI through a model. Actual Skill-guided execution, automatic task-start reads,
project switching, edits and compaction recovery remain unverified.

## Distribution checks (2026-10-28)

Local checks passed with Ruff 0.17.3 and build 1.6.1:

```bash
python -m ruff check .
python -m build
python scripts/verify_distribution.py dist/*.whl
python scripts/verify_mcp.py
```

The build creates an sdist, then builds the wheel from that sdist. The packaged
Skill is included in both; the sdist also includes the architecture SVGs linked
by the READMEs. The distribution check installs the wheel without dependencies
in a fresh venv outside the checkout, removes inherited Python import overrides,
and runs Skill setup with a quoted workspace path. It exercises bootstrap, read,
non-mutating preview, apply, stale-revision rejection, search, forget and the demo.
It uses disposable synthetic context and never installs into a global Skill path.

The two-session MCP protocol check passed again after these changes. These
checks establish package contents and local CLI/protocol behavior, not Skill
execution by a model. CI includes lint/build/wheel checks in addition to the
macOS/Linux Python 3.11/3.13 test matrix; remote results must be checked separately.
