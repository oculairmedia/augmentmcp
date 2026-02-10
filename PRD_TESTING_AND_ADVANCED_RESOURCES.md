# Product Requirements Document: Testing & Advanced Resources

## Executive Summary

This PRD outlines the implementation of comprehensive testing infrastructure and advanced resource capabilities for augment-mcp-tool. The goal is to achieve production-grade quality through systematic testing while adding high-value features for workspace exploration and performance monitoring.

---

## 1. Objectives

### Primary Goals
1. **Achieve 90%+ test coverage** for all new resources, prompts, and tools
2. **Implement advanced resources** for file search, history, and metrics
3. **Establish testing best practices** for future development
4. **Enable CI/CD integration** with automated test execution

### Success Metrics
- ✅ All resources have unit tests
- ✅ All prompts have unit tests
- ✅ Integration tests cover end-to-end workflows
- ✅ Tests run in <30 seconds
- ✅ Zero flaky tests
- ✅ Advanced resources provide actionable insights

---

## 2. Testing Strategy

### 2.1 Testing Framework

**Primary Framework: pytest + pytest-asyncio**

**Rationale:**
- Industry standard for Python testing
- Excellent async support via pytest-asyncio
- Rich fixture ecosystem
- FastMCP examples use pytest
- Powerful parametrization capabilities

**Additional Tools:**
- `pytest-cov` - Code coverage reporting
- `pytest-mock` - Enhanced mocking capabilities
- `inline-snapshot` - Schema validation (as used in FastMCP)
- `pytest-xdist` - Parallel test execution

### 2.2 Test Categories

#### Unit Tests (Priority: HIGH)
**Scope:** Individual functions and methods in isolation

**Coverage:**
- All resource functions
- All prompt functions
- All tool functions
- Helper functions (_load_paths, _extract_command_metadata, etc.)

**Example Structure:**
```python
# tests/unit/test_resources.py
async def test_get_capabilities_returns_expected_structure():
    """Test capabilities resource returns all required fields."""
    result = await get_capabilities.fn()
    
    assert "tools" in result
    assert "prompts" in result
    assert "resources" in result
    assert "features" in result
    assert "supported_models" in result
    assert isinstance(result["tools"], list)
```

#### Integration Tests (Priority: HIGH)
**Scope:** End-to-end workflows with real Auggie CLI

**Coverage:**
- Resource → Tool workflows
- Prompt → Tool workflows
- Multi-step operations
- Error handling paths

**Example Structure:**
```python
# tests/integration/test_workflows.py
async def test_security_review_workflow(tmp_workspace):
    """Test complete security review workflow."""
    # 1. Get workspace settings
    settings = await get_workspace_settings.fn(str(tmp_workspace))
    assert settings["exists"] is False
    
    # 2. Configure permissions
    await augment_configure.fn(
        workspace_root=str(tmp_workspace),
        permissions=[{"tool-name": "view", "permission": {"type": "allow"}}],
        scope="project"
    )
    
    # 3. Use security review prompt
    prompt = await security_review_prompt.fn(
        file_path="test.py",
        focus_areas="all"
    )
    
    # 4. Execute review
    result = await augment_review.fn(
        instruction=prompt[0].content,
        workspace_root=str(tmp_workspace),
        paths=["test.py"]
    )
    
    assert "security" in result.lower()
```

#### Fixture Tests (Priority: MEDIUM)
**Scope:** Reusable test fixtures and mocks

**Coverage:**
- Fake Auggie CLI
- Temporary workspaces
- Mock file systems
- Sample configurations

---

## 3. Testing Implementation Plan

### Phase 1: Test Infrastructure (Week 1, Days 1-2)

#### 3.1 Setup Test Environment

**Files to Create:**
```
tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_resources.py       # Resource unit tests
│   ├── test_prompts.py         # Prompt unit tests
│   ├── test_tools.py           # Tool unit tests
│   └── test_helpers.py         # Helper function tests
├── integration/
│   ├── __init__.py
│   ├── test_workflows.py       # End-to-end workflows
│   └── test_error_handling.py  # Error scenarios
└── fixtures/
    ├── __init__.py
    ├── workspaces.py           # Workspace fixtures
    ├── commands.py             # Command file fixtures
    └── settings.py             # Settings file fixtures
```

#### 3.2 Core Fixtures (conftest.py)

