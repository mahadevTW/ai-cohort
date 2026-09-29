# ticketing-service

A small ticketing system: FastAPI REST API + web UI (SQLite), and an MCP server (streamable HTTP) exposing every feature as a tool.

Run each server in its own terminal (both from the repo root, with the project venv active):

```bash
python ticketing-service/api_server.py   # API + UI  -> http://localhost:8010  (docs: /docs)
python ticketing-service/mcp_server.py   # MCP       -> http://localhost:8011/mcp
```

Use it from the harness:

```bash
python server/mith-mcp-server.py ticketing "show me all open tickets"
```

Inspect the MCP server: `fastmcp list http://localhost:8011/mcp`

## API

| Method | Path | Notes |
|---|---|---|
| POST | `/api/tickets` | `title` (required), `description`, `priority`, `assignee` |
| GET | `/api/tickets` | filters: `status`, `priority`, `assignee`, `q` (text search), `limit` |
| GET | `/api/tickets/stats` | total + count per status |
| GET | `/api/tickets/{id}` | |
| PATCH | `/api/tickets/{id}` | any of `title`, `description`, `status`, `priority`, `assignee` |
| DELETE | `/api/tickets/{id}` | |

Status: `open`, `in_progress`, `resolved`, `closed`. Priority: `low`, `medium`, `high`, `urgent`.

## MCP tools

`create_ticket`, `list_tickets`, `get_ticket`, `update_ticket`, `delete_ticket`, `ticket_stats` — thin wrappers over the API, so the API server must be running.

## Config (env vars)

`TICKETING_PORT` (8010), `TICKETING_DB` (`ticketing-service/tickets.db`), `TICKETING_MCP_PORT` (8011), `TICKETING_API_URL` (`http://localhost:8010`), and in the harness `TICKETING_MCP_URL` (`http://localhost:8011/mcp`).

The chat backend also reads `TICKETING_MCP_URL` (default `http://localhost:8011/mcp`) to discover and call these tools. Start both the ticketing API and MCP servers to enable ticket operations in chat.
