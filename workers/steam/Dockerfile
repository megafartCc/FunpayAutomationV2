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

# Wrap uvicorn so `$PORT` tokens work even when the platform doesn't run a shell.
RUN python - <<'PY'
from __future__ import annotations

import os

path = "/usr/local/bin/uvicorn"

script = """#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

_TOKENS = {"$PORT", "${PORT}", "${PORT:-8000}"}


def _parse_port(value: str | None) -> int | None:
    if not value:
        return None
    try:
        port = int(value)
    except ValueError:
        return None
    if 1 <= port <= 65535:
        return port
    return None


def _runtime_port() -> int:
    for name in ("PORT", "APP_PORT", "SERVER_PORT"):
        port = _parse_port(os.getenv(name))
        if port is not None:
            return port
    return 8000


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _replace_port_tokens(args: list[str], port: int) -> tuple[list[str], bool]:
    touched = False
    out: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]

        if arg == "--port":
            out.append(arg)
            if i + 1 < len(args):
                val = args[i + 1]
                if _strip_quotes(val) in _TOKENS:
                    out.append(str(port))
                    touched = True
                else:
                    out.append(val)
                i += 2
                continue
            out.append(str(port))
            touched = True
            i += 1
            continue

        if arg.startswith("--port="):
            key, val = arg.split("=", 1)
            if _strip_quotes(val) in _TOKENS:
                out.append(f"{key}={port}")
                touched = True
            else:
                out.append(arg)
            i += 1
            continue

        if _strip_quotes(arg) in _TOKENS:
            out.append(str(port))
            touched = True
        else:
            out.append(arg)
        i += 1

    if "PORT" in os.environ and "--port" not in out and not any(a.startswith("--port=") for a in out):
        out.extend(["--port", str(port)])
        touched = True

    return out, touched


def main(argv: list[str]) -> int:
    port = _runtime_port()
    args, touched = _replace_port_tokens(argv[1:], port)

    if touched:
        print(f"[uvicorn-wrapper] resolved port={port}", file=sys.stderr)

    os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", *args])
    return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
"""

with open(path, "w", encoding="utf-8") as f:
    f.write(script)
os.chmod(path, 0o755)
PY

COPY . /app

EXPOSE 8000
CMD ["uvicorn", "steam_worker:app", "--host", "0.0.0.0"]

