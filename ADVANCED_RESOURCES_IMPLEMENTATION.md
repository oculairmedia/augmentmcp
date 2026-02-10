# Advanced Resources Implementation Guide

## Overview

This document provides detailed implementation specifications for the three advanced resources:
1. **Workspace Search** - File search using grep/ripgrep
2. **Auggie Run History** - Track CLI invocations
3. **Performance Metrics** - Server monitoring

---

## 1. Workspace Search Resource

### 1.1 Specification

**URI Pattern:** `augment://workspace/{workspace_path}/search?query={query}&max_results={max_results}`

**Purpose:** Enable fast file content search across workspace using native tools

**Parameters:**
- `workspace_path` (required) - Workspace directory path
- `query` (required) - Search query string
- `max_results` (optional, default=20) - Maximum results to return

**Response Schema:**
```json
{
  "workspace": "/path/to/workspace",
  "query": "search term",
  "total_matches": 42,
  "max_results": 20,
  "search_tool": "ripgrep",
  "results": [
    {
      "file": "src/auth.py",
      "line_number": 15,
      "line_content": "def authenticate_user(username, password):",
      "match_context": {
        "before": ["# User authentication module", ""],
        "after": ["    \"\"\"Authenticate user credentials.\"\"\"", "    if not username:"]
      }
    }
  ],
  "truncated": false
}
```

### 1.2 Implementation

```python
import asyncio
import json
import shutil
from pathlib import Path
from typing import Any
from fastmcp.exceptions import ResourceError

@mcp.resource(
    "augment://workspace/{workspace_path}/search",
    name="Workspace File Search",
    description="Search file contents in workspace using ripgrep or grep",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False}
)
async def search_workspace(
    workspace_path: str,
    query: str,
    max_results: int = 20,
    context_lines: int = 2
) -> dict[str, Any]:
    """Search workspace files for query string.
    
    Args:
        workspace_path: Path to workspace directory
        query: Search query string
        max_results: Maximum number of results to return
        context_lines: Number of context lines before/after match
    
    Returns:
        Search results with file paths, line numbers, and context
    """
    workspace = _expand_workspace(workspace_path)
    
    if not workspace.exists():
        raise ResourceError(f"Workspace not found: {workspace}")
    
    # Determine which search tool to use
    search_tool = _get_search_tool()
    
    if search_tool == "ripgrep":
        results = await _search_with_ripgrep(
            workspace, query, max_results, context_lines
        )
    elif search_tool == "grep":
        results = await _search_with_grep(
            workspace, query, max_results, context_lines
        )
    else:
        raise ResourceError("No search tool available (install ripgrep or grep)")
    
    return {
        "workspace": str(workspace),
        "query": query,
        "total_matches": len(results),
        "max_results": max_results,
        "search_tool": search_tool,
        "results": results[:max_results],
        "truncated": len(results) > max_results
    }


def _get_search_tool() -> str | None:
    """Determine which search tool is available."""
    if shutil.which("rg"):
        return "ripgrep"
    elif shutil.which("grep"):
        return "grep"
    return None


async def _search_with_ripgrep(
    workspace: Path,
    query: str,
    max_results: int,
    context_lines: int
) -> list[dict[str, Any]]:
    """Search using ripgrep (fast, recommended)."""
    cmd = [
        "rg",
        "--json",
        f"--context={context_lines}",
        f"--max-count={max_results}",
        "--no-heading",
        "--line-number",
        query,
        str(workspace)
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode not in (0, 1):  # 1 = no matches
        raise ResourceError(f"ripgrep failed: {stderr.decode()}")
    
    # Parse ripgrep JSON output
    results = []
    for line in stdout.decode().splitlines():
        if not line.strip():
            continue
        
        try:
            data = json.loads(line)
            if data.get("type") == "match":
                match_data = data["data"]
                results.append({
                    "file": match_data["path"]["text"],
                    "line_number": match_data["line_number"],
                    "line_content": match_data["lines"]["text"].rstrip(),
                    "match_context": {
                        "before": [],  # ripgrep provides this separately
                        "after": []
                    }
                })
        except json.JSONDecodeError:
            continue
    
    return results


async def _search_with_grep(
    workspace: Path,
    query: str,
    max_results: int,
    context_lines: int
) -> list[dict[str, Any]]:
    """Search using grep (fallback)."""
    cmd = [
        "grep",
        "-r",
        "-n",
        f"-C{context_lines}",
        f"--max-count={max_results}",
        query,
        str(workspace)
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode not in (0, 1):  # 1 = no matches
        raise ResourceError(f"grep failed: {stderr.decode()}")
    
    # Parse grep output
    results = []
    for line in stdout.decode().splitlines():
        if not line.strip() or line.startswith("--"):
            continue
        
        try:
            # Format: file:line_number:content
            parts = line.split(":", 2)
            if len(parts) >= 3:
                results.append({
                    "file": parts[0],
                    "line_number": int(parts[1]),
                    "line_content": parts[2],
                    "match_context": {
                        "before": [],
                        "after": []
                    }
                })
        except (ValueError, IndexError):
            continue
    
    return results
```

