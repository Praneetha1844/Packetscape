FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir ".[plots]"

COPY examples ./examples

RUN useradd --create-home --uid 1000 simulator
USER simulator

# Mount a host directory at /results to keep the output.
ENTRYPOINT ["packetscape"]
CMD ["run", "examples/dumbbell_aimd.yaml", "--out", "/tmp/results"]
