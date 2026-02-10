# MCP Resources Implementation Proposal

## Overview

MCP Resources provide **read-only access** to data sources, perfect for exposing Augment's workspace context, configuration, and custom commands to LLMs without consuming token context in prompts.

## Why Resources Are Perfect for Augment

### Current Limitations
- Tools require explicit invocation
- Context must be passed via stdin or file paths
- No way to browse available custom commands
- Configuration is opaque to clients
- Workspace structure is hidden

### Resources Enable
- **Lazy loading** - Only fetch data when needed
- **Discovery** - Clients can list available resources
- **Caching** - Clients can cache read-only data
- **Templates** - Dynamic resources based on parameters
- **Metadata** - Rich annotations for client optimization

---

## Proposed Resources

### 1. Workspace Configuration

**Purpose:** Expose Augment workspace settings and tool permissions

```python
@mcp.resource(
    "augment://workspace/{workspace_path}/settings",
    name="Workspace Settings",
    description="Augment workspace configuration and tool permissions",
    mime_type="application/json",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_workspace_settings(workspace_path: str) -> dict:
    """Get Augment settings for a workspace."""
    settings_file = Path(workspace_path) / ".augment" / "settings.json"
    
    if not settings_file.exists():
        return {
            "workspace": workspace_path,
            "settings_file": str(settings_file),
            "exists": False,
            "default_permissions": "unrestricted"
        }
    
    async with aiofiles.open(settings_file) as f:
        settings = json.loads(await f.read())
    
    return {
        "workspace": workspace_path,
        "settings_file": str(settings_file),
        "exists": True,
        "tool_permissions": settings.get("tool-permissions", []),
        "custom_settings": settings
    }
```

**Benefits:**
- LLM can understand current security posture
- Clients can display permission status
- Helps LLM suggest appropriate operations

---

### 2. Custom Commands Catalog

**Purpose:** List available custom slash commands

```python
@mcp.resource(
    "augment://workspace/{workspace_path}/commands",
    name="Custom Commands",
    description="Available Augment custom commands for this workspace",
    mime_type="application/json",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_custom_commands(workspace_path: str) -> dict:
    """List all available custom Augment commands."""
    
    commands = []
    
    # Check workspace commands
    workspace_commands = Path(workspace_path) / ".augment" / "commands"
    if workspace_commands.exists():
        for cmd_file in workspace_commands.rglob("*.md"):
            commands.append({
                "name": cmd_file.stem,
                "path": str(cmd_file),
                "scope": "workspace",
                "namespace": cmd_file.parent.name if cmd_file.parent != workspace_commands else None
            })
    
    # Check user commands
    user_commands = Path.home() / ".augment" / "commands"
    if user_commands.exists():
        for cmd_file in user_commands.rglob("*.md"):
            commands.append({
                "name": cmd_file.stem,
                "path": str(cmd_file),
                "scope": "user",
                "namespace": cmd_file.parent.name if cmd_file.parent != user_commands else None
            })
    
    return {
        "workspace": workspace_path,
        "commands": commands,
        "total": len(commands)
    }
```

**Benefits:**
- LLM can discover available workflows
- Clients can show command palette
- Enables command auto-completion

---

### 3. Custom Command Details

**Purpose:** Get full details of a specific command

```python
@mcp.resource(
    "augment://command/{command_name}",
    name="Command Details",
    description="Detailed information about a custom Augment command",
    mime_type="application/json",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_command_details(command_name: str) -> dict:
    """Get detailed information about a custom command."""
    
    # Search for command file
    search_paths = [
        Path.home() / ".augment" / "commands",
        Path(".augment") / "commands"
    ]
    
    for base_path in search_paths:
        cmd_file = base_path / f"{command_name}.md"
        if cmd_file.exists():
            async with aiofiles.open(cmd_file) as f:
                content = await f.read()
            
            # Parse frontmatter
            frontmatter = {}
            prompt = content
            
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    frontmatter = yaml.safe_load(parts[1])
                    prompt = parts[2].strip()
            
            return {
                "name": command_name,
                "path": str(cmd_file),
                "description": frontmatter.get("description", ""),
                "argument_hint": frontmatter.get("argument-hint", ""),
                "model": frontmatter.get("model"),
                "prompt": prompt,
                "frontmatter": frontmatter
            }
    
    raise ToolError(f"Command not found: {command_name}")
```

**Benefits:**
- LLM can understand command purpose
- Clients can show command documentation
- Enables intelligent command suggestions

---

### 4. Workspace Index Status

**Purpose:** Show Augment's indexing status for a workspace

