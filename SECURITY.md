# Security and privacy

This alpha is for a trusted local user on macOS/Linux. It is not a sandbox for
malicious local processes, multiple tenants, untrusted filesystem mutations, or
network clients. Do not expose it through unauthenticated HTTP.

- Keep the config, vault, parent directories and state directory under trusted
  control. The allowlist covers notes only. A project scope is not an ACL.
- Symlinks are rejected, but parent-directory check/open races, hardlinks and
  arbitrary privileged filesystem changes are not fully contained. Cooperating
  processes must use the same state directory for their locks to coordinate.
- The final external-edit check is not filesystem compare-and-swap. External
  editors can still race a replacement. No recovery snapshots are retained.
- The core makes no network or model calls. Installing optional dependencies can
  download packages. Your agent can transmit retrieved content to its provider.
- No automatic approval, fact validation, evidence verification, secret detection
  or sensitivity classifier is implemented. A nonempty source string is only
  provenance supplied by the caller, not proof. Enforce policy in the client.
- Retrieved text may contain prompt injection. Treat ordinary note content as
  untrusted data, not executable instructions or permission to broaden access.
- Temporary replacement files can contain new note text. They are cleaned up
  during normal error handling, but abrupt termination may leave them in the
  vault. Review `.memory-*.tmp` before indexing or syncing; do not delete files
  you cannot attribute to this tool. Erasure from SSD blocks is not guaranteed.
- `forget` only removes an exact passage from the current file. It does not erase
  Git history, backups, model logs, client transcripts or external copies.
- The library preserves ordinary permission bits, not ACLs, xattrs or other
  extended filesystem metadata. Test in a disposable vault first.

Please report security concerns without posting real notes, tokens, home
directories or other private data in public issues. This project does not yet
offer a private disclosure inbox; if no private channel is available, describe
only the general issue publicly and withhold exploit details/private material.
