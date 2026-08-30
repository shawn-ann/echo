# AGENTS.md

High-signal guidance for OpenCode sessions. Echo = LLM-powered English-correction web app (React 19 + FastAPI + PostgreSQL).

## Branch & deploy

- Active branch is **`v0.1`** (not `master`). `master` is stale; all work lands on `v0.1`.
- **Pushing to `v0.1` deploys to production** via `.github/workflows/deploy.yml` (build → Aliyun ACR → SSH to ECS, live at `https://echo.hootooa.com`). Do not push to `v0.1` just to test.
- Deploy triggers on the **branch** `v0.1`, not a tag (despite docs phrasing "git push origin v0.1").

## Commands

### Backend (from `backend/`, Python 3.12, venv at `backend/.venv`)
- Run app: `uvicorn app.main:app --reload --port 8000`
- Migrate: `alembic upgrade head` (first time / after model changes)
- New migration: `alembic revision --autogenerate -m "..."`
- Tests: `pytest -v`  ·  single: `pytest tests/test_auth_api.py::test_name -v`
- **No backend lint/typecheck configured** (no ruff/mypy).

### Frontend (from `web/`, Node 24 required by Vite 8)
- `source ~/.nvm/nvm.sh && nvm use 24`
- Dev: `npm run dev` (port 5173)  ·  Lint: `npm run lint` (oxlint)
- Build: `npm run build` → `tsc -b && vite build`. **No separate `typecheck` script**; this is the typecheck.
- E2E: `npm run test:e2e` (Playwright, system Chrome via `channel: 'chrome'`)

### Full local stack
- `docker compose up -d --build` (db + api + web, web on :80)  ·  DB only: `docker compose up -d db`

## Testing gotchas

- **Backend tests need a running PostgreSQL** with `echo` **and** `echo_test` databases. `conftest.py` forces `DATABASE_URL` to `.../echo_test`, uses `Base.metadata.create_all` (NOT alembic), drops/truncates tables per session/test.
- **Seed account differs between tests and the running app**:
  - Tests (`conftest.py`): `demo` / `demo1234` (hardcoded, ignores `SEED_*`)
  - Running app (`seed.py` ← `config.py` `SEED_*`): `shawn` / `shawn!QAZ1qaz`
  - `README.md` and `.opencode/command/frontend-check.md` still say `demo` — **stale**. Real login is `shawn`.
- E2E (`playwright.config.ts`) auto-starts backend with `LLM_MODE=mock` and frontend via `webServer`. Expects `backend/.venv/bin/uvicorn` to exist and `db` container running. `fullyParallel: false`, `retries: 0`.

## LLM integration

- `LLM_MODE` env: `""` = real call (needs `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`); `"mock"` = deterministic mock (tests/demo).
- `backend/.env` (gitignored) holds **real, billable** LLM credentials (百炼/GLM-5.2). Local dev makes real LLM calls by default — set `LLM_MODE=mock` to avoid cost.
- Non-streaming; structured JSON report validated by Pydantic.
- `CONTEXT_LIMIT=40` recent messages sent to LLM; full history stays in DB.
- Prompt-engineering scripts in `backend/app/scripts/` (model compare, ground-truth eval, thinking compare); reports in `backend/docs/prompts/`. Golden cases: `backend/app/prompts/golden_cases.json`.

## Architecture notes

- API prefix `/api/v1`; unified error shape `{code, message, details}`.
- Frontend path alias `@` → `web/src` (vite.config.ts).
- Frontend API base: `VITE_API_BASE_URL` env, defaults `http://localhost:8000/api/v1` (dev); prod injects `/api/v1` (nginx same-origin reverse proxy, no CORS).
- Backend Dockerfile runs `alembic upgrade head && uvicorn ...` on container start.
- Two compose files: root `docker-compose.yml` (local dev) vs `deploy/docker-compose.prod.yml` (self-contained db/api/web/proxy-Caddy; db/api not exposed publicly).
- Data model: `users` / `sessions` (login sessions, DB-backed) / `session_conversations` / `messages` / `correction_reports` (JSONB). **Login session ≠ conversation** — don't confuse them.
- MVP is **single-turn correction only** (follow-up/追问 was removed; migration `a1b2c3d4e5f6_drop_follow_up_message_types`).

## Conventions

- Chinese is the working language for docs, commit messages, and PRDs (`PRD/`, `docs/tech-design/`). Match this.
- Commit style: `type(scope): 中文描述`, e.g. `feat(correction): 回车发送 + Shift+Enter 换行`.
- PRD = source of truth for product behavior; `docs/tech-design/` for contracts; **code is source of truth for what's actually implemented** (docs sometimes lag).
- `.opencode/command/frontend-check.md` defines a `/frontend-check` slash command (Playwright MCP login walkthrough) — but its `demo` account refs are stale.
