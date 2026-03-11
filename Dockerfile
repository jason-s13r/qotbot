FROM python:3.13-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir uv
RUN uv sync --frozen

# Run the bot
CMD ["uv", "run", "qotbot"]
