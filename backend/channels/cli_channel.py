"""Generic CLI tool channel with Jinja2 template support."""

import asyncio
import json
import re
import shlex
import shutil
from typing import Any

from backend.channels.base import AbstractChannel, ChannelResult
from backend.channels.registry import register_channel

_TEMPLATE_RE = re.compile(r"\{\{(\w+)\}\}")


def _render_template(value: str, context: dict[str, Any]) -> str:
    """Simple {{key}} template rendering."""
    return _TEMPLATE_RE.sub(lambda m: str(context.get(m.group(1), m.group(0))), value)


@register_channel
class CLIChannel(AbstractChannel):
    """Collect data by running an arbitrary CLI tool."""

    channel_type = "cli"

    async def collect(
        self, config: dict[str, Any], parameters: dict[str, Any]
    ) -> ChannelResult:
        binary: str = config.get("binary", "")
        command_template: list[str] = config.get("command", [])
        output_format: str = config.get("output_format", "json")
        timeout: int = config.get("timeout", 60)
        env_vars: dict[str, str] = config.get("env", {})

        context = {**config.get("defaults", {}), **parameters}
        rendered_cmd = [
            _render_template(part, context) for part in command_template
        ]
        full_cmd = [binary, *rendered_cmd]

        import os
        env = {**os.environ, **env_vars}

        try:
            proc = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            return ChannelResult.fail(f"CLI command timed out after {timeout}s")
        except FileNotFoundError:
            return ChannelResult.fail(f"Binary not found: {binary!r}")
        except Exception as exc:
            return ChannelResult.fail(f"CLI execution failed: {exc}")

        if proc.returncode != 0:
            return ChannelResult.fail(
                f"CLI exited with code {proc.returncode}: {stderr.decode()[:500]}"
            )

        output = stdout.decode()
        if output_format == "json":
            try:
                data = json.loads(output)
                items = data if isinstance(data, list) else [data]
            except json.JSONDecodeError as exc:
                return ChannelResult.fail(f"Failed to parse CLI JSON output: {exc}")
        else:
            # Plain text: each line is a record
            items = [{"line": line} for line in output.splitlines() if line.strip()]

        return ChannelResult.ok(items, binary=binary, command=full_cmd)

    async def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if not config.get("binary"):
            errors.append("'binary' is required for cli channel")
        if not config.get("command"):
            errors.append("'command' is required for cli channel")
        return errors

    async def health_check(self) -> bool:
        return True  # Binary existence checked per-collect
