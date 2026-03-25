# Exa Websets → Ashby pipeline

FastAPI service (Phase 1 build). SQLite path is configurable for Railway persistent disks.

## Local run

```bash
cd exa-ashby-pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: `GET http://localhost:8000/health`
- Exa: `POST http://localhost:8000/webhook` (requires `Exa-Signature` + `EXA_WEBHOOK_SECRET`, or `EXA_SKIP_WEBHOOK_SIGNATURE_VERIFY=true` for local tests only)
- Admin: `GET/POST http://localhost:8000/api/mappings` (HTTP Basic when `ADMIN_BASIC_USER` + `ADMIN_BASIC_PASSWORD` are set)
- Catch-up: `GET` or `POST http://localhost:8000/catch-up` with header `X-Cron-Secret` matching `CATCH_UP_SECRET`, plus `EXA_API_KEY` — re-lists Exa items for each active mapping and syncs any not already pushed
- Create `data/` automatically on startup (default `DATABASE_PATH=data/app.db`).

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Uses a temporary `DATABASE_PATH` so the project `data/` directory is not required for tests.

## Docker

```bash
docker build -t exa-ashby-pipeline .
docker run -p 8000:8000 --env-file .env exa-ashby-pipeline
```

## Railway go-live

Repo includes [`railway.toml`](railway.toml) (Dockerfile build, `/health` check). The container listens on Railway’s `PORT` ([`Dockerfile`](Dockerfile)).

### Phase A — Service, volume, env (Slack later)

1. **New service** from this repo; Railway will pick up the root `Dockerfile`.
2. **Volume:** add a persistent volume, mount at e.g. `/data`, set **`DATABASE_PATH=/data/app.db`**.
3. **Variables** (copy names from [`.env.example`](.env.example); leave Slack vars empty until Phase E):
   - `EXA_API_KEY`, `EXA_WEBHOOK_SECRET` (after Exa webhook is created)
   - `ASHBY_API_KEY`, optional `BRANDON_ASHBY_USER_ID`
   - `ADMIN_BASIC_USER`, `ADMIN_BASIC_PASSWORD` (for `/api/mappings`)
   - `CATCH_UP_SECRET` (for `X-Cron-Secret` on `/catch-up`)
   - Production: do **not** set `EXA_SKIP_WEBHOOK_SIGNATURE_VERIFY`; optional `DRY_RUN=true` for a no-write smoke test
4. **Health:** `GET https://<public-host>/health` → `{"status":"ok"}`  
   Local smoke: `BASE_URL=http://127.0.0.1:8000 ./scripts/railway-smoke.sh`

### Phase B — Exa webhook and mappings

5. In Exa, set webhook URL to **`https://<public-host>/webhook`**, save **`EXA_WEBHOOK_SECRET`** in Railway, redeploy if needed.
6. Create a mapping (example):

   ```bash
   BASE_URL=https://<public-host> ADMIN_BASIC_USER=... ADMIN_BASIC_PASSWORD=... \
   WEBSET_ID=... ASHBY_JOB_ID=... SOURCE_TAG=... \
   ./scripts/post-mapping.sh
   ```

7. List: `GET /api/mappings` with the same Basic auth.

### Phase C — Validate

8. Locally: `pip install -r requirements-dev.txt && pytest`
9. Trigger a `webset.item.enriched` event or run catch-up; confirm a candidate on the Ashby job.

### Phase D — Catch-up (optional)

10. Call **`GET` or `POST /catch-up`** with header **`X-Cron-Secret: $CATCH_UP_SECRET`** (requires `EXA_API_KEY` on the service). Example:

    ```bash
    BASE_URL=https://<public-host> CATCH_UP_SECRET=... ./scripts/catch-up.sh
    ```

    Or use Railway’s cron / an external scheduler on your cadence.

### Phase E — Slack (after core path works)

11. Set `SLACK_INCOMING_WEBHOOK_URL`, and if needed `SLACK_BOT_TOKEN`, `BRANDON_SLACK_USER_ID`.
12. Confirm failure alerts reach the intended channel (e.g. after a controlled Ashby error).
