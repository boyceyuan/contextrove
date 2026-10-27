"""Exercise two actual MCP stdio sessions against a disposable synthetic vault."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def payload(result):
    if result.structuredContent is not None:
        return result.structuredContent
    return json.loads(next(c.text for c in result.content if c.type == "text"))


async def run():
    with tempfile.TemporaryDirectory(prefix="shared-memory-mcp-") as directory:
        root = Path(directory)
        (root / "vault").mkdir()
        (root / "vault" / "decision.md").write_text("# Decision\nStatus: pending\n")
        config = root / "config.json"
        config.write_text(json.dumps({"vault": "vault", "state_dir": "state",
                                      "notes": ["decision.md"], "bootstrap": [], "projects": {}}))
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "shared_memory_gateway.server", "--config", str(config)],
            env={"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                 "PATH": os.environ.get("PATH", "")},
        )
        async with stdio_client(params) as (ra, wa), stdio_client(params) as (rb, wb):
            async with ClientSession(ra, wa) as a, ClientSession(rb, wb) as b:
                await a.initialize()
                await b.initialize()
                tools = await a.list_tools()
                assert {t.name for t in tools.tools} == {
                    "bootstrap", "search", "read", "propose_update", "apply_update", "forget"}
                initial = payload(await a.call_tool("read", {"note": "decision.md"}))
                arguments = dict(note="decision.md", expected_revision=initial["revision"],
                                 old="pending", new="verified", reason="Synthetic correction",
                                 source="Synthetic user statement")
                proposal = payload(await a.call_tool("propose_update", arguments))
                stale = payload(await b.call_tool("propose_update", dict(arguments, new="stale")))
                result = await a.call_tool("apply_update", {"proposal": proposal})
                assert not result.isError, result
                updated = payload(await b.call_tool("read", {"note": "decision.md"}))
                assert updated["content"] == "# Decision\nStatus: verified\n"
                conflict = await b.call_tool("apply_update", {"proposal": stale})
                assert conflict.isError and "VERSION_CONFLICT" in str(conflict)
                correction = payload(await b.call_tool("propose_update", dict(
                    arguments, expected_revision=updated["revision"], old="verified", new="corrected")))
                assert not (await b.call_tool("apply_update", {"proposal": correction})).isError
                assert "corrected" in payload(await a.call_tool("read", {"note": "decision.md"}))["content"]
                denied = await a.call_tool("read", {"note": "../outside.md"})
                assert denied.isError and "OUT_OF_SCOPE" in str(denied)
                print(json.dumps({
                    "protocol": "MCP stdio", "sessions": 2, "tools": len(tools.tools),
                    "A_write_B_read": "PASS", "B_correct_A_refresh": "PASS",
                    "stale_write_rejected": "PASS", "path_escape_rejected": "PASS",
                    "scope": "Synthetic vault; protocol clients, not real agent model sessions",
                }, indent=2))


if __name__ == "__main__":
    asyncio.run(run())
