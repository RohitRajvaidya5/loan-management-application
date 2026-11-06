# Backend operations and production release gate

## What is and is not deployed

The repository includes a non-root Python 3.12 container, separate outbox
worker, private persistent document volume, health probes, explicit pool
limits, and development Compose configuration. These files are a starting
point, not evidence of a deployed or secured production environment.

Docker/image execution, live SMTP delivery, HTTPS, external monitoring,
backup restoration and production load acceptance require an operator.
No real messages are sent by the test suite. No customer portal or refresh
token endpoint exists; staff access and short-lived revocable JWTs remain.

## Configuration and startup

1. Keep `.env`, `.env.test`, database dumps and document copies out of Git.
   In production inject secrets from the deployment platform, not the image.
   Generate an independent random JWT secret (48 random bytes or more).
2. Set `APP_ENV=production`, `DEBUG=false`, production database credentials
   and private durable `DOCUMENT_STORAGE_PATH`. HTTPS origins in
   `CORS_ORIGINS` must be exact origins without paths or trailing slashes.
   Empty origins means cross-origin browser access is denied.
3. Use a least-privilege application database account. Apply migrations with
   a separately authorized release identity when possible. PostgreSQL
   connections across untrusted networks must require certificate-validated
   TLS using your platform's supported asyncpg connection configuration.
4. Choose `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` and process/replica count together:
   maximum API connections are roughly `(size + overflow) * processes *
   replicas`, plus worker, release and operator connections.
5. Apply `uv run alembic upgrade head` once as a release job, then
   `uv run python -m app.database.seed`. Seeding is additive and idempotent.
   Bootstrap the first admin interactively with
   `uv run python -m app.database.create_admin`.
6. Start `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
   --no-proxy-headers`. Use a managed process supervisor, not reload mode.
7. Terminate HTTPS at a trusted ingress/reverse proxy, set body/connection
   limits and timeouts, block direct backend access, and serve no upload
   directory as static files. HSTS belongs at the HTTPS ingress.
8. Enable notifications only after configuring and testing the SMTP
   provider: `NOTIFICATIONS_ENABLED=true`, SMTP host/port, TLS, sender, and
   optionally a username/password pair. Production rejects plaintext SMTP
   and the example sender. Start a separately supervised
   `uv run python -m app.services.notification_worker`.

### Development containers

```powershell
docker compose build
docker compose run --rm api python -m alembic upgrade head
docker compose run --rm api python -m app.database.seed
docker compose up -d api
# Only after explicitly enabling/configuring email:
docker compose --profile notifications up -d notification-worker
```

The container connects to the configured external PostgreSQL instance; there
is no automatically provisioned production database. `localhost` inside a
container is the container itself. Configure the correct host/network before
running. The API binds only the host loopback port by default. Persist and
back up the named document volume; do not use `docker compose down -v`.

The worker image intentionally has no HTTP health check. Monitor its process,
queue age, due/exhausted jobs and provider failures instead. Stable
Message-ID and enqueue deduplication do **not** make SMTP exactly-once: a crash
after provider acceptance and before database acknowledgement can duplicate
delivery. Recover expired leases; do not manually run the same job elsewhere.
Set the lease comfortably above the worst-case complete SMTP operation,
not just a single socket timeout.

## Health, errors and monitoring

- `/health/live`: process liveness, no database access.
- `/health/ready`: PostgreSQL connectivity, 503 when unavailable.
- A ready API does not prove a worker is alive, storage is durable, the
  migration is current or SMTP is working. Check each release dependency.
- API errors preserve `detail` and add `code` and `request_id`; the matching
  `X-Request-ID` is returned. Validation excludes raw input/context; database
  and unexpected failures do not expose SQL, parameters or exception text.
- JSON request logs contain a UUID, route **template**, method, status and
  elapsed milliseconds, not bodies/query strings/Authorization. Provider
  errors store only their exception class, never provider text.
- Configure collection/alerting for readiness, 5xx/429 rates, latency,
  database pool saturation, disk space, queue age, exhausted jobs, repeated
  login failures and worker restarts. Validate alert delivery before release.
- Disable SQL echo, proxy request-body logging and debug tracebacks. Keep
  ingress access logs free of credentials and tokens.
- Do not trust arbitrary forwarded IP headers. The default uses the direct
  socket peer for shared login limits (10/minute). Behind a proxy it will be
  shared by that proxy unless you explicitly configure trusted proxy peers,
  forwarded-header sanitization and network isolation. Never trust `*`.

## Backups and restoration rehearsal (operator gate)

Back up PostgreSQL **and** private document bytes. Metadata alone cannot
restore files. Encrypt both, restrict access, monitor completion and align
their restore points. Establish business/legal approved RPO/RTO, document
retention, deletion/hold, audit retention and log retention before launch.
Development currently retains audit history and soft-deleted/replaced
documents indefinitely; this is not a legal retention policy.

Use your platform's managed backups/PITR or `pg_dump --format=custom` with
credentials supplied securely through a protected service/password file,
never printed in logs or embedded in command history. Restore with
`pg_restore --no-owner --exit-on-error` into a **new disposable database**,
never the running application database. Restore matching document backups
into separate private storage and point an isolated API at them.

For each rehearsal record timestamps, versions, backup checksums, restore
duration, record counts, migration revision, a sampled authorized document
download, history/audit checks, readiness and actual data-loss window.
Disable notifications while rehearsing. Destroy only the explicitly named
disposable restore environment after approval. No restoration rehearsal is
claimed by this implementation.

Rate-limit rows older than the chosen operational horizon can be removed
with a scheduled parameterized deletion on `window_start`; never delete
current windows. Coordinate revoked-token expiry cleanup separately.
No automatic destructive retention job is enabled.

## Release and rollback

1. Record immutable image/version, migration revision and configuration
   version without secrets. Back up data/documents and rehearse recovery.
2. Run isolated tests, lint/format checks, security review and representative
   staging load. Review the current worktree; do not blindly commit every
   file or a generated credential configuration.
3. Stop/drain workers before an incompatible schema change. Run the release
   migration once, seed, deploy the API and worker, then check readiness,
   authentication, a permitted read, document retrieval, report totals and
   a controlled test-recipient delivery.
4. On failure stop the new worker, route to the previous compatible image
   and preserve data for investigation. Prefer forward fixes.
5. **Do not blindly downgrade.** Revision `d74b2c59f136` drops the outbox and
   rate-limit tables on downgrade, losing pending/history data. Obtain
   approval, export needed records, stop users/workers and verify schema
   compatibility first. Disaster recovery restores into a separate
   environment before any controlled traffic switch.

## Unclosed production gates

- Infrastructure-specific HTTPS, credentials/secret rotation, network and
  PostgreSQL TLS verification.
- Container build/run and image vulnerability scan on the target platform.
- Real provider delivery, sender-domain SPF/DKIM/DMARC and bounce handling.
- Malware scanning/quarantine for production document uploads.
- Encrypted backups plus successful restoration rehearsal.
- Approved legal retention and deletion/hold procedure.
- Monitoring/alert delivery, resource sizing and production workload SLOs.

These are release blockers to be signed off externally, not checked boxes
merely because local application tests pass.
