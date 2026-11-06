# Loan Management API

## Seed initial database data

After applying the database migrations, run:

```powershell
uv run python -m app.database.seed
```

The command seeds the initial roles, permissions, role-permission mappings, and
loan types in PostgreSQL. It is safe to rerun: existing records and custom
permission mappings are left unchanged; missing baseline records are added.

On a new database, create the first administrator from a local terminal after
seeding:

```powershell
uv run python -m app.database.create_admin
```

The command prompts for the administrator's name, email, and password; it does
not accept passwords as command-line arguments and refuses to run when an
administrator already exists. This provides a first-account bootstrap without
enabling public signup.

## JWT authentication

Set `JWT_SECRET_KEY` in `.env` to a unique random value of at least 32
characters. Generate one in PowerShell with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`JWT_ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 15. Start the API with
`uv run uvicorn app.main:app --reload`, then use `POST /api/v1/auth/token` with
JSON `email` and `password` credentials to get a bearer access token. Send the
token in `Authorization: Bearer <access_token>` when calling the protected
`GET /api/v1/auth/me` endpoint.

## Role and permission checks

Protect API routes by adding one of the reusable dependencies from
`app.api.v1.dependencies`:

```python
@router.get("/customers", dependencies=[Depends(require_permission("customers:read"))])
async def list_customers():
    ...


@router.get("/admin/reports", dependencies=[Depends(require_role("administrator"))])
async def read_admin_reports():
    ...
