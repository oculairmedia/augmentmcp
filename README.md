# Augment FastMCP Server

This project provides a [FastMCP](https://pypi.org/project/fastmcp/) server that exposes
Augment's Auggie CLI over the MCP protocol. It allows other MCP-compatible agents to
invoke Auggie for code reviews, contextual analysis, and reusable workflows via HTTP
transport.

## Features

- HTTP-hosted FastMCP server (`augment_review` tool)
- Streams file contents and additional context to Auggie
- Workspace-aware indexing via `workspace_root`
- Optional model selection for cost/performance tuning
- Enforced tool permissions with `augment_configure`
- Reusable slash commands via `augment_custom_command` and discovery with
  `augment_list_commands`
- Discoverable MCP prompts for common review workflows
- Read-only resources exposing Augment settings and command catalogs
- Graceful handling of timeouts, cancellations, and CLI errors

## Prerequisites

- Python 3.11 or later
- Node.js 22 or later (required for Auggie CLI)
- Auggie CLI installed globally

## Setup

1. **Install Auggie CLI**

   ```bash
   npm install -g @augmentcode/auggie
   ```

2. **Authenticate Auggie**

   ```bash
   auggie --login
   AUGMENT_SESSION_AUTH="$(auggie --print-augment-token)"
   export AUGMENT_SESSION_AUTH
   ```

   Optionally set `AUGGIE_PATH` if the binary is not on your `PATH`.

3. **Install Python dependencies**

   ```bash
   pip install -r requirements.txt
   ```

## Running the server

```bash
export AUGMENT_SESSION_AUTH="<token>"
python3 -m augment_mcp.server
```

Environment variables:

- `AUGMENT_MCP_HOST` (default `127.0.0.1`)
- `AUGMENT_MCP_PORT` (default `8000`)
- `AUGMENT_MCP_LOG_LEVEL` (default `INFO`)
- `AUGGIE_PATH` (optional path to Auggie binary)

The server listens via HTTP transport, making it easy to connect from clients that
support the Streamable HTTP MCP protocol.

### Docker

Build the container image and run it with access to `/opt/stacks` (mounted into the
container at the same path) so Auggie can reference local files if needed:

```bash
docker build -t augment-mcp .

docker run --rm \
  -e AUGMENT_SESSION_AUTH="<token>" \
  -e AUGMENT_MCP_PORT="8000" \
  -p 8000:8000 \
  -v /opt/stacks:/opt/stacks \
  augment-mcp
```

Override `AUGMENT_MCP_HOST`/`PORT` to match your deployment target. The container
exposes port `8000` by default and starts the FastMCP HTTP server immediately.

#### Docker Compose

To use the included `docker-compose.yml` (binds port `503` on host and container):

1. Create a `.env` file adjacent to `docker-compose.yml` with your Augment token:

   ```dotenv
   AUGMENT_SESSION_AUTH=<token-json>
   ```

2. Start the stack:

   ```bash
   docker compose up --build
   ```

The compose file loads environment variables from `.env`, mounts `/opt/stacks` into the
container, sets the server to listen on port `503`, and keeps the service running until
stopped.

### Example Claude Desktop configuration

```json
{
  "mcpServers": {
    "augment": {
      "command": "python3",
      "args": ["-m", "augment_mcp.server"],
      "env": {
        "AUGMENT_SESSION_AUTH": "<token>",
        "AUGMENT_MCP_HOST": "127.0.0.1",
        "AUGMENT_MCP_PORT": "8000"
      }
    },
    "Context 7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    },
    "Sequential thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
  }
}
```

The additional MCP servers above provide Auggie with advanced semantic search (Context7)
and guided reasoning utilities (Sequential Thinking). They are optional but recommended for
rich project context and structured analysis.

## Tool Reference

### `augment_review`

| Parameter | Type | Description |
|-----------|------|-------------|
| `instruction` | string (required) | Prompt passed to Auggie via `--print` |
| `context` | string | Additional raw text piped to Auggie stdin |
| `paths` | list[string] | Files whose contents are streamed to Auggie with headers |
| `workspace_root` | string | Enables Augment's codebase indexing for richer context |
| `model` | string | Override the Auggie model used for the request |
| `compact` | bool | Adds the `--compact` flag |
| `github_api_token` | string | Overrides GitHub auth for the request |
| `timeout_ms` | int | Aborts Auggie after the specified milliseconds |
| `extra_args` | list[string] | Additional CLI arguments forwarded verbatim |
| `binary_path` | string | Overrides the Auggie binary for this call |
| `session_token` | string | Overrides `AUGMENT_SESSION_AUTH` per invocation |

The tool aggregates file contents and inline context, feeds them to Auggie, and returns
its textual response. CLI stderr is logged but not returned unless Auggie exits with an
error.

### `augment_configure`

Writes Augment settings for either the current workspace or the calling user's global
configuration. Useful for enforcing read-only review modes or allowing specific process
launch commands in CI.

| Parameter | Type | Description |
|-----------|------|-------------|
| `workspace_root` | string (required) | Workspace directory to configure |
| `permissions` | object | JSON-serialisable permissions payload written to settings |
| `scope` | string (`"project"`\|`"user"`) | Location of settings (`project` default) |

Returns the path to the written `.augment/settings.json` file.

### `augment_custom_command`

Runs Auggie slash commands (for example `security-review`) so teams can reuse shared
prompt templates. Additional arguments are forwarded to the command and optional
`workspace_root` enables command execution with Augment's index loaded.

### `augment_list_commands`

Lists available custom commands for the provided workspace so developers can discover
team workflows.

## MCP Resources

- `augment://workspace/{workspace_path}/settings` — Augment configuration and tool
  permissions for the workspace.
- `augment://workspace/{workspace_path}/commands` — Catalog of workspace and user-level
  custom commands with basic metadata.

## MCP Prompts

- `security_review` — Generates a detailed security audit brief for a target file.
- `refactor_code` — Produces a scoped refactoring plan with explicit improvement goals.
- `generate_tests` — Suggests a structured set of automated tests and coverage notes.

Clients can fetch prompts via `prompts/list` and render them with context-specific
arguments to standardise review requests across the team.

## Workspace Indexing

Pass `workspace_root` to `augment_review`, `augment_custom_command`, or
`augment_list_commands` to enable Augment's indexing engine. When supplied, Auggie is able
to reference the entire repository instead of only the explicit `paths` you stream. This
dramatically improves code understanding and recommendation quality.

## Tool Permissions

Use `augment_configure` to manage Augment's tool-level permissions. Project-scoped
settings live at `<workspace>/.augment/settings.json`, while user scope writes to
`~/.augment/settings.json`. See `docs/SECURITY.md` and `.augment/settings.example.json`
for recommended defaults.

## Custom Commands

Store shared workflows in `.augment/commands/*.md` (see `docs/CUSTOM_COMMANDS.md`). Use
`augment_custom_command` to execute a command and `augment_list_commands` to discover the
catalog. This keeps code reviews consistent and reduces prompt repetition.

## Development

- `python3 -m augment_mcp.server` — run the server locally (blocks)
- Use environment variables above to tune host/port/logging at runtime

## License

MIT
