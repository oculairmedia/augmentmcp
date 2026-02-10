# MCP Capabilities Implementation Roadmap

## Vision

Transform augment-mcp-tool from a simple CLI wrapper into a **comprehensive MCP server** that exposes Augment's full capabilities through:

1. **Tools** - Active operations (review, configure, execute)
2. **Resources** - Read-only data access (settings, commands, status)
3. **Prompts** - Reusable templates (security review, refactoring, testing)

---

## Current State

### ✅ Implemented
- `augment_review` tool - Basic code review
- `augment_configure` tool - Settings management
- `augment_custom_command` tool - Custom command execution
- `augment_list_commands` tool - Command discovery

### ❌ Missing
- **Resources** - No read-only data exposure
- **Prompts** - No reusable templates
- **Workspace context** - Limited indexing support
- **Discovery** - Hard to find available capabilities

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

#### 1.1 Core Resources
```python
# Expose Augment's configuration and state
@mcp.resource("augment://capabilities")
async def get_capabilities() -> dict:
    """Available Auggie CLI features and tools"""

@mcp.resource("augment://workspace/{path}/settings")
async def get_workspace_settings(path: str) -> dict:
    """Workspace configuration and tool permissions"""

@mcp.resource("augment://workspace/{path}/commands")
async def get_custom_commands(path: str) -> dict:
    """Available custom commands for workspace"""
```

**Benefits:**
- LLMs can discover capabilities without trial-and-error
- Clients can show configuration UI
- Reduces token usage (no need to pass config in prompts)

#### 1.2 Essential Prompts
```python
# Standardize common workflows
@mcp.prompt(name="security_review")
def security_review_prompt(file_path: str, focus_areas: str = "all") -> str:
    """Generate comprehensive security review request"""

@mcp.prompt(name="generate_tests")
def generate_tests_prompt(file_path: str, test_framework: str = "pytest") -> str:
    """Generate test cases with coverage goals"""
```

**Benefits:**
- Consistent code reviews across team
- Reusable best practices
- Faster onboarding

---

### Phase 2: Discovery & Navigation (Week 2)

#### 2.1 Workspace Resources
```python
@mcp.resource("augment://workspace/{path}/tree")
async def get_workspace_tree(path: str, max_depth: int = 3) -> dict:
    """Directory structure of workspace"""

@mcp.resource("augment://workspace/{path}/index-status")
async def get_index_status(path: str) -> dict:
    """Indexing status and statistics"""

@mcp.resource("augment://command/{name}")
async def get_command_details(name: str) -> dict:
    """Detailed information about a custom command"""
```

**Benefits:**
- LLMs understand project structure
- Clients can show file browsers
- Better context for code analysis

#### 2.2 Workflow Prompts
```python
@mcp.prompt(name="refactor_code")
def refactor_code_prompt(file_path: str, goals: list[str]) -> str:
    """Generate refactoring request with specific goals"""

@mcp.prompt(name="api_design_review")
def api_design_review_prompt(file_path: str, api_type: str = "REST") -> str:
    """Review API design against best practices"""
```

**Benefits:**
- Standardized refactoring workflows
- Consistent API design reviews
- Encoded architectural knowledge

---

### Phase 3: Advanced Features (Week 3)

#### 3.1 Dynamic Resources
```python
@mcp.resource("augment://workspace/{path}/file/{file_path}")
async def get_file_with_context(path: str, file_path: str) -> dict:
    """File content with Augment context annotations"""

@mcp.resource("augment://workspace/{path}/search/{query}")
async def search_workspace(path: str, query: str) -> dict:
    """Search results using Augment's context engine"""
```

**Benefits:**
- Rich file metadata
- Powerful search capabilities
- Context-aware code navigation

#### 3.2 Specialized Prompts
```python
@mcp.prompt(name="analyze_performance")
async def analyze_performance_prompt(file_path: str, focus: str = "all") -> str:
    """Analyze code for performance issues"""

@mcp.prompt(name="generate_documentation")
def generate_documentation_prompt(file_path: str, doc_style: str = "google") -> str:
    """Generate comprehensive documentation"""

@mcp.prompt(name="create_migration_guide")
def create_migration_guide_prompt(old_version: str, new_version: str) -> list[PromptMessage]:
    """Create migration guide for breaking changes"""
```

**Benefits:**
- Performance optimization workflows
- Consistent documentation
- Smooth version migrations

---

## Integration Examples

### Example 1: Security Review Workflow