```

Permission and role requirements are checked against the database for the
authenticated user's assigned role. A signed-in user without the required
grant receives `403 Forbidden`.

## Management APIs

The versioned API exposes:

- `/api/v1/users`: administrator-only user creation, listing, lookup, updates,
  and activation/deactivation. User creation is intentionally not public
  signup; new accounts require an administrator and an existing role.
- `/api/v1/customers`: staff-only customer creation, listing with `q`, `city`,
  and `state` filters, lookup, and updates.
- `/api/v1/applications`: staff-only loan-application creation, retrieval,
  updates, filtering by `status`, `customer_id`, or `assigned_to`, and
  pagination. Assignment, status history, and internal notes use nested
  application routes.
- `/api/v1/applications/{application_id}/documents`: staff document upload
  and metadata listing, also available under `/api/v1/loan-applications`.
  Download file contents from `/api/v1/documents/{document_id}/download`
  (the earlier `/content` alias is retained). See Phase 5 below for review,
  replacement, deletion, and requirement configuration.
- `/api/v1/audit-logs`: administrator permission-gated, filterable audit
  history.

Paginated list responses contain `items`, `total`, `page`, and `page_size`;
page sizes are limited to 100. Document bytes are stored locally under
`DOCUMENT_STORAGE_PATH` (default `var/documents/`) for development. Uploads
are limited to PDF, JPEG, and PNG, with a default 10 MiB size cap controlled
by `MAX_DOCUMENT_SIZE_BYTES`. For deployment, configure a durable private
storage service and backup policy before using local storage in production.

Customer and loan-application APIs are staff-only. Customer accounts are not
given access to list or retrieve financial records because the current schema
does not associate a user account with an individual customer record.

## Phase 4: loan application engine

Apply the engine migration before starting the updated API:

```powershell
uv run alembic upgrade head
```

Revision `a41e9b26c803` adds the application `version` column and PostgreSQL
reference sequence. Existing records start at version 1 and retain their
references. The migration initializes the counter above existing numeric
`LN-YYYY-...` references.

### Submission and validation

Submit an application with `POST /api/v1/loan-applications`. The existing
`POST /api/v1/applications` remains supported and uses the same service.
Both require an active staff account with `loan_applications:create`.

```json
{
  "customer_id": "<existing customer UUID>",
  "loan_type_id": "<active loan type UUID>",
  "requested_amount": 500000,
  "tenure_months": 60,
  "employment_type": "SALARIED",
  "monthly_income": 60000,
  "purpose": "Home renovation"
}
```

A successful submission returns `201` with the application ID,
`LN-YYYY-000001` reference, `NEW` status, `version: 1`, financial fields,
timestamps, and customer/loan-type summaries. Missing customer or
missing/inactive loan type returns `404`; invalid field values return `422`.
Submission saves the application, initial history, and audit event in one
transaction.

Validation policies:

- Requested amount must be positive, with at most 15 total digits and two
  decimal places; tenure must be 1-600 months.
- Optional `monthly_income` must be positive when supplied, with the same
  monetary precision.
- Optional `employment_type` accepts `SALARIED`, `SELF_EMPLOYED`, `BUSINESS`,
  `UNEMPLOYED`, `RETIRED`, or `OTHER` (uppercase).
- These are input checks, not an automatic eligibility or approval decision.
  Existing employment strings remain readable.

References use the UTC year and one global PostgreSQL sequence, **not** a
counter that resets annually. The numeric part has a six-digit minimum width.
Concurrent submissions receive distinct references; rolled-back submissions
consume sequence values, so gaps are intentional. Existing `LA-...` references
are unchanged.

### Retrieval and updates

Both `/api/v1/loan-applications` and `/api/v1/applications` support:

| Method | Suffix | Purpose |
|---|---|---|
| `GET` | (none) | Paginated list and search |
| `GET` | `/{id}` | Details including customer and loan type |
| `PATCH` | `/{id}` | Update editable application fields |
| `PATCH` | `/{id}/assignment` | Assign active staff or clear assignment |
| `PATCH` | `/{id}/status` | Apply an allowed status transition |
| `POST` | `/emi` | Calculate an EMI without saving an application |

List filters can be combined: `reference`, `status`, `customer_id`,
`loan_type_id`, `assigned_to`, `date_from`, `date_to`, `page`, and `page_size`.
`reference` is a case-insensitive literal substring, not a SQL wildcard
pattern. Dates use `YYYY-MM-DD` and include the whole UTC calendar day;
reversed ranges return `422`. Pagination defaults to page 1, size 50, with
a maximum size of 100 and stable newest-first ordering.

**Client contract change:** application edits, assignment changes, and status
changes require `expected_version` on **both** API paths. Read the current
`version` from a detail or mutation response, then send it with the change:

```json
{
  "expected_version": 1,
  "status": "CONTACTED",
  "remarks": "Customer contacted by phone."
}
```

A successful mutation increments the version. A stale version returns `409`:
reload the application before deciding whether to retry. Missing/invalid
versions return `422`. Row locks and the version check prevent concurrent
updates from silently overwriting one another. Notes and documents do not
change the core application version.

### Lifecycle and history

Status updates still require a staff role and
`loan_applications:status_update` permission; the seeded administrator and
underwriter roles have this grant.

| Current status | Allowed next statuses |
|---|---|
| `NEW` | `CONTACTED`, `CANCELLED` |
| `CONTACTED` | `DOCUMENTS_PENDING`, `UNDER_REVIEW`, `CANCELLED` |
| `DOCUMENTS_PENDING` | `UNDER_REVIEW`, `CANCELLED` |
| `UNDER_REVIEW` | `DOCUMENTS_PENDING`, `SUBMITTED_TO_LENDER`, `REJECTED`, `CANCELLED` |
| `SUBMITTED_TO_LENDER` | `APPROVED`, `REJECTED`, `CANCELLED` |
| `APPROVED` | `DISBURSED`, `CANCELLED` |
| `REJECTED`, `DISBURSED`, `CANCELLED` | None (terminal) |

Self-transitions and invalid transitions return `409`. Nonblank remarks are
required for rejection, cancellation, and returning from `UNDER_REVIEW` to
`DOCUMENTS_PENDING`; missing required remarks return `422`.

Read history using `GET /api/v1/loan-applications/{id}/history`; the existing
`GET /api/v1/applications/{id}/status-history` remains supported. History
includes the initial `NEW` record, previous/new status, actor, remarks, and
timestamp. Status, history, version, and audit writes commit or roll back
together; rejected changes create no history/audit entry.

### EMI calculation

Call `POST /api/v1/loan-applications/emi` (or its legacy-path equivalent) with
an authorized staff bearer token and `loan_applications:read` permission:

```json
{
  "principal": "500000.00",
  "annual_interest_rate": "10",
  "tenure_months": 60
}
```

The response echoes these inputs and returns:

```json
{
  "principal": "500000.00",
  "annual_interest_rate": "10",
  "tenure_months": 60,
  "monthly_emi": "10623.52",
  "total_repayment": "637411.34",
  "total_interest": "137411.34"
}
```

Principal is positive with the same precision as application amounts; annual
interest is 0-100 percent with up to six decimal places; tenure is 1-600 months.
The reducing-balance formula uses `Decimal` and supports zero interest.
Currency outputs use two decimals with `ROUND_HALF_UP`. Totals are calculated
from the **unrounded** EMI, then rounded separately; displayed EMI multiplied
by tenure may therefore differ slightly from displayed total repayment.
This is a calculator, not a repayment schedule or a final-instalment adjustment.

### Tests

Run unit tests (PostgreSQL integration cases skip by default):

```powershell
uv run python -m pytest -q
```

Create a **separate** test PostgreSQL database, then run the full suite:

```powershell
uv run python -m app.database.setup_test_database
$env:RUN_POSTGRES_INTEGRATION = "1"
uv run python -m pytest -q
Remove-Item Env:\RUN_POSTGRES_INTEGRATION
```

All integration tests now require `TEST_DATABASE_URL` (or ignored `.env.test`).
The local helper creates `loan_management_test` without altering existing
databases and writes `.env.test` only if absent; it needs local CREATE DATABASE
permission. Alternatively provision a dedicated database yourself and set
`TEST_DATABASE_URL` securely. Tests reject production configuration, the
application database name, and names not ending in `_test`. They
create/drop uniquely named schemas **inside the test database** and use separate connections to check
real concurrent submissions and conflicting status changes. They also verify
transaction rollback, migration downgrade/upgrade and sequence initialization,
API lifecycle/history, combined search filters, and legacy-path parity.

## Phase 5: document management

### Setup and access

```powershell
uv sync
uv run alembic upgrade head
uv run python -m app.database.seed
uv run uvicorn app.main:app --reload
```

Revision `b52f0a37d914` adds document review/version/deletion metadata,
replacement links, review history, and configurable per-loan-type
requirements. Existing document types, filenames, and storage keys are
preserved; old documents start at `PENDING`, version/revision 1, each in its
own revision group. Run the seeder after migrating to add the new permissions
and initial requirements. Rerunning it preserves configured requirements,
including an intentionally empty requirement set.

Document routes are **staff-only** even if a customer role has a document
permission: customer access remains disabled until there is a trusted
user-to-customer ownership link.

| Action | Role and permission |
|---|---|
| Upload or replace | Staff + `documents:create` (seeded administrator/loan officer) |
| List, details, download, history, requirements | Staff + `documents:read` |
| Verify/reject/request resubmission | Administrator or underwriter + `documents:verify` |
| Soft delete | Administrator + `documents:delete` |
| Configure requirements | Administrator + `documents:configure` |

### 5.1 Categories and loan-specific requirements

`GET /api/v1/document-types` returns the accepted categories, formats, and
configured maximum byte size. New uploads use one of:

`PAN_CARD`, `AADHAAR_CARD`, `BANK_STATEMENT`, `SALARY_SLIPS`, `ITR`,
`ADDRESS_PROOF`, `PHOTOGRAPH`, `PROPERTY_DOCUMENTS`.

The initial seed configures PAN, Aadhaar, and bank statement as mandatory
for all five seeded loan types. Property documents are additionally mandatory
for Home Loan; all remaining categories are optional.

- `GET /api/v1/loan-types/{loan_type_id}/document-requirements`: configured
  mandatory/optional categories.
- `PUT` on the same path: administrator replaces the whole requirement set,
  with an audit event. Omitted categories are removed from requirements, not
  banned from upload; an empty set is allowed.
- `GET /api/v1/loan-applications/{application_id}/document-requirements`:
  category presence/verification, `missing_required`, `unverified_required`,
  `configured`, `complete`, and `verified_complete`.
  The `/api/v1/applications` equivalent is also supported.

Example configuration body:

```json
{
  "requirements": [
    {"document_type": "PAN_CARD", "is_required": true},
    {"document_type": "PHOTOGRAPH", "is_required": false}
  ]
}
```

Completeness is **non-blocking**: it does not change submission or application
status rules. `complete` means all mandatory categories have a current,
nondeleted upload, even if a review rejected it; `verified_complete` additionally
requires accepted documents. Unconfigured loan types report `configured: false`
and neither completeness flag is true. Requirements are evaluated using the
loan type's current configuration, not a submission-time snapshot.

### 5.2-5.5 Upload, storage, metadata, and download

Upload using multipart form fields `document_type` and `upload`:

```powershell
$token = "<access token>"
$applicationId = "<application UUID>"
curl.exe -X POST "http://127.0.0.1:8000/api/v1/loan-applications/$applicationId/documents" `
  -H "Authorization: Bearer $token" `
  -F "document_type=PAN_CARD" `
  -F "upload=@C:\documents\pan.pdf;type=application/pdf"
```

