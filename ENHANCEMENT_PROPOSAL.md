# Augment Capabilities Enhancement Proposal

## Current Limitations

The current implementation only uses Auggie's `--print` flag with basic context passing. We're missing:

1. **Workspace indexing** - Augment's superior codebase context engine
2. **Tool permissions** - Security and compliance controls
3. **Custom commands** - Reusable workflows
4. **Advanced configuration** - Settings files and policies

## Proposed Enhancements

### 1. Workspace Context Support

**Add to `augment_review` tool:**

```python
async def augment_review(
    instruction: str,
    workspace_root: str | None = None,  # NEW: Enable workspace indexing
    context: str | None = None,
    paths: list[str] | None = None,
    # ... existing params
) -> str:
```

**Implementation:**
```python
args: list[str] = []
if workspace_root:
    args.extend(["--workspace-root", workspace_root])
if compact:
    args.append("--compact")
# ... rest of args
```

**Benefits:**
- Auggie can leverage full codebase context
- Better code suggestions based on project patterns
- Access to codebase-retrieval tool's indexing

### 2. Tool Permissions Configuration

**Add new tool: `augment_configure`**

```python
@mcp.tool(name="augment_configure")
async def augment_configure(
    workspace_root: str,
    permissions: dict[str, Any],
    scope: Literal["user", "project"] = "project",
) -> str:
    """Configure Auggie tool permissions for security and compliance."""
    
    settings_path = Path(workspace_root) / ".augment" / "settings.json"
    if scope == "user":
        settings_path = Path.home() / ".augment" / "settings.json"
    
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    
    config = {"tool-permissions": permissions}
    settings_path.write_text(json.dumps(config, indent=2))
    
    return f"Configured tool permissions at {settings_path}"
```

**Example usage:**
```python
# Read-only mode for code review
permissions = [
    {"tool-name": "view", "permission": {"type": "allow"}},
    {"tool-name": "codebase-retrieval", "permission": {"type": "allow"}},
    {"tool-name": "str-replace-editor", "permission": {"type": "deny"}},
    {"tool-name": "save-file", "permission": {"type": "deny"}},
    {"tool-name": "remove-files", "permission": {"type": "deny"}},
]
```

### 3. Custom Command Support

**Add new tool: `augment_custom_command`**

```python
@mcp.tool(name="augment_custom_command")
async def augment_custom_command(
    command_name: str,
    arguments: str | None = None,
    workspace_root: str | None = None,
    timeout_ms: int | None = None,
) -> str:
    """Execute a custom Auggie slash command."""
    
    args = ["command", command_name]
    if arguments:
        args.append(arguments)
    
    if workspace_root:
        args.extend(["--workspace-root", workspace_root])
    
    timeout_seconds = timeout_ms / 1000 if timeout_ms else None
    
    result = await run_auggie_command(
        args=args,
        timeout_seconds=timeout_seconds,
    )
    
    return result.stdout.strip()
```

**Benefits:**
- Leverage pre-defined workflows
- Team can share standardized prompts
- Consistent code review/analysis patterns

### 4. Model Selection

**Add to `augment_review`:**

```python
async def augment_review(
    instruction: str,
    model: str | None = None,  # NEW: Override default model
    # ... existing params
) -> str:
```

**Implementation:**
```python
if model:
    args.extend(["--model", model])
```

**Benefits:**
- Use different models for different tasks
- Cost optimization (cheaper models for simple tasks)
- Performance tuning

### 5. Settings Management

**Add new tool: `augment_list_commands`**

```python
@mcp.tool(name="augment_list_commands")
async def augment_list_commands(
    workspace_root: str | None = None,
) -> str:
    """List all available custom Auggie commands."""
    
    args = ["command", "list"]
    if workspace_root:
        args.extend(["--workspace-root", workspace_root])
    
    result = await run_auggie_command(args=args)
    return result.stdout.strip()
```

### 6. Enhanced Error Context

**Add workspace info to errors:**

```python
except AuggieCommandError as exc:
    message = [str(exc)]
    if workspace_root:
        message.append(f"Workspace: {workspace_root}")
    stderr = exc.result.stderr.strip()
    # ... rest of error handling
```

## Implementation Priority

### Phase 1: Core Enhancements (High Priority)
1. ✅ Add `workspace_root` parameter to `augment_review`
2. ✅ Add `model` parameter for model selection
3. ✅ Enhance error messages with workspace context

### Phase 2: Configuration (Medium Priority)
4. ✅ Add `augment_configure` tool for permissions
5. ✅ Add `.augmentignore` template generation
6. ✅ Add settings validation

### Phase 3: Advanced Features (Low Priority)
7. ✅ Add `augment_custom_command` tool
8. ✅ Add `augment_list_commands` tool
9. ✅ Add webhook policy support

## Security Considerations

### Default Permissions
For production deployments, recommend default read-only mode:

```json
{
  "tool-permissions": [
    {"tool-name": "view", "permission": {"type": "allow"}},
    {"tool-name": "codebase-retrieval", "permission": {"type": "allow"}},
    {"tool-name": "grep-search", "permission": {"type": "allow"}},
    {"tool-name": "web-search", "permission": {"type": "allow"}},
    {"tool-name": "str-replace-editor", "permission": {"type": "deny"}},
    {"tool-name": "save-file", "permission": {"type": "deny"}},
    {"tool-name": "remove-files", "permission": {"type": "deny"}},
    {"tool-name": "launch-process", "permission": {"type": "deny"}}
  ]
}
```

### Docker Considerations
- Mount workspace directories read-only by default
- Provide separate write-enabled mode for code generation
- Document security implications in README

## Documentation Updates

### README.md
- Add "Workspace Indexing" section
- Add "Tool Permissions" section
- Add "Custom Commands" section
- Add security best practices

### New Files
- `docs/SECURITY.md` - Security guidelines
- `docs/CUSTOM_COMMANDS.md` - Command examples
- `.augment/settings.example.json` - Template configuration

## Breaking Changes

None - all enhancements are additive and backward compatible.

## Testing Strategy

1. Unit tests for new parameters
2. Integration tests with workspace indexing
3. Security tests for permission enforcement
4. Docker tests with mounted workspaces

## Success Metrics

- ✅ Auggie can access full codebase context
- ✅ Tool permissions can be configured per deployment
- ✅ Custom commands can be shared across team
- ✅ Security policies can be enforced
- ✅ Different models can be selected per task

