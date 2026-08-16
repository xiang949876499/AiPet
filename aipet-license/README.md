# AIPet License Server

Minimal FastAPI license validation service for Phase 1.

Run locally:

```bash
pip install -r requirements.txt
uvicorn server:app --reload
```

Core endpoints:

- `POST /api/activate` and legacy-compatible `POST /activate`
- `POST /api/verify`
- `POST /api/heartbeat` and legacy-compatible `POST /heartbeat`
- `POST /api/renew`
- `POST /api/upgrade`
- `POST /admin/activation-codes`
- `POST /admin/licenses/{license_id}/unbind`

Admin UI:

- `GET /admin`

Run tests:

```bash
uv run pytest tests -q
```
