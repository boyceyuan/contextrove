"""Explicitly allowlisted Markdown access and cooperative POSIX writer locking.

The caller supplies the semantic edit; this module never invents facts. A lock
coordinates gateway writers only, not arbitrary editors or hostile local users.
"""

from __future__ import annotations

import difflib
import fcntl
import hashlib
import json
import os
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath


class MemoryError(Exception):
    """A stable, machine-readable application error."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def revision(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Memory:
    def __init__(self, config_path: str | Path):
        config_path = Path(config_path).resolve(strict=True)
        config = json.loads(config_path.read_text(encoding="utf-8"))
        base = config_path.parent
        self.vault = (base / config["vault"]).resolve(strict=True)
        self.state = (base / config["state_dir"]).resolve()
        if not self.vault.is_dir() or self.state == self.vault or self.vault in self.state.parents:
            raise MemoryError("INVALID_CONFIG", "State directory must be outside the vault")
        allowed = config.get("notes", [])
        if not allowed or not all(isinstance(n, str) for n in allowed):
            raise MemoryError("INVALID_CONFIG", "An explicit nonempty notes allowlist is required")
        self.notes = frozenset(allowed)
        for note in self.notes:
            self._validate_name(note)
        self.bootstrap_notes = config.get("bootstrap", [])
        self.projects = config.get("projects", {})
        self.max_bytes = config.get("max_bytes", 262144)
        if not isinstance(self.max_bytes, int) or not 1 <= self.max_bytes <= 1048576:
            raise MemoryError("INVALID_CONFIG", "max_bytes must be between 1 and 1048576")
        if not set(self.bootstrap_notes) <= self.notes:
            raise MemoryError("INVALID_CONFIG", "Bootstrap notes must be allowlisted")
        for project in self.projects.values():
            if not set(project["notes"]) <= self.notes:
                raise MemoryError("INVALID_CONFIG", "Project notes must be allowlisted")
        # State contains locks only, never note bodies, proposals, or history.
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._identity = revision(str(self.vault).encode())

    @staticmethod
    def _validate_name(note: str) -> None:
        p = PurePosixPath(note)
        if (not note or p.is_absolute() or ".." in p.parts or "\\" in note
                or str(p) != note or p.suffix != ".md"):
            raise MemoryError("OUT_OF_SCOPE", "Use an exact allowlisted relative .md path")

    def _path(self, note: str) -> Path:
        self._validate_name(note)
        if note not in self.notes:
            raise MemoryError("OUT_OF_SCOPE", "Note is not allowlisted")
        path = self.vault / note
        # Reject all symlink components, even links pointing back into the vault.
        current = self.vault
        for part in PurePosixPath(note).parts:
            current = current / part
            if current.is_symlink():
                raise MemoryError("OUT_OF_SCOPE", "Symlink notes and directories are not supported")
        if self.vault not in path.resolve().parents:
            raise MemoryError("OUT_OF_SCOPE", "Note escapes the vault")
        return path

    def _bytes(self, note: str) -> bytes:
        path = self._path(note)
        try:
            # O_NOFOLLOW also protects the final component between check and open.
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError as exc:
            raise MemoryError("NOT_FOUND", "Note does not exist") from exc
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise MemoryError("OUT_OF_SCOPE", "Only regular files are supported")
            data = stream.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise MemoryError("TOO_LARGE", "Note exceeds max_bytes")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MemoryError("INVALID_ENCODING", "Note must be UTF-8") from exc
        return data

    def read(self, note: str) -> dict:
        data = self._bytes(note)
        return {"note": note, "revision": revision(data), "content": data.decode("utf-8")}

    @contextmanager
    def _lock(self, note: str):
        self._path(note)
        # All processes for the same vault MUST use the same state_dir.
        key = revision(f"{self._identity}:{note}".encode())
        with (self.state / f"{key}.lock").open("a+b") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _edit(self, note: str, expected_revision: str, old: str, new: str,
              reason: str, source: str) -> tuple[bytes, bytes]:
        if not reason.strip() or not source.strip():
            raise MemoryError("SOURCE_REQUIRED", "A nonempty reason and source are required")
        before = self._bytes(note)
        if revision(before) != expected_revision:
            raise MemoryError("VERSION_CONFLICT", "Note changed; reread and reconcile before retrying")
        if not old or old == new:
            raise MemoryError("INVALID_EDIT", "old must be nonempty and differ from new")
        old_bytes = old.encode("utf-8")
        if before.count(old_bytes) != 1:
            raise MemoryError("AMBIGUOUS_EDIT", "old must match exactly once")
        after = before.replace(old_bytes, new.encode("utf-8"), 1)
        if len(after) > self.max_bytes:
            raise MemoryError("TOO_LARGE", "Updated note exceeds max_bytes")
        return before, after

    def _proposal(self, note: str, expected_revision: str, old: str, new: str,
                  reason: str, source: str) -> dict:
        before, after = self._edit(note, expected_revision, old, new, reason, source)
        arguments = dict(note=note, expected_revision=expected_revision, old=old,
                         new=new, reason=reason, source=source)
        digest = revision(json.dumps(arguments, sort_keys=True, ensure_ascii=False).encode())
        diff = "".join(difflib.unified_diff(
            before.decode().splitlines(keepends=True), after.decode().splitlines(keepends=True),
            fromfile=note, tofile=note))
        return {"arguments": arguments, "proposal_digest": digest,
                "result_revision": revision(after), "diff": diff}

    def propose_update(self, note: str, expected_revision: str, old: str, new: str,
                       reason: str, source: str) -> dict:
        """Preview an exact replacement. No proposal text is stored on disk."""
        with self._lock(note):
            return self._proposal(note, expected_revision, old, new, reason, source)

    def apply_update(self, proposal: dict) -> dict:
        """Recheck the proposal and revision under the cooperative writer lock.

        A proposal digest binds the exact request, not user authorization or truth.
        The model/client must decide whether policy permits this change.
        """
        args = proposal["arguments"]
        note = args["note"]
        with self._lock(note):
            current = self._proposal(**args)
            if current["proposal_digest"] != proposal["proposal_digest"]:
                raise MemoryError("INVALID_PROPOSAL", "Proposal arguments have changed")
            before, after = self._edit(**args)
            path = self._path(note)
            mode = stat.S_IMODE(path.stat().st_mode) & 0o777
            fd, temporary = tempfile.mkstemp(prefix=".memory-", suffix=".tmp", dir=path.parent)
            replaced = False
            try:
                with os.fdopen(fd, "wb") as stream:
                    os.fchmod(stream.fileno(), mode)
                    stream.write(after)
                    stream.flush()
                    os.fsync(stream.fileno())
                # Best effort detection, NOT CAS against noncooperating editors.
                if self._bytes(note) != before:
                    raise MemoryError("VERSION_CONFLICT", "External edit detected before replacement")
                os.replace(temporary, path)
                replaced = True
                directory_fd = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
                if self._bytes(note) != after:
                    raise MemoryError("WRITE_UNCERTAIN", "File changed after replacement; reread")
            except OSError as exc:
                if replaced:
                    raise MemoryError("WRITE_UNCERTAIN", "Replacement occurred; verify disk state") from exc
                raise
            finally:
                Path(temporary).unlink(missing_ok=True)
        return {"note": note, "revision": revision(after), "updated": True,
                "reason": args["reason"], "source": args["source"]}

    def forget(self, note: str, expected_revision: str, text: str, reason: str,
               source: str) -> dict:
        """Remove one exact passage; no semantic search, history, or file deletion."""
        proposal = self.propose_update(note, expected_revision, text, "", reason, source)
        result = self.apply_update(proposal)
        result["limitations"] = "Git history, backups, caller transcripts and external copies are not erased"
        return result

    def search(self, query: str, project: str | None = None, limit: int = 10) -> dict:
        """Literal case-insensitive substring search; always rereads disk, no index."""
        if not query.strip() or not 1 <= limit <= 50:
            raise MemoryError("INVALID_QUERY", "Provide a nonempty query and limit 1..50")
        allowed = self.notes
        if project is not None:
            if project not in self.projects:
                raise MemoryError("UNMATCHED_PROJECT", "Unknown project")
            allowed = frozenset(self.projects[project]["notes"])
        results = []
        errors = []
        for note in sorted(allowed):
            try:
                record = self.read(note)
            except MemoryError as exc:
                errors.append({"note": note, "code": exc.code})
                continue
            for number, line in enumerate(record["content"].splitlines(), 1):
                if query.casefold() in line.casefold():
                    results.append({"note": note, "revision": record["revision"],
                                    "line": number, "snippet": line[:500]})
                    break
            if len(results) == limit:
                break
        return {"results": results, "errors": errors, "mode": "literal-substring"}

    def bootstrap(self, project_root: str) -> dict:
        root = Path(project_root)
        if not root.is_absolute():
            raise MemoryError("INVALID_PROJECT_ROOT", "project_root must be absolute")
        root = root.resolve()
        matches = []
        for name, project in self.projects.items():
            for registered in project["roots"]:
                p = Path(registered)
                if not p.is_absolute():
                    raise MemoryError("INVALID_CONFIG", "Registered project roots must be absolute")
                p = p.resolve()
                if p == root or p in root.parents:
                    matches.append(name)
                    break
        status = "matched" if len(matches) == 1 else "ambiguous" if matches else "unmatched"
        entries = self.projects[matches[0]]["notes"] if len(matches) == 1 else []
        return {"status": status, "projects": matches,
                "context": [self.read(n) for n in self.bootstrap_notes], "entries": entries}
