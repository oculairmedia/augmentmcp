"""FastMCP server exposing Augment review capability via Auggie CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import time
from collections.abc import Awaitable, Sequence
from contextlib import contextmanager
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
from .telemetry import collect_auggie_history, collect_performance_metrics, record_operation

LOGGER = logging.getLogger(__name__)

INSTRUCTIONS = """\
Call the `augment_review` tool to delegate reviews to Augment's Auggie CLI.
Provide the instruction you want Auggie to follow and optional context such as
raw text or file paths. The tool streams context to Auggie and returns its
textual response. Set AUGMENT_SESSION_AUTH in the environment before running the
server or pass `session_token` per call.
"""

mcp = FastMCP(name="augment-fastmcp", instructions=INSTRUCTIONS)


@contextmanager
def _metric_scope(kind: Literal["tool", "resource", "prompt"]) -> None:
    """Record execution duration for telemetry metrics."""

    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        record_operation(kind, duration_ms)


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


async def _read_json_file(path: Path) -> dict[str, Any]:
    raw = await _read_text_file(path)
    return json.loads(raw or "{}")


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
        cleaned_key = key.strip()
        cleaned_value = value.strip()
        if cleaned_key == "tags":
            tags = [token.strip() for token in cleaned_value.split(",") if token.strip()]
            meta[cleaned_key] = tags
        else:
            meta[cleaned_key] = cleaned_value
    return meta


def _safe_relative_path(path: Path, workspace: Path) -> str:
    """Return the path relative to workspace when possible."""

    try:
        workspace_resolved = workspace.resolve()
        return path.resolve().relative_to(workspace_resolved).as_posix()
    except (ValueError, OSError):
        return str(path)


async def _gather_context_lines(
    path: Path,
    line_number: int,
    context_lines: int,
    cache: dict[Path, list[str]],
) -> dict[str, list[str]]:
    """Return surrounding context lines for a file and line number."""

    if context_lines <= 0:
        return {"before": [], "after": []}

    lines = cache.get(path)
    if lines is None:
        try:
            text = await _read_text_file(path)
        except OSError:
            cache[path] = []
            lines = []
        else:
            lines = text.splitlines()
            cache[path] = lines

    if not lines:
        return {"before": [], "after": []}

    index = max(line_number - 1, 0)
    before_start = max(index - context_lines, 0)
    before = lines[before_start:index]
    after = lines[index + 1 : index + 1 + context_lines]
    return {"before": before, "after": after}


async def _format_search_results(
    matches: list[dict[str, Any]],
    workspace: Path,
    context_lines: int,
) -> list[dict[str, Any]]:
    """Format raw search matches with relative paths and context."""

    if not matches:
        return []

    cache: dict[Path, list[str]] = {}
    workspace_resolved = workspace.resolve()
    formatted: list[dict[str, Any]] = []
    for match in matches:
        raw_path = Path(match["file"]).expanduser()
        context = await _gather_context_lines(
            raw_path, int(match["line_number"]), context_lines, cache
        )
        formatted.append(
            {
                "file": _safe_relative_path(raw_path, workspace_resolved),
                "line_number": int(match["line_number"]),
                "line_content": match["line_content"].rstrip("\n"),
                "match_context": context,
            }
        )
    return formatted


def _get_search_tool() -> str:
    """Determine which search backend is available."""

    if shutil.which("rg"):
        return "ripgrep"
    if shutil.which("grep"):
        return "grep"
    return "python"


async def _search_with_ripgrep(
    workspace: Path,
    query: str,
    max_results: int,
) -> tuple[list[dict[str, Any]], int]:
    """Search using ripgrep returning raw matches and total count."""

    cmd = ["rg", "--json", "--no-heading", query, str(workspace)]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode not in (0, 1):  # 1 => no matches
        raise ResourceError(f"ripgrep failed: {stderr.decode('utf-8', 'replace').strip()}")

    matches: list[dict[str, Any]] = []
    total_matches = 0
    for line in stdout.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if data.get("type") != "match":
            continue
        total_matches += 1
        if len(matches) < max_results:
            match_data = data["data"]
            matches.append(
                {
                    "file": match_data["path"]["text"],
                    "line_number": match_data["line_number"],
                    "line_content": match_data["lines"]["text"],
                }
            )

    return matches, total_matches


async def _search_with_grep(
    workspace: Path,
    query: str,
    max_results: int,
) -> tuple[list[dict[str, Any]], int]:
    """Search using GNU grep returning raw matches and total count."""

    cmd = [
        "grep",
        "-R",
        "-n",
        "--color=never",
        "--binary-files=without-match",
        query,
        str(workspace),
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode not in (0, 1):
        raise ResourceError(f"grep failed: {stderr.decode('utf-8', 'replace').strip()}")

    matches: list[dict[str, Any]] = []
    total_matches = 0
    for line in stdout.decode("utf-8", "replace").splitlines():
        if not line.strip() or line.startswith("Binary file"):
            continue
        parts = line.split(":", 2)
        if len(parts) < 3:
            continue
        try:
            line_number = int(parts[1])
        except ValueError:
            continue
        total_matches += 1
        if len(matches) < max_results:
            matches.append(
                {
                    "file": parts[0],
                    "line_number": line_number,
                    "line_content": parts[2],
                }
            )

    return matches, total_matches


async def _search_with_python(
    workspace: Path,
    query: str,
    max_results: int,
) -> tuple[list[dict[str, Any]], int]:
    """Fallback search implementation in pure Python."""

    matches: list[dict[str, Any]] = []
    total_matches = 0

    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = await _read_text_file(path)
        except OSError:
            continue
        for index, line in enumerate(text.splitlines(), start=1):
            if query in line:
                total_matches += 1
                if len(matches) < max_results:
                    matches.append(
                        {
                            "file": str(path),
                            "line_number": index,
                            "line_content": line,
                        }
                    )
                if total_matches > max_results and len(matches) >= max_results:
                    return matches, total_matches

    return matches, total_matches
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
    "augment://capabilities",
    name="Augment Capabilities",
    description="Discover available Augment MCP tools, resources, and prompts",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_capabilities() -> dict[str, Any]:
    """Expose high-level information about registered MCP interfaces."""

    with _metric_scope("resource"):
        tools = await mcp.get_tools()
        prompts = await mcp.get_prompts()
        resource_templates = await mcp.get_resource_templates()

        tool_entries = [
            {
                "name": name,
                "description": tool.description,
                "enabled": tool.enabled,
            }
            for name, tool in sorted(tools.items())
        ]

        prompt_entries = [
            {
                "name": name,
                "description": prompt.description,
                "tags": sorted(prompt.tags),
                "enabled": prompt.enabled,
            }
            for name, prompt in sorted(prompts.items())
        ]

        resource_entries = [
            {
                "uri": uri,
                "name": template.name,
                "description": template.description,
            }
            for uri, template in sorted(resource_templates.items())
        ]

        features = {
            "workspace_indexing": True,
            "custom_commands": True,
            "tool_permissions": True,
            "mcp_resources": True,
            "mcp_prompts": True,
            "workspace_search": True,
            "run_history": True,
            "performance_metrics": True,
        }

        supported_models = [
            "claude-sonnet-4",
            "claude-sonnet-3.5",
            "gpt-4o",
            "gpt-4o-mini",
        ]

        return {
            "tools": tool_entries,
            "prompts": prompt_entries,
            "resources": resource_entries,
            "features": features,
            "supported_models": supported_models,
        }


@mcp.resource(
    "augment://workspace/{workspace_path}/settings",
    name="Augment Workspace Settings",
    description="Current Augment configuration and tool permissions for a workspace",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_workspace_settings(workspace_path: str) -> dict[str, Any]:
    """Expose Augment settings for the provided workspace."""

    with _metric_scope("resource"):
        workspace = _expand_workspace(workspace_path)
        settings_path = workspace / ".augment" / "settings.json"

        if not settings_path.exists():
            return {
                "workspace": str(workspace),
                "settings_file": str(settings_path),
                "exists": False,
            }

        try:
            data = await _read_json_file(settings_path)
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
                "title": meta.get("title"),
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

    with _metric_scope("resource"):
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


@mcp.resource(
    "augment://workspace/{workspace_path}/tree",
    name="Augment Workspace Tree",
    description="Directory structure snapshot for the workspace",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_workspace_tree(
    workspace_path: str,
    max_depth: int | None = None,
) -> dict[str, Any]:
    """Return a truncated directory tree for the workspace."""

    with _metric_scope("resource"):
        workspace = _expand_workspace(workspace_path)
        depth = max_depth if max_depth is not None else 3
        depth = max(depth, 0)

        loop = asyncio.get_running_loop()
        try:
            tree = await loop.run_in_executor(None, _build_tree_sync, workspace, depth)
        except OSError as exc:  # pragma: no cover - permission issues
            raise ResourceError(f"Failed to walk workspace: {exc}") from exc

        return tree


@mcp.resource(
    "augment://workspace/{workspace_path}/index-status",
    name="Augment Index Status",
    description="Status information for Augment workspace indexing",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_index_status(workspace_path: str) -> dict[str, Any]:
    """Read Augment index status metadata when available."""

    with _metric_scope("resource"):
        workspace = _expand_workspace(workspace_path)
        status_path = workspace / ".augment" / "index" / "status.json"

        if not status_path.exists():
            return {
                "workspace": str(workspace),
                "status_file": str(status_path),
                "indexed": False,
                "message": "Index status file not found",
            }

        try:
            data = await _read_json_file(status_path)
        except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - read errors
            raise ResourceError(f"Failed to read index status: {exc}") from exc

        data.setdefault("workspace", str(workspace))
        data.setdefault("status_file", str(status_path))
        return data


@mcp.resource(
    "augment://workspace/{workspace_path}/command/{command_name}",
    name="Augment Command Details",
    description="Metadata and content for a specific Augment custom command",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_command_details(
    workspace_path: str,
    command_name: str,
) -> dict[str, Any]:
    """Return command metadata and body for a specific command name."""

    with _metric_scope("resource"):
        workspace = _expand_workspace(workspace_path)
        candidates = _iter_command_candidates(workspace, command_name)

        if not candidates:
            raise ResourceError(
                f"Command '{command_name}' not found in workspace or user commands"
            )

        scope, path = candidates[0]
        try:
            raw = await _read_text_file(path)
        except OSError as exc:  # pragma: no cover - file permissions
            raise ResourceError(f"Failed to read command '{command_name}': {exc}") from exc

        meta = _extract_command_metadata(raw)

        return {
            "name": command_name,
            "scope": scope,
            "path": str(path),
            "meta": meta,
            "content": raw,
        }


def _iter_command_candidates(workspace: Path, command_name: str) -> list[tuple[str, Path]]:
    search_roots = [
        ("workspace", workspace / ".augment" / "commands"),
        ("user", Path.home() / ".augment" / "commands"),
    ]

    matches: list[tuple[str, Path]] = []
    for scope, root in search_roots:
        if not root.exists():
            continue
        for cmd_file in root.rglob("*.md"):
            if cmd_file.stem == command_name:
                matches.append((scope, cmd_file))
    return matches


def _build_tree_sync(root: Path, max_depth: int) -> dict[str, Any]:
    def walk(path: Path, depth: int) -> dict[str, Any]:
        node: dict[str, Any] = {
            "name": path.name or str(path),
            "path": str(path),
            "type": "directory" if path.is_dir() else "file",
        }

        if depth >= max_depth:
            node["truncated"] = path.is_dir()
            return node

        if path.is_dir():
            children: list[dict[str, Any]] = []
            try:
                for child in sorted(path.iterdir(), key=lambda p: p.name.lower()):
                    if child.name.startswith("."):
                        continue
                    children.append(walk(child, depth + 1))
            except OSError as exc:
                node["error"] = str(exc)
            else:
                node["children"] = children
        return node

    return walk(root, 0)


@mcp.resource(
    "augment://workspace/{workspace_path}/search",
    name="Augment Workspace Search",
    description="Search workspace files for a query string",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False},
)
async def search_workspace(
    workspace_path: str,
    query: str | None = None,
    max_results: int = 20,
    context_lines: int = 2,
) -> dict[str, Any]:
    """Search workspace files using ripgrep, grep, or a Python fallback."""

    with _metric_scope("resource"):
        workspace = _expand_workspace(workspace_path)
        if not workspace.exists() or not workspace.is_dir():
            raise ResourceError(f"Workspace not found: {workspace_path}")

        if query is None:
            raise ResourceError("query parameter is required")

        query = query.strip()
        if not query:
            raise ResourceError("query must not be empty")

        if max_results <= 0:
            raise ResourceError("max_results must be greater than zero")

        tool = _get_search_tool()
        if tool == "ripgrep":
            raw_matches, total_matches = await _search_with_ripgrep(
                workspace, query, max_results
            )
        elif tool == "grep":
            raw_matches, total_matches = await _search_with_grep(
                workspace, query, max_results
            )
        else:
            raw_matches, total_matches = await _search_with_python(
                workspace, query, max_results
            )
            tool = "python"

        formatted_matches = await _format_search_results(
            raw_matches, workspace, context_lines
        )

        return {
            "workspace": str(workspace),
            "query": query,
            "total_matches": total_matches,
            "max_results": max_results,
            "search_tool": tool,
            "results": formatted_matches,
            "truncated": total_matches > len(formatted_matches),
        }


@mcp.resource(
    "augment://history/{scope}/runs",
    name="Auggie Run History",
    description="Recent Auggie CLI invocations and their results",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False},
)
async def get_auggie_history(scope: str = "global", limit: int = 50) -> dict[str, Any]:
    """Return recent Auggie execution history."""

    with _metric_scope("resource"):
        payload = collect_auggie_history(limit)
        payload["scope"] = scope
        return payload


@mcp.resource(
    "augment://metrics/{scope}/performance",
    name="Performance Metrics",
    description="Server performance metrics and aggregated statistics",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": True},
)
async def get_performance_metrics(scope: str = "server") -> dict[str, Any]:
    """Expose telemetry metrics collected by the server."""

    with _metric_scope("resource"):
        payload = collect_performance_metrics()
        payload["scope"] = scope
        return payload


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

    with _metric_scope("tool"):
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

    with _metric_scope("prompt"):
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
) -> list[Message]:
    """Prompt template for structured refactoring guidance."""

    with _metric_scope("prompt"):
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
) -> list[Message]:
    """Prompt template for generating tests covering a file or module."""

    with _metric_scope("prompt"):
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


@mcp.prompt(
    name="api_design_review",
    description="Evaluate API design decisions with consistency and best practices",
    tags={"api", "design", "review"},
)
def api_design_review_prompt(
    file_path: str,
    api_type: str = "REST",
    guidelines: str | None = None,
) -> list[Message]:
    """Prompt template for API design analysis."""

    with _metric_scope("prompt"):
        type_notes = {
            "REST": "Assess resource modelling, HTTP verb usage, status codes, and pagination.",
            "GRAPHQL": "Evaluate schema design, query complexity, resolver patterns, and caching strategies.",
            "GRPC": "Review service definitions, streaming usage, compatibility, and error handling.",
        }

        focus_note = type_notes.get(api_type.upper(), type_notes["REST"])
        guidelines_note = (
            f"Follow the documented guidelines: {guidelines}."
            if guidelines
            else "Reference existing project API standards and established industry guidelines."
        )

        content = f"""Review the API implementation in `{file_path}`.

