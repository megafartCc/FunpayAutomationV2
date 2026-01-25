"""Backend package bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path


# Ensure shared packages (DatabaseHandler, FunPayAPI, SteamHandler, etc.)
# are importable regardless of the working directory.
ROOT = Path(__file__).resolve().parents[3]
SHARED_PACKAGES = ROOT / "packages" / "shared"
if SHARED_PACKAGES.exists():
    sys.path.insert(0, str(SHARED_PACKAGES))
