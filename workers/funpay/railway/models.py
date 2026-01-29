from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RentalMonitorState:
    last_check_ts: float = 0.0
    freeze_cache: dict[int, bool] = field(default_factory=dict)
    expire_delay_since: dict[int, datetime] = field(default_factory=dict)
    expire_delay_next_check: dict[int, datetime] = field(default_factory=dict)
    expire_delay_notified: set[int] = field(default_factory=set)
    expire_soon_notified: dict[int, int] = field(default_factory=dict)

