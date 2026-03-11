FROM python:3.13-slim

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv sync --frozen

# Run the bot
CMD ["uv", "run", "qotbot"]