In Swagger, authorize first, select the upload endpoint, choose a category,
and select a file. The legacy `/api/v1/applications/{id}/documents` path
uses the same validation/service.

Validation checks extension **and** declared MIME **and** parsed content:

| MIME | Accepted extensions |
|---|---|
| `application/pdf` | `.pdf` |
| `image/jpeg` | `.jpg`, `.jpeg` |
| `image/png` | `.png` |

Pillow verifies/decodes images and rejects decompression-bomb warnings/errors.
pypdf parses PDFs and their page content; encrypted, empty-page, and malformed
PDFs are rejected. Header-only fake files are not accepted. The default maximum
is 10 MiB (`MAX_DOCUMENT_SIZE_BYTES`). Empty/invalid filenames return `422`,
oversized files `413`, invalid format/content `415`, and missing applications
`404`. New free-form document labels such as `identity` now return `422`;
legacy stored labels remain readable.

`DocumentStorage` separates file operations from document business logic.
The development implementation uses `DOCUMENT_STORAGE_PATH` (default
`var/documents`) with server-generated `{application UUID}/{random UUID}.{ext}`
keys and exclusive file creation. User filenames are display metadata only.
Paths are constrained to the private root; no static/public file mount or
storage key is exposed in responses. Bytes are never stored in PostgreSQL.
An alternative cloud backend can implement the same save/open/delete contract
and be injected through `get_document_storage`.

