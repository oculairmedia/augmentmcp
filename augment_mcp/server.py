"""FastMCP server exposing Augment review capability via Auggie CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import Awaitable, Sequence
from pathlib import Path
from typing import Any, Iterable, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from .auggie import (
    AuggieAbortedError,
    AuggieCommandError,
    AuggieError,
    AuggieNotInstalledError,
    AuggieTimeoutError,
    AuggieRunResult,
    run_auggie,
    run_auggie_command,
)

LOGGER = logging.getLogger(__name__)

INSTRUCTIONS = """\
Call the `augment_review` tool to delegate reviews to Augment's Auggie CLI.
Provide the instruction you want Auggie to follow and optional context such as
raw text or file paths. The tool streams context to Auggie and returns its
textual response. Set AUGMENT_SESSION_AUTH in the environment before running the
server or pass `session_token` per call.
"""

mcp = FastMCP(name="augment-fastmcp", instructions=INSTRUCTIONS)


async def _load_paths(paths: Iterable[str]) -> str:
    """Concatenate file contents with headers for Auggie context."""

    chunks: list[str] = []
    loop = asyncio.get_running_loop()
    for raw_path in paths:
        path = Path(raw_path).expanduser()
        if not path.is_file():
            raise ToolError(f"Path is not a readable file: {raw_path}")

        try:
            text = await loop.run_in_executor(
                None, lambda p=path: p.read_text(encoding="utf-8", errors="replace")
            )
        except OSError as exc:  # pragma: no cover - filesystem issues
            raise ToolError(f"Failed to read {raw_path}: {exc}") from exc

        chunks.append(f"# File: {raw_path}\n\n{text}")

    return "\n\n".join(chunks)


async def _execute_with_error_handling(
    call: Awaitable[AuggieRunResult],
    *,
    workspace_root: str | None = None,
) -> str:
    """Run an Auggie coroutine and normalize errors into ToolError."""

    try:
        result = await call
    except AuggieNotInstalledError as exc:
        raise ToolError(str(exc)) from exc
    except AuggieTimeoutError as exc:
        raise ToolError(str(exc)) from exc
    except AuggieAbortedError as exc:
        raise ToolError(str(exc)) from exc
    except AuggieCommandError as exc:
        message = [str(exc)]
        if workspace_root:
            message.append(f"Workspace: {workspace_root}")
        stderr = exc.result.stderr.strip()
        stdout = exc.result.stdout.strip()
        if stderr:
            message.append(f"stderr:\n{stderr}")
        if stdout:
            message.append(f"stdout:\n{stdout}")
        raise ToolError("\n\n".join(message)) from exc
    except AuggieError as exc:
        raise ToolError(str(exc)) from exc

    if result.stderr.strip():
        LOGGER.warning("Auggie stderr: %s", result.stderr.strip())

    output = result.stdout.strip()
    return output or "Auggie produced no output"


@mcp.tool(name="augment_review", description="Use Auggie to review artifacts with Augment context engine")
async def augment_review(
    instruction: str,
    context: str | None = None,
    paths: list[str] | None = None,
    workspace_root: str | None = None,
    model: str | None = None,
    compact: bool | None = None,
    github_api_token: str | None = None,
    timeout_ms: int | None = None,
    extra_args: list[str] | None = None,
    binary_path: str | None = None,
    session_token: str | None = None,
) -> str:
    """Invoke Auggie CLI with the provided instruction and context."""

    path_context = ""
    if paths:
        path_context = await _load_paths(paths)

    combined_context_parts = [part for part in (path_context, context) if part]
    combined_context = "\n\n".join(combined_context_parts) if combined_context_parts else None

    timeout_seconds = timeout_ms / 1000 if timeout_ms is not None else None

    return await _execute_with_error_handling(
        run_auggie(
            instruction=instruction,
            input_text=combined_context,
            workspace_root=workspace_root,
            model=model,
            compact=compact,
            github_api_token=github_api_token,
            extra_args=extra_args,
            timeout_seconds=timeout_seconds,
            session_token=session_token,
            binary_path=binary_path,
        ),
        workspace_root=workspace_root,
    )


@mcp.tool(
    name="augment_configure",
    description="Configure Augment tool permissions for a workspace",
)
async def augment_configure(
    workspace_root: str,
    permissions: Any,
    scope: Literal["user", "project"] = "project",
) -> str:
    """Write Augment permission configuration to the appropriate settings file."""

    if scope not in {"user", "project"}:
        raise ToolError("scope must be either 'user' or 'project'")

    if scope == "project":
        settings_root = Path(workspace_root).expanduser()
        if not settings_root.exists():
            raise ToolError(f"Workspace root does not exist: {workspace_root}")
        settings_path = settings_root / ".augment" / "settings.json"
    else:
        settings_path = Path.home() / ".augment" / "settings.json"

    settings_path.parent.mkdir(parents=True, exist_ok=True)

    config = {"tool-permissions": permissions}

    try:
        settings_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem errors
        raise ToolError(f"Failed to write settings: {exc}") from exc

    return f"Configured tool permissions at {settings_path}"


@mcp.tool(
    name="augment_custom_command",
    description="Execute a custom Auggie command for reusable workflows",
)
async def augment_custom_command(
    command_name: str,
    arguments: Sequence[str] | str | None = None,
    workspace_root: str | None = None,
    timeout_ms: int | None = None,
    binary_path: str | None = None,
    session_token: str | None = None,
) -> str:
    """Run a custom Auggie command and return its output."""

    arg_list: list[str] = ["command", command_name]

    if arguments:
        if isinstance(arguments, str):
            arg_list.append(arguments)
        else:
            arg_list.extend(arguments)

    if workspace_root:
        arg_list.extend(["--workspace-root", workspace_root])

    timeout_seconds = timeout_ms / 1000 if timeout_ms is not None else None

    return await _execute_with_error_handling(
        run_auggie_command(
            args=arg_list,
            timeout_seconds=timeout_seconds,
            session_token=session_token,
            binary_path=binary_path,
        ),
        workspace_root=workspace_root,
    )


@mcp.tool(
    name="augment_list_commands",
    description="List available Auggie custom commands",
)
async def augment_list_commands(
    workspace_root: str | None = None,
    timeout_ms: int | None = None,
    binary_path: str | None = None,
    session_token: str | None = None,
) -> str:
    """List registered Auggie slash commands."""

    args = ["command", "list"]
    if workspace_root:
        args.extend(["--workspace-root", workspace_root])

    timeout_seconds = timeout_ms / 1000 if timeout_ms is not None else None

    return await _execute_with_error_handling(
        run_auggie_command(
            args=args,
            timeout_seconds=timeout_seconds,
            session_token=session_token,
            binary_path=binary_path,
        ),
        workspace_root=workspace_root,
    )


def main() -> None:
    """Entrypoint for running the FastMCP server over HTTP transport."""

    host = os.environ.get("AUGMENT_MCP_HOST", "127.0.0.1")
    port_raw = os.environ.get("AUGMENT_MCP_PORT", "8000")
    try:
        port = int(port_raw)
    except ValueError as exc:  # pragma: no cover - env misconfiguration
        raise SystemExit(f"Invalid AUGMENT_MCP_PORT: {port_raw}") from exc

    log_level = os.environ.get("AUGMENT_MCP_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=log_level)

    LOGGER.info("Starting Augment FastMCP server on http://%s:%s", host, port)
    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    main()
