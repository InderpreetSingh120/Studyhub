# API contract

Shared by the web and Android clients. Every route is prefixed with the value
of `API_PREFIX` (`/api` by default). All timestamps are UTC.

Errors use a single shape:

```json
{ "detail": "human readable message" }
```

Status codes: `400` bad input, `401` unauthenticated, `403` forbidden,
`404` not found, `409` conflict, `413` upload too large, `415` unsupported
file type, `422` validation error, `503` dependency unavailable.

## Meta

### `GET /api/health`

Public. Verifies the process and the database connection.

`200`

```json
{ "status": "ok", "database": "ok", "environment": "development", "version": "0.1.0" }
```

`503` when the database is unreachable.

## Auth

All protected endpoints require:

```http
Authorization: Bearer <access_token>
```

Tokens are signed JWTs (HS256) valid for `JWT_EXPIRE_MINUTES` (default
10080 = 7 days). A missing, malformed or expired token returns `401` with a
`WWW-Authenticate: Bearer` header.

### `POST /api/auth/register`

Public. Creates an account and returns a token (the user is logged in
immediately).

```json
{ "username": "Aarav Mehta", "phone": "+91 98765 43210", "password": "password123" }
```

Rules:

- `username` is a **display name**: 3–60 characters, letters with single
  spaces between words (`^[A-Za-z]+(?: [A-Za-z]+)*$`). Names **may repeat** —
  the phone number is the identity — so an admin may later rename a name that
  is in the way.
- `phone` is the unique login key. Any of `9876543210`, `+91 98765 43210`,
  `09876543210`, `91 98765 43210` collapses to the same ten digits.
- `password` is 8–72 bytes.

`201`

```json
{ "access_token": "…", "token_type": "bearer", "user": { "id": 2, "username": "Aarav Mehta", "phone": "9876543210", "role": "user", "created_at": "2026-09-25T10:13:02" } }
```

`409` when an account already exists for that phone number, `422` on invalid
input.

The registration screens of both clients warn that an unrecognized username
may be renamed or removed by an administrator.

### `POST /api/auth/login`

Public. Accepts the phone number **or** the username in `identifier`.

```json
{ "identifier": "9876543210", "password": "password123" }
```

A phone number always resolves directly. A username only resolves when
exactly one account carries it; when several do, the answer is
`409 Several accounts share this username; log in with your phone number`.

`200` with the same body as register. `401 Incorrect phone number or
password` for an unknown user or a wrong password — the same message in both
cases.

### `GET /api/auth/me`

Protected. `200` → the current user object (`role` is `user` or `admin`).
`401` otherwise.

## Subjects

Subjects are **shared syllabus topics**: everybody sees the same list and
everybody's note can point at it, which is what keeps the gallery filter
consistent. `created_by` records who added it.

`name` is trimmed, 1–60 characters; `color` is an optional hex value such as
`#3b82f6` (send `null` or `""` to leave it unset).

### `GET /api/subjects` → `200`

All subjects, alphabetically, case-insensitive.

```json
[{ "id": 1, "name": "Data Structures", "color": null, "created_by": 2, "created_at": "2026-09-25T10:12:00" }]
```

### `POST /api/subjects` → `201`

```json
{ "name": "Data Structures", "color": "#3b82f6" }
```

Names are compared without regard to case: `409 This subject already exists`.

### `PATCH /api/subjects/{id}` → `200`

Partial update of `name`, `color`. Only the creator or an admin may change a
subject — anybody else gets `403`; a missing subject is `404`. `null` clears
`color`, `422` for `name`.

### `DELETE /api/subjects/{id}` → `204`

Same permission rule. The notes keep their text and lose their subject
(`subject_id` becomes `null`).

## Notes

The gallery is **public to everyone signed in**: any note that exists can be
read, and every read carries the uploader's name. Writing — update, delete,
attachments — is limited to the owner or an admin (`403` for everybody else).