Partial or cancelled local writes are cleaned up. If database persistence
fails, its transaction rolls back and the new file is removed. Storage or
cleanup failures return `503` and are logged for operators rather than
returning a success-shaped response.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/loan-applications/{id}/documents` | Current, nondeleted documents; paginated |
| `GET` | `/api/v1/documents/{id}` | Metadata, review state, and document version |
| `GET` | `/api/v1/documents/{id}/download` | Authorized attachment download |
| `GET` | `/api/v1/documents/{id}/revisions` | All metadata revisions in the same group |
| `GET` | `/api/v1/documents/{id}/reviews` | Append-only review decisions for that revision |

The list accepts `page`, `page_size` (maximum 100), and `include_history=true`
to include replaced/soft-deleted metadata. Download also retains the old
`/content` alias. Responses use attachment disposition, `Cache-Control:
no-store`, and `X-Content-Type-Options: nosniff`. Authorized download initiation
is audited before streaming; the audit event does not prove complete delivery.

### 5.6 Verification

```http
PATCH /api/v1/documents/{document_id}/verification
```

```json
{
  "expected_version": 1,
  "status": "RESUBMISSION_REQUIRED",
  "remarks": "Please upload a clearer copy showing all four corners."
}
```

Statuses are `PENDING`, `VERIFIED`, `REJECTED`, and `RESUBMISSION_REQUIRED`.
Uploads/replacements start pending. Reviewers can set any nonpending status,
but cannot repeat the current status (`409`) or manually reset to pending
(`422`); submit a replacement instead. Rejection/resubmission require nonblank
remarks. Corrections to a previous review append a new review record rather
than erase the old decision.

Metadata exposes the latest reviewer, timestamp, and remarks. The fields
`verified_by`/`verified_at` record the **latest review**, including a rejection;
only `status: VERIFIED` means accepted. Review metadata, append-only history,
version increment, and audit event commit atomically.

### 5.7 Replacement and soft deletion

`POST /api/v1/documents/{id}/replacement` takes multipart fields
`document_type`, `expected_version`, and `upload`. Use the document version,
**not** the application's version.

- The successor gets a new ID/storage key, `PENDING`, version 1, and the next
  `revision`, linked by `replaces_document_id` and `document_group_id`.
- The prior file, review metadata, and review history are retained; its
  `replaced_at` is set and version increments.
- Known categories cannot change during replacement. A legacy free-form
  category can be mapped to an accepted category when replacing it.
- Concurrent replacements/reviews/deletions use a row lock and version check;
  stale versions return `409`. Deleted or replaced revisions cannot be edited.

Administrator soft deletion uses a JSON body:

```http
DELETE /api/v1/documents/{document_id}
```

```json
{
  "expected_version": 1,
  "remarks": "Duplicate upload."
}
```

Deletion records actor/time/reason in metadata/audit, increments version, hides
the current document from ordinary lists/completeness checks, and blocks its
downloads (`404`). It intentionally retains the physical file and historical
metadata. Replaced, nondeleted revisions remain downloadable by authorized
staff; deleting a current revision does not erase its predecessors. There is
no permanent purge endpoint or automatic retention expiration in this phase.

### 5.8 Testing and production boundaries

```powershell
# Focused unit tests
uv run python -m pytest tests\test_document_api.py -q

# Full regression suite including isolated PostgreSQL workflows
$env:RUN_POSTGRES_INTEGRATION = "1"
uv run python -m pytest -q
Remove-Item Env:\RUN_POSTGRES_INTEGRATION
```

Integration tests exercise real file storage, API lifecycle, permissions,
requirements/seeding, migration backfill, concurrent reviews/replacements,
and database rollback with file cleanup. New test files use temporary storage;
database fixtures use uniquely named schemas and remove them afterward.

Before production:

- Add malware scanning/quarantine and an approved clean-file release policy.
  Parsing a supported file **does not** establish that it is malware-free,
  script-free, or appropriate for a lender.
- Apply gateway request-size/rate limits and isolated parser resource limits;
  the endpoint size check happens after multipart intake.
- Use a private, durable storage backend or dedicated directory outside the
  web root, restrictive service-account filesystem permissions, encryption,
  backups, monitoring, and an approved retention/purge policy.
- Reconcile unreferenced files after crashes and failed cleanup. A filesystem
  and PostgreSQL do not share a distributed transaction; compensating cleanup
  handles observed failures but cannot guarantee crash-proof atomicity.
- Add customer ownership authorization before enabling customer access.

## Phase 6: notes, audit logs, and activity tracking

### Setup and compatibility

```powershell
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Revision `c63a1b48e025` adds bounded audit user-agent metadata, an audit
timestamp index, a user token-version counter, revoked-token digests, and a
private document deletion-reason field. Existing notes/audits remain intact;
there is no new timeline table and no automatic purge.