```python
@mcp.resource(
    "augment://workspace/{workspace_path}/index-status",
    name="Index Status",
    description="Augment workspace indexing status and statistics",
    mime_type="application/json",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": False  # Status can change
    }
)
async def get_index_status(workspace_path: str) -> dict:
    """Get workspace indexing status."""
    
    workspace = Path(workspace_path)
    
    # Count files
    total_files = 0
    indexed_files = 0
    ignored_files = 0
    
    gitignore_patterns = []
    augmentignore_patterns = []
    
    # Read .gitignore
    gitignore = workspace / ".gitignore"
    if gitignore.exists():
        async with aiofiles.open(gitignore) as f:
            gitignore_patterns = [line.strip() for line in (await f.read()).splitlines() 
                                 if line.strip() and not line.startswith("#")]
    
    # Read .augmentignore
    augmentignore = workspace / ".augmentignore"
    if augmentignore.exists():
        async with aiofiles.open(augmentignore) as f:
            augmentignore_patterns = [line.strip() for line in (await f.read()).splitlines() 
                                     if line.strip() and not line.startswith("#")]
    
    return {
        "workspace": str(workspace),
        "gitignore_patterns": gitignore_patterns,
        "augmentignore_patterns": augmentignore_patterns,
        "indexing_enabled": True,
        "cache_location": str(Path.home() / ".augment" / "cache")
    }
```

**Benefits:**
- LLM understands what files are indexed
- Clients can show indexing status
- Helps debug context issues

---

### 5. Auggie CLI Capabilities

**Purpose:** Expose available Auggie CLI features

```python
@mcp.resource(
    "augment://capabilities",
    name="Auggie Capabilities",
    description="Available Auggie CLI features and tools",
    mime_type="application/json",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_auggie_capabilities() -> dict:
    """Get Auggie CLI capabilities and available tools."""
    
    return {
        "version": "1.0.0",  # Could query actual version
        "tools": [
            {"name": "view", "description": "Read file contents"},
            {"name": "str-replace-editor", "description": "Edit files"},
            {"name": "save-file", "description": "Create new files"},
            {"name": "remove-files", "description": "Delete files"},
            {"name": "codebase-retrieval", "description": "Search codebase"},
            {"name": "grep-search", "description": "Regex search"},
            {"name": "launch-process", "description": "Execute commands"},
            {"name": "github-api", "description": "GitHub operations"},
        ],
        "features": {
            "workspace_indexing": True,
            "custom_commands": True,
            "tool_permissions": True,
            "model_selection": True,
            "mcp_integration": True
        },
        "supported_models": [
            "claude-sonnet-4",
            "claude-sonnet-3.5",
            "gpt-4o",
            "gpt-4o-mini"
        ]
    }
```

**Benefits:**
- LLM knows what operations are possible
- Clients can show feature availability
- Enables capability-based UI

---

### 6. Workspace File Tree

**Purpose:** Browse workspace structure

```python
@mcp.resource(
    "augment://workspace/{workspace_path}/tree",
    name="Workspace Tree",
    description="Directory structure of the workspace",
    mime_type="application/json",
    annotations={
        "readOnlyHint": True,
        "idempotentHint": True
    }
)
async def get_workspace_tree(workspace_path: str, max_depth: int = 3) -> dict:
    """Get workspace directory tree."""
    
    def build_tree(path: Path, current_depth: int = 0) -> dict:
        if current_depth >= max_depth:
            return {"truncated": True}
        
        tree = {
            "name": path.name,
            "type": "directory" if path.is_dir() else "file",
            "path": str(path)
        }
        
        if path.is_dir():
            children = []
            try:
                for child in sorted(path.iterdir()):
                    if child.name.startswith("."):
                        continue
                    children.append(build_tree(child, current_depth + 1))
                tree["children"] = children
            except PermissionError:
                tree["error"] = "Permission denied"
        
        return tree
    
    workspace = Path(workspace_path)
    return build_tree(workspace)
```

**Benefits:**
- LLM can understand project structure
- Clients can show file browser
- Helps with navigation

---

## Implementation Plan

### Phase 1: Core Resources (High Priority)
1. ✅ Workspace settings
2. ✅ Custom commands catalog
3. ✅ Auggie capabilities

### Phase 2: Discovery Resources (Medium Priority)
4. ✅ Command details
5. ✅ Index status
6. ✅ Workspace tree

### Phase 3: Advanced Resources (Low Priority)
7. ✅ Recent Auggie runs (history)
8. ✅ Performance metrics
9. ✅ Error logs

---

## Benefits Summary

| Feature | Before | After |
|---------|--------|-------|
| **Command Discovery** | Manual documentation | Auto-discovery via resources |
| **Configuration Visibility** | Opaque | Transparent via resources |
| **Workspace Context** | Must pass explicitly | Available on-demand |
| **Caching** | None | Client-side caching |
| **Token Usage** | High (context in prompts) | Low (lazy loading) |

---

## Next Steps

1. Implement core resources in `augment_mcp/server.py`
2. Add resource tests
3. Update README with resource documentation
4. Create example client usage
5. Add resource discovery tool