### `GET /api/notes` → `200`

Every note, newest first (`updated_at` descending), each with
`attachment_count` and the author's display name.

| Query | Meaning |
|---|---|
| `q` | case-insensitive match against title **or** body (wildcards are literal) |
| `subject_id` | only notes in that subject |
| `semester` | 1–8 |
| `branch` | case-insensitive exact branch, e.g. `cse` |
| `kind` | `notes` / `practical` / `mst` / `final` (`400` for anything else) |
| `mine` | `true` = only my uploads |
| `done` | `true` / `false` completion filter |
| `limit` | 1–200, default 100 |
| `offset` | default 0 |

```json
{
  "id": 1, "title": "Stacks and Queues", "body": "notes…",
  "subject_id": 1, "semester": 4, "branch": "CSE",
  "kind": "notes", "kind_label": "Notes", "is_done": false,
  "author_id": 2, "author": "Aarav Mehta", "attachment_count": 1,
  "created_at": "2026-09-25T10:13:02", "updated_at": "2026-09-25T10:17:23"
}
```

### `POST /api/notes` → `201`

```json
{ "title": "Wave equation", "body": "notes…", "subject_id": 1, "semester": 4, "branch": "CSE", "kind": "mst", "is_done": false }
```

`title` is required (trimmed, 1–200), `body` defaults to `""` (max 100 000
characters), `semester` is 1–8, `branch` is 1–40 characters, `kind` defaults
to `notes`. `subject_id` must exist — `400 Unknown subject` otherwise — and
may be `null` for an unfiled note.

### `GET /api/notes/{id}` → `200`

Same object; `404` only when the note does not exist.

### `PATCH /api/notes/{id}` → `200`

Partial update of `title`, `body`, `subject_id`, `semester`, `branch`, `kind`,
`is_done`. Omitted fields are left untouched; `subject_id: null` removes the
subject; explicit `null` for any other field is `422`.

### `DELETE /api/notes/{id}` → `204`

Deletes the note **and** its attachments, including their stored files.

## Attachments

PDF and image uploads (`application/pdf`, `image/png`, `image/jpeg`,
`image/webp`, `image/gif`), capped at `MAX_UPLOAD_BYTES` (default 20 MiB).
Clients that send `application/octet-stream` are accepted when the filename
extension is one of the allowed types. Storage is local during development and
S3-compatible (R2/B2) in production; the API shape is identical either way.

### AI summaries

Uploading a PDF kicks off a background task **automatically** — no button is
involved. The server extracts the text (up to `SUMMARY_MAX_CHARS`, 60 pages),
asks `SUMMARY_MODEL` on OpenRouter for at most `SUMMARY_MAX_TOKENS` tokens and
stores the result on the attachment row. `summary_status` walks:

| Status | Meaning |
|---|---|
| `pending` | the job is queued or running — clients poll |
| `ready` | `summary` holds the text |
| `skipped` | not summarised: no `OPENROUTER_API_KEY`, or the file is not a PDF |
| `failed` | extraction or the model call failed (`summary` is `null`) |

Without a key the upload still succeeds and the row becomes `skipped`, which
is the state of a development server with no configuration.

### `POST /api/notes/{id}/attachments` → `201`

`multipart/form-data` with a single part named `file`. Owner (or admin) only.

```json
{ "id": 1, "filename": "chapter3.pdf", "content_type": "application/pdf", "size_bytes": 431, "summary": null, "summary_status": "pending", "created_at": "2026-09-25T10:17:23" }
```

`413` when the file exceeds the limit, `415` for a disallowed type.

### `GET /api/notes/{id}/attachments` → `200`

Array of the same objects, ordered by id (the internal storage key is never
exposed). Poll this while a `summary_status` is `pending`.

### `GET /api/notes/{id}/attachments/{attachment_id}` → `200`

Returns the file bytes with `Content-Disposition: attachment`. With object
storage this is a `302` to a presigned URL (valid 15 minutes); locally the
app streams the file itself.

