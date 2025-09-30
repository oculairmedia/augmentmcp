#!/usr/bin/env python3
"""Simple fake Auggie CLI for testing."""

import sys


def _parse_args(argv):
    """Parse the minimal Auggie CLI flags we care about for tests."""

    args_iter = iter(argv)
    compact_value = False
    github_value = None
    instruction_value = None
    extras: list[str] = []

    for arg in args_iter:
        if arg == "--compact":
            compact_value = True
        elif arg == "--github-api-token":
            github_value = next(args_iter, None)
        elif arg == "--print":
            instruction_value = next(args_iter, "")
        else:
            extras.append(arg)

    return compact_value, github_value, instruction_value, extras


def _extract_workspace_flag(values: list[str]) -> tuple[list[str], str | None]:
    """Split out --workspace-root from the list of arguments (if present)."""

    cleaned: list[str] = []
    workspace: str | None = None
    iterator = iter(range(len(values)))
    idx_iterator = 0
    while idx_iterator < len(values):
        current = values[idx_iterator]
        if current == "--workspace-root" and idx_iterator + 1 < len(values):
            workspace = values[idx_iterator + 1]
            idx_iterator += 2
            continue
        cleaned.append(current)
        idx_iterator += 1
    return cleaned, workspace


def main(argv: list[str]) -> int:
    compact, github_token, instruction, extra = _parse_args(argv)

    if "--fail" in extra:
        print("forced failure", file=sys.stderr)
        return 2

    # Handle "command" subcommand early (doesn't need stdin)
    if extra and extra[0] == "command":
        cleaned_extra, workspace_root = _extract_workspace_flag(extra)
        command_name = cleaned_extra[1] if len(cleaned_extra) > 1 else "<missing>"
        if command_name == "list":
            print("security-review: Security review following company standards")
            print("performance-check: Analyze code for performance issues")
        else:
            print(f"Executed command: {command_name}")
            if len(cleaned_extra) > 2:
                print(f"Arguments: {' '.join(cleaned_extra[2:])}")
        if workspace_root:
            print(f"Workspace root: {workspace_root}")
        return 0

    # Only read stdin for regular --print commands
    context = sys.stdin.read()

    print("[fake-auggie]")
    print(f"Instruction: {instruction}")
    print(f"Compact: {compact}")
    if github_token:
        print(f"GitHub token: {github_token}")
    if extra:
        print(f"Extra args: {' '.join(extra)}")
    if context.strip():
        print("Context:\n" + context)
    else:
        print("(no context provided)")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