```python
import pytest
import tempfile
from pathlib import Path
from augment_mcp.server import mcp

@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with standard structure."""
    workspace = tmp_path / "test-workspace"
    workspace.mkdir()
    
    # Create .augment directory
    augment_dir = workspace / ".augment"
    augment_dir.mkdir()
    
    # Create commands directory
    commands_dir = augment_dir / "commands"
    commands_dir.mkdir()
    
    return workspace

@pytest.fixture
def sample_settings():
    """Sample Augment settings configuration."""
    return {
        "tool-permissions": [
            {"tool-name": "view", "permission": {"type": "allow"}},
            {"tool-name": "str-replace-editor", "permission": {"type": "deny"}}
        ]
    }

@pytest.fixture
def sample_command_file(tmp_workspace):
    """Create a sample command file."""
    cmd_file = tmp_workspace / ".augment" / "commands" / "test-command.md"
    cmd_file.write_text("""---
description: Test command
tags: testing, example
---

This is a test command prompt.
""")
    return cmd_file

@pytest.fixture
async def mcp_server():
    """Provide the FastMCP server instance for testing."""
    return mcp
```

### Phase 2: Resource Tests (Week 1, Days 3-4)

#### 3.3 Resource Unit Tests

**Test Coverage:**
- ✅ get_capabilities
- ✅ get_workspace_settings
- ✅ get_custom_commands
- ✅ get_workspace_tree
- ✅ get_index_status
- ✅ get_command_details

**Example Test:**
```python
# tests/unit/test_resources.py
import pytest
from augment_mcp.server import (
    get_capabilities,
    get_workspace_settings,
    get_custom_commands,
    get_workspace_tree,
    get_index_status,
    get_command_details
)

class TestCapabilitiesResource:
    """Tests for augment://capabilities resource."""
    
    async def test_returns_all_required_fields(self):
        """Capabilities should include tools, prompts, resources, features."""
        result = await get_capabilities.fn()
        
        assert "tools" in result
        assert "prompts" in result
        assert "resources" in result
        assert "features" in result
        assert "supported_models" in result
    
    async def test_tools_list_is_populated(self):
        """Should list all registered tools."""
        result = await get_capabilities.fn()
        
        tool_names = [t["name"] for t in result["tools"]]
        assert "augment_review" in tool_names
        assert "augment_configure" in tool_names
        assert "augment_custom_command" in tool_names
    
    async def test_prompts_list_is_populated(self):
        """Should list all registered prompts."""
        result = await get_capabilities.fn()
        
        prompt_names = [p["name"] for p in result["prompts"]]
        assert "security_review" in prompt_names
        assert "refactor_code" in prompt_names
        assert "generate_tests" in prompt_names

class TestWorkspaceSettingsResource:
    """Tests for augment://workspace/{path}/settings resource."""
    
    async def test_nonexistent_settings_returns_exists_false(self, tmp_workspace):
        """Should indicate when settings file doesn't exist."""
        result = await get_workspace_settings.fn(str(tmp_workspace))
        
        assert result["exists"] is False
        assert result["workspace"] == str(tmp_workspace)
        assert "settings_file" in result
    
    async def test_existing_settings_returns_data(self, tmp_workspace, sample_settings):
        """Should return settings data when file exists."""
        import json
        settings_file = tmp_workspace / ".augment" / "settings.json"
        settings_file.write_text(json.dumps(sample_settings))
        
        result = await get_workspace_settings.fn(str(tmp_workspace))
        
        assert result["exists"] is True
        assert result["tool_permissions"] == sample_settings["tool-permissions"]
        assert result["settings"] == sample_settings
    
    async def test_invalid_json_raises_resource_error(self, tmp_workspace):
        """Should raise ResourceError for malformed JSON."""
        from fastmcp.exceptions import ResourceError
        
        settings_file = tmp_workspace / ".augment" / "settings.json"
        settings_file.write_text("{ invalid json }")
        
        with pytest.raises(ResourceError):
            await get_workspace_settings.fn(str(tmp_workspace))

class TestCustomCommandsResource:
    """Tests for augment://workspace/{path}/commands resource."""
    
    async def test_empty_workspace_returns_empty_list(self, tmp_workspace):
        """Should return empty commands list for new workspace."""
        result = await get_custom_commands.fn(str(tmp_workspace))
        
        assert result["total"] == 0
        assert result["commands"] == []
    
    async def test_finds_workspace_commands(self, tmp_workspace, sample_command_file):
        """Should discover commands in workspace .augment/commands."""
        result = await get_custom_commands.fn(str(tmp_workspace))
        
        assert result["total"] == 1
        assert result["commands"][0]["name"] == "test-command"
        assert result["commands"][0]["scope"] == "workspace"
    
    async def test_parses_command_metadata(self, tmp_workspace, sample_command_file):
        """Should extract frontmatter metadata from command files."""
        result = await get_custom_commands.fn(str(tmp_workspace))
        
        cmd = result["commands"][0]
        assert cmd["description"] == "Test command"
        assert "testing" in cmd["tags"]
        assert "example" in cmd["tags"]
```

