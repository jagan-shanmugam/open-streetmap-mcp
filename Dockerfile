FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN pip install uv && uv sync --frozen

EXPOSE 8000

ENTRYPOINT ["uv", "run", "src/osm_mcp_server/server.py"]
CMD ["--transport", "http"]
