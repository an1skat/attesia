FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock* ./

RUN uv sync --frozen --no-cache || uv pip install --system -r <(uv pip compile pyproject.toml 2>/dev/null || echo "")

COPY apps/api/app .

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]