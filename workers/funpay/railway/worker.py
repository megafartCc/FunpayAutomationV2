from __future__ import annotations

import sys
from pathlib import Path

# Allow running from repo root while importing FunPayAPI from this folder.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from .runner_utils import main, run_multi_user, run_single_user

__all__ = ["main", "run_multi_user", "run_single_user"]


if __name__ == "__main__":
    main()