**Sign in again after upgrading.** Older JWTs do not contain the new required
version and unique-token claims, so they now return `401`. Newly issued tokens
still use the configured access-token lifetime.

Existing dotted audit action names are intentionally preserved, rather than
renaming historical events to uppercase. Administrators can discover the
supported names at `GET /api/v1/audit-logs/actions`.

### 6.1 Append-only internal notes

Both application prefixes support:

| Method | Path suffix | Purpose |
|---|---|---|
| `POST` | `/{application_id}/notes` | Add a note |
| `GET` | `/{application_id}/notes` | Paginated notes |
| `GET` | `/{application_id}/notes/{note_id}` | Retrieve a note belonging to that application |

Use `/api/v1/loan-applications` or the retained `/api/v1/applications` prefix.
Staff require `application_notes:create` to add notes and
`application_notes:read` to retrieve them. Customer accounts cannot access
internal notes, regardless of permission grants.

```http
POST /api/v1/loan-applications/{application_id}/notes
```

```json
{
  "note": "Customer requested two additional days to submit bank statements."
}
```

Notes are trimmed, nonblank, and limited to 10,000 characters. Responses
include author ID, application ID, and timestamps. Listing supports `page`,
`page_size` (1-100), and `sort=asc|desc` (default `desc`), ordered by creation
time and ID. Missing applications or mismatched/missing note IDs return `404`.
There are no note-edit or note-delete APIs. The note and its audit event commit
together; the note body is not copied into audit details.

### 6.2-6.3 Consistent, privacy-limited audit events

The shared audit service validates each action's entity type and structured
detail schema **before** adding a row. Unknown actions/entities/extra detail
fields fail explicitly. Invalid-detail errors do not echo rejected values.

Events capture actor ID (nullable for failed authentication), entity type/ID,
server timestamp, validated direct-peer IP, and a control-character-filtered
user-agent of at most 512 characters. Arbitrary `X-Forwarded-For` values are
not used by the audit service; configure trusted proxy handling at the server
boundary if deploying behind a proxy.

Tracked actions include:

| Area | Actions |
|---|---|
| Users | `user.created`, `user.updated`, `user.activated`, `user.deactivated`, `user.role_changed`, `user.password_changed` |
| Authentication | `auth.login_succeeded`, `auth.login_failed`, `auth.logged_out` |
| Customers | `customer.created`, `customer.updated` |
| Applications | `loan_application.created`, `loan_application.updated`, `loan_application.assigned`, `loan_application.status_updated` |
| Notes | `application_note.created` |
| Documents | `document.uploaded`, `document.reviewed`, `document.replaced`, `document.deleted`, `document.downloaded` |
| Administration | `document_requirements.updated` |

Details contain allowed UUID references, field **names**, statuses, categories,
sizes, or requirement booleans—not passwords, password hashes, bearer tokens,
emails, note bodies, filenames, file content, banking data, or unrestricted
free text. Document deletion remarks now live in protected document metadata
(`deletion_remarks`), not new audit records. Existing historical audit details
are preserved, not silently rewritten or sanitized by this migration.

Business mutations and their audit records use the same database transaction.
Failure to persist an audit prevents the relevant operation from succeeding;
errors propagate rather than being swallowed. Read/download audit events
indicate authorized access initiation, not proof of complete file delivery.

### 6.4 Login, logout, and account-security activity

- Successful token issuance records `auth.login_succeeded` and updates
  `last_login_at` in the same commit, before returning a token.
- Invalid credentials, unknown users, and inactive-account login attempts
  record `auth.login_failed` before returning the same generic `401`.
  Failed events deliberately omit the submitted email and target user ID;
  investigate them by time/IP/user-agent rather than by an unverified identity.
- `POST /api/v1/auth/logout` with the current bearer token returns `204`,
  atomically storing its SHA-256 digest/expiry and recording logout.
  The token then returns `401`; other sessions remain valid. No raw bearer
  token or token digest is copied into audit details.
- `POST /api/v1/auth/password` changes the authenticated user's password:

```json
{
  "current_password": "<current password>",
  "new_password": "<different password of at least 12 characters>"
}
```

