FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install uv && uv export --frozen | pip install -r /dev/stdin

# Copy application code
COPY bot/ ./bot/

# Create data directory for persistence
RUN mkdir -p /app/data/logs

# Set environment variables
ENV PYTHONPATH=/app
ENV DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
ENV DATA_PATH=/app/data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from bot.db.database import init_db; asyncio.run(init_db())" || exit 1

# Run the bot
CMD ["python", "bot/main.py"]