### Phase 3: Prompt Tests (Week 1, Day 5)

#### 3.4 Prompt Unit Tests

**Test Coverage:**
- ✅ security_review
- ✅ refactor_code
- ✅ generate_tests
- ✅ api_design_review
- ✅ analyze_performance

**Example Test:**
```python
# tests/unit/test_prompts.py
import pytest
from augment_mcp.server import (
    security_review_prompt,
    refactor_code_prompt,
    generate_tests_prompt,
    api_design_review_prompt,
    analyze_performance_prompt
)

class TestSecurityReviewPrompt:
    """Tests for security_review prompt."""
    
    async def test_generates_valid_message_list(self):
        """Should return list of Message objects."""
        result = await security_review_prompt.fn(
            file_path="test.py",
            focus_areas="all"
        )
        
        assert isinstance(result, list)
        assert len(result) > 0
        assert hasattr(result[0], "role")
        assert hasattr(result[0], "content")
    
    async def test_includes_file_path_in_content(self):
        """Should mention the target file in prompt."""
        result = await security_review_prompt.fn(
            file_path="src/auth.py",
            focus_areas="all"
        )
        
        content = result[0].content
        assert "src/auth.py" in content
    
    async def test_focus_areas_all_includes_comprehensive_checks(self):
        """Should include all security areas when focus='all'."""
        result = await security_review_prompt.fn(
            file_path="test.py",
            focus_areas="all"
        )
        
        content = result[0].content.lower()
        assert "sql injection" in content
        assert "cross-site scripting" in content
        assert "authentication" in content
        assert "cryptograph" in content
    
    async def test_focus_areas_auth_filters_checks(self):
        """Should focus only on auth when focus='auth'."""
        result = await security_review_prompt.fn(
            file_path="test.py",
            focus_areas="auth"
        )
        
        content = result[0].content.lower()
        assert "authentication" in content
        assert "authorization" in content
    
    async def test_severity_threshold_included(self):
        """Should mention severity threshold in prompt."""
        result = await security_review_prompt.fn(
            file_path="test.py",
            severity_threshold="high"
        )
        
        content = result[0].content
        assert "high" in content.lower()
```

### Phase 4: Integration Tests (Week 2, Days 1-2)

#### 3.5 End-to-End Workflow Tests

```python
# tests/integration/test_workflows.py
import pytest
from augment_mcp.server import (
    get_capabilities,
    get_workspace_settings,
    security_review_prompt,
    augment_configure,
    augment_review
)

class TestSecurityReviewWorkflow:
    """Integration tests for complete security review workflow."""
    
    async def test_discover_configure_review_workflow(self, tmp_workspace):
        """Test full workflow: discover → configure → review."""
        # Step 1: Discover capabilities
        caps = await get_capabilities.fn()
        assert "security_review" in [p["name"] for p in caps["prompts"]]
        
        # Step 2: Check workspace settings
        settings = await get_workspace_settings.fn(str(tmp_workspace))
        assert settings["exists"] is False
        
        # Step 3: Configure read-only permissions
        config_result = await augment_configure.fn(
            workspace_root=str(tmp_workspace),
            permissions=[
                {"tool-name": "view", "permission": {"type": "allow"}},
                {"tool-name": "codebase-retrieval", "permission": {"type": "allow"}},
                {"tool-name": "str-replace-editor", "permission": {"type": "deny"}}
            ],
            scope="project"
        )
        assert "Configured tool permissions" in config_result
        
        # Step 4: Verify settings were written
        settings = await get_workspace_settings.fn(str(tmp_workspace))
        assert settings["exists"] is True
        assert len(settings["tool_permissions"]) == 3
        
        # Step 5: Generate security review prompt
        prompt = await security_review_prompt.fn(
            file_path="src/auth.py",
            focus_areas="auth",
            severity_threshold="medium"
        )
        assert "authentication" in prompt[0].content.lower()
        
        # Step 6: Execute review (with fake Auggie)
        # This would call actual Auggie in real integration test
        # For now, we verify the call structure
        assert prompt[0].role == "user"
        assert "src/auth.py" in prompt[0].content
```

