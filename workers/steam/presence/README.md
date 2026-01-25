# Steam presence worker

Runs the Steam rich-presence bot separately from the FastAPI backend so it can live in its own Railway service.

## Env
- `STEAM_PRESENCE_ENABLED=1`
- `STEAM_PRESENCE_LOGIN` / `STEAM_PRESENCE_PASSWORD`
- `STEAM_PRESENCE_SHARED_SECRET` (optional)
- `STEAM_PRESENCE_IDENTITY_SECRET` (optional)
- `STEAM_PRESENCE_REFRESH_TOKEN` (optional)

## Run
```bash
cd workers/steam/presence
python worker.py
```