Password change returns `204`, hashes the new password with the existing
Argon2 implementation, and invalidates **all** that user's existing tokens.
An incorrect current password returns `400`; invalid/unchanged new passwords
return `422`. Sign in with the new password afterward.

Administrator role changes and actual activation/deactivation changes also
increment the user's token version, preventing old tokens from working after
a later reactivation. A role change records both the existing generic
`user.updated` event and an explicit `user.role_changed` event with old/new
role IDs. Repeating an unchanged activation state is a successful no-op and
does not manufacture another state-change audit or invalidate sessions.

Token versions and revocation are checked on each authenticated request.
Invalidation applies to subsequent authorization checks, not retroactively
to requests already authorized and in flight. Expired revocation digests may
be removed through a future approved maintenance process; this phase does not
silently delete any records.

### 6.5 Application activity timeline

```http
GET /api/v1/loan-applications/{application_id}/activity?page=1&page_size=50&sort=asc
```

The legacy application prefix also works. Access requires a staff role,
`loan_applications:read`, **and** `application_notes:read`.

The database query combines:

- Internal notes, with their author and note text.
- Status history, including initial `NEW`, previous/new statuses, remarks,
  and changing user.
- Application audit events and document audit events linked to that
  application, including historical document revisions.

Note-creation/status-change audit copies are suppressed because the original
business records already represent those events. The application creation
audit and initial `NEW` history are distinct source records and both appear.
Other applications' events and global administrative/security events are
excluded.

Each item exposes a source, event ID/action/time, actor ID/current display
name, and applicable note/status/document fields. Global audit details, IP
addresses, user-agents, emails, and file storage locations are not exposed
through this staff timeline. Actor names reflect the current user record,
not an immutable historical name snapshot.

Pagination is applied to a SQL union, not to an in-memory collection of all
events. Ordering uses timestamp, source, and ID, with `sort=asc` (default) or
`desc`; ties have deterministic pagination. The response is the standard
`items`, `total`, `page`, `page_size` envelope.

### 6.6 Administrator audit investigation

`GET /api/v1/audit-logs` now requires **both** administrator role and
`audit_logs:read`, even if another role accidentally receives that permission.

Filters combine by AND:

- `user_id`
- `action` (exact dotted name; historical names remain searchable)
- `entity_type`
- `entity_id`
- `date_from`, `date_to` (inclusive UTC calendar dates, `YYYY-MM-DD`)
- `page`, `page_size` (1-100), `sort=asc|desc` (default `desc`)

For example:

```http
GET /api/v1/audit-logs?action=loan_application.created&entity_type=loan_application&date_from=2026-11-01&date_to=2026-11-05
```

Reversed dates or invalid pagination/sort return `422`. Timestamp/ID ordering
is deterministic, and IPv4/IPv6 values serialize correctly as JSON strings.
There are no ordinary APIs to modify or delete audit entries.

### 6.7 Retention, integrity boundaries, and tests

**Development retention policy:** retain notes and audit logs indefinitely;
no scheduled deletion, purge API, or automatic legal-retention assumption.

Before production, approve jurisdiction/business-specific retention periods,
legal holds, access review, encryption/backups, archival, and deletion
procedures. Application-level append-only APIs are **not** tamper-proof
against a database owner or privileged operator. Use least-privilege database
roles, separate administrative credentials, restricted update/delete grants,
and tamper-resistant external archival/monitoring as appropriate.

IP addresses and user-agent strings are personal/untrusted request metadata;
restrict access and include them in the retention/privacy review. Do not put
secrets in user-agent strings or internal notes. The shared PostgreSQL login
limiter now permits 10 attempts per minute per direct peer by default.
Add gateway abuse controls/monitoring before production; failed-login auditing
alone is not a brute-force prevention mechanism. See the proxy caveat in
[operations](OPERATIONS.md).

```powershell
# Focused audit privacy/unit checks
uv run python -m pytest tests\test_phase6_activity.py tests\test_jwt_auth.py -q

# Complete regression suite, including isolated PostgreSQL integration tests
$env:RUN_POSTGRES_INTEGRATION = "1"
uv run python -m pytest -q
Remove-Item Env:\RUN_POSTGRES_INTEGRATION
```

Integration coverage includes note creation/retrieval, mixed-source timeline
ordering/ties/isolation, combined audit filters, role/permission denials, real
logout/revocation, password/role/activation invalidation, migration roundtrip,
and audit-failure rollback for notes, authentication, and user mutations.

### Running pytest directly

From the repository root, both commands are supported:

```powershell
uv run pytest -q
uv run python -m pytest -q
```

The pytest configuration adds the repository root to its Python import path,
so the console entry point can import `app` just like the module invocation.
PostgreSQL integration tests skip unless `RUN_POSTGRES_INTEGRATION=1` is set;
enable them only with the separately configured test database described above.

