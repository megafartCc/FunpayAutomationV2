FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy the whole monorepo so we can reach shared packages.
COPY . .

# Install backend dependencies (includes editable pysteamauth path).
RUN pip install --no-cache-dir -r apps/backend/requirements.txt

# Make backend package and shared libs importable.
ENV PYTHONPATH="/app/apps/backend:/app/packages/shared"

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
