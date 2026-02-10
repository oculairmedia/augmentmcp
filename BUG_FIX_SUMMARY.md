# Bug Fix: Test Hanging Issue

## Problem

Tests were hanging indefinitely when running `augment_list_commands` and `augment_custom_command` tests.

## Root Cause

**File:** `tests/fake_auggie.py`  
**Line:** 54 (original)

```python
context = sys.stdin.read()  # This line blocked forever
```

The fake Auggie CLI script was **unconditionally reading from stdin**, even when:
- No input was being provided
- The command didn't need stdin (like `command list`)
- The subprocess wasn't sending any data

This caused the script to **block indefinitely** waiting for input that would never arrive.

## Why It Happened

When tests called:
```python
await augment_list_commands(workspace_root="/workspace/project")
```

The implementation would run:
```bash
auggie command list --workspace-root /workspace/project
```

The fake script would:
1. Parse arguments ✅
2. Check for `--fail` flag ✅
3. **Read from stdin** ❌ ← BLOCKS HERE FOREVER
4. Never reach the command handling code

## The Fix

**Move stdin reading to AFTER command handling:**

```python
def main(argv: list[str]) -> int:
    compact, github_token, instruction, extra = _parse_args(argv)

    if "--fail" in extra:
        print("forced failure", file=sys.stderr)
        return 2

    # Handle "command" subcommand early (doesn't need stdin)
    if extra and extra[0] == "command":
        cleaned_extra, workspace_root = _extract_workspace_flag(extra)
        command_name = cleaned_extra[1] if len(cleaned_extra) > 1 else "<missing>"
        if len(cleaned_extra) > 2 and cleaned_extra[1] == "list":
            print("security-review: Security review following company standards")
            print("performance-check: Analyze code for performance issues")
        else:
            print(f"Executed command: {command_name}")
            if len(cleaned_extra) > 2:
                print(f"Arguments: {' '.join(cleaned_extra[2:])}")
        if workspace_root:
            print(f"Workspace root: {workspace_root}")
        return 0  # ← EXIT EARLY, don't read stdin

    # Only read stdin for regular --print commands
    context = sys.stdin.read()  # ← Now only runs for --print commands
    
    # ... rest of the code
```

## Key Changes

1. **Early return for `command` subcommand** - Exits before reading stdin
2. **Stdin read moved down** - Only executes for `--print` commands that actually need it
3. **Added comment** - Clarifies why stdin is read at that point

## Impact

- ✅ `test_augment_list_commands_returns_catalog` - Now completes instantly
- ✅ `test_augment_custom_command_executes_with_workspace` - Now completes instantly
- ✅ All other tests - Still work correctly (stdin is provided for `--print` commands)

## Testing

The fix ensures:
- Commands that don't need stdin (`command list`, `command <name>`) exit immediately
- Commands that need stdin (`--print "instruction"`) still read it correctly
- No breaking changes to existing test behavior

## Lessons Learned

1. **Always check if stdin is needed** before reading it
2. **Handle special cases early** to avoid unnecessary blocking operations
3. **Test with subprocess communication** to catch blocking issues
4. **Document why stdin is read** to prevent future regressions

