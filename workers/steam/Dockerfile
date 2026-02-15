FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libx11-6 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libgbm1 libdrm2 libxcb1 \
    libxkbcommon0 libasound2 libglib2.0-0 libgobject-2.0-0 \
    libgio-2.0-0 libexpat1 libdbus-1-3 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# This Dockerfile is intended to be built with `workers/steam` as the build context.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && python -m playwright install chromium

COPY . /app

EXPOSE 8000
ENV PORT=8000
CMD ["sh", "-c", "python -m uvicorn steam_worker:app --host 0.0.0.0 --port ${PORT:-8000}"]

