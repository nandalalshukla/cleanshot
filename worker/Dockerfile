# syntax=docker/dockerfile:1.7
# CleanShot worker image.
#   docker build -t cleanshot-worker .
#   docker build --build-arg EXTRAS="[diffusion]" -t cleanshot-worker:diffusion .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    U2NET_HOME=/models/u2net \
    HF_HOME=/models/hf \
    CLEANSHOT_DATA_DIR=/data

RUN apt-get update \
 && apt-get install -y --no-install-recommends libglib2.0-0 curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY cleanshot_worker ./cleanshot_worker

ARG EXTRAS=""
RUN pip install ".${EXTRAS}"

# Bake the fast model into the image so the first request doesn't download it.
ARG PRELOAD_MODELS="u2netp"
RUN python -m cleanshot_worker.pipeline.segmentation ${PRELOAD_MODELS}

RUN useradd --system --uid 10001 cleanshot \
 && mkdir -p /data /models \
 && chown -R cleanshot /data /models
USER cleanshot

VOLUME ["/data", "/models"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["cleanshot-worker"]
