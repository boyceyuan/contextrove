"""Small optional Basic Memory compatibility probe, using synthetic notes only.

Run inside a pinned basic-memory environment. It is NOT an exhaustive backend
certification, a client integration test, or a production-vault migration.
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def edit_worker(identifier, checksum):
    from basic_memory.cli.commands.command_utils import run_with_cleanup
    from basic_memory.mcp.tools import edit_note

    # The CLI's edit-note command currently does not expose expected_checksum,
    # so exercise the underlying tool function in a fresh process.
    try:
        result = run_with_cleanup(edit_note(
            identifier=identifier, project="probe", operation="find_replace",
            find_text="pending", content="verified", expected_checksum=checksum,
            output_format="json",
        ))
        print(json.dumps({"ok": True, "result": result}, default=str))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))


def main():
    with tempfile.TemporaryDirectory(prefix="basic-memory-probe-") as temporary:
        root = Path(temporary)
        vault = root / "vault"
        vault.mkdir()
        (root / "home").mkdir()
        note = vault / "decision.md"
        original = b"---\ntitle: Decision\ntype: note\nembed: false\n---\n# Decision\n\nStatus: pending\n"
        note.write_bytes(original)
        plain = vault / "plain.md"
        plain_original = "# 原始笔记\n\n保留 [[Decision]] 链接。\n"
        plain.write_text(plain_original, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if not any(
            token in k.upper() for token in ("KEY", "TOKEN", "SECRET", "PASSWORD"))}
        env.update({
            "HOME": str(root / "home"), "BASIC_MEMORY_CONFIG_DIR": str(root / "config"),
            "BASIC_MEMORY_HOME": str(root / "default-vault"), "BASIC_MEMORY_LOGFIRE_ENABLED": "false",
            "BASIC_MEMORY_LOGFIRE_SEND_TO_LOGFIRE": "false",
            "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "DO_NOT_TRACK": "1", "LITELLM_LOCAL_MODEL_COST_MAP": "True",
        })

        def cli(*args):
            result = subprocess.run([sys.executable, "-m", "basic_memory.cli.main", *args],
                                    env=env, capture_output=True, text=True, timeout=90)
            # Some releases use basic_memory.cli.__main__, so use its installed console script.
            if result.returncode and "No module named" in result.stderr:
                result = subprocess.run([str(Path(sys.executable).parent / "basic-memory"), *args],
                                        env=env, capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError(f"Basic Memory {args[:2]} failed: {result.stderr[-3000:]} {result.stdout[-1500:]}")
            return result.stdout

        cli("project", "add", "probe", str(vault), "--default", "--local")
        imported_unchanged = note.read_bytes() == original
        plain_unchanged = plain.read_text(encoding="utf-8") == plain_original
        record = json.loads(cli("tool", "read-note", "decision.md", "--project", "probe", "--json"))
        checksum = record["checksum"]

        def worker(expected):
            result = subprocess.run([sys.executable, __file__, "--worker", "decision.md", expected],
                                    env=env, capture_output=True, text=True, timeout=90)
            if result.returncode:
                raise RuntimeError(result.stderr[-3000:])
            return json.loads(result.stdout.strip().splitlines()[-1])

        first = worker(checksum)
        if not first["ok"]:
            raise RuntimeError(first["error"])
        after = note.read_text(encoding="utf-8")
        rejected = worker(checksum)
        reread = json.loads(cli("tool", "read-note", "decision.md", "--project", "probe", "--json"))
        # A direct external edit is checked with a new process, without a daemon watcher.
        external = after.replace("Status: verified", "Status: externally-corrected").replace(
            "Status: pending", "Status: externally-corrected")
        assert external != after, "External-edit probe must actually change the file"
        note.write_text(external, encoding="utf-8")
        external_read = json.loads(cli("tool", "read-note", "decision.md", "--project", "probe", "--json"))
        report = {
            "backend": "basic-memory", "version": "0.24.1", "synthetic_only": True,
            "invocation": "tool function via official run_with_cleanup (drains materialization)",
            "preformatted_import_preserves_bytes": imported_unchanged,
            "plain_import_preserves_bytes": plain_unchanged,
            "plain_after_import": plain.read_text(encoding="utf-8"),
            "formatted_file_after_tool_update": after,
            "tool_content_after_update": reread.get("content"),
            "tool_update_result": first["result"],
            "disk_observed_replaced_not_appended": "pending" not in after and after.count("verified") == 1,
            "tool_content_observed_replaced_not_appended": "pending" not in str(reread.get("content"))
                and str(reread.get("content")).count("verified") == 1,
            "new_process_reads_update": "verified" in str(reread.get("content")),
            "stale_revision_rejected": not rejected["ok"],
            "stale_error": rejected.get("error"),
            "external_edit_visible_without_explicit_sync": "externally-corrected" in str(external_read.get("content")),
            "external_file_preserved_after_read": note.read_text(encoding="utf-8") == external,
            "before_sha256": hashlib.sha256(original).hexdigest(),
            "limitations": ["No real agent clients", "No crash/concurrent-editor certification",
                            "Disk sampled after official short-process cleanup, no long-running watcher",
                            "No explicit sync between direct external edit and next read",
                            "Plain note permits default embedding attempt; offline flags prevent model download"],
        }
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        edit_worker(sys.argv[2], sys.argv[3])
    else:
        main()
