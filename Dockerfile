FROM python:3.13-slim

WORKDIR /app
COPY src /app/src
COPY pyproject.toml /app/
COPY uv.lock /app/
COPY README.md /app/

RUN apt-get update && apt-get install -y ffmpeg wget && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv
RUN uv sync --frozen

RUN mkdir -p /app/data/models
RUN wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx -O /app/data/models/kokoro-v1.0.onnx
RUN wget https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin -O /app/data/models/voices-v1.0.bin

# Run the bot
CMD ["uv", "run", "qotbot"]
