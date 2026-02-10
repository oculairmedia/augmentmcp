# MCP Prompts Implementation Proposal

## Overview

MCP Prompts provide **reusable, parameterized message templates** that help LLMs generate structured responses. They're perfect for standardizing common Augment workflows and making them easily accessible to any MCP client.

## Why Prompts Are Perfect for Augment

### Current Limitations
- Users must manually craft instructions for common tasks
- No standardization across team members
- Repetitive prompt engineering
- Hard to maintain consistency
- No discoverability of best practices

### Prompts Enable
- **Reusable templates** - Define once, use everywhere
- **Parameterization** - Customize for specific contexts
- **Discovery** - Clients can list available prompts
- **Consistency** - Standardized workflows across team
- **Best practices** - Encode expert knowledge in templates

---

## Proposed Prompts

### 1. Security Review Prompt

**Purpose:** Generate comprehensive security review requests

```python
@mcp.prompt(
    name="security_review",
    description="Generate a comprehensive security review request for code",
    tags={"security", "review", "code-quality"}
)
def security_review_prompt(
    file_path: str,
    focus_areas: str = "all",
    severity_threshold: str = "medium"
) -> str:
    """Generate a security-focused code review request.
    
    Args:
        file_path: Path to the file to review
        focus_areas: Comma-separated list (sql-injection, xss, auth, crypto, all)
        severity_threshold: Minimum severity to report (low, medium, high, critical)
    """
    
    focus_map = {
        "all": [
            "SQL injection vulnerabilities",
            "Cross-site scripting (XSS)",
            "Authentication and authorization flaws",
            "Cryptographic weaknesses",
            "Input validation issues",
            "Error handling and information disclosure",
            "Secure coding best practices"
        ],
        "sql-injection": ["SQL injection vulnerabilities", "Parameterized queries"],
        "xss": ["Cross-site scripting (XSS)", "Output encoding"],
        "auth": ["Authentication", "Authorization", "Session management"],
        "crypto": ["Cryptographic operations", "Key management", "Secure random generation"]
    }
    
    areas = focus_map.get(focus_areas, focus_map["all"])
    areas_text = "\n".join(f"- {area}" for area in areas)
    
    return f"""Please perform a comprehensive security review of the file: {file_path}

Focus on the following areas:
{areas_text}

Report findings with severity level {severity_threshold} or higher.

For each issue found, provide:
1. Severity level (low/medium/high/critical)
2. Specific line numbers
3. Description of the vulnerability
4. Potential impact
5. Recommended fix with code example

Use the workspace context to understand the broader application architecture and identify issues that might not be apparent from this file alone."""
```

**Usage:**
```python
# Client calls: prompts/get with name="security_review"
# Arguments: {"file_path": "src/auth.py", "focus_areas": "auth"}
```

---

### 2. Code Refactoring Prompt

**Purpose:** Generate structured refactoring requests

```python
@mcp.prompt(
    name="refactor_code",
    description="Generate a code refactoring request with specific goals",
    tags={"refactoring", "code-quality", "maintenance"}
)
def refactor_code_prompt(
    file_path: str,
    goals: list[str] = Field(
        default=["readability", "performance"],
        description='JSON array of goals: ["readability", "performance", "testability", "maintainability"]'
    ),
    preserve_behavior: bool = True
) -> str:
    """Generate a refactoring request with specific improvement goals.
    
    Args:
        file_path: Path to the file to refactor
        goals: List of refactoring goals
        preserve_behavior: Whether to maintain exact current behavior
    """
    
    goal_descriptions = {
        "readability": "Improve code clarity and readability",
        "performance": "Optimize for better performance",
        "testability": "Make code more testable",
        "maintainability": "Improve long-term maintainability",
        "modularity": "Increase modularity and separation of concerns"
    }
    
    goals_text = "\n".join(f"- {goal_descriptions.get(g, g)}" for g in goals)
    behavior_note = "CRITICAL: Preserve exact current behavior - this is a refactoring, not a feature change." if preserve_behavior else "You may modify behavior if it improves the code."
    
    return f"""Please refactor the code in: {file_path}

Refactoring Goals:
{goals_text}

{behavior_note}

For each change:
1. Explain what you're changing and why
2. Show before/after code snippets
3. Highlight any potential risks
4. Suggest tests to verify behavior is preserved

Use the codebase context to ensure refactoring aligns with existing patterns and conventions."""
```

---

### 3. Test Generation Prompt

