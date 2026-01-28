# PlayerOk worker

This worker is intended to run separately from the FunPay worker.

## Entrypoint
- `worker.py`

## Environment variables (suggested)
- `MYSQL_URL` or standard Railway MySQL vars (`MYSQLHOST`, `MYSQLUSER`, etc.)
- `PLAYEROK_POLL_SECONDS` (default 15)
- `PLAYEROK_PROXY_CHECK_SECONDS` (default 600)
- `PLAYEROK_WORKSPACE_ID` (optional, restricts to a single workspace)
- `PLAYEROK_COOKIES_DIR` (default `.playerok_cookies`)
- `PLAYEROK_LOG_LEVEL` (default INFO)

## Notes
- Each PlayerOk workspace must store cookie JSON (list of cookies) in the workspace key field.
- Keep this worker isolated so it cannot starve other platform workers.
