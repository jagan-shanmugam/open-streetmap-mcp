FROM python:3.13-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir uv && \
    uv sync --frozen

# Copy and set up entrypoint script (with execute permissions)
COPY --chmod=755 entrypoint.sh /app/entrypoint.sh

# Expose port (default 8000, configurable via PORT environment variable)
EXPOSE 8000

# Use entrypoint script to read PORT from environment variable
ENTRYPOINT ["/app/entrypoint.sh"]
