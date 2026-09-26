# Deploying the backend (Redmi Note 5 Pro + Termux)

Target architecture:

```text
PC            development machine (edit, test, build clients)
Redmi + Termux  clones this repo, runs FastAPI + SQLite
GitHub        source repository
Cloudflare R2 / Backblaze B2   permanent attachment storage (optional)
```

Everything below was verified against the repository; nothing is assumed.

## 1. What Git holds

| Path | Committed |
|---|---|
| `backend/app/`, `backend/tests/` | source |
| `backend/requirements.txt` | runtime deps |
| `backend/requirements-dev.txt` | test deps (not installed on the phone) |
| `backend/pytest.ini`, `backend/start.sh` | runner + start script |
| `.env.example` | variable names/placeholders only |
| `.gitignore` | keeps secrets and artefacts out |
| `web/`, `android/`, `docs/`, `README.md` | clients + documentation |

Never committed (see `.gitignore`): `.env`, `*.db` (runtime SQLite with user
data), `backend/uploads/`, `*.log`, `.venv/`, `node_modules/`, `dist/`,
`android/app/build/`, `local.properties`, `__pycache__/`, `.pytest_cache/`,
IDE metadata.

## 2. First install on the phone

```bash
pkg update && pkg install python git

# Only needed if pip has to compile something (bcrypt, pydantic-core, SQLAlchemy):
pkg install clang rust binutils maturin

cd ~
git clone <REPOSITORY_URL> studyhub
cd studyhub

cp .env.example .env      # lives at the REPOSITORY ROOT, next to backend/
nano .env                 # see section 3

cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 3. Configuration (`.env` at the repository root)

`backend/app/config.py` reads process environment first, then the `.env` file
at the repository root (`ENV_FILE` overrides that path).

Minimum for a real deployment:

```bash
ENVIRONMENT=production
JWT_SECRET=<python -c "import secrets; print(secrets.token_urlsafe(48))">
ADMIN_PASSWORD=<your moderation password>
CORS_ORIGINS=http://<origin-of-the-web-app>
```

`ENVIRONMENT=production` makes the server **refuse to start** without a real
`JWT_SECRET` and a non-placeholder `ADMIN_PASSWORD`. Everything else has safe
defaults:

| Variable | Default | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./study.db` | resolved to `backend/study.db`, not the cwd |
| `STORAGE_BACKEND` | `local` | `s3` for R2/B2 (requires `STORAGE_BUCKET`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`; `STORAGE_ENDPOINT` for R2) |
| `UPLOAD_DIR` | `backend/uploads/` | only used by `local` storage |
| `MAX_UPLOAD_BYTES` | `20971520` | 20 MiB |
| `OPENROUTER_API_KEY` | empty | empty = uploads succeed, `summary_status: "skipped"` |
| `SUMMARY_MODEL` | `meta-llama/llama-3.3-70b-instruct:free` | |
| `JWT_EXPIRE_MINUTES` | `10080` | 7 days |
| `API_PREFIX` | `/api` | |
| `ADMIN_USERNAME` / `ADMIN_PHONE` | `admin` / `0000000000` | seeded on every start |

No secret is committed anywhere in the repository; keep it that way (`.env` is
git-ignored, `.env.example` holds placeholders only).

## 4. Start the server

```bash
cd ~/studyhub
bash backend/start.sh
```

`start.sh` cds into `backend/` (required: the app is the `app` package) and
runs:

```bash
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` is required so other devices can reach the phone; the default
`127.0.0.1` would keep it local. Background run:

```bash
termux-wake-lock                       # stop Android killing the process
nohup bash backend/start.sh > studyhub.log 2>&1 &
tail -f studyhub.log
```

Verify:

```bash
curl http://127.0.0.1:8000/api/health          # {"status":"ok",...}
curl http://127.0.0.1:8000/docs                # Swagger UI
ip addr | grep inet                             # phone IP for other devices -> http://<ip>:8000
```

## 5. Database

No migration step exists or is needed:

- schema is created on startup by `Base.metadata.create_all` (SQLAlchemy models
  in `backend/app/models.py`);
- the moderation account is seeded idempotently on every start (`seed_admin`);
- SQLite file `backend/study.db` is created automatically on first run.

There is no Alembic: a future schema change means creating the column/table
manually or dropping the dev database. Nothing in the repository seeds demo
notes/subjects - the app starts on an empty database.

## 6. Attachments

- `STORAGE_BACKEND=local` (default): files under `backend/uploads/` on the
  phone. Phone storage can be wiped - use this only for trying things out.
- `STORAGE_BACKEND=s3`: Cloudflare R2 or Backblaze B2 (both speak the S3 API),
  objects addressed with presigned URLs (or `STORAGE_PUBLIC_URL` for a public
  bucket). This is the durable option.

## 7. Clients

Android (a real device sees the phone serving the API):

```bash
cd android
.\gradlew.bat assembleDebug -PapiBaseUrl=http://<phone-ip>:8000/api
```

Cleartext HTTP is already allowed in `AndroidManifest.xml`.

Web in development on the PC (no code change - Vite proxies `/api`):

```powershell
$env:VITE_API_ORIGIN = "http://<phone-ip>:8000"; npm run dev
```

Web as a production build uses origin-relative URLs (`/api` in
`web/src/api/http.ts`, `window.location.host` for the WebSocket in
`web/src/api/endpoints.ts`), so the build must be served from the same origin
as the API (reverse proxy on the server), or those two constants must be
pointed at the API origin.

## 8. Termux notes

- Install into the phone's internal storage (`~/studyhub`), never onto an SD
  card (no execute permission).
- `termux-wake-lock` while the server runs, otherwise Android suspends it when
  the screen turns off.
- Python packages are installed from PyPI like anywhere else; only packages
  without a usable Android wheel compile locally (that is what the `clang`,
  `rust`, `maturin` line in section 2 is for).
- Keep `backend/study.db` and `backend/uploads/` inside the app's private
  storage.
- Exposing the server past your LAN needs an HTTPS reverse proxy - not included
  in this repository.
