FROM python:3.13-slim

WORKDIR /app
COPY src /app/src
COPY pyproject.toml /app/
COPY uv.lock /app/
COPY README.md /app/

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
RUN uv sync --frozen

# Run the bot
CMD ["uv", "run", "qotbot"]
