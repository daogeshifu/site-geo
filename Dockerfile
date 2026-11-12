FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALLOW_PLAYWRIGHT=true \
    GOOGLE_RENDER_TIMEOUT_SECONDS=25

WORKDIR /app

COPY requirements.txt /app/requirements.txt

# Playwright's bundled Node must start before --with-deps can install browser libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && playwright install --with-deps chromium

COPY app /app/app
COPY README.md /app/README.md

EXPOSE 8023

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8023"]
