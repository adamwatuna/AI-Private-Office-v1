# AI Private Office V6 — Engine Starter

This package preserves the V5 frontend and V2 office background and adds a **real OpenAI-backed draft generator**. It does NOT yet implement autonomous agents, website research, connected editing tools, social posting, partner logins, HOD approvals, family succession, or secure production authorization. All V5 settings for these remain **browser demo settings only**.

## Run locally with Docker
1. Copy `.env.example` to `.env`.
2. Set a strong `CEO_PASSWORD`, a random `SESSION_SECRET`, and your `OPENAI_API_KEY` in `.env`. Do not share or commit it.
3. Run `docker compose up --build`.
4. Open `http://localhost:8000`. Create a CEO task, open **Manage Task**, select **Generate AI Draft (Engine)** and enter your backend CEO password.
5. The AI draft goes to **Draft Tasks** for CEO review. It does not publish, send email or approve anything.

## Deployment / security warning
This is a **development starter**, not a production-safe multi-user system. The existing V4 backend uses single-password CEO login, browser-held tokens, and whole-snapshot replacement; the V5 frontend still saves tasks locally. Do not invite partners or upload confidential information yet. Before internet deployment implement proper multi-user auth + MFA, server-side project ACLs, database-backed V5 records, audit logs, rate limiting, private object storage, secure session cookies, CSRF defenses, backups and server-enforced AI tool permissions. Use HTTPS, private secrets and managed database.

## API
`POST /api/engine/draft` with CEO bearer token and task_id/title/instruction/staff_name/staff_role/staff_description. Uses OpenAI Responses API and `store=false`. No tool execution.

## Important limitations
- AI output may be inaccurate; CEO must verify it.
- AI provider usage incurs charges.
- The generated draft is saved in the browser's localStorage; it is not yet synchronized to PostgreSQL.
- `OPENAI_API_KEY` is used server-side only.
