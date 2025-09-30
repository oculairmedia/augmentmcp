# Augment Custom Commands

Augment supports reusable slash commands stored in `.augment/commands`. Each command file
is a Markdown document with a YAML header describing the command metadata followed by the
prompt body. For example:

```
.augment/
  commands/
    security-review.md
    performance-check.md
```

Example command (`.augment/commands/security-review.md`):

```markdown
---
command-name: security-review
description: Security review following company standards
argument-hint: [file-path]
---

Review the code following our security checklist:
1. SQL injection and database access
2. Input validation and sanitisation
3. Authentication/authorisation flows
4. Error handling and logging
5. Dependency and secrets management
```

## Listing Commands

Call `augment_list_commands(workspace_root="/path/to/workspace")` to see all commands
available to the current workspace.

## Running Commands

Use `augment_custom_command` with the command name and any arguments:

```python
await augment_custom_command(
    command_name="security-review",
    arguments="src/api/users.py",
    workspace_root="/path/to/workspace",
)
```

Augment loads the workspace index (when provided) and runs the command using the same
permissions configured via `augment_configure`.

Keep commands under version control so the whole team benefits from the same curated
workflows.
