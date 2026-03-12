FROM python:3.13-slim

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
RUN uv sync --frozen

# Run the bot
CMD ["uv", "run", "qotbot"]