### 1.3 Tests

```python
# tests/unit/test_advanced_resources.py
import pytest
from augment_mcp.server import search_workspace

class TestWorkspaceSearch:
    """Tests for workspace search resource."""
    
    async def test_search_finds_matches(self, tmp_workspace):
        """Should find matching content in files."""
        # Create test file
        test_file = tmp_workspace / "test.py"
        test_file.write_text("def authenticate_user():\n    pass\n")
        
        result = await search_workspace.fn(
            workspace_path=str(tmp_workspace),
            query="authenticate"
        )
        
        assert result["total_matches"] > 0
        assert result["results"][0]["file"].endswith("test.py")
        assert "authenticate" in result["results"][0]["line_content"]
    
    async def test_search_respects_max_results(self, tmp_workspace):
        """Should limit results to max_results."""
        # Create multiple matching files
        for i in range(10):
            (tmp_workspace / f"file{i}.py").write_text("test content\n")
        
        result = await search_workspace.fn(
            workspace_path=str(tmp_workspace),
            query="test",
            max_results=5
        )
        
        assert len(result["results"]) <= 5
        assert result["truncated"] is True
    
    async def test_search_nonexistent_workspace_raises_error(self):
        """Should raise ResourceError for invalid workspace."""
        from fastmcp.exceptions import ResourceError
        
        with pytest.raises(ResourceError):
            await search_workspace.fn(
                workspace_path="/nonexistent/path",
                query="test"
            )
```

---

## 2. Auggie Run History Resource

### 2.1 Specification

**URI Pattern:** `augment://history/runs?limit={limit}`

**Purpose:** Track recent Auggie CLI invocations for debugging and monitoring

**Parameters:**
- `limit` (optional, default=50) - Maximum history entries to return

**Response Schema:**
```json
{
  "total_runs": 150,
  "limit": 50,
  "runs": [
    {
      "timestamp": "2025-09-30T14:32:15Z",
      "command": "auggie --print --workspace-root /opt/project",
      "instruction": "Review this code for security issues",
      "workspace_root": "/opt/project",
      "model": "claude-sonnet-4",
      "duration_ms": 2341,
      "success": true,
      "output_length": 1523,
      "error": null
    }
  ]
}
```

### 2.2 Implementation

```python
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from collections import deque

# Global history storage (in-memory for now)
_auggie_history: deque = deque(maxlen=1000)


def _record_auggie_run(
    command: str,
    instruction: str,
    workspace_root: str | None,
    model: str | None,
    duration_ms: int,
    success: bool,
    output_length: int,
    error: str | None = None
) -> None:
    """Record an Auggie CLI run in history."""
    _auggie_history.append({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "command": command,
        "instruction": instruction,
        "workspace_root": workspace_root,
        "model": model,
        "duration_ms": duration_ms,
        "success": success,
        "output_length": output_length,
        "error": error
    })


@mcp.resource(
    "augment://history/runs",
    name="Auggie Run History",
    description="Recent Auggie CLI invocations and their results",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False}
)
async def get_auggie_history(limit: int = 50) -> dict[str, Any]:
    """Return recent Auggie CLI runs.
    
    Args:
        limit: Maximum number of history entries to return
    
    Returns:
        History of recent Auggie runs with timing and status
    """
    runs = list(_auggie_history)[-limit:]
    
    return {
        "total_runs": len(_auggie_history),
        "limit": limit,
        "runs": runs,
        "statistics": {
            "total_success": sum(1 for r in runs if r["success"]),
            "total_failures": sum(1 for r in runs if not r["success"]),
            "avg_duration_ms": sum(r["duration_ms"] for r in runs) / len(runs) if runs else 0,
            "most_used_model": _most_common([r["model"] for r in runs if r["model"]])
        }
    }


def _most_common(items: list) -> str | None:
    """Return most common item in list."""
    if not items:
        return None
    from collections import Counter
    return Counter(items).most_common(1)[0][0]
```

### 2.3 Integration with auggie.py

