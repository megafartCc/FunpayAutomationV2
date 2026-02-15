from __future__ import annotations

import os
import sys


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
    # Railway (and most PaaS) provide PORT as an integer env var.
    for name in ("PORT", "APP_PORT", "SERVER_PORT"):
        port = _parse_port(os.getenv(name))
        if port is not None:
            return port
    return 8000


def _replace_port_tokens(args: list[str], port: int) -> list[str]:
    tokens = {"$PORT", "${PORT}", "${PORT:-8000}"}
    out: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--port" and i + 1 < len(args):
            val = args[i + 1]
            if val in tokens:
                out.extend(["--port", str(port)])
            else:
                out.extend(["--port", val])
            i += 2
            continue

        if arg in tokens:
            out.append(str(port))
        elif arg.startswith("--port="):
            _, val = arg.split("=", 1)
            if val in tokens:
                out.append(f"--port={port}")
            else:
                out.append(arg)
        else:
            out.append(arg)
        i += 1
    return out


def main(argv: list[str]) -> int:
    port = _runtime_port()
    args = argv[1:]

    # Default command when platform doesn't provide one.
    if not args:
        args = [
            sys.executable,
            "-m",
            "uvicorn",
            "steam_worker:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ]
    else:
        args = _replace_port_tokens(args, port)

    os.execvp(args[0], args)
    return 127


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