API style: {api_type}
{focus_note}
{guidelines_note}

For the review, cover:
1. Request and response structure clarity
2. Error handling strategy and surface
3. Versioning and backwards compatibility considerations
4. Authentication and authorization enforcement
5. Performance implications and rate limiting
6. Documentation or discoverability gaps

Compare this API with existing endpoints in the workspace to maintain consistency."""

        return [Message(role="user", content=content)]


@mcp.prompt(
    name="analyze_performance",
    description="Investigate performance hotspots and optimisation opportunities",
    tags={"performance", "analysis"},
)
def analyze_performance_prompt(
    file_path: str,
    focus: list[str] | None = None,
    include_benchmarks: bool = False,
) -> list[Message]:
    """Prompt template encouraging structured performance analysis."""

    with _metric_scope("prompt"):
        focus_items = focus or ["cpu", "memory"]
        focus_text = "\n".join(
            f"- {item.title()} usage and bottlenecks" for item in focus_items
        )
        benchmark_note = (
            "Include benchmark scenarios and target metrics for the proposed optimisations."
            if include_benchmarks
            else "Call out relevant metrics or profiling tools without drafting full benchmarks."
        )

        content = f"""Analyse performance characteristics of `{file_path}`.

Primary focus areas:
{focus_text}

{benchmark_note}

Provide:
1. Summary of current performance risks or antipatterns
2. Proposed improvements with estimated impact
3. References to similar optimised code within the workspace
4. Potential trade-offs or regression risks
5. Suggested monitoring or alerting follow-up

Use workspace context (profiling data, comparable modules, configuration) to ground the analysis."""

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

    with _metric_scope("tool"):
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

    with _metric_scope("tool"):
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

    with _metric_scope("tool"):
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
