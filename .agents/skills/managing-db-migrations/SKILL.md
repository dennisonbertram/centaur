---
name: managing-db-migrations
description: "Manages Centaur Postgres migrations with the repo's dbmate wrapper. Use when asked to create a migration, apply or roll back migrations, check migration status, inspect schema_migrations, or work on files under services/api/db/migrations. Triggers on: db migration, database migration, dbmate, schema_migrations, migrate up, migrate rollback."
---

# Managing DB Migrations

Manage Centaur database migrations through `./scripts/dbmate` and `services/api/db/migrations`.

## Use This Skill When

- The user asks to create a new database migration.
- The user asks to apply, roll back, or inspect migrations.
- The task touches `services/api/db/migrations` or `schema_migrations`.
- The task mentions `dbmate` or migration status.

## Default Workflow

1. Inspect the existing SQL files in `services/api/db/migrations` to understand the numbering and recent schema changes.
2. For a new migration, run `./scripts/dbmate new <short_name>` from the repo root.
3. Edit the generated SQL file and keep both `-- migrate:up` and `-- migrate:down` sections.
4. For runtime checks, prefer `./scripts/dbmate status`, `./scripts/dbmate up`, or `./scripts/dbmate rollback` instead of invoking `dbmate` directly.
5. If the change affects runtime behavior, run the highest-value local verification the environment supports and report any blocked checks clearly.

## Rules

- Prefer adding a new migration over editing an old one. Only rewrite an existing migration when the user explicitly asks or the migration is clearly unreleased in the current branch.
- Do not renumber existing migration files.
- Keep migration names short, lowercase, and descriptive; the wrapper normalizes them to the repo format.
- Make SQL idempotent where that is cheap and clear, especially for `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, `DROP ... IF EXISTS`, and index creation.
- If a rollback cannot be automated safely, leave a brief comment in the `down` section explaining that instead of faking a destructive rollback.

## Wrapper Behavior

- `./scripts/dbmate new add_agent_leases` creates the next numbered file in `services/api/db/migrations`.
- `./scripts/dbmate status` runs `dbmate` inside the `api` container.
- If `DATABASE_URL` is not set in the host shell, the wrapper reads it from the running `api` container.
- The repo mounts `services/api/db` into `/app/db`, so new migration files are visible to the `api` container without rebuilding the image.

## Common Commands

```bash
./scripts/dbmate new add_agent_leases
./scripts/dbmate status
./scripts/dbmate up
./scripts/dbmate rollback
```

## If Docker Is Unavailable

If Docker or the local stack is unavailable, still do the highest-value part of the task:

- create or edit the migration file,
- validate obvious SQL and file-shape issues,
- explain that live `status` or `up` verification is blocked by the missing runtime.