---

## 4. Advanced Resources Implementation

### 4.1 File Search Resource

**Resource URI:** `augment://workspace/{workspace_path}/search/{query}`

**Purpose:** Search workspace files using Augment's context engine

**Implementation:**
```python
@mcp.resource(
    "augment://workspace/{workspace_path}/search/{query}",
    name="Workspace Search",
    description="Search files in workspace using Augment context engine",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False}
)
async def search_workspace(workspace_path: str, query: str, max_results: int = 20) -> dict[str, Any]:
    """Search workspace files using grep or Augment's search."""
    # Implementation details in next section
```

### 4.2 Auggie Run History Resource

**Resource URI:** `augment://history/runs`

**Purpose:** Track recent Auggie CLI invocations for debugging

**Implementation:**
```python
@mcp.resource(
    "augment://history/runs",
    name="Auggie Run History",
    description="Recent Auggie CLI invocations and their results",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False}
)
async def get_auggie_history(limit: int = 50) -> dict[str, Any]:
    """Return recent Auggie CLI runs from history file."""
    # Implementation details in next section
```

### 4.3 Performance Metrics Resource

**Resource URI:** `augment://metrics/performance`

**Purpose:** Expose performance statistics for monitoring

**Implementation:**
```python
@mcp.resource(
    "augment://metrics/performance",
    name="Performance Metrics",
    description="Server performance metrics and statistics",
    mime_type="application/json",
    annotations={"readOnlyHint": True, "idempotentHint": False}
)
async def get_performance_metrics() -> dict[str, Any]:
    """Return performance metrics for the MCP server."""
    # Implementation details in next section
```

---

## 5. Testing Best Practices (from FastMCP examples)

### 5.1 Atomic Tests
✅ **DO:** Test one behavior per test function
```python
async def test_tool_registration():
    """Test that tools are properly registered."""
    tools = mcp.list_tools()
    assert len(tools) == 1
```

❌ **DON'T:** Test multiple behaviors in one test
```python
async def test_server_functionality():
    # Tests tools, resources, AND auth - too much!
    assert mcp.list_tools()
    assert mcp.list_resources()
    assert mcp.auth is not None
```

### 5.2 Use Inline Snapshots for Complex Schemas
```python
from inline_snapshot import snapshot

async def test_tool_schema():
    tools = mcp.list_tools()
    schema = tools[0].inputSchema
    
    assert schema == snapshot({
        "type": "object",
        "properties": {...},
        "required": [...]
    })
```

### 5.3 Fixture-Based Testing
```python
@pytest.fixture
async def weather_server():
    mcp = FastMCP("weather")
    
    @mcp.tool
    def get_temperature(city: str) -> dict:
        return {"city": city, "temp": 85}
    
    return mcp

async def test_temperature_tool(weather_server):
    async with Client(weather_server) as client:
        result = await client.call_tool("get_temperature", {"city": "LA"})
        assert result.data == {"city": "LA", "temp": 85}
```

---

## 6. Deliverables

### Week 1
- ✅ Test infrastructure setup (conftest.py, fixtures)
- ✅ All resource unit tests
- ✅ All prompt unit tests
- ✅ Helper function tests
- ✅ Coverage report showing 90%+

### Week 2
- ✅ Integration tests for workflows
- ✅ Error handling tests
- ✅ Advanced resources implemented
- ✅ Advanced resource tests
- ✅ CI/CD configuration (GitHub Actions)

---

## 7. Success Criteria

- [ ] 90%+ code coverage
- [ ] All tests pass consistently
- [ ] Tests run in <30 seconds
- [ ] Zero flaky tests
- [ ] CI/CD pipeline configured
- [ ] Advanced resources functional
- [ ] Documentation updated

---

## 8. Next Steps

1. Review and approve this PRD
2. Set up test infrastructure
3. Implement resource tests
4. Implement prompt tests
5. Implement integration tests
6. Implement advanced resources
7. Configure CI/CD
8. Update documentation