Test clients use `httpx2` (including Starlette's `TestClient` and asynchronous
ASGI integration clients). Run `uv sync` after pulling dependency changes;
the legacy `httpx` dependency is no longer needed. To catch future deprecated
test-client usage, run:

```powershell
uv run pytest -q -W error::DeprecationWarning
```

## Phase 7: dashboard and reporting

Apply migrations and rerun the seeder to add the new grants:

```powershell
uv run alembic upgrade head
uv run python -m app.database.seed
```

| Endpoint | Access |
|---|---|
| `GET /api/v1/dashboard/summary` | Staff role + `dashboard:read` |
| `GET /api/v1/dashboard/application-statistics` | Staff role + `dashboard:read` |
| `GET /api/v1/reports/loan-types` | Administrator + `reports:read` |
| `GET /api/v1/reports/staff-performance` | Administrator + `reports:read` |
| `GET /api/v1/reports/application-processing` | Administrator + `reports:read` |
| `GET /api/v1/reports/financial-summary` | Administrator + `reports:read` |
| `GET /api/v1/reports/applications/export` | Administrator + `reports:export` |
| `GET /api/v1/reports/customers/export` | Administrator + `reports:export` |
| `GET /api/v1/reports/financial-summary/export` | Administrator + `reports:export` |
| `GET /api/v1/loan-types` and `/{id}` | Staff + `loan_applications:read` |

Use inclusive `date_from=2026-01-01&date_to=2026-01-31` and optional
`loan_type_id=<uuid>` for an **application submission-date UTC cohort**.
Customer export has its own customer creation-date filters, not loan type.
Reversed/invalid ranges return 422. Loan-type/staff/processing pages use
`page` and `page_size` (maximum 100). Processing also accepts `status` and
`threshold_days` (default 7): `pending_beyond_days` measures age since
submission; the returned stuck list measures age since the latest transition.
Unchanged applications use submission time.

Definitions:

- Approved means **currently APPROVED or DISBURSED**. Rejected means currently
  REJECTED. Rates divide by all applications in the filtered cohort.
- Awaiting review means DOCUMENTS_PENDING or UNDER_REVIEW.
- Customer and active-user dashboard counts are global; application totals
  obey the cohort. NEW/CONTACTED/other states are available in statistics.
- Staff attribution uses the **current assignee**, not historical ownership.
  Completion duration uses the first REJECTED, DISBURSED or CANCELLED history
  timestamp. Pending excludes those terminal states (APPROVED remains pending
  until disbursement/cancellation).
- Processing averages use the **first** matching history timestamp. Missing
  history yields `null`, not invented durations.
- Financial totals use PostgreSQL NUMERIC and Python Decimal. Actual approved
  and disbursed amounts are **not stored**, so their fields remain `null` and
  `actual_amounts_available=false`; CSV writes `UNAVAILABLE`. Requested amounts
  are never presented as actual approved/disbursed amounts.
- Empty data returns zero counts/sums/rates and null averages.
- Summary/statistics financial group lists are limited to 5000 groups; narrow
  filters if exceeded. Loan-type and staff rows include zero-activity records.
- `created_at` is now immutable on ORM updates, preserving cohort membership;
  `updated_at` still changes. Previously overwritten historical creation
  dates cannot be reconstructed automatically.

CSV exports allow **at most 5000 data rows**, otherwise return 422 before any
download/audit success. Cells beginning with spreadsheet formula characters
are escaped. Customer export contains only ID, name and creation time, not
email/phone/address/identity fields. These exports are still private business
data: authorization precedes queries, downloads use no-store, and successful
exports create structured `report.exported` audit events. Excel is not enabled.

Example in Swagger: authenticate, call
`/api/v1/reports/financial-summary?date_from=2026-01-01&date_to=2026-12-31`,
then inspect the explicit unavailable actual-amount fields.

## Phase 8: durable email notifications

Revision `d74b2c59f136` creates the PostgreSQL outbox and shared rate-limit
tables. No additional broker is needed. SMTP runs in a **separate worker**,
never inside request execution. Enqueueing commits/rolls back with the
application/document/history/audit transaction.

Email is **disabled by default** (`NOTIFICATIONS_ENABLED=false`): events do
not create queued messages and starting the worker fails explicitly. There
is no automatic retrospective notification when it is later enabled.

Configure `.env` using `.env.example`, then opt in explicitly:

```dotenv
NOTIFICATIONS_ENABLED=true
SMTP_HOST=your-provider-host
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_TIMEOUT_SECONDS=15
EMAIL_FROM=notifications@your-owned-domain.example
EMAIL_SENDER_NAME=Loan Management
# Set SMTP_USERNAME and SMTP_PASSWORD together through your secret manager.
NOTIFICATION_MAX_ATTEMPTS=3
NOTIFICATION_RETRY_SECONDS=60
NOTIFICATION_LEASE_SECONDS=300
```

