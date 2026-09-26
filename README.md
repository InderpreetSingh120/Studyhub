# StudyHub

A shared study-notes **gallery** with automatic AI summaries, invite-code group
chats and one everyone-chat. Two clients — a React web app and a native
Kotlin/Compose Android app — talk to one FastAPI backend over REST and
WebSocket.

What somebody gets after signing up with a phone number:

- **Gallery** — every uploaded note is visible to every signed-in user, with
  the uploader's name, filtered by subject, semester (1–8), branch, type
  (`notes`, `practical`, `mst`, `final`) and a search box.
- **AI summaries** — a PDF upload is read back, its text extracted and a short
  revision summary requested from OpenRouter automatically; both clients poll
  until it is `ready` (or `skipped` when no API key is configured).
- **Chat** — a global room for everyone plus private groups joined with an
  8-character invite code; both are live over WebSocket.
- **Moderation** — a seeded admin (`admin` / `headachefromu`) can rename and
  delete accounts and remove notes or messages from the web admin panel.

## Status

| Phase | Feature | State |
|---|---|---|
| 1 | Backend foundation (app, config, database, health, tests) | done |
| 2 | Authentication (phone + password) | done |
| 3 | Notes, subjects, attachments | done |
| 4 | Groups and membership | done |
| 5 | Chat (REST history, then WebSocket) | done |
| 6 | Web frontend | done |
| 7 | Android app | done |
| — | Scope pivot: public gallery, taxonomy, AI summaries, everyone-chat, admin | done |
| 8 | Deployment | guide ready (`docs/deployment.md`), not yet deployed |

Verification: backend `pytest` → **179 passed**; web `npm run lint` → 0
warnings and 0 errors, `npm run build` clean; Android `assembleDebug` clean and
the flows above exercised end-to-end on an emulator (register/login, gallery,
PDF upload, download, global chat, group chat, sign-out).

## Repository layout

```text
backend/    FastAPI application and tests
web/        React + Vite client
android/    Kotlin + Compose client
docs/       architecture, API contract, diagrams
```

## Backend quickstart

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/uvicorn app.main:app --reload     # macOS/Linux: .venv/bin/uvicorn
```

- Health check: <http://127.0.0.1:8000/api/health>
- Interactive API docs: <http://127.0.0.1:8000/docs>

Run the tests:

```bash
cd backend
.venv/Scripts/pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/pip
.venv/Scripts/pytest      # macOS/Linux: .venv/bin/pytest
```

Configuration comes from the environment or a `.env` file at the repository
root - copy `.env.example` to `.env`. No secret is committed. Startup creates
the tables and seeds the moderation account; in development its credentials are
`admin` / `headachefromu` (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_PHONE`),
and without `OPENROUTER_API_KEY` uploads still succeed but are marked
`summary_status: "skipped"`.

Deploying the API to a phone (Redmi + Termux) or any Linux box: see
[`docs/deployment.md`](docs/deployment.md) - clone, `.env`, `pip install -r
requirements.txt`, `bash backend/start.sh`.

## Web quickstart

```bash
cd web
npm install
npm run dev      # http://127.0.0.1:5173, backend on :8000
```

The dev server proxies `/api` (REST and both WebSockets) to
`http://127.0.0.1:8000`; set `VITE_API_ORIGIN` to point somewhere else.
`npm run build` type-checks and bundles for production, `npm run lint`
runs oxlint.

Screens: sign in / register (phone number), gallery, note detail with the AI
summary and download, note editor, dashboard, everyone-chat, group chat, and —
for the admin account only — `/admin` for accounts, notes and chat moderation.

## Android quickstart

```bash
cd android
.\gradlew.bat assembleDebug      # macOS/Linux: ./gradlew assembleDebug
```

Needs the Android SDK (Android Studio is enough) and a JDK 17+;
`local.properties` holds `sdk.dir`. The debug build targets
`http://10.0.2.2:8000/api`, which is the host loopback address as seen from
the emulator, so start the backend first. Override for a physical device:

```bash
.\gradlew.bat assembleDebug -PapiBaseUrl=http://192.168.1.10:8000/api
```

The APK lands in `app/build/outputs/apk/debug/`; install with
`adb install -r app-debug.apk`. Bottom navigation is Home / Gallery / Chat /
Groups; downloads land in the shared Downloads collection, files open through
the system document viewer, and Android has no admin UI.

## Documentation

- [docs/architecture.md](docs/architecture.md) — architecture and decisions
- [docs/api.md](docs/api.md) — API contract shared by both clients
- [docs/diagrams/architecture.md](docs/diagrams/architecture.md) — diagrams
