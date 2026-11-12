# On-demand memory assembly reference

This reference extracts the request-assembly logic from a local OpenCode V2
Obsidian integration without shipping personal notes, absolute paths, aliases,
credentials, or the local append/delete tools. It is **not an installed plugin**
or a replacement for ContextRove's allowlisted, revision-checked writer.

The caller supplies `vault`, approved `coreNotes`, `indexNote`, the actual session
`directory`, and an asynchronous `discoverEntries(directory)` callback returning
approved candidate note paths. Do not expose unapproved notes. Paths and note
contents are user data; only explicitly approved core notes are policy sources.

In an OpenCode V2 plugin, call `injectMemoryContext(event, options)` from the
`context` and `generate` session hooks, resolving the session directory for each
request. `assembleMemoryContext(options)` also supports explicit context reads.
See the official [plugin API](https://opencode.ai/v2/docs/build/plugins/server).
No plugin registration, dependency installation, or global configuration is
performed by these files.

Properties: fresh disk reads; identical current rules reused; missing rules
returned in full; candidate bodies not loaded; bounded navigation with explicit
omissions; read failures surfaced; repeat injection replaces only its own block.
No session skip state, automatic semantic consolidation, background scanning,
or model calls. Full-text substring deduplication is not semantic equivalence;
changed rules may coexist with stale instructions from another source, so the
caller must handle conflicting policy sources.

Run deterministic synthetic tests with Node.js 18+:

```sh
node --test integrations/opencode/memory-context.test.mjs
```

These tests do not validate actual OpenCode hook dispatch, model retrieval,
cross-client correction behavior, or real compaction recovery. The local
Obsidian adapter remains separately installed; this is a configurable reference,
not a byte-for-byte copy or a claim of deployment parity.