### `DELETE /api/notes/{id}/attachments/{attachment_id}` → `204`

Removes the row and the stored object. Owner (or admin) only.

## Everyone-chat

One room that every signed-in user shares, alongside the invite-code groups.

### `GET /api/chat` → `200`

A page of messages **oldest first within the page**, newest page first:

```json
[{ "id": 4, "sender_id": 2, "sender": "Aarav Mehta", "body": "hello campus", "created_at": "2026-09-25T10:20:31" }]
```

| Query | Meaning |
|---|---|
| `before_id` | only messages with a lower id (use the oldest id you already hold) |
| `limit` | 1–200, default 50 |

### `POST /api/chat` → `201`

```json
{ "body": "see you at the library" }
```

`body` is trimmed, 1–4000 characters. The message is stored and pushed to
every socket connected to the global room.

### `WS /api/ws/global?token=<access_token>`

Same frame protocol as the group sockets below; `connected` carries
`"group_id": 0` (the global channel).

## Groups

A private group is created with a random 8-character **invite code** (letters
and digits without look-alikes, e.g. `C74GSXWS`). Only people who have the code
can join, and every member can see it so they can invite friends.

Permission model: **owner** vs **member**. The owner may rename and delete the
group; everybody else may read it, list members, chat and leave.
Non-members always get `404`, members who lack permission get `403`.

### `GET /api/groups` → `200`

Every group you belong to, alphabetically, each with `member_count` and
`my_role` (`owner` / `member`).

### `POST /api/groups` → `201`

```json
{ "name": "Exam prep", "description": "week 12" }
```

`name` is required (trimmed, 1–60); `description` optional (trimmed, ≤200).
You become the owner and the only member.

### `POST /api/groups/join` → `200`

```json
{ "invite_code": "c74gsxws" }
```

Codes are case-insensitive. `404 Invalid invite code` for an unknown code,
`409 You are already in this group` when you are a member.

### `GET /api/groups/{id}` → `200`

The group plus your role. `404` if you are not a member.

### `GET /api/groups/{id}/members` → `200`

```json
[{ "user_id": 1, "username": "alice", "role": "owner", "joined_at": "…" }]
```

Ordered by join time.

### `PATCH /api/groups/{id}` → `200`

Owner only. Partial update of `name` / `description`; `null` is rejected with
`422` (send `""` to clear the description).

### `POST /api/groups/{id}/leave` → `204`

- Ordinary member: removed from the group.
- Owner with other members: ownership passes to the member who joined first,
  then you are removed.
- Last member: the group is deleted outright, because nobody could get back in.

### `DELETE /api/groups/{id}` → `204`

Owner only; the group and all its memberships disappear.

## Group chat

Every member of a group may read and send messages; non-members get `404` as
usual. Deleting a group deletes its messages.

### `GET /api/groups/{id}/messages` → `200`

Returns a page of messages **oldest first**:

```json
[{ "id": 12, "group_id": 3, "sender_id": 1, "sender": "alice", "body": "hi", "created_at": "…" }]
```

| Query | Meaning |
|---|---|
| `before_id` | only messages with a lower id (use the oldest id you already hold) |
| `limit` | 1–200, default 50 |

### `POST /api/groups/{id}/messages` → `201`

```json
{ "body": "see you at the library" }
```

`body` is trimmed, 1–4000 characters. The message is stored and pushed to
every socket that is connected to the group.

### `WS /api/ws/groups/{id}?token=<access_token>`

The browser and Android clients cannot set an `Authorization` header during
the handshake, so the same JWT travels as a query parameter. The connection is
accepted first and then authenticated, so a bad token is visible to the client
as a readable frame:

| Close code | Meaning |
|---|---|
| `4401` | missing, malformed or expired token |
| `4404` | you are not a member of that group |

Frames are JSON objects with a `type` field.

