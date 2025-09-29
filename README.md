# Augment FastMCP Server

This project provides a [FastMCP](https://pypi.org/project/fastmcp/) server that exposes
Augment's Auggie CLI over the MCP protocol. It allows other MCP-compatible agents to
invoke Auggie for code reviews and contextual analysis via HTTP transport.

## Features

- HTTP-hosted FastMCP server (`augment_review` tool)
- Streams file contents and additional context to Auggie
- Supports Auggie flags such as `--compact`, GitHub token override, and extra CLI args
- Graceful handling of timeouts, cancellations, and CLI errors

## Setup

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Authenticate Auggie**

   ```bash
   npm install -g @augmentcode/auggie
   auggie --login
   AUGMENT_SESSION_AUTH="$(auggie --print-augment-token)"
   export AUGMENT_SESSION_AUTH
   ```

   Optionally set `AUGGIE_PATH` if the binary is not on your `PATH`.

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
    }
  }
}
```

## Tool Reference

### `augment_review`

| Parameter | Type | Description |
|-----------|------|-------------|
| `instruction` | string (required) | Prompt passed to Auggie via `--print` |
| `context` | string | Additional raw text piped to Auggie stdin |
| `paths` | list[string] | Files whose contents are streamed to Auggie with headers |
| `compact` | bool | Adds the `--compact` flag |
| `github_api_token` | string | Overrides GitHub auth for the request |
| `timeout_ms` | int | Aborts Auggie after the specified milliseconds |
| `extra_args` | list[string] | Additional CLI arguments forwarded verbatim |
| `binary_path` | string | Overrides the Auggie binary for this call |
| `session_token` | string | Overrides `AUGMENT_SESSION_AUTH` per invocation |

The tool aggregates file contents and inline context, feeds them to Auggie, and returns
its textual response. CLI stderr is logged but not returned unless Auggie exits with an
error.

## Development

- `python3 -m augment_mcp.server` — run the server locally (blocks)
- Use environment variables above to tune host/port/logging at runtime

## License

MIT