Production requires TLS and a non-example sender. Do not copy the placeholder
sender into a real deployment. Start the configured worker:

```powershell
uv run python -m app.services.notification_worker
# Bounded processing of due jobs (exits when no jobs are due):
uv run python -m app.services.notification_worker --once --limit 100
```

| Event | Recipient |
|---|---|
| Application submitted / document uploaded or replaced | Active administrators + active assigned staff, deduplicated |
| Assignment | Active assignee |
| Status changed | Customer email, when present |
| DOCUMENTS_PENDING / document rejected or resubmission required | Customer email |
| APPROVED / REJECTED / DISBURSED | Customer email with dedicated generic template |

Templates are plain text + HTML, deliberately without names, loan amounts,
identity fields, document bytes, tokens or internal remarks. Missing/invalid
email is explicitly skipped and logged without exposing the address.
Customer enquiries are not wired because no enquiry API exists. SMS and
in-app delivery are optional and are not implemented.

Outbox statuses are PENDING, PROCESSING, SENT and FAILED. Workers claim jobs
with row locks/SKIP LOCKED, commit a lease before SMTP, and fence acknowledgements
with a lease token. Failed delivery is retried after exponentially increasing
delays, up to three attempts by default. FAILED can mean a scheduled retry or
an exhausted job; inspect `retry_count`/`available_at`. Expired leases recover
after a crash; exhausted final leases become FAILED.

Delivery is **at least once**, not exactly once. Stable event keys deduplicate
enqueueing and stable Message-ID helps correlation, but a crash between SMTP
acceptance and database acknowledgement can duplicate an email. SMTP acceptance
is not proof of inbox delivery; bounces are a provider operations concern.

Administrator history requires `notifications:read`:

- `GET /api/v1/notifications?status=FAILED&event_type=status_updated&application_id=<uuid>&page=1&page_size=50`
- `GET /api/v1/notifications/{id}`
- `POST /api/v1/notifications/{id}/retry` also requires `notifications:retry`.

Retry accepts only FAILED jobs, starts a new bounded attempt cycle immediately,
and creates `notification.retried` audit history. No arbitrary recipient/body
or general-purpose email-send endpoint is exposed. Outbox recipient addresses
are private, administrator-only data; event keys and lease tokens are omitted.

## Phase 9: validation, hardening and release preparation

- Shared PostgreSQL login limit: 10/minute/direct peer, configurable via
  `AUTH_RATE_LIMIT_*`. Counters commit independently of failed login auditing.
  429 responses include `Retry-After: 60`. Arbitrary forwarded IPs are ignored.
- Explicit CORS origins, production DEBUG/rate-limit/secret/TLS checks, hidden
  production docs, bounded database pools and SQL parameter redaction.
- Errors preserve existing `detail` while adding `code` and UUID `request_id`.
  The same ID is returned in `X-Request-ID`. Validation excludes raw inputs;
  500/503 responses and logs do not reveal internal exception/provider text.
  Client-supplied request IDs are accepted only if valid UUIDs.
- JSON request logs contain route templates, status and elapsed time, not
  request bodies or query values. Sensitive responses use `Cache-Control:
  no-store` and `X-Content-Type-Options: nosniff`.
- Tests cover authentication/RBAC, business workflows, transaction rollback,
  exact 5000-row CSV boundary, outbox dedup/retries/timeouts/concurrent claims,
  lease recovery/fencing, production CORS/docs and safe error responses.
- Integration tests use only the dedicated test database, with isolated
  schemas. A complete authenticated flow creates a customer/application,
  assigns staff, adds notes, uploads/reviews a document, reaches DISBURSED,
  checks history/timeline/dashboard/audit, and drains a **fake** email provider.
- Query-budget tests assert one dashboard query, two staff-report queries and
  five statistics queries independent of row count. A read-only EXPLAIN
  ANALYZE and 20 concurrent summary queries over 1200 records provide local
  regression evidence, not a production capacity guarantee.

Quality commands:

```powershell
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
uv run pytest -q -W error::DeprecationWarning
$env:RUN_POSTGRES_INTEGRATION="1"
uv run pytest -q -W error::DeprecationWarning
Remove-Item Env:\RUN_POSTGRES_INTEGRATION
```

See [operations and production gates](OPERATIONS.md) for container startup,
worker supervision, reverse-proxy/IP caveats, backup/restore rehearsal,
monitoring, retention and rollback. **Application implementation through 9.10
does not mean production deployment is approved**: live SMTP, target-platform
container execution, HTTPS, backup restoration, malware scanning, legal
retention and production workload acceptance remain operator gates.
