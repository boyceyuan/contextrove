# Contributing

This project intentionally starts small. Changes should include synthetic tests,
clear evidence of what was validated, and honest limits on what was not.
Its purpose is portable personal and project context; Markdown is an implementation
format. Avoid framing it solely as a note-taking application.

## Pull request workflow

Make each cohesive change on a branch from the latest `master`, open a pull
request, review its diff and checks, then merge it into `master`. Avoid direct
pushes to `master`; keep separate changes in separate PRs. Include the reason for
the change, synthetic verification, and remaining validation limits in the PR.

```bash
python3 -m pip install -e '.[mcp]'
python3 -m unittest discover -s tests -v
python3 scripts/verify_mcp.py
```

Please do not commit real vaults, client configuration, personal context, API
keys, transcripts, machine-specific paths or test-generated state. Use generic
fixtures; keep source/decision/evidence distinctions intact in documentation.

Before adding automatic extraction, indexing or a third-party backend, explain
canonical-store ownership, conflict handling, outbound data, dependency/license
implications, and deletion behavior. Do not turn a disposable retrieval index into
a competing source of current truth. Do not claim agent-level integration from
protocol tests alone.
