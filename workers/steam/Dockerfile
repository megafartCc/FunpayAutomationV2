FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# This Dockerfile is intended to be built with `workers/steam` as the build context.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . /app

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "steam_worker:app", "--host", "0.0.0.0", "--port", "8000"]

