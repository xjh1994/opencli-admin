"""End-to-end smoke for external_http processor against the live stub.

Starts examples/external_http/stub.py in a subprocess, waits for it to
listen, then drives the actual ExternalProcessor.process() against it.
Asserts the contract works against a real HTTP server, not just mocks.

Run:
    uv run python examples/external_http/smoke.py

Exit code 0 if all enrichments parse correctly.
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.processors.external_processor import ExternalProcessor  # noqa: E402


def wait_for_port(host: str, port: int, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"stub did not come up on {host}:{port} within {timeout}s")


async def drive() -> None:
    records = [
        SimpleNamespace(normalized_data={"title": "Hello World", "content": "Body 1"}),
        SimpleNamespace(normalized_data={"title": "Second item", "content": "Body 2"}),
    ]
    proc = ExternalProcessor()
    result = await proc.process(
        records,
        "Summarize: {{title}} :: {{content}}",
        {
            "endpoint": "http://127.0.0.1:8088/process",
            "agent_id": "smoke-tagger",
            "timeout": 5,
        },
    )
    assert result.success, f"processor reported failure: {result.error}"
    assert len(result.enrichments) == 2, result.enrichments
    for i, enr in enumerate(result.enrichments):
        assert "error" not in enr, f"record {i} returned error: {enr}"
        assert enr["echo_agent_id"] == "smoke-tagger"
        assert "Stub processed" in enr["summary"]
        print(
            f"  [{i}] tags={enr['tags']} summary={enr['summary']!r} "
            f"prompt_chars={enr['prompt_chars']}"
        )


def main() -> int:
    stub_path = Path(__file__).with_name("stub.py")
    stub = subprocess.Popen(
        [sys.executable, str(stub_path)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_port("127.0.0.1", 8088)
        print("stub listening on 127.0.0.1:8088")
        asyncio.run(drive())
        print("smoke OK")
        return 0
    finally:
        stub.terminate()
        try:
            stub.wait(timeout=2)
        except subprocess.TimeoutExpired:
            stub.kill()


if __name__ == "__main__":
    sys.exit(main())
