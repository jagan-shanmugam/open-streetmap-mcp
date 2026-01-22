#!/bin/sh
# Entrypoint script for OpenStreetMap MCP server
# Reads PORT from environment variable (default: 8000)
exec uv run src/osm_mcp_server/server.py \
    --transport http \
    --host 0.0.0.0 \
    --port "${PORT:-8000}"
