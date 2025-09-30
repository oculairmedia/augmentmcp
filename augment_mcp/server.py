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
from fastmcp.exceptions import ResourceError, ToolError
from fastmcp.prompts import Message

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


def _expand_workspace(path: str) -> Path:
    """Expand and validate a workspace path string."""

    return Path(path).expanduser()


async def _read_text_file(path: Path) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, path.read_text, "utf-8", "replace")


def _extract_command_metadata(text: str) -> dict[str, Any]:
    """Parse simple front matter from a command file if present."""

    meta: dict[str, Any] = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta

    for line in lines[1:]:
        stripped = line.strip()
        if stripped == "---":  # End of front matter
            break
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta


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


@mcp.resource(
    "augment://workspace/{workspace_path}/settings",
    name="Augment Workspace Settings",
    description="Current Augment configuration and tool permissions for a workspace",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_workspace_settings(workspace_path: str) -> dict[str, Any]:
    """Expose Augment settings for the provided workspace."""

    workspace = _expand_workspace(workspace_path)
    settings_path = workspace / ".augment" / "settings.json"

    if not settings_path.exists():
        return {
            "workspace": str(workspace),
            "settings_file": str(settings_path),
            "exists": False,
        }

    try:
        raw = await _read_text_file(settings_path)
        data = json.loads(raw or "{}")
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - rare IO errors
        raise ResourceError(f"Failed to read workspace settings: {exc}") from exc

    return {
        "workspace": str(workspace),
        "settings_file": str(settings_path),
        "exists": True,
        "tool_permissions": data.get("tool-permissions", []),
        "settings": data,
    }


async def _collect_command_entries(root: Path, scope: str) -> list[dict[str, Any]]:
    if not root.exists():
        return []

    entries: list[dict[str, Any]] = []
    for cmd_file in sorted(root.rglob("*.md")):
        if not cmd_file.is_file():
            continue
        try:
            raw = await _read_text_file(cmd_file)
        except OSError:  # pragma: no cover - filesystem access error
            continue
        meta = _extract_command_metadata(raw)
        namespace = None
        parent = cmd_file.parent
        if parent != root:
            namespace = parent.relative_to(root).as_posix()
        entries.append(
            {
                "name": cmd_file.stem,
                "path": str(cmd_file),
                "scope": scope,
                "namespace": namespace,
                "description": meta.get("description"),
                "tags": meta.get("tags"),
            }
        )

    return entries


@mcp.resource(
    "augment://workspace/{workspace_path}/commands",
    name="Augment Custom Commands",
    description="List available Augment custom command definitions",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_custom_commands(workspace_path: str) -> dict[str, Any]:
    """Enumerate workspace and user-level Augment command files."""

    workspace = _expand_workspace(workspace_path)
    workspace_commands = await _collect_command_entries(
        workspace / ".augment" / "commands", scope="workspace"
    )
    user_commands = await _collect_command_entries(
        Path.home() / ".augment" / "commands", scope="user"
    )

    commands = workspace_commands + user_commands

    return {
        "workspace": str(workspace),
        "total": len(commands),
        "commands": commands,
    }


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


@mcp.prompt(
    name="security_review",
    description="Generate a comprehensive security review request for a file",
    tags={"security", "review", "code-quality"},
)
def security_review_prompt(
    file_path: str,
    focus_areas: str = "all",
    severity_threshold: str = "medium",
) -> list[dict[str, Any]]:
    """Prompt template for requesting a security-focused review."""

    focus_map = {
        "all": [
            "SQL injection and parameterized queries",
            "Cross-site scripting and output encoding",
            "Authentication and authorization controls",
            "Cryptography usage and key management",
            "Input validation and sanitisation",
            "Error handling and information disclosure",
            "Secure coding best practices",
        ],
        "sql-injection": ["SQL injection vulnerabilities", "Use of parameterized queries"],
        "xss": ["Cross-site scripting", "Output encoding of untrusted data"],
        "auth": ["Authentication checks", "Authorization logic", "Session management"],
        "crypto": ["Cryptographic primitives", "Key management", "Secure randomness"],
    }

    areas = focus_map.get(focus_areas, focus_map["all"])
    bullet_list = "\n".join(f"- {item}" for item in areas)

    content = f"""Please perform a comprehensive security review of `{file_path}`.

Focus on the following areas:
{bullet_list}

Report findings with severity **{severity_threshold}** or higher. For each issue found, include:
1. Severity (low/medium/high/critical)
2. Specific code locations or line numbers
3. Description of the vulnerability
4. Potential impact
5. Recommended remediation steps or safer code examples

Use the workspace context to identify related risks in neighbouring modules and ensure recommendations align with existing project patterns."""

    return [Message(role="user", content=content)]


@mcp.prompt(
    name="refactor_code",
    description="Request a refactoring plan with targeted improvement goals",
    tags={"refactoring", "code-quality"},
)
def refactor_code_prompt(
    file_path: str,
    goals: list[str] | None = None,
    preserve_behavior: bool = True,
) -> list[dict[str, Any]]:
    """Prompt template for structured refactoring guidance."""

    goal_catalog = {
        "readability": "Improve clarity and naming consistency",
        "performance": "Optimise hot paths and resource usage",
        "testability": "Enable easier unit testing with seams and dependency injection",
        "maintainability": "Simplify structure to reduce long-term maintenance cost",
        "modularity": "Increase separation of concerns and reuse",
    }

    selected = goals or ["readability", "maintainability"]
    goals_text = "\n".join(
        f"- {goal_catalog.get(goal, goal)}" for goal in selected
    )

    behavior_text = (
        "Preserve the current observable behaviour unless changes are required for the goals."
        if preserve_behavior
        else "Minor behaviour adjustments are acceptable if they significantly improve the goals."
    )

    content = f"""Please review `{file_path}` and propose a refactoring plan.

Refactoring goals:
{goals_text}

{behavior_text}

For each suggested change, include:
1. Summary of the problem
2. Recommended approach with rationale
3. Code snippets or pseudocode illustrating the change
4. Potential risks or regression areas
5. Suggested follow-up tasks (tests, docs, monitoring)

Reference similar patterns in the workspace to keep the refactor aligned with existing conventions."""

    return [Message(role="user", content=content)]


@mcp.prompt(
    name="generate_tests",
    description="Request targeted automated tests for recent changes",
    tags={"testing", "quality"},
)
def generate_tests_prompt(
    file_path: str,
    test_style: str = "unit",
    frameworks: str | None = None,
) -> list[dict[str, Any]]:
    """Prompt template for generating tests covering a file or module."""

    style_notes = {
        "unit": "Focus on fast, isolated unit tests that cover critical branches and edge cases.",
        "integration": "Create integration tests exercising interactions between major components.",
        "end-to-end": "Outline end-to-end scenarios validating real user flows.",
    }

    style_text = style_notes.get(test_style, style_notes["unit"])
    frameworks_note = (
        f"Preferred frameworks or tools: {frameworks}."
        if frameworks
        else "Use the predominant testing frameworks already present in the workspace."
    )

    content = f"""Generate a suite of {test_style} tests for `{file_path}`.

{style_text}
{frameworks_note}

The output should include:
1. Test strategy overview and key scenarios
2. Concrete test cases with expected outcomes
3. Example code snippets for each test case
4. Suggestions for fixtures, mocks, or test data
5. Gaps in existing coverage and how to address them

Leverage project conventions and existing helpers when proposing the tests."""

    return [Message(role="user", content=content)]


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