```python
# 1. Client discovers available prompts
prompts = await client.list_prompts()
# Returns: [{"name": "security_review", "description": "..."}, ...]

# 2. Client gets workspace settings to check permissions
settings = await client.read_resource("augment://workspace/my-project/settings")
# Returns: {"tool_permissions": [...], "exists": true}

# 3. Client uses prompt to generate review request
prompt = await client.get_prompt("security_review", {
    "file_path": "src/auth.py",
    "focus_areas": "auth"
})
# Returns: Structured prompt with security review instructions

# 4. Client executes review using augment_review tool
result = await client.call_tool("augment_review", {
    "instruction": prompt.messages[0].content,
    "workspace_root": "/workspace/my-project",
    "paths": ["src/auth.py"]
})
```

### Example 2: Custom Command Discovery

```python
# 1. List available commands via resource
commands = await client.read_resource("augment://workspace/my-project/commands")
# Returns: {"commands": [{"name": "security-review", "scope": "workspace"}, ...]}

# 2. Get command details
details = await client.read_resource("augment://command/security-review")
# Returns: {"description": "...", "prompt": "...", "argument_hint": "..."}

# 3. Execute command via tool
result = await client.call_tool("augment_custom_command", {
    "command_name": "security-review",
    "arguments": "src/api.py",
    "workspace_root": "/workspace/my-project"
})
```

### Example 3: Workspace Exploration

```python
# 1. Get workspace capabilities
caps = await client.read_resource("augment://capabilities")
# Returns: {"tools": [...], "features": {...}, "supported_models": [...]}

# 2. Get workspace tree
tree = await client.read_resource("augment://workspace/my-project/tree")
# Returns: {"name": "my-project", "type": "directory", "children": [...]}

# 3. Check indexing status
status = await client.read_resource("augment://workspace/my-project/index-status")
# Returns: {"gitignore_patterns": [...], "augmentignore_patterns": [...]}

# 4. Use refactoring prompt with context
prompt = await client.get_prompt("refactor_code", {
    "file_path": "src/legacy.py",
    "goals": ["readability", "testability"]
})
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Client (Claude, etc.)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ MCP Protocol
                              │
┌─────────────────────────────────────────────────────────────┐
│                   augment-mcp-tool Server                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │    Tools     │  │  Resources   │  │   Prompts    │      │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤      │
│  │ • review     │  │ • settings   │  │ • security   │      │
│  │ • configure  │  │ • commands   │  │ • refactor   │      │
│  │ • execute    │  │ • tree       │  │ • tests      │      │
│  │ • list       │  │ • status     │  │ • api-review │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Auggie CLI Integration                    │  │
│  │  • Workspace indexing                                  │  │
│  │  • Tool permissions                                    │  │
│  │  • Custom commands                                     │  │
│  │  • Context engine                                      │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ CLI invocation
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Auggie CLI                              │
│  • Codebase indexing                                         │
│  • Context retrieval                                         │
│  • Code analysis                                             │
│  • File operations                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Success Metrics

### Discoverability
- ✅ All capabilities listed via `resources/list` and `prompts/list`
- ✅ Rich metadata for each capability
- ✅ Searchable by tags

### Usability
- ✅ Consistent naming conventions
- ✅ Clear parameter descriptions
- ✅ Helpful error messages
- ✅ Usage examples in documentation

### Performance
- ✅ Resources cached by clients
- ✅ Lazy loading of expensive data
- ✅ Async operations for I/O
- ✅ Minimal token usage

### Maintainability
- ✅ Comprehensive tests
- ✅ Type hints throughout
- ✅ Clear separation of concerns
- ✅ Documented architecture

---

## Migration Path

### For Existing Users
1. **No breaking changes** - All existing tools continue to work
2. **Gradual adoption** - Can use new resources/prompts incrementally
3. **Backward compatible** - Old clients still work

### For New Users
1. **Start with prompts** - Use standardized templates
2. **Explore resources** - Discover capabilities
3. **Advanced usage** - Combine tools, resources, and prompts

---

## Next Steps

1. **Review proposals** - Get feedback on resource and prompt designs
2. **Implement Phase 1** - Core resources and essential prompts
3. **Test integration** - Verify with real MCP clients
4. **Document** - Update README with examples
5. **Iterate** - Gather feedback and refine

---

## Questions to Consider

1. **Resource URIs** - Should we use `augment://` or `resource://augment/`?
2. **Prompt naming** - Underscore (`security_review`) or dash (`security-review`)?
3. **Workspace paths** - Absolute paths or relative to server root?
4. **Caching** - Should resources include cache hints?
5. **Versioning** - How to handle breaking changes to resources/prompts?