**Purpose:** Generate comprehensive test requests

```python
@mcp.prompt(
    name="generate_tests",
    description="Generate test cases for code with specific coverage goals",
    tags={"testing", "quality-assurance", "tdd"}
)
def generate_tests_prompt(
    file_path: str,
    test_framework: str = "pytest",
    coverage_target: int = 80,
    include_edge_cases: bool = True
) -> list[PromptMessage]:
    """Generate comprehensive test cases for code.
    
    Args:
        file_path: Path to the file to test
        test_framework: Testing framework (pytest, unittest, jest, etc.)
        coverage_target: Target code coverage percentage
        include_edge_cases: Whether to include edge case tests
    """
    
    system_msg = Message(
        role="system",
        content=f"You are an expert in {test_framework} and test-driven development. Generate comprehensive, maintainable tests."
    )
    
    edge_case_note = """
Include edge cases such as:
- Boundary conditions
- Null/empty inputs
- Invalid inputs
- Error conditions
- Concurrent access (if applicable)
""" if include_edge_cases else ""
    
    user_msg = Message(
        role="user",
        content=f"""Generate comprehensive {test_framework} tests for: {file_path}

Requirements:
- Target {coverage_target}% code coverage
- Follow {test_framework} best practices
- Use descriptive test names
- Include docstrings explaining what each test verifies
{edge_case_note}

For each function/method:
1. Test happy path scenarios
2. Test error conditions
3. Test boundary conditions
4. Mock external dependencies appropriately

Use the codebase context to understand dependencies and create appropriate mocks/fixtures."""
    )
    
    return [system_msg, user_msg]
```

---

### 4. API Design Review Prompt

**Purpose:** Review API design against best practices

```python
@mcp.prompt(
    name="api_design_review",
    description="Review API design for REST/GraphQL best practices",
    tags={"api", "design", "review", "rest", "graphql"}
)
def api_design_review_prompt(
    file_path: str,
    api_type: str = "REST",
    standards: str = "OpenAPI 3.0"
) -> str:
    """Generate an API design review request.
    
    Args:
        file_path: Path to API definition or implementation
        api_type: Type of API (REST, GraphQL, gRPC)
        standards: Standards to check against
    """
    
    rest_checks = """
- HTTP method usage (GET, POST, PUT, DELETE, PATCH)
- Resource naming conventions
- URL structure and hierarchy
- Status code appropriateness
- Request/response payload design
- Pagination, filtering, sorting
- Versioning strategy
- Error response format
- Authentication/authorization headers
"""
    
    graphql_checks = """
- Schema design and type definitions
- Query/mutation naming
- Field naming conventions
- Pagination (cursor vs offset)
- Error handling
- N+1 query prevention
- Batching and caching strategies
"""
    
    checks = rest_checks if api_type == "REST" else graphql_checks
    
    return f"""Please review the {api_type} API design in: {file_path}

Check against {standards} standards:
{checks}

For each issue:
1. Describe the problem
2. Explain why it matters
3. Provide a concrete example of the fix
4. Reference relevant standards/best practices

Use the codebase context to ensure consistency with existing API patterns."""
```

---

### 5. Performance Analysis Prompt

**Purpose:** Generate performance analysis requests

```python
@mcp.prompt(
    name="analyze_performance",
    description="Analyze code for performance issues and optimization opportunities",
    tags={"performance", "optimization", "profiling"}
)
async def analyze_performance_prompt(
    file_path: str,
    focus: str = "all",
    ctx: Context = None
) -> str:
    """Generate a performance analysis request.
    
    Args:
        file_path: Path to the file to analyze
        focus: Focus area (all, database, algorithms, memory, network)
    """
    
    focus_areas = {
        "all": "all performance aspects",
        "database": "database queries and ORM usage",
        "algorithms": "algorithmic complexity and data structures",
        "memory": "memory usage and garbage collection",
        "network": "network calls and I/O operations"
    }
    
    focus_text = focus_areas.get(focus, focus)
    
    return f"""Please analyze the performance of: {file_path}

Focus on: {focus_text}

Identify:
1. Performance bottlenecks
2. Inefficient algorithms (analyze time/space complexity)
3. Unnecessary computations
4. Memory leaks or excessive allocations
5. N+1 query problems
6. Blocking I/O operations

For each issue:
- Explain the performance impact
- Estimate the improvement potential
- Provide optimized code examples
- Suggest profiling approaches to verify improvements

Use the codebase context to understand usage patterns and identify real-world performance impacts."""
```

