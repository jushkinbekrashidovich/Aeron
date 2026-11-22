# AERON replay API.
#
# Data and models are NOT baked into the image: the PM2.5 series has no stated licence and
# model files must be made with the same library versions that load them. They are mounted
# (see docker-compose.yml) and the model is trained inside this image.
FROM python:3.12-slim

# LightGBM needs the OpenMP runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY scripts ./scripts
COPY configs ./configs
# Editable install keeps aeron.config.ROOT at /app, where data/ and artifacts/ are mounted.
RUN pip install --no-cache-dir -e ".[api,trees]"

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/artifacts/models /app/data/processed \
    && chown -R app:app /app/artifacts
USER app

ENV AERON_DAILY_CSV=/app/data/processed/daily_us_embassy.csv \
    AERON_MODELS_ROOT=/app/artifacts/models \
    PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "aeron.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
