"""Telemetry helpers for Augment MCP server."""

from __future__ import annotations

import time
from collections import Counter, deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Literal, Optional

__all__ = [
    "record_operation",
    "collect_performance_metrics",
    "record_auggie_run",
    "collect_auggie_history",
    "reset_telemetry",
]


_METRIC_HISTORY_LIMIT = 1000
_AUGGIE_HISTORY_LIMIT = 1000


_server_start_time: float = time.time()
_metrics: Dict[str, Any] = {
    "tools_called": 0,
    "resources_read": 0,
    "prompts_requested": 0,
    "tool_durations": [],
    "resource_durations": [],
    "prompt_durations": [],
}

_auggie_history: Deque[Dict[str, Any]] = deque(maxlen=_AUGGIE_HISTORY_LIMIT)


def reset_telemetry() -> None:
    """Reset telemetry data (used by tests)."""

    global _server_start_time
    _server_start_time = time.time()

    _metrics["tools_called"] = 0
    _metrics["resources_read"] = 0
    _metrics["prompts_requested"] = 0
    _metrics["tool_durations"].clear()
    _metrics["resource_durations"].clear()
    _metrics["prompt_durations"].clear()

    _auggie_history.clear()


def record_operation(kind: Literal["tool", "resource", "prompt"], duration_ms: float) -> None:
    """Record execution metrics for tools, resources, and prompts."""

    duration_list_key = {
        "tool": "tool_durations",
        "resource": "resource_durations",
        "prompt": "prompt_durations",
    }[kind]

    counter_key = {
        "tool": "tools_called",
        "resource": "resources_read",
        "prompt": "prompts_requested",
    }[kind]

    _metrics[counter_key] += 1
    durations: List[float] = _metrics[duration_list_key]
    durations.append(duration_ms)
    if len(durations) > _METRIC_HISTORY_LIMIT:
        del durations[0 : len(durations) - _METRIC_HISTORY_LIMIT]


def _average(values: List[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def collect_performance_metrics() -> Dict[str, Any]:
    """Return a snapshot of performance metrics and statistics."""

    uptime_seconds = max(time.time() - _server_start_time, 0)
    total_requests = _metrics["tools_called"] + _metrics["resources_read"]

    return {
        "server": {
            "uptime_seconds": int(uptime_seconds),
            "start_time": datetime.fromtimestamp(_server_start_time, tz=timezone.utc).isoformat(),
        },
        "requests": {
            "total_tools_called": _metrics["tools_called"],
            "total_resources_read": _metrics["resources_read"],
            "total_prompts_requested": _metrics["prompts_requested"],
            "requests_per_minute": (total_requests / (uptime_seconds / 60)) if uptime_seconds > 0 else 0.0,
        },
        "performance": {
            "avg_tool_duration_ms": _average(_metrics["tool_durations"]),
            "avg_resource_duration_ms": _average(_metrics["resource_durations"]),
            "avg_prompt_duration_ms": _average(_metrics["prompt_durations"]),
        },
        "auggie": {
            "total_runs": len(_auggie_history),
            "success_rate": (
                sum(1 for item in _auggie_history if item.get("success")) / len(_auggie_history)
                if _auggie_history
                else 0.0
            ),
            "avg_duration_ms": (
                sum(item.get("duration_ms", 0) for item in _auggie_history) / len(_auggie_history)
                if _auggie_history
                else 0.0
            ),
        },
    }


def record_auggie_run(
    *,
    command: str,
    instruction: Optional[str],
    workspace_root: Optional[str],
    model: Optional[str],
    duration_ms: int,
    success: bool,
    output_length: int,
    error: Optional[str],
) -> None:
    """Record an Auggie CLI invocation for history tracking."""

    entry = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "command": command,
        "instruction": (instruction or "")[:200],
        "workspace_root": workspace_root,
        "model": model,
        "duration_ms": duration_ms,
        "success": success,
        "output_length": output_length,
        "error": error,
    }
    _auggie_history.append(entry)


def collect_auggie_history(limit: int = 50) -> Dict[str, Any]:
    """Return recent Auggie CLI run history."""

    limit = max(1, min(limit, _AUGGIE_HISTORY_LIMIT))
    runs = list(_auggie_history)[-limit:]

    success_count = sum(1 for item in runs if item.get("success"))
    failure_count = sum(1 for item in runs if not item.get("success"))
    durations = [item.get("duration_ms", 0) for item in runs]
    models = [item.get("model") for item in runs if item.get("model")]
    most_used_model = Counter(models).most_common(1)[0][0] if models else None

    return {
        "total_runs": len(_auggie_history),
        "limit": limit,
        "runs": runs,
        "statistics": {
            "total_success": success_count,
            "total_failures": failure_count,
            "avg_duration_ms": (_average(durations) if durations else 0.0),
            "most_used_model": most_used_model,
        },
    }
