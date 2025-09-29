"""Helpers for interacting with the Augment Auggie CLI."""

from __future__ import annotations

import asyncio
import contextlib
import os
from dataclasses import dataclass
from typing import Sequence

__all__ = [
    "AuggieError",
    "AuggieNotInstalledError",
    "AuggieTimeoutError",
    "AuggieAbortedError",
    "AuggieCommandError",
    "AuggieRunResult",
    "run_auggie",
]


class AuggieError(RuntimeError):
    """Base error raised for Auggie-related failures."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class AuggieNotInstalledError(AuggieError):
    """Raised when the Auggie binary cannot be located."""

    def __init__(self, binary_path: str, *, cause: Exception | None = None) -> None:
        super().__init__(
            f"Auggie CLI was not found. Expected executable at: {binary_path}",
            cause=cause,
        )
        self.binary_path = binary_path


class AuggieTimeoutError(AuggieError):
    """Raised when Auggie execution exceeds the configured timeout."""

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(f"Auggie CLI timed out after {int(timeout_seconds * 1000)}ms")
        self.timeout_seconds = timeout_seconds


class AuggieAbortedError(AuggieError):
    """Raised when the Auggie invocation is aborted by the caller."""

    def __init__(self) -> None:
        super().__init__("Auggie invocation aborted by the caller")


@dataclass(slots=True)
class AuggieRunResult:
    """Successful Auggie invocation result."""

    stdout: str
    stderr: str
    exit_code: int
    command: str


class AuggieCommandError(AuggieError):
    """Raised when Auggie exits with a non-zero status code."""

    def __init__(self, result: AuggieRunResult) -> None:
        super().__init__(
            f"Auggie exited with code {result.exit_code}. Command: {result.command}"
        )
        self.result = result


def _default_binary_path() -> str:
    return os.environ.get("AUGGIE_PATH", "auggie")


def _quote_arg(arg: str) -> str:
    return f'"{arg}"' if " " in arg else arg


async def run_auggie(
    *,
    instruction: str,
    input_text: str | None = None,
    compact: bool | None = None,
    github_api_token: str | None = None,
    extra_args: Sequence[str] | None = None,
    timeout_seconds: float | None = None,
    session_token: str | None = None,
    binary_path: str | None = None,
) -> AuggieRunResult:
    """Execute the Auggie CLI with the provided options."""

    instruction = instruction.strip()
    if not instruction:
        raise AuggieError("Instruction is required for Auggie invocations")

    binary = binary_path or _default_binary_path()
    env = os.environ.copy()
    token = session_token or env.get("AUGMENT_SESSION_AUTH")
    if token:
        env["AUGMENT_SESSION_AUTH"] = token

    args: list[str] = []
    if compact:
        args.append("--compact")
    if github_api_token:
        args.extend(["--github-api-token", github_api_token])
    if extra_args:
        args.extend(extra_args)
    args.extend(["--print", instruction])

    command = " ".join((_quote_arg(binary), *(_quote_arg(arg) for arg in args)))

    try:
        process = await asyncio.create_subprocess_exec(
            binary,
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
    except FileNotFoundError as exc:  # pragma: no cover - direct OS error handling
        raise AuggieNotInstalledError(binary, cause=exc) from exc
    except OSError as exc:  # pragma: no cover - unexpected spawn failure
        raise AuggieError("Failed to start Auggie CLI", cause=exc) from exc

    input_bytes = input_text.encode("utf-8") if input_text else None

    async def _communicate() -> tuple[bytes, bytes]:
        try:
            return await process.communicate(input_bytes)
        finally:
            if process.stdin and not process.stdin.is_closing():
                process.stdin.close()

    communicate_task = asyncio.create_task(_communicate())

    try:
        if timeout_seconds is not None:
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    communicate_task, timeout_seconds
                )
            except asyncio.TimeoutError as exc:
                communicate_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await communicate_task
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                raise AuggieTimeoutError(timeout_seconds) from exc
        else:
            stdout_bytes, stderr_bytes = await communicate_task
    except asyncio.CancelledError:
        communicate_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await communicate_task
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 1)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        raise AuggieAbortedError() from None
    finally:
        if not communicate_task.done():
            communicate_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await communicate_task

    exit_code = process.returncode or 0
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    result = AuggieRunResult(
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        command=command,
    )

    if exit_code != 0:
        raise AuggieCommandError(result)

    return result
