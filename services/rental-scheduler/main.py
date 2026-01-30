from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

def _resolve_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "workers").exists():
            return parent
    return current.parent


ROOT = _resolve_repo_root()
WORKERS_FUNPAY = ROOT / "workers" / "funpay"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(WORKERS_FUNPAY))

from FunPayAPI.account import Account

from workers.funpay.railway.db_utils import get_mysql_config
from workers.funpay.railway.models import RentalMonitorState
from workers.funpay.railway.proxy_utils import build_proxy_config, fetch_workspaces, normalize_proxy_url
from workers.funpay.railway.rental_utils import process_rental_monitor


def _run_for_account(
    logger: logging.Logger,
    *,
    golden_key: str,
    proxy_url: str | None,
    user_agent: str | None,
    site_username: str | None,
    user_id: int | None,
    workspace_id: int | None,
) -> None:
    proxy_cfg = build_proxy_config(proxy_url)
    if not proxy_cfg:
        logger.warning("Missing or invalid proxy_url; skipping rental monitor.")
        return
    account = Account(golden_key, user_agent=user_agent, proxy=proxy_cfg)
    account.get()
    username = site_username or account.username
    state = RentalMonitorState()
    process_rental_monitor(logger, account, username, user_id, workspace_id, state)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("rental-scheduler")

    mysql_cfg = get_mysql_config()
    user_agent = os.getenv("FUNPAY_USER_AGENT")
    explicit_multi = os.getenv("FUNPAY_MULTI_USER")
    golden_key = os.getenv("FUNPAY_GOLDEN_KEY")

    multi_user = bool(explicit_multi) or not golden_key

    if multi_user:
        workspaces = fetch_workspaces(mysql_cfg)
        if not workspaces:
            logger.info("No workspaces found for rental scheduling.")
            return
        for workspace in workspaces:
            try:
                _run_for_account(
                    logger,
                    golden_key=workspace.get("golden_key") or "",
                    proxy_url=normalize_proxy_url(workspace.get("proxy_url")),
                    user_agent=user_agent,
                    site_username=workspace.get("username"),
                    user_id=workspace.get("user_id"),
                    workspace_id=workspace.get("workspace_id"),
                )
            except Exception:
                logger.exception("Rental scheduler failed for workspace %s.", workspace.get("workspace_id"))
    else:
        proxy_url = normalize_proxy_url(os.getenv("FUNPAY_PROXY_URL"))
        if not golden_key:
            logger.error("FUNPAY_GOLDEN_KEY is required for single-user mode.")
            return
        _run_for_account(
            logger,
            golden_key=golden_key,
            proxy_url=proxy_url,
            user_agent=user_agent,
            site_username=None,
            user_id=None,
            workspace_id=None,
        )


if __name__ == "__main__":
    main()
