# Backend runtime secrets

API production startup requires `DATABASE_URL_FILE`; the worker requires
`DEMANDRIFT_BROKER_URL_FILE`. The migration process supports its own
`DATABASE_URL_FILE`, containing the migration credential, separately from the
restricted application credential. `GEMINI_API_KEY_FILE` is supported for the
accepted backend/worker provider integration; this loader does not enable live
requests or select a provider route.

Files are absolute canonical paths to private regular files, owned by the
effective process user (or root), mode `0400` or `0600`, one hard link,
1–4096 bytes. Docker bind-mounted secrets must actually be readable by the
container UID; Compose file-secret `uid`/`mode` settings alone do not establish
that. Prepare separate host files for PostgreSQL and UID10001 applications.
Do not put secret values into Compose environment, image build arguments,
repository files, browser variables, command arguments or logs.

Reads reject symlinks, directories, FIFOs, changed files, ambiguous environment
and file settings, non-ASCII/whitespace/control bytes and oversized content.
One final LF is accepted without trimming the value. Errors omit paths and
values. Nonproduction native tests may explicitly supply environment values;
production never falls back to them. Redis URLs are also hidden from settings
representations.

Production and every database-backed app expose authenticated project and
research preparation routes. The five historic unscoped research fixture
routers are available only in database-free nonproduction mode. Fixture output
does not serve as live tenant data. `/health` stays a process liveness check;
database startup still requires the accepted schema and restricted role.

This change is local runtime configuration. Hetzner installation, credential
rotation, migration/recovery/backup gates, worker pipeline and actual metered
Gemini acceptance remain separate deliveries.
