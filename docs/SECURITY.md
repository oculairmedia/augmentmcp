# Augment Security Guidelines

Augment exposes powerful tools that can modify files and launch processes. When running
Augment in CI/CD pipelines or shared review environments, apply the principle of least
privilege.

## Recommended Read-Only Permissions

For most review-only scenarios, configure Augment with read-only access:

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

Use the `augment_configure` tool with `scope="project"` to write this JSON to
`<workspace>/.augment/settings.json` so permissions travel with your repository. For
personal overrides, set `scope="user"` to write to `~/.augment/settings.json`.

## CI/CD Considerations

When Augment runs in automation, limit the `launch-process` permission to a safelist of CI
commands such as unit tests or linters. Example:

```json
{
  "tool-permissions": [
    {"tool-name": "view", "permission": {"type": "allow"}},
    {"tool-name": "codebase-retrieval", "permission": {"type": "allow"}},
    {"tool-name": "grep-search", "permission": {"type": "allow"}},
    {
      "tool-name": "launch-process",
      "shell-input-regex": "^(npm test|npm run lint|pytest)\\s",
      "permission": {"type": "allow"}
    },
    {"tool-name": "launch-process", "permission": {"type": "deny"}},
    {"tool-name": "str-replace-editor", "permission": {"type": "deny"}},
    {"tool-name": "save-file", "permission": {"type": "deny"}},
    {"tool-name": "remove-files", "permission": {"type": "deny"}}
  ]
}
```

Mount project directories read-only in containers unless Augment needs write access for a
specific workflow.

## Audit and Change Control

- Store `.augment/settings.json` under version control for team visibility.
- Review permission changes through pull requests.
- Document approved commands in `docs/CUSTOM_COMMANDS.md` to help auditors understand
  available workflows.