---

### 6. Documentation Generation Prompt

**Purpose:** Generate comprehensive documentation

```python
@mcp.prompt(
    name="generate_documentation",
    description="Generate comprehensive documentation for code",
    tags={"documentation", "comments", "docstrings"}
)
def generate_documentation_prompt(
    file_path: str,
    doc_style: str = "google",
    include_examples: bool = True,
    audience: str = "developers"
) -> str:
    """Generate documentation for code.
    
    Args:
        file_path: Path to the file to document
        doc_style: Documentation style (google, numpy, sphinx, jsdoc)
        include_examples: Whether to include usage examples
        audience: Target audience (developers, api-users, end-users)
    """
    
    examples_note = """
Include usage examples for:
- Common use cases
- Edge cases
- Error handling
""" if include_examples else ""
    
    audience_notes = {
        "developers": "Focus on implementation details, parameters, return values, and exceptions.",
        "api-users": "Focus on public API, usage patterns, and integration examples.",
        "end-users": "Focus on high-level functionality and user-facing features."
    }
    
    return f"""Please generate comprehensive documentation for: {file_path}

Requirements:
- Use {doc_style} documentation style
- Target audience: {audience}
- {audience_notes.get(audience, '')}
{examples_note}

For each function/class:
1. Clear description of purpose
2. Parameter descriptions with types
3. Return value description
4. Exceptions that may be raised
5. Usage examples (if applicable)
6. Notes about side effects or important behavior

Use the codebase context to ensure documentation is consistent with project conventions."""
```

---

### 7. Migration Guide Prompt

**Purpose:** Generate migration guides for breaking changes

```python
@mcp.prompt(
    name="create_migration_guide",
    description="Create a migration guide for API or dependency changes",
    tags={"migration", "breaking-changes", "upgrade"}
)
def create_migration_guide_prompt(
    old_version: str,
    new_version: str,
    component: str,
    breaking_changes: str
) -> list[PromptMessage]:
    """Generate a migration guide for version upgrades.
    
    Args:
        old_version: Current version
        new_version: Target version
        component: Component being upgraded (library, API, framework)
        breaking_changes: Description of breaking changes
    """
    
    return [
        Message(
            role="system",
            content="You are a technical writer creating clear, actionable migration guides."
        ),
        Message(
            role="user",
            content=f"""Create a migration guide for upgrading {component} from {old_version} to {new_version}.

Breaking changes:
{breaking_changes}

The guide should include:
1. Overview of changes and why they were made
2. Step-by-step migration instructions
3. Before/after code examples
4. Common pitfalls and how to avoid them
5. Testing recommendations
6. Rollback procedures

Use the codebase context to provide specific examples from our codebase showing how to migrate actual usage patterns."""
        )
    ]
```

---

## Implementation Plan

### Phase 1: Code Quality Prompts (High Priority)
1. ✅ Security review
2. ✅ Code refactoring
3. ✅ Test generation

### Phase 2: Design & Architecture (Medium Priority)
4. ✅ API design review
5. ✅ Performance analysis
6. ✅ Documentation generation

### Phase 3: Maintenance & Operations (Low Priority)
7. ✅ Migration guides
8. ✅ Dependency updates
9. ✅ Code cleanup

---

## Benefits Summary

| Feature | Before | After |
|---------|--------|-------|
| **Consistency** | Manual prompts vary | Standardized templates |
| **Discoverability** | Hidden knowledge | Listed in prompts/list |
| **Reusability** | Copy-paste prompts | Parameterized templates |
| **Best Practices** | Tribal knowledge | Encoded in prompts |
| **Onboarding** | Learn by osmosis | Discover via MCP |

---

## Integration with Resources

Prompts and Resources work together:

```python
# Resource exposes available custom commands
@mcp.resource("augment://commands")
async def list_commands() -> dict:
    return {"commands": [...]}

# Prompt uses that resource to generate requests
@mcp.prompt
async def use_custom_command(command_name: str, ctx: Context) -> str:
    # Could fetch command details from resource
    commands = await ctx.read_resource("augment://commands")
    # Generate prompt using command metadata
    return f"Execute command: {command_name}"
```

---

## Next Steps

1. Implement core prompts in `augment_mcp/server.py`
2. Add prompt tests
3. Update README with prompt documentation
4. Create prompt catalog resource
5. Add prompt discovery tool

