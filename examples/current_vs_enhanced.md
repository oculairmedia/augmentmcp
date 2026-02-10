# Current vs Enhanced Implementation Examples

## Example 1: Code Review

### Current Implementation ❌
```python
# Limited context - only what you explicitly pass
result = await augment_review(
    instruction="Review this code for security issues",
    paths=["src/auth.py"],
)
```

**Limitations:**
- Auggie only sees `src/auth.py`
- No knowledge of project structure
- Can't reference related files
- No access to coding standards
- Can't use codebase-retrieval tool

### Enhanced Implementation ✅
```python
# Full codebase context via workspace indexing
result = await augment_review(
    instruction="Review this code for security issues",
    workspace_root="/opt/stacks/my-project",
    paths=["src/auth.py"],
)
```

**Benefits:**
- Auggie indexes entire codebase
- Can reference related authentication code
- Understands project patterns
- Can suggest improvements based on existing code
- Uses codebase-retrieval for context

---

## Example 2: Security-Controlled Review

### Current Implementation ❌
```python
# No security controls - Auggie can do anything
result = await augment_review(
    instruction="Fix the authentication bug",
    paths=["src/auth.py"],
)
```

**Risks:**
- Auggie might modify files
- Could delete code
- Might run dangerous commands
- No audit trail

### Enhanced Implementation ✅
```python
# Step 1: Configure read-only permissions
await augment_configure(
    workspace_root="/opt/stacks/my-project",
    permissions=[
        {"tool-name": "view", "permission": {"type": "allow"}},
        {"tool-name": "codebase-retrieval", "permission": {"type": "allow"}},
        {"tool-name": "str-replace-editor", "permission": {"type": "deny"}},
        {"tool-name": "save-file", "permission": {"type": "deny"}},
        {"tool-name": "remove-files", "permission": {"type": "deny"}},
        {"tool-name": "launch-process", "permission": {"type": "deny"}},
    ],
    scope="project",
)

# Step 2: Safe review with enforced permissions
result = await augment_review(
    instruction="Analyze the authentication bug and suggest fixes",
    workspace_root="/opt/stacks/my-project",
    paths=["src/auth.py"],
)
```

**Benefits:**
- Auggie can only read, not modify
- Safe for production code review
- Enforced at CLI level
- Audit trail in settings.json

---

## Example 3: Custom Workflows

### Current Implementation ❌
```python
# Manual, repetitive instructions
result = await augment_review(
    instruction="""
    Review this code following our standards:
    1. Check for SQL injection vulnerabilities
    2. Verify input validation
    3. Check authentication/authorization
    4. Review error handling
    5. Check logging practices
    """,
    paths=["src/api/users.py"],
)
```

**Problems:**
- Repetitive prompt engineering
- Inconsistent reviews across team
- No standardization
- Hard to maintain

### Enhanced Implementation ✅
```python
# Step 1: Create custom command (one-time setup)
# File: .augment/commands/security-review.md
"""
---
description: Security review following company standards
argument-hint: [file-path]
---

Review the code for security issues following our standards:

1. SQL Injection: Check all database queries use parameterized statements
2. Input Validation: Verify all user inputs are validated and sanitized
3. Authentication: Ensure proper authentication checks
4. Authorization: Verify role-based access control
5. Error Handling: Check errors don't leak sensitive information
6. Logging: Verify sensitive data is not logged
7. Cryptography: Check proper use of approved crypto libraries
"""

# Step 2: Use the custom command
result = await augment_custom_command(
    command_name="security-review",
    arguments="src/api/users.py",
    workspace_root="/opt/stacks/my-project",
)
```

**Benefits:**
- Consistent reviews across team
- Reusable workflow
- Version controlled in repo
- Easy to update standards

---

## Example 4: Model Selection

### Current Implementation ❌
```python
# Always uses default model (expensive for simple tasks)
result = await augment_review(
    instruction="Count the number of functions in this file",
    paths=["src/utils.py"],
)
```

**Problems:**
- Wastes expensive model on simple task
- Slower response time
- Higher costs

### Enhanced Implementation ✅
```python
# Use cheaper/faster model for simple tasks
result = await augment_review(
    instruction="Count the number of functions in this file",
    paths=["src/utils.py"],
    model="gpt-4o-mini",  # Faster, cheaper for simple tasks
)

# Use powerful model for complex analysis
result = await augment_review(
    instruction="Refactor this code to improve performance",
    workspace_root="/opt/stacks/my-project",
    paths=["src/core/engine.py"],
    model="claude-sonnet-4",  # More powerful for complex tasks
)
```

**Benefits:**
- Cost optimization
- Faster responses for simple tasks
- Better results for complex tasks

---

## Example 5: Team Collaboration

### Current Implementation ❌
```python
# Each developer writes their own prompts
# No consistency, no sharing
```

### Enhanced Implementation ✅
```python
# Step 1: List available team commands
commands = await augment_list_commands(
    workspace_root="/opt/stacks/my-project"
)
# Returns:
# - security-review: Security review following company standards
# - performance-check: Analyze code for performance issues
# - test-coverage: Check test coverage and suggest improvements
# - api-design: Review API design against REST best practices

# Step 2: Use team-standardized workflows
result = await augment_custom_command(
    command_name="api-design",
    arguments="src/api/v2/endpoints.py",
    workspace_root="/opt/stacks/my-project",
)
```

**Benefits:**
- Shared knowledge across team
- Consistent code quality
- Onboarding new developers easier
- Best practices encoded in commands

---

## Example 6: CI/CD Integration

### Current Implementation ❌
```python
# Unsafe for CI/CD - no restrictions
result = await augment_review(
    instruction="Review PR changes",
    paths=changed_files,
)
```

**Risks:**
- Could modify code in CI
- Could delete files
- Could run arbitrary commands
- Security nightmare

### Enhanced Implementation ✅
```python
# Step 1: Configure CI/CD-safe permissions
await augment_configure(
    workspace_root=os.environ["CI_PROJECT_DIR"],
    permissions=[
        # Allow read operations
        {"tool-name": "view", "permission": {"type": "allow"}},
        {"tool-name": "codebase-retrieval", "permission": {"type": "allow"}},
        {"tool-name": "grep-search", "permission": {"type": "allow"}},
        
        # Allow safe test commands
        {
            "tool-name": "launch-process",
            "shell-input-regex": "^(npm test|npm run lint|pytest)\\s",
            "permission": {"type": "allow"}
        },
        
        # Deny everything else
        {"tool-name": "str-replace-editor", "permission": {"type": "deny"}},
        {"tool-name": "save-file", "permission": {"type": "deny"}},
        {"tool-name": "remove-files", "permission": {"type": "deny"}},
        {"tool-name": "launch-process", "permission": {"type": "deny"}},
    ],
    scope="project",
)

# Step 2: Safe PR review
result = await augment_review(
    instruction="Review PR changes and run tests",
    workspace_root=os.environ["CI_PROJECT_DIR"],
    paths=changed_files,
)
```

**Benefits:**
- Safe for automated workflows
- Can't modify code
- Can run approved test commands
- Audit trail for compliance

---

## Summary

| Feature | Current | Enhanced | Benefit |
|---------|---------|----------|---------|
| Workspace Context | ❌ | ✅ | Better code understanding |
| Tool Permissions | ❌ | ✅ | Security & compliance |
| Custom Commands | ❌ | ✅ | Team standardization |
| Model Selection | ❌ | ✅ | Cost & performance optimization |
| CI/CD Safety | ❌ | ✅ | Production-ready automation |

The enhanced implementation unlocks Augment's **superior indexing capabilities** and makes the tool production-ready for enterprise use.

