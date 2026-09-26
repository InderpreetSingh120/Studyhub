# Architecture

## Overview

One FastAPI process serves both clients. The React web app and the Kotlin
Android app speak exactly the same API contract, documented in
[api.md](api.md). There is no Android-specific backend and no duplicated
business logic in either client.

```text
web (React)  ─┐              ┌──────────────── OpenRouter (AI summaries)
              ├─ REST ───────┤
android (Kotlin) ─ WebSocket ─┤
                             ▼
                      FastAPI application
     auth │ subjects │ notes+attachments │ groups │ chat │ dashboard │ admin
                             │
               ┌─────────────┼──────────────┐
               ▼             ▼              ▼
        SQLAlchemy      object storage   in-process
         ORM          (local / R2 / B2) socket registry
               │                          │  global room + every group
        SQLite dev / PostgreSQL prod
```

Everything a user can see — notes, subjects, the everyone-chat — is shared:
the permission boundary is *read for any signed-in user, write for the owner
(or an admin)*, plus invite codes for group membership and a `role == "admin"`
guard for moderation.

## Decisions

| Decision | Why |
|---|---|
| Single FastAPI process for REST and WebSocket | One deployment, one contract, no message broker to operate. |
| SQLAlchemy 2.0 ORM, `DATABASE_URL` as the only switch | SQLite in development, PostgreSQL in production — no SQL to rewrite. |
| `Base.metadata.create_all` instead of Alembic for now | The schema is still changing every phase; migrations are added before the first post-deploy schema change. |
| Phone number as the unique identity, display name may repeat | Students already share names, and a phone number is harder to take twice; a clashing name only asks for the phone number at login, and an admin can rename the offender. |
| Stateless JWT + bcrypt | No server-side session store to keep in sync across two clients; a 7-day token also gives both clients session persistence. |
| Public gallery with owner-only writes (`403`, not `404`, for write attempts) | The whole point of the app is that everyone sees everyone's notes; hiding existence only applies to subjects you may not edit. |
| Taxonomy (semester / branch / type) stored on the note, subjects shared | Filtering must agree across every client, so the columns live where the notes live and subjects are one shared list rather than one per user. |
| Summaries run as an in-process background task right after upload | No queue to operate; the row's `summary_status` (`pending` → `ready` / `skipped` / `failed`) *is* the queue, and clients poll it. Without `OPENROUTER_API_KEY` uploads still succeed and are marked `skipped`. |
| Admin endpoints under `/api/admin`, admin UI only in the web client | Moderation is a desktop job; Android ships without the extra surface. |
| In-memory `channel → websockets` registry for fan-out | One channel per group plus the global room; the groups are small and the backend is a single instance. Redis pub/sub is the documented upgrade path if that changes. |
| Uploads go to R2/B2, database stores only the key | Keeps the database small and backups cheap; local-disk fallback keeps development offline. |
| Naive UTC timestamps everywhere | SQLite and PostgreSQL return identical values, so no timezone normalisation is needed in application code. API responses label timestamps as UTC. |
| Dashboard charts drawn with CSS/SVG instead of a chart library | The dashboard only needs bars and a trend line, and a chart library would dominate the bundle; both clients still render the same JSON aggregates. |
| Android talks to `10.0.2.2:8000` by default, overridable with `-PapiBaseUrl=` | The emulator reaches the host machine through `10.0.2.2`; a physical device needs the host's LAN address, so one Gradle property covers both without a source change. |
| OkHttp + `org.json` on Android instead of Retrofit/Moshi/Gson | Both ship with the platform or AndroidX toolchain, keep the client small, and mirror the single-file API layer the web client uses. Files open through a `FileProvider` intent and downloads go to the shared Downloads collection (scoped-storage safe, `WRITE_EXTERNAL_STORAGE` limited to `maxSdkVersion 28`). |

## Client layout

| Web | Android |
|---|---|
| `api/` — typed fetch wrappers, one per endpoint group | `data/Api.kt` — the same wrappers over OkHttp |
| `auth/` — token in `localStorage`, `AuthContext` | `data/Session.kt` — token + user in `SharedPreferences` |
| `pages/` — gallery, detail, editor, dashboard, chat, admin | `ui/` — the same screens in Compose, no admin tab |
| `/admin` route behind `role === "admin"` | — |

Both clients attach the JWT to REST headers and pass it as `?token=` on the
WebSocket handshake, and both poll `summary_status` until a PDF summary
leaves `pending`.

## Known limits

- Chat fan-out is in-process: running more than one backend replica requires a
  shared broker.
- Summaries also run in-process, so a crash mid-upload leaves the row
  `pending`; there is no retry loop yet.
- SQLite allows a single writer; switch to PostgreSQL before concurrent write
  load matters.
- HTTPS/WSS termination happens at the reverse proxy; the application itself
  speaks plain HTTP internally.
