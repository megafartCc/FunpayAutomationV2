import os
import sys
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[3]
APP_DIR = ROOT / "apps" / "backend"
SHARED_DIR = ROOT / "packages" / "shared"
for path in (APP_DIR, SHARED_DIR):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port)
