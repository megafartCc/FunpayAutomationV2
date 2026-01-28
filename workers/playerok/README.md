# PlayerOk worker

This worker is intended to run separately from the FunPay worker.

## Entrypoint
- `worker.py`

## Environment variables (suggested)
- `PLAYEROK_COOKIES_JSON` or `PLAYEROK_COOKIES_PATH`
- `PLAYEROK_POLL_SECONDS` (default 10)
- `PLAYEROK_LOG_LEVEL` (default INFO)

## Notes
- Keep this worker isolated so it cannot starve other platform workers.
