# AI Private Office V4 — Cloud Backend Edition

A working single-CEO backend for the existing V4 frontend, preserving the V2 office layout and background.

## Features
- Password-protected CEO login (24-hour signed session token)
- Database persistence for staff profiles, tasks, progress, deadlines, draft/final approvals, activity, News, Planning, Project Analysis and AI Suggestions
- Authenticated uploads/downloads for instruction and draft files (25 MB per file by default)
- Same-origin frontend + API; `/api/docs` for API documentation
- SQLite for quick local testing; PostgreSQL for hosted deployments
- AI agents are **not** connected; staff progress remains manually updated.

## Local test with Docker
1. Copy `.env.example` to `.env`.
2. Set a **long unique** `CEO_PASSWORD` and a random `SESSION_SECRET` (e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`).
3. Run `docker compose up --build -d`.
4. Open `http://localhost:8000`, enter CEO password.

## Deploy to a cloud service
Use a Docker-compatible host such as Render, Railway or a VPS.
1. Create a **private** repository for this project; don't commit `.env`.
2. Configure Docker deployment and expose the `PORT` variable (default 8000).
3. Set `CEO_PASSWORD` and `SESSION_SECRET` as secret environment variables.
4. Provision managed PostgreSQL; set `DATABASE_URL=postgresql+psycopg://...`.
5. Mount a **persistent volume** at `/app/data` for uploaded files. Without it, uploaded files can disappear on redeploy.
6. Enable HTTPS and use a custom domain if desired.
7. Set automated backups for PostgreSQL and the persistent volume.

**Important:** Use a single running application instance for now. This initial edition uses last-write-wins snapshot updates; it is not suitable for concurrent CEO editors. File upload/download access is authenticated, but no antivirus scanning, object-storage lifecycle policy, rate limiting, audit-grade logging, or fine-grained staff access control is implemented. For production with multiple users, add per-record APIs, role-based permissions, audit logging, rate limiting and managed object storage (e.g. S3/Supabase Storage). Rotate secrets if exposed.

## API
- `POST /api/login` — `{ "password": "..." }` returns a bearer token
- `GET /api/health` — health check
- `GET /api/snapshot` — retrieve persisted office data (CEO auth)
- `PUT /api/snapshot` — save staff/tasks/activity/intelligence (CEO auth)
- `POST /api/tasks/{task_id}/files?stage=instruction|draft|final` — multipart file upload
- `GET /api/tasks/{task_id}/files` — list task attachments
- `GET /api/files/{asset_id}` — download an attachment

## Known limitations
- No live AI execution; this is the backend foundation.
- Browser-local data from the previous V4 version is not automatically imported into an existing cloud workspace. On a new empty cloud database, initial default staff records are seeded from the frontend.
- Approved draft files remain marked `draft` in storage, but are downloadable from approved task views.
- Textual final deliverables can be downloaded from the original frontend's Final Tasks tab.
- This build has not been deployed to an actual cloud account; cloud provider setup and credentials are required.