```python
# In augment_mcp/auggie.py, modify run_auggie():

async def run_auggie(
    *,
    instruction: str,
    input_text: str | None = None,
    workspace_root: str | None = None,
    model: str | None = None,
    # ... other params
) -> str:
    """Execute Auggie CLI and record in history."""
    start_time = time.time()
    success = False
    error = None
    output = ""
    
    try:
        # ... existing implementation
        output = result.output
        success = True
        return output
    except Exception as e:
        error = str(e)
        raise
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Record in history
        from augment_mcp.server import _record_auggie_run
        _record_auggie_run(
            command=f"auggie --print",
            instruction=instruction[:100],  # Truncate
            workspace_root=workspace_root,
            model=model,
            duration_ms=duration_ms,
            success=success,
            output_length=len(output),
            error=error
        )
```

---

## 3. Performance Metrics Resource

### 3.1 Specification

**URI Pattern:** `augment://metrics/performance`

**Purpose:** Expose server performance metrics for monitoring

**Response Schema:**
```json
{
  "server": {
    "uptime_seconds": 3600,
    "start_time": "2025-09-30T10:00:00Z"
  },
  "requests": {
    "total_tools_called": 42,
    "total_resources_read": 18,
    "total_prompts_requested": 7,
    "requests_per_minute": 1.2
  },
  "performance": {
    "avg_tool_duration_ms": 234,
    "avg_resource_duration_ms": 12,
    "avg_prompt_duration_ms": 5
  },
  "auggie": {
    "total_runs": 15,
    "success_rate": 0.93,
    "avg_duration_ms": 2341
  }
}
```

### 3.2 Implementation

```python
import time
from datetime import datetime
from typing import Any

# Global metrics storage
_server_start_time = time.time()
_metrics = {
    "tools_called": 0,
    "resources_read": 0,
    "prompts_requested": 0,
    "tool_durations": [],
    "resource_durations": [],
    "prompt_durations": []
}


@mcp.resource(
    "augment://metrics/performance",
    name="Performance Metrics",
    description="Server performance metrics and statistics",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False}
)
async def get_performance_metrics() -> dict[str, Any]:
    """Return server performance metrics."""
    uptime = time.time() - _server_start_time
    
    return {
        "server": {
            "uptime_seconds": int(uptime),
            "start_time": datetime.fromtimestamp(_server_start_time).isoformat() + "Z"
        },
        "requests": {
            "total_tools_called": _metrics["tools_called"],
            "total_resources_read": _metrics["resources_read"],
            "total_prompts_requested": _metrics["prompts_requested"],
            "requests_per_minute": (_metrics["tools_called"] + _metrics["resources_read"]) / (uptime / 60) if uptime > 0 else 0
        },
        "performance": {
            "avg_tool_duration_ms": _avg(_metrics["tool_durations"]),
            "avg_resource_duration_ms": _avg(_metrics["resource_durations"]),
            "avg_prompt_duration_ms": _avg(_metrics["prompt_durations"])
        },
        "auggie": {
            "total_runs": len(_auggie_history),
            "success_rate": sum(1 for r in _auggie_history if r["success"]) / len(_auggie_history) if _auggie_history else 0,
            "avg_duration_ms": sum(r["duration_ms"] for r in _auggie_history) / len(_auggie_history) if _auggie_history else 0
        }
    }


def _avg(values: list[float]) -> float:
    """Calculate average of values."""
    return sum(values) / len(values) if values else 0.0


def _record_metric(metric_type: str, duration_ms: float) -> None:
    """Record a metric."""
    if metric_type == "tool":
        _metrics["tools_called"] += 1
        _metrics["tool_durations"].append(duration_ms)
    elif metric_type == "resource":
        _metrics["resources_read"] += 1
        _metrics["resource_durations"].append(duration_ms)
    elif metric_type == "prompt":
        _metrics["prompts_requested"] += 1
        _metrics["prompt_durations"].append(duration_ms)
    
    # Keep only last 1000 durations
    for key in ["tool_durations", "resource_durations", "prompt_durations"]:
        if len(_metrics[key]) > 1000:
            _metrics[key] = _metrics[key][-1000:]
```

---

## 4. Summary

### Implementation Checklist

- [ ] Implement workspace search resource
- [ ] Add search tool detection (_get_search_tool)
- [ ] Implement ripgrep integration
- [ ] Implement grep fallback
- [ ] Add history tracking to auggie.py
- [ ] Implement history resource
- [ ] Implement metrics resource
- [ ] Add metrics recording to tools/resources
- [ ] Write unit tests for all resources
- [ ] Write integration tests
- [ ] Update documentation

### Testing Priority

1. **High:** Workspace search (most complex)
2. **Medium:** History tracking
3. **Low:** Metrics (simple aggregation)