Client → server:

```json
{ "type": "message", "body": "hi" }
{ "type": "ping" }
```

Server → client:

```json
{ "type": "connected", "group_id": 3, "user_id": 1 }
{ "type": "message", "message": { "id": 12, "group_id": 3, "sender_id": 1, "sender": "alice", "body": "hi", "created_at": "…" } }
{ "type": "pong" }
{ "type": "error", "detail": "human readable message" }
```

A `connected` frame is the first thing a successful client receives. An
`error` frame does not close the socket — only the codes above do — so a
rejected message can be fixed and retried. Messages sent over REST are pushed
to the same sockets, so a client that only ever receives still sees everything.

Fan-out happens in one process; running more than one replica needs a shared
broker (see [architecture.md](architecture.md)).

## Dashboard

### `GET /api/dashboard` → `200`

Everything the home screen needs in one request, so neither client has to page
through the whole gallery to draw its summary. Aggregates cover the **whole
gallery** (it is public), groups stay personal to the caller.

```json
{
  "notes": {
    "total": 42,
    "done": 7,
    "without_subject": 3,
    "by_subject": [{ "subject_id": 1, "name": "Data Structures", "color": null, "count": 12 }],
    "by_kind":     [{ "key": "notes", "label": "Notes", "count": 30 }],
    "by_branch":   [{ "key": "CSE",   "label": "CSE",   "count": 30 }],
    "by_semester": [{ "key": "4",     "label": "Semester 4", "count": 12 }]
  },
  "recent_notes": [
    { "id": 1, "title": "Stacks and Queues", "author": "Aarav Mehta", "subject_id": 1, "semester": 4, "branch": "CSE", "kind": "notes", "is_done": false, "updated_at": "…" }
  ],
  "groups": [
    { "id": 1, "name": "Exam prep", "member_count": 4, "last_message": { "sender": "bob", "body": "…", "created_at": "…" } }
  ],
  "trend": [{ "date": "2026-08-27", "count": 0 }]
}
```

| Field | Meaning |
|---|---|
| `notes` | totals with counts per subject (`color` may be `null`), per type, per branch and per semester — `by_kind` is ordered by count then key, `by_semester` by key (1…8) |
| `recent_notes` | the 5 notes touched most recently, newest first, each with its author |
| `groups` | every group you belong to, alphabetically, with its member count and a preview of its newest message (`null` when the group is silent) |
| `trend` | 30 zero-filled points, oldest first, one per UTC day — ready for a chart |

## Admin

Every route requires `role == "admin"`; a signed-in non-admin gets
`403 Admin access required`. The moderation account is seeded at startup from
`ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_PHONE`.

### `GET /api/admin/users` → `200`

```json
[{ "id": 2, "username": "Aarav Mehta", "phone": "9876543210", "role": "user", "created_at": "…", "note_count": 1, "message_count": 3 }]
```

Ordered by creation time; `note_count` and `message_count` are the moderation
workload for that account (chat messages across the global room and groups).

### `PATCH /api/admin/users/{id}` → `200`

```json
{ "username": "Aarav M." }
```

Renames the account — the answer to a duplicate or abusive display name.
Same username rules as registration; `404` for an unknown user.

### `DELETE /api/admin/users/{id}` → `204`

Deletes the account; notes, attachments on disk, groups, memberships and
messages cascade. `400 You cannot delete your own account` for the admin's own
id.

### `GET /api/admin/notes?limit=100&offset=0` → `200`

Every note in the gallery as `NoteOut` (author included), `limit` up to 500.

### `DELETE /api/admin/notes/{id}` → `204`

Removes any note and its files, regardless of owner.

### `DELETE /api/admin/chat/messages/{message_id}` → `204`

Deletes a message from the everyone-chat.

### `DELETE /api/admin/groups/{group_id}/messages/{message_id}` → `204`

Deletes a message from a group chat; `404` when the message is not in that
group.
