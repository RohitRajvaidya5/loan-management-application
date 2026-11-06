# Loan Management Application - Project Progress

## Phase 1: Backend Foundation

### 1. Create Project Directories

Created separate directories for frontend and backend development.

```text
loan-management-application/
├── frontend/
└── backend/
```

### 2. Configure uv

Installed `uv` as the Python package and project manager.

**Installation command:**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Version verification:**

- uv: 0.13.6
- Initial Python version: 3.11.9
- Active development environment later verified with Python 3.12.4.

### 3. Initialize Python Project

Initialized the backend Python project using:

```powershell
uv init
```

Initial project structure:

```text
backend/
├── .python-version
├── main.py
├── pyproject.toml
└── README.md
```

### 4. Install Dependencies

**Initial dependencies:**

```powershell
uv add fastapi "uvicorn[standard]" pydantic-settings
```

**Development dependencies:**

```powershell
uv add --dev pytest httpx ruff
```

**Database dependencies:**

```powershell
uv add sqlalchemy asyncpg alembic
```

### 5. Backend Project Structure

Created the backend application structure.

```text
backend/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── security.py
│   │   └── exceptions.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       └── __init__.py
│   │
│   ├── database/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   ├── dependencies/
│   └── utils/
│
├── tests/
├── alembic/
├── .venv/
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
└── uv.lock
```

### 6. Configure Environment Variables

Created `.env` and `.env.example`.

Configured the following application settings:

```env
APP_NAME=Loan Management API
APP_ENV=development
DEBUG=true
```

Configured the PostgreSQL database connection through `DATABASE_URL`.

The actual database credentials are stored in `.env` and excluded from Git.

### 7. Create Application Configuration

Created:

```text
app/core/config.py
```

Implemented a Pydantic Settings class to load environment variables and make application configuration available throughout the backend.

Used `SecretStr` for sensitive configuration values.

### 8. Add Health Check Endpoints

Implemented health check endpoints:

- `/health/live`: Checks whether the application is running.
- `/health/ready`: Checks application readiness, including database connectivity.

Configured application metadata, application name, environment and documentation URLs.

Verified the API through the browser and FastAPI documentation.

### 9. Git and Code Quality

- [x] Initialized Git repository.
- [x] Created `.gitignore`.
- [x] Excluded `.env`, `.venv` and Python-generated files.
- [x] Installed Ruff for code quality checks.
- [x] Installed pytest and HTTPX for testing.

---

## Phase 2: Database and ORM Setup

### 2.1 Create PostgreSQL Database

- [x] Installed and configured PostgreSQL.
- [x] Verified PostgreSQL connection through pgAdmin.
- [x] Created database: `loan_management_db`.
- [x] Created dedicated database role: `loan_app_user`.
- [x] Configured database ownership and privileges.
- [x] Verified database connectivity.

**Database details:**

- Database: `loan_management_db`
- PostgreSQL version: 18.6
- Port: 5432

### 2.2 SQLAlchemy and asyncpg Configuration

- [x] Installed SQLAlchemy 2.0.
- [x] Installed asyncpg.
- [x] Configured asynchronous SQLAlchemy engine.
- [x] Configured `async_sessionmaker`.
- [x] Created reusable asynchronous database session dependency.
- [x] Configured connection pooling with `pool_pre_ping=True`.
- [x] Verified database connection successfully.

Important files:

```text
app/database/
├── __init__.py
├── session.py
├── base.py
└── check_connection.py
```

### 2.3 Alembic and Database Migrations

#### 1. Initialize Alembic

Command:

```powershell
uv run alembic init -t async alembic
```

- [x] Initialized Alembic using the asynchronous migration template.
- [x] Created the `alembic` directory.
- [x] Created `alembic.ini`.
- [x] Created migration environment and version directories.

#### 2. Configure Alembic

- [x] Updated `alembic/env.py` to use SQLAlchemy declarative `Base`.
- [x] Configured Alembic to load the database URL from application settings.
- [x] Configured asynchronous database migrations using SQLAlchemy's async engine.
- [x] Enabled automatic detection of column type changes using `compare_type=True`.
- [x] Removed the hardcoded database URL from `alembic.ini`.
- [x] Registered SQLAlchemy models through `app/models/__init__.py`.

#### 3. Verify Alembic Configuration

Commands:

```powershell
uv run alembic current
```

```powershell
uv run alembic history
```

Results:

- [x] Successfully identified PostgreSQL as the database dialect.
- [x] Verified Alembic migration context.
- [x] Confirmed Alembic configuration is working correctly.

### 2.4 Database Design and SQLAlchemy Models

Designed the initial relational database structure for the Loan Management System.

Implemented the following models:

| Model | Purpose |
|---|---|
| Role | Stores application roles |
| Permission | Stores application permissions |
| RolePermission | Maps roles to permissions |
| User | Stores administrative and staff users |
| Customer | Stores customer information |
| LoanType | Stores available loan types |
| LoanApplication | Stores loan application details |
| ApplicationStatusHistory | Tracks application status changes |
| Document | Stores document metadata |
| ApplicationNote | Stores internal application notes |
| AuditLog | Stores application audit records |

**Common database design decisions:**

- UUID primary keys.
- Created and updated timestamps where applicable.
- PostgreSQL timezone-aware timestamps.
- NUMERIC fields for monetary values.
- PostgreSQL JSONB for audit log details.
- PostgreSQL INET for IP addresses.
- Foreign-key constraints.
- Unique constraints and indexes.
- PostgreSQL enum for application status.

**Application statuses:**

1. NEW
2. CONTACTED
3. DOCUMENTS_PENDING
4. UNDER_REVIEW
5. SUBMITTED_TO_LENDER
6. APPROVED
7. REJECTED
8. DISBURSED
9. CANCELLED

### 2.5 SQLAlchemy Model Relationships

- [x] Created the common declarative `Base` class.
- [x] Created UUID primary-key mixin.
- [x] Created timestamp mixin.
- [x] Implemented Role and Permission relationships.
- [x] Implemented many-to-many RolePermission association.
- [x] Implemented User and Role relationships.
- [x] Implemented Customer and LoanApplication relationships.
- [x] Implemented LoanType and LoanApplication relationships.
- [x] Implemented LoanApplication assignment to users.
- [x] Implemented application status history relationships.
- [x] Implemented document relationships.
- [x] Implemented application notes relationships.
- [x] Implemented audit log relationships.
- [x] Registered all 11 models with SQLAlchemy metadata.
- [x] Verified model registration and relationships.

**Registered application tables:**

1. application_notes
2. application_status_history
3. audit_logs
4. customers
5. documents
6. loan_applications
7. loan_types
8. permissions
9. role_permissions
10. roles
11. users

### 2.6 Initial Database Migration

Generated the initial database migration using Alembic autogenerate.

**Migration file:**

```text
alembic/versions/
└── 0cca17cb8963_create_initial_database_schema.py
```

**Migration revision:**

`0cca17cb8963`

**Completed tasks:**

- [x] Generated initial migration.
- [x] Reviewed generated table definitions.
- [x] Reviewed foreign-key constraints and indexes.
- [x] Corrected PostgreSQL enum handling.
- [x] Created the `application_status` enum once and reused it across three columns.
- [x] Configured enum deletion in migration downgrade.
- [x] Applied migration successfully to PostgreSQL.
- [x] Verified Alembic migration status.

**Commands:**

```powershell
uv run alembic upgrade head
```

```powershell
uv run alembic current
```

**Current Alembic revision:**

`0cca17cb8963 (head)`

### 2.7 Database Schema Verification

Completed database schema verification through pgAdmin and PostgreSQL information schema queries.

#### 1. Table Verification

- [x] Verified all 11 application tables.
- [x] Confirmed `alembic_version` table exists separately.

#### 2. Column and Data Type Verification

- [x] Verified columns across all 11 application tables.
- [x] Verified UUID columns.
- [x] Verified NUMERIC monetary fields.
- [x] Verified timezone-aware timestamps.
- [x] Verified JSONB audit details.
- [x] Verified INET IP address field.
- [x] Verified PostgreSQL enum columns.
- [x] Reviewed nullable and non-nullable columns.

**Note:** `application_notes` currently uses an append-only design and does not contain an `updated_at` column.

#### 3. Foreign-Key Verification

- [x] Verified all 13 foreign-key constraints.
- [x] Verified User and Role relationship.
- [x] Verified Role and Permission relationships.
- [x] Verified Customer and LoanApplication relationship.
- [x] Verified LoanType and LoanApplication relationship.
- [x] Verified application assignment relationship.
- [x] Verified document relationships.
- [x] Verified application notes relationships.
- [x] Verified status history relationships.
- [x] Verified audit log relationship.
- [x] Reviewed ON DELETE rules: NO ACTION, CASCADE and SET NULL.

#### 4. PostgreSQL Enum Verification

- [x] Verified `application_status` enum.
- [x] Verified all 9 enum values.
- [x] Confirmed enum ordering matches the application workflow.

#### 5. Index Verification

- [x] Verified 32 indexes across the database, including the Alembic version table.
- [x] Verified primary-key indexes.
- [x] Verified unique indexes and constraints.
- [x] Verified foreign-key lookup indexes.
- [x] Verified unique user email index.
- [x] Verified unique loan application number index.
- [x] Verified document storage key uniqueness.

**Phase 2 Status: Completed**

The initial database schema has been successfully created, migrated and verified.

---

## Phase 3: Backend API Development

### 3.1 Database Seed Data

**Status: Completed**

Planned tasks:

- [x] Design initial role seed data.
- [x] Define initial permissions.
- [x] Map permissions to roles.
- [x] Create initial loan type records.
- [x] Implement an idempotent database seeding process.
- [x] Verify seeded records in PostgreSQL (4 roles, 18 permissions, 41 role-permission mappings, and 5 loan types).

#### Implementation Details

- Added `app/database/seed.py` with the initial roles: `administrator`,
  `loan_officer`, `underwriter`, and `customer`.
- Defined 18 named permissions covering user management, customer management,
  loan-application management and assignment, status updates, application
  notes, documents, and audit-log reads.
- Mapped all 18 permissions to `administrator`; assigned operational
  customer/application permissions to `loan_officer`, review and status
  permissions to `underwriter`, and customer-facing read/application/document
  permissions to `customer`.
- Seeded five loan types: Personal Loan, Auto Loan, Home Loan, Business Loan,
  and Education Loan.
- Used PostgreSQL `ON CONFLICT DO NOTHING` for roles, permissions,
  role-permission mappings, and loan types. Re-running the seeder adds missing
  baseline rows without replacing existing records or removing custom grants.
- Run after database migrations with `uv run python -m app.database.seed`.
- Ran the seeder twice and verified PostgreSQL contains 4 roles, 18
  permissions, 41 role-permission mappings, and 5 loan types. Ruff lint and
  format checks, Python compilation, and `git diff --check` passed.

### 3.2 Authentication and Password Hashing

**Status: Completed**

- [x] Select Argon2id password hashing using `argon2-cffi`.
- [x] Implement password hashing.
- [x] Implement password verification.
- [x] Add authentication schemas and services.

#### Implementation Details

- Added `app/core/security.py` with Argon2id password hashing and verification.
  Passwords are never stored in plaintext; each hash uses a random salt.
- Invalid hashes and incorrect passwords fail verification without exposing
  password details.
- Added `LoginRequest` in `app/schemas/auth.py`, using `SecretStr` for the
  password, trimming surrounding email whitespace, enforcing field length
  limits, and rejecting unexpected fields.
- Added `authenticate_user` in `app/services/auth.py`. It looks up the user by
  email and returns a user only when the password is valid and the account is
  active; invalid credentials and unknown users return `None`.
- Added `argon2-cffi` as a runtime dependency and updated `uv.lock`.
- Added focused tests for password hashing, unique salts, invalid hashes,
  credential verification, inactive/unknown users, and login-schema handling.
- Validation: 10 focused tests passed; Ruff lint/format checks, Pylance
  diagnostics for the changed Python files, and `git diff --check` passed.

### 3.3 JWT Access-Token Authentication

**Status: Completed**

- [x] Configure JWT using PyJWT and HS256 with a required signing secret and 15-minute default expiry.
- [x] Implement access-token generation.
- [x] Implement token validation.
- [x] Create current-user dependency.
- [x] Protect an authenticated endpoint and add a token-issuing endpoint.

#### Implementation Details

- Added PyJWT and configured `JWT_SECRET_KEY` as a required secret of at least
  32 characters. `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` defaults to 15 and must be
  positive; no signing-key default is provided.
- Added JWT creation and validation in `app/core/security.py`. Access tokens
  contain the user ID, issue/expiry times, and an access-token type. Validation
  restricts the algorithm to HS256 and rejects expired, malformed, wrongly
  signed, or non-access tokens.
- Added `POST /api/v1/auth/token`, which issues a bearer token after verifying
  active-user credentials, and protected `GET /api/v1/auth/me`.
- The current-user dependency validates the token subject, reloads the user
  from PostgreSQL, and rejects missing, malformed, unknown, or inactive users.
- Added JWT secret and lifetime settings to `.env.example`; documented secret
  generation and endpoint usage in `README.md`.
- Added tests for token creation/validation and both authentication endpoints.
- Validation: all 20 tests passed; Ruff, Pylance diagnostics, and
  `git diff --check` passed. The test run reports a Starlette/httpx
  deprecation warning from the installed test-client package.

### 3.4 Role-Based Access Control

**Status: Completed**

- [x] Implement permission checking.
- [x] Implement role-based authorization.
- [x] Restrict API access according to user permissions.

#### Implementation Details

- Added reusable `require_permission(...)` and `require_role(...)` dependencies
  in `app/api/v1/dependencies.py`. Both require an authenticated active user
  and query the database using that user's assigned role.
- Permission checks match a permission name through `role_permissions`;
  role checks accept one or more exact role names. Blank requirements are
  rejected, and unauthorized users receive `403 Forbidden`.
- Documented how to apply the guards to FastAPI routes in `README.md`. The
  application does not yet have customer, loan, or user-management routes;
  those routes can apply the corresponding guards as they are added.
- Added protected-route tests for granted and denied permissions and roles,
  plus validation of empty requirements.
- Validation: all 25 tests passed; Ruff, Pylance diagnostics, and
  `git diff --check` passed. The test run reports the existing
  Starlette/httpx test-client deprecation warning.

### 3.5 User Management APIs

**Status: Completed**

- [x] Create user.
- [x] Retrieve users.
- [x] Retrieve user by ID.
- [x] Update user.
- [x] Activate and deactivate users.

#### Implementation Details

- Added administrator-only user creation, paginated list/retrieve, partial
  profile/role updates, and a separate activation endpoint under
  `/api/v1/users`.
- Passwords are accepted as secrets and stored only as Argon2 hashes. User
  response schemas never expose password hashes. Email addresses are validated
  and normalized; duplicate email conflicts return `409`.
- Role IDs are validated against existing roles. User creation is
  administrator-controlled, not public signup. Added a local interactive
  `app.database.create_admin` bootstrap command for the first administrator;
  it reads passwords through a hidden prompt and refuses when an administrator
  already exists.
- User create, update, and activation changes are audited.

### 3.6 Customer Management APIs

**Status: Completed**

- [x] Create customer.
- [x] Retrieve customers.
- [x] Retrieve customer by ID.
- [x] Update customer.
- [x] Search and filter customers.

#### Implementation Details

- Added staff-only customer create, paginated list/retrieve, and partial update
  endpoints under `/api/v1/customers`.
- List supports text search across name, email, and phone, plus city and state
  filters. Customer create/update operations are audited.
- Customer-account access is intentionally not exposed: the current schema
  does not link a user login to a customer record, so customer self-service
  could expose other customers' financial data.

### 3.7 Loan Application APIs

**Status: Completed**

- [x] Create loan application.
- [x] Retrieve loan applications.
- [x] Retrieve application by ID.
- [x] Update application.
- [x] Assign application to staff.
- [x] Implement application filtering and pagination.

#### Implementation Details

- Added staff-only application create, paginated list/retrieve, update, and
  assignment endpoints under `/api/v1/applications`.
- Creation validates the customer and active loan type, generates a unique
  application number, and records the initial `NEW` status in history.
- List filters include status, customer ID, and assigned staff ID. Assignment
  is limited to active staff accounts and may be cleared.
- Create, update, and assignment operations are audited. API models validate
  positive requested amounts/income and tenure ranges.

### 3.8 Application Workflow and Supporting APIs

**Status: Completed**

- [x] Implement application status updates.
- [x] Record status history.
- [x] Implement internal application notes.
- [x] Implement document metadata management.
- [x] Integrate document storage.
- [x] Implement audit logging.

#### Implementation Details

- Added status update and status-history read endpoints. Each status change
  stores previous/new status, actor, timestamp, and optional remarks. As
  agreed, any defined status is accepted.
- Added staff-only internal-note create/list endpoints.
- Added staff-only document upload, metadata listing, and content download.
  Development storage uses `DOCUMENT_STORAGE_PATH` (default `var/documents`),
  stores files under generated keys, limits uploads to PDF/JPEG/PNG and
  10 MiB by default, validates file signatures, and removes a newly written
  file if its database transaction fails. Storage keys are not returned by
  the metadata API.
- Added audit records for user, customer, application, assignment, status,
  note, and document changes, plus a permission-protected paginated audit-log
  query API.
- Added `email-validator` and `python-multipart` dependencies and documented
  endpoint paths, access policy, pagination, and local-storage configuration
  in `README.md`.
- Validation: 35 tests passed, including management schemas, admin user
  creation/auditing, application status history/auditing, RBAC, and document
  upload validation/storage. Ruff lint/format, Python compilation,
  OpenAPI generation (18 paths), Pylance diagnostics, and `git diff --check`
  passed. The test run reports the existing Starlette/httpx test-client
  deprecation warning. CRUD workflows have not yet been exercised against a
  live PostgreSQL database.

---

## Phase 4: Loan Application Engine

**Status: Completed - 8/8 modules completed**

Reused the Phase 3 models, schemas, authentication, and authorization. After
completing submission, implemented the remaining modules using the approved
validation, lifecycle, reference, financial-rounding, and concurrency policies.
Both application API paths remain available, with an intentional new
`expected_version` requirement on core application PATCH requests.

### 4.1 Application Submission

**Status: Completed**

- [x] Review the existing `LoanApplication` model and database constraints.
- [x] Reuse `LoanApplicationCreate` and `LoanApplicationResponse` schemas.
- [x] Add application repository functions and a submission service.
- [x] Implement `POST /api/v1/loan-applications`.
- [x] Validate customer existence and loan type existence/active state.
- [x] Save the application, initial status history, and audit event together.
- [x] Return the created application with related customer/loan-type data.
- [x] Add API tests and verify persistence in PostgreSQL.

#### Implementation Details

- Reused the UUID relationships, `Numeric(15, 2)` monetary columns, existing
  unique application-number constraint, and `NEW` initial status without
  changing the database schema.
- Added `app/repositories/loan_application_repository.py` for reference
  lookup, application insertion, and eager-loaded application retrieval.
- Added `app/services/loan_application_service.py` for database-dependent
  validation and transactional submission. Response validation occurs before
  commit; a failed write/commit rolls back and propagates the error.
- Added the requested `/api/v1/loan-applications` submission route while
  retaining `/api/v1/applications` as a compatible submission route. Both
  use the same service and existing staff/permission guards.
- At completion of 4.1, retained the random `LA-...` reference format.
  Modules 4.2-4.8 below subsequently added sequential references, employment
  policy, lifecycle rules, and EMI; older stored references remain unchanged.
- Added API tests covering both paths, initial history/audit records, missing
  and inactive references, invalid inputs, authentication/authorization
  denials, and rollback on commit failure.
- Added an opt-in PostgreSQL test that verifies application/history/audit
  persistence through the API and rolls back its test records with an outer
  transaction. Set `RUN_POSTGRES_INTEGRATION=1` to run it against the configured
  development/test database; ordinary unit tests retain their dummy database
  configuration.
- Validation: all 50 tests passed with the PostgreSQL integration test enabled.
  The integration test confirmed application, initial history, and audit rows
  and verified that its test application was absent after rollback. Task-scoped
  Ruff lint/format checks, Pylance diagnostics, and `git diff --check` passed.
  The existing Starlette/httpx test-client deprecation warning remains.

### 4.2 Input Validation

**Status: Completed**

- [x] Define accepted employment types and eligibility-input rules.
- [x] Extend field validation and service-level business validation.
- [x] Add positive and negative tests for the agreed policies.

#### Implementation Details

- Added the shared employment enum: `SALARIED`, `SELF_EMPLOYED`, `BUSINESS`,
  `UNEMPLOYED`, `RETIRED`, and `OTHER`. Create/update inputs enforce uppercase
  values; employment and monthly income remain optional.
- Enforced positive requested amount and supplied income, monetary precision
  compatible with `Numeric(15, 2)`, and tenure between 1 and 600 months.
- Kept customer existence and active loan-type validation in the service;
  edits that change loan type also validate the new reference.
- Invalid fields return `422`; missing customers or missing/inactive loan
  types return `404`. No unapproved age/income eligibility decision was added.
- Tests cover valid inputs, unsupported employment values, missing fields,
  nonpositive/nonfinite money, excessive precision/amount, and tenure bounds.

### 4.3 Application Reference Number Generation

**Status: Completed**

- [x] Agree sequential reference format and implement atomic database-backed generation.
- [x] Verify concurrent uniqueness and rollback behavior.

#### Implementation Details

- Added `app/services/application_reference.py` using a PostgreSQL sequence
  and UTC year to generate `LN-YYYY-000001` references.
- The counter is global and never resets annually; padding is a minimum of
  six digits. Existing `LA-...` references and the database uniqueness
  constraint are preserved.
- Added Alembic revision `a41e9b26c803`, initializing the sequence above
  existing numeric `LN-YYYY-...` references. Applied it successfully to the
  configured PostgreSQL database.
- Real parallel submissions verify ten distinct sequential references.
  A rolled-back `nextval` is not reused: gaps are intentional.
- An isolated-schema downgrade/upgrade test confirms reference preservation,
  version initialization, and sequence continuation after an existing
  `LN-2026-000100` reference.

### 4.4 Application Status Management

**Status: Completed**

- [x] Define permitted transitions, required remarks, and terminal-state rules.
- [x] Implement status service and the new loan-application status endpoint.
- [x] Test permitted/denied transitions and concurrent changes.

#### Implementation Details

- Added a centralized transition policy in
  `app/services/application_status_service.py` and transactional status
  mutation in the shared application service.
- Implemented `PATCH /api/v1/loan-applications/{id}/status`; the legacy
  application status endpoint uses the same service and policy.
- Approved transitions:

  | Current status | Allowed next statuses |
  |---|---|
  | `NEW` | `CONTACTED`, `CANCELLED` |
  | `CONTACTED` | `DOCUMENTS_PENDING`, `UNDER_REVIEW`, `CANCELLED` |
  | `DOCUMENTS_PENDING` | `UNDER_REVIEW`, `CANCELLED` |
  | `UNDER_REVIEW` | `DOCUMENTS_PENDING`, `SUBMITTED_TO_LENDER`, `REJECTED`, `CANCELLED` |
  | `SUBMITTED_TO_LENDER` | `APPROVED`, `REJECTED`, `CANCELLED` |
  | `APPROVED` | `DISBURSED`, `CANCELLED` |
  | `REJECTED`, `DISBURSED`, `CANCELLED` | None |

- Terminal statuses cannot be reopened; self-transitions are also denied.
  Invalid transitions return `409`.
- Nonblank remarks are mandatory for rejection, cancellation, and review
  returning to documents pending; missing remarks return `422`.
- Retained staff-role and status-update permission checks. Tests exercise all
  81 source/destination combinations, remarks rules, protected routes, and
  concurrent attempts. These rules supersede Phase 3's unrestricted
  defined-status update behavior.

### 4.5 Application Status History

**Status: Completed**

- [x] Extend existing transactional history handling for the Phase 4 workflow.
- [x] Add `GET /api/v1/loan-applications/{id}/history`.
- [x] Test history accuracy and rollback together with status updates.

#### Implementation Details

- Reused the existing history model/schema and retained the legacy
  `/api/v1/applications/{id}/status-history` endpoint.
- Persisted previous/new status, changing user, remarks, and timestamp.
  Submission still creates the initial `NEW` history entry.
- Status, version increment, history, and audit record commit in one
  transaction. Invalid or stale changes produce no extra history.
- PostgreSQL tests verify ordered lifecycle history and force a foreign-key
  failure to prove status/version/history/audit changes roll back together.

### 4.6 EMI Calculation Engine

**Status: Completed**

- [x] Implement Decimal-based reducing-balance EMI, total repayment, and interest.
- [x] Handle zero interest and define two-decimal rounding semantics.
- [x] Test financial scenarios and invalid inputs.

#### Implementation Details

- Added validated EMI schemas and `app/services/emi_calculator.py` using
  `Decimal` with precision 60 and monthly rate = annual percent / 1200.
- Added protected `POST /api/v1/loan-applications/emi` and
  `/api/v1/applications/emi` routes, requiring staff and application-read
  permission. Calculations do not create application records.
- Accepted positive principal, 0-100% annual interest with up to six decimal
  places, and 1-600 months; zero interest uses principal / tenure.
- Rounded currency outputs to cents with `ROUND_HALF_UP`. Total repayment
  and interest derive from the unrounded EMI before separate rounding,
  so displayed EMI times months may differ slightly from displayed total.
- Verified the 500000 principal, 10% annual rate, 60-month example:
  EMI `10623.52`, repayment `637411.34`, interest `137411.34`.
- Added unit cases for known financial outcomes, zero interest, rounding,
  allowed boundaries, and invalid inputs. This is not an amortization
  schedule or final-payment adjustment.

### 4.7 Application Retrieval and Search

**Status: Completed**

- [x] Extend pagination/detail queries with reference, loan-type, and date filters.
- [x] Expose Phase 4 retrieval routes and verify filter combinations.

#### Implementation Details

- Added Phase 4 list/detail, update, and assignment routes by reusing existing
  handlers, preserving a single implementation across both API paths.
- Combined `reference`, `status`, `customer_id`, `loan_type_id`, `assigned_to`,
  `date_from`, and `date_to` filtering with existing pagination.
- Reference matching is case-insensitive literal substring search, escaping
  SQL wildcard characters. Date bounds include complete UTC calendar days;
  reversed date ranges return `422`, and the maximum date avoids overflow.
- Kept related customer/loan-type/assigned-user details, stable newest-first
  ordering, and page sizes from 1 to 100.
- PostgreSQL API tests cover combined filters, individually mismatching
  filters, pagination, date boundaries, and legacy-list response parity.

### 4.8 Application Transaction and Concurrency Safety

**Status: Completed**

- [x] Add concurrency protection for lifecycle updates and reference generation.
- [x] Test concurrent submissions, conflicting updates, and transaction rollback.

#### Implementation Details

- Added a non-null `version` column, initialized to 1 for existing/new rows.
  Application responses now expose the current version.
- Application edits, assignment, and status PATCH requests on both paths
  require `expected_version >= 1`. Mutations lock the application row,
  refresh cached ORM state, compare versions, and increment once on success.
- Stale versions return `409` with reload guidance; missing versions return
  `422`. This is an approved client contract change. Notes/documents do not
  increment the core application version.
- Locked only the application table, avoiding nullable joined-relationship
  locking errors. Centralized transaction handling rolls back unsuccessful
  writes/commits while propagating errors.
- Tests use independent PostgreSQL connections: ten concurrent submissions
  succeed uniquely; two competing version-1 changes yield one success and
  one conflict, with only one additional history/audit entry.
- New engine integration tests create and clean up uniquely named schemas;
  existing submission integration records are rolled back via savepoints.
  Run integration tests only against a development/test database.

#### Phase 4 Verification

- Full suite with `RUN_POSTGRES_INTEGRATION=1`: **195 passed**.
- Verified migration application, isolated migration roundtrip, live
  concurrency, sequence gaps, transaction rollback, lifecycle/history,
  API filtering, permission denials, and EMI output.
- Ruff lint passed on new engine, schema, repository, API, migration, and
  test files; all 16 task-scoped Python files passed formatting checks.
  The existing application model still reports six pre-existing `F821`
  forward-reference findings, confirmed against the original Git version.
  They were not changed as part of this phase.
- Pylance reported no diagnostics on the engine services, schemas, API
  handlers, repository, employment enum, and migration. Service syntax
  validation and `git diff --check` passed.
- Generated OpenAPI and verified both API paths and required version fields.
  Confirmed no `phase4_test_...` PostgreSQL schemas remained after testing.
- Existing Starlette/httpx TestClient deprecation warning remains; no
  unrelated dependency changes were made to suppress it.

---

## Phase 5: Document Management System

**Status: Completed - 8/8 modules completed**

Implemented all modules after confirming staff-only access, the initial
loan-specific requirement matrix, reviewer roles, immutable replacement
revisions, administrator soft deletion, and PDF/JPEG/PNG parser validation.
Customer access remains deferred until the schema supports trusted ownership.

### 5.1 Document Types and Requirements

**Status: Completed**

- [x] Define accepted document categories.
- [x] Define mandatory/optional requirements by loan type.
- [x] Configure maximum size and accepted formats.
- [x] Provide requirement configuration and completeness APIs.

#### Implementation Details

- Added the eight-category `DocumentType` enum: PAN, Aadhaar, bank statement,
  salary slips, ITR, address proof, photograph, and property documents.
  `GET /api/v1/document-types` exposes accepted values, extensions/MIME types,
  and the configured upload-size cap.
- Added `document_requirements` keyed uniquely by loan type and category.
  Administrator-only PUT replaces a loan type's requirement set; GET exposes
  configuration. Both use the existing authentication/permission system.
- Extended the idempotent seeder with mandatory PAN/Aadhaar/bank statements
  for all five baseline loan types and mandatory Home Loan property documents.
  Remaining categories are optional, yielding 40 initial requirement records.
- A loan-type configuration marker prevents reseeding from restoring removed
  requirements or overwriting custom/empty configurations.
- Application requirement summaries report present/verified categories,
  missing/unverified mandatory types, configuration state, and two completeness
  flags. These checks are informational and do not silently change Phase 4
  submission or status policies.

### 5.2 Document Upload API

**Status: Completed**

- [x] Implement the requested multipart upload endpoint.
- [x] Validate category, application, file extension/MIME/content, and size.
- [x] Enforce permissions and persist metadata/audit atomically.
- [x] Add positive and negative upload tests.

#### Implementation Details

- Added `POST /api/v1/loan-applications/{id}/documents` while retaining the
  legacy `/api/v1/applications/{id}/documents`. Both call the same service.
- Multipart fields are `document_type` and `upload`. New uploads require an
  accepted enum category; older free-form database labels remain readable.
- Retained the configurable 10 MiB default limit and PDF/JPEG/PNG formats.
  Extension, declared MIME, signatures, and actual parser results must agree.
- Empty files/invalid filenames return `422`, unsupported/malformed content
  `415`, oversized files `413`, missing applications `404`, and unauthorized
  requests `401`/`403`. Upload streams close even on validation failure.
- Added Pillow and pypdf to the manifest/lockfile and installed them through
  `uv sync`; resolved Pillow 13.0.0 and pypdf 6.21.4.

### 5.3 File Storage Integration

**Status: Completed**

- [x] Add a replaceable storage contract and private local implementation.
- [x] Generate collision-resistant server-side storage names.
- [x] Handle write failures, partial writes, cancellation, and DB rollback.
- [x] Keep bytes outside PostgreSQL and public static routes.

#### Implementation Details

- Added `DocumentStorage` save/open/delete protocol with injectable
  `LocalDocumentStorage`. This is the extension point for a future private
  cloud backend; no cloud credentials or provider coupling were introduced.
- Preserved `DOCUMENT_STORAGE_PATH` (default `var/documents`) and existing
  storage keys. New keys use application UUID directories and random UUID
  filenames with validated extensions, created exclusively.
- Local path resolution rejects traversal, absolute paths, drive prefixes,
  backslashes, and paths outside the private root. Original filenames are
  sanitized display metadata, never used as storage paths.
- File I/O runs off the event loop. Partial/cancelled writes are removed;
  failed persistence rolls back the database and removes the new file.
- Storage/cleanup errors are logged and surfaced as `503`. No silent
  successful response is returned when storage operations fail.
- Documented that compensating cleanup is not a distributed transaction:
  process crashes or failed cleanup need operator reconciliation.

### 5.4 Document Metadata Management

**Status: Completed**

- [x] Review and extend the existing document model/response schema.
- [x] Preserve filename, storage key, type, MIME, size, uploader, and time.
- [x] Add listing/details/revision/review-history APIs.
- [x] Migrate existing records without rewriting their file keys or labels.

#### Implementation Details

- Added Alembic revision `b52f0a37d914` after the Phase 4 migration.
  It adds review/version/replacement/deletion fields, review-history and
  requirement tables, and the loan-type requirement-configuration marker.
- Backfilled each existing document into its own revision group with pending
  status and version/revision 1. Kept historical type labels and storage keys.
- Added paginated listing on both application paths, metadata lookup at
  `/api/v1/documents/{id}`, revision-group history at `/revisions`, and
  append-only review history at `/reviews`.
- Ordinary lists exclude replaced/deleted revisions; `include_history=true`
  includes their metadata. Responses omit private storage keys/paths.
- Migration was applied successfully to configured PostgreSQL. An isolated
  downgrade/upgrade test verifies legacy-row backfill and preservation.

### 5.5 Document Retrieval and Download

**Status: Completed**

- [x] Add the requested authorized download endpoint.
- [x] Preserve the legacy content route.
- [x] Block missing/deleted files and avoid public direct file access.
- [x] Audit authorized document access.

#### Implementation Details

- Added `GET /api/v1/documents/{id}/download`; retained `/content`.
- All access requires an active staff role and document-read permission;
  customer-role permissions alone never expose another customer's documents.
- Downloads open the file through the storage contract, record an access
  audit event, and stream an attachment with encoded original filename,
  `Cache-Control: no-store`, and `X-Content-Type-Options: nosniff`.
- Download initiation is audited before streaming; this is not proof of
  completed delivery. Audit failure prevents a successful download response.
- Missing metadata/content and soft-deleted files return `404`. Storage read
  failures are explicit; private filesystem locations are not returned.

### 5.6 Document Verification

**Status: Completed**

- [x] Add pending/verified/rejected/resubmission-required statuses.
- [x] Track reviewer, review time, remarks, and immutable review decisions.
- [x] Implement verification service/API with role and permission checks.
- [x] Test review validation, conflict detection, and rollback.

#### Implementation Details

- Added `PATCH /api/v1/documents/{id}/verification`, restricted to
  administrator/underwriter with `documents:verify`.
- Uploads start `PENDING`. Reviewers can choose `VERIFIED`, `REJECTED`, or
  `RESUBMISSION_REQUIRED`; rejection/resubmission requires nonblank remarks.
  Same-status decisions return `409`; manual pending resets return `422`.
- Persisted latest reviewer/time/remarks on the document and every accepted
  decision in `document_reviews`. The `verified_by`/`verified_at` fields record
  latest review information even for rejection; status determines acceptance.
- Review corrections append history rather than erase earlier decisions.
  Review, history, version increment, and audit changes share one transaction.
- Added explicit seed permissions for review, deletion, and requirement
  configuration. Administrator receives all three; underwriter receives review.

### 5.7 Document Replacement and Deletion

**Status: Completed**

- [x] Implement history-preserving replacements with new file/revision records.
- [x] Restrict deletion and record its reason/actor/time.
- [x] Use optimistic version checks and row locks.
- [x] Test concurrent replacements and rollback without losing original files.

#### Implementation Details

- Added `POST /api/v1/documents/{id}/replacement`, accepting multipart
  `document_type`, `expected_version`, and `upload`.
- Each successor has its own ID/key, pending status, version 1, incremented
  revision, shared group ID, and a unique predecessor link. Previous files
  and review history are not overwritten.
- Known categories must remain unchanged; replacing a legacy free-form label
  can map it to a supported category.
- Added administrator-only `DELETE /api/v1/documents/{id}` with JSON
  `expected_version` and nonblank remarks. Soft deletion hides the active
  record from lists/requirements, blocks downloads, and preserves bytes/history.
- Deleted/replaced revisions cannot be modified. Replaced, nondeleted
  historical files remain readable by authorized staff; deleting a successor
  does not erase its predecessor.
- Version checks use the document version, not the application's version.
  Concurrent stale changes return `409` rather than silently overwrite state.
- No permanent purge endpoint or retention scheduler was added; a production
  retention policy must be agreed before physical removal of historical files.

### 5.8 Document Security and Testing

**Status: Completed**

- [x] Parse real file content rather than trusting extension/MIME alone.
- [x] Test file-size/format boundaries, traversal, and authorization.
- [x] Test storage failures, cancellation, database rollback, and concurrency.
- [x] Document malware scanning and operational prerequisites.

#### Implementation Details

- Pillow verifies/decodes images and rejects decompression-bomb warnings or
  errors. pypdf parses PDF pages/content and rejects malformed, encrypted, or
  empty-page PDFs. Header-only fake files are rejected.
- Tests cover valid PDF/JPEG/PNG, mismatched type/extension, unsupported files,
  encrypted/malformed content, empty files, exact-size/oversize boundaries,
  unsafe storage paths, server-generated keys, and private response metadata.
- Tested real seeded role boundaries: customers denied despite document
  grants; loan officers can read/upload but not review/delete/configure;
  underwriters can review but not upload/replace/delete; administrator can
  manage the complete workflow.
- Real PostgreSQL tests verify lifecycle history, soft-delete behavior,
  missing content, custom requirement preservation, failed upload/replacement
  cleanup, review rollback, and concurrent review/replacement conflicts.
- Cancellation/partial-write/storage-error tests verify cleanup and explicit
  operator-visible errors. Temporary file storage and isolated PostgreSQL
  schemas are used rather than modifying application document records.
- Malware scanning/quarantine, parser resource isolation, gateway intake/rate
  limits, encryption/backups, private filesystem ACLs, retention/purge, and
  crash reconciliation remain documented production prerequisites. Format
  validation does not certify that a document is malware-free.

#### Phase 5 Verification

- Focused document tests: **52 passed** within the full PostgreSQL-enabled run.
- Complete regression suite: **245 passed**, including Phase 4 and Phase 5
  PostgreSQL tests.
- Applied revision `b52f0a37d914` and successfully reran the seeder twice.
- Pylance diagnostics were clean for the new document services, API, schemas,
  models, repository, migration, and updated seeder/loan-type model; service
  syntax validation passed.
- All 15 task-scoped Python files passed Ruff lint and were formatted using
  the existing project tooling.
- Verified generated OpenAPI route/version/category contracts and storage-key
  exclusion. PostgreSQL contains the new revision, 21 baseline permissions,
  and 40 initial requirement records after two seed runs; no integration-test
  schemas remained. `git diff --check` passed.
- The pre-existing Starlette/httpx TestClient deprecation warning remains.

---

## Phase 6: Application Notes, Audit Logs and Activity Tracking

**Status: Completed - 7/7 modules completed**

Reused the existing note/audit tables and business audit calls. Confirmed
compatible dotted action names, strict detail allowlists, staff-only timeline
access, real logout/token invalidation, and indefinite development retention
before implementation.

### 6.1 Application Notes Management

**Status: Completed**

- [x] Review/reuse note model and request/response schemas.
- [x] Extract a note repository and transactional creation service.
- [x] Add create/list/detail routes on the new application path.
- [x] Preserve legacy routes, pagination, sorting, and append-only behavior.
- [x] Test validation, author attribution, access restrictions, and rollback.

#### Implementation Details

- Added `app/repositories/application_note_repository.py` and
  `app/services/application_note_service.py`, keeping note insertion and
  its audit entry in one transaction.
- Exposed POST/GET `/api/v1/loan-applications/{id}/notes` and GET
  `/{id}/notes/{note_id}`; retained equivalent legacy application routes.
- Required staff plus existing note create/read permissions; customer-role
  grants cannot bypass the staff boundary.
- Notes are trimmed, nonblank, and at most 10,000 characters. Retrieval checks
  both application and note IDs to prevent cross-application lookup.
- Added `sort=asc|desc` to paginated listing, with timestamp/ID tie-breaking.
  No update/delete endpoints were introduced.
- Tests verify correct author/application, both route families, blank-input
  rejection, 404/405 behavior, pagination/sorting, and rollback on audit failure.

### 6.2 Audit Logging Foundation

**Status: Completed**

- [x] Centralize audit actions, entity rules, and detail schemas.
- [x] Capture actor/entity/server timestamp and bounded request metadata.
- [x] Validate audit structures and reject sensitive/unrecognized details.
- [x] Reuse the current transaction rather than independently committing audits.

#### Implementation Details

- Added `AuditAction` with all 22 supported dotted names, preserving existing
  stored/action-filter compatibility rather than renaming history.
- Added per-action Pydantic detail allowlists in
  `app/schemas/audit_details.py`. The shared service rejects unknown actions,
  wrong entity types, extra fields, and invalid structured values.
- Detail schemas permit UUIDs, allowed changed-field names, statuses,
  categories, byte counts, and requirements—not arbitrary free text or
  customer/authentication secrets. Validation errors omit rejected values.
- Added a bounded, control-filtered user-agent and validated direct-peer IP.
  The helper does not trust arbitrary forwarded-IP headers.
- Added `c63a1b48e025` migration for request metadata, audit timestamp index,
  token invalidation support, and protected document deletion remarks.
- Fixed real asyncpg INET response handling: native IPv4/IPv6 objects now
  validate/serialize correctly through the audit response schema.

### 6.3 Audit Event Tracking

**Status: Completed**

- [x] Track customer/user/application/document mutations.
- [x] Track assignment, lifecycle transitions, notes, and administrative changes.
- [x] Add explicit role/security events while preserving existing event names.
- [x] Keep critical mutation/audit persistence atomic.

#### Implementation Details

- Wired existing create/update/activation, application submission/edit/
  assignment/status, document upload/review/replacement/deletion/download,
  notes, and requirement-configuration actions through the validated service.
- Role updates emit both the compatible `user.updated` event and a dedicated
  `user.role_changed` event containing only old/new role IDs.
- Changed-field details record field names, never the entered personal/
  financial values. Note text and file names/contents are not duplicated.
- New document deletion reasons are retained on document metadata as
  `deletion_remarks`, rather than copied as unrestricted audit free text.
  Existing historical audit details are not rewritten.
- Audit errors propagate and prevent the corresponding operation from
  completing; they are not swallowed or returned as success.

### 6.4 User Activity Tracking

**Status: Completed**

- [x] Record successful and failed logins.
- [x] Add real logout with digest-based token revocation.
- [x] Implement authenticated password changes and audit them.
- [x] Invalidate sessions after password/role/activation changes.
- [x] Capture request metadata without logging authentication secrets.

#### Implementation Details

- Token issuance now updates `last_login_at` and commits
  `auth.login_succeeded` before returning the JWT.
- Failed/unknown/inactive logins commit `auth.login_failed` and return a
  generic `401`. Failed events deliberately have no submitted email,
  password, token, or claimed target-user identity.
- Added POST `/api/v1/auth/logout`: stores only a SHA-256 token digest and
  expiry in `revoked_tokens`, atomically with `auth.logged_out`, then returns
  `204`. Subsequent use of that token returns `401`.
- Added POST `/api/v1/auth/password` with secret-safe current/new-password
  fields, existing Argon2 hashing, and `user.password_changed`.
- New JWTs contain a unique ID and user token version; authentication checks
  both the database version and token revocation on every protected request.
- Password/actual role/activation changes increment token version, so
  previously issued tokens cannot resume after reactivation. Repeated
  unchanged activation is an idempotent no-op.
- User-row locks serialize relevant authentication/account mutations;
  password change rechecks the version after locking.
- Existing pre-Phase-6 JWTs lack required claims and must be replaced by
  signing in again after migration. Token invalidation does not retroactively
  cancel already-authorized in-flight requests.

### 6.5 Application Activity Timeline

**Status: Completed**

- [x] Combine notes, status history, and related audit events.
- [x] Include actor/source information and deterministic chronological sorting.
- [x] Add database pagination and both application-path endpoints.
- [x] Enforce internal access and avoid global-audit metadata leakage.

#### Implementation Details

- Added SQL-union timeline service and
  GET `/api/v1/loan-applications/{id}/activity`, plus legacy alias.
- Combined notes, status history (including initial NEW), application audits,
  and document audits linked through that application's document records.
- Suppressed duplicate note-created/status-change audit copies; application
  creation audit and initial NEW remain separate source events.
- Included event source/ID/action/time, actor ID/current display name,
  applicable note/status remarks, and document ID.
- Required staff plus both application-read and notes-read permission.
  Timeline responses do not expose global audit details/IP/user-agent/email
  or storage locations.
- SQL-level pagination orders by timestamp/source/ID; supports asc/desc and
  stable tie-breaking. No timeline table or all-records in-memory aggregation.
- Tests cover mixed sources, reverse ordering, equal-time ties, pagination,
  author attribution, duplicate suppression, and other-application isolation.

### 6.6 Audit Log Retrieval and Search

**Status: Completed**

- [x] Extend audit retrieval with dates and sorting.
- [x] Combine actor/action/entity/date filters with pagination.
- [x] Require administrator role and audit-read permission.
- [x] Keep audit endpoints read-only and test their boundaries.

#### Implementation Details

- Added an audit repository for exact-match user/action/entity filters and
  inclusive UTC date bounds with maximum-date overflow handling.
- `GET /api/v1/audit-logs` accepts `user_id`, `action`, `entity_type`,
  `entity_id`, `date_from`, `date_to`, `page`, `page_size`, and `sort`.
- Kept a 100-row maximum and deterministic timestamp/ID ordering.
  Invalid page/sort or reversed dates return `422`.
- Added administrator-only `/actions` discovery for supported names. Exact
  string filters remain open to historical action names.
- Administrator role is now required in addition to audit-read permission;
  accidental grants to other roles do not expose global records.
- Tests verify combined filters, individually nonmatching filters,
  UTC boundaries, response serialization, role/permission denial, and no
  modification/deletion APIs.

### 6.7 Security, Retention and Testing

**Status: Completed**

- [x] Protect internal notes/global audits and restrict sensitive details.
- [x] Define development retention and production integrity requirements.
- [x] Test failed transactions and authentication-token behavior.
- [x] Validate migration, existing behavior, and complete API regression.

#### Implementation Details

- Development policy retains notes/audits indefinitely; no purge schedule,
  update/delete endpoint, or invented legal retention duration was added.
- Documented production requirements for approved retention/legal holds,
  least-privilege database roles, restricted privileged access, backups,
  tamper-resistant archival, and access review.
- Application append-only APIs are explicitly not a claim of tamper-proof
  storage against a database owner; no destructive database privilege changes
  were made in a shared development environment.
- Privacy tests inject prohibited detail keys across every supported action,
  ensure rejected values are absent from error messages, and verify bounded
  metadata and forwarded-IP handling.
- Real PostgreSQL tests verify note/authentication/role/activation rollback
  when audit persistence fails, including no phantom revocation, password
  change, session-version increment, login time, or note.
- Logout, password changes, role changes, and deactivate/reactivate behavior
  are tested using real bearer tokens and database-backed authorization.
- Login rate limits, long-term retention approval, archival, and revocation
  housekeeping remain explicitly documented production/maintenance follow-ups.

#### Phase 6 Verification

- Focused Phase 6 suite with PostgreSQL enabled: **144 passed**.
- Complete regression suite with PostgreSQL enabled: **389 passed**.
- Applied Alembic revision `c63a1b48e025`; isolated downgrade/upgrade test
  preserved existing users and audit records and initialized new fields.
- Pylance diagnostics were clean for the inspected new/changed services,
  schemas, API handlers, audit/revocation models, and migration.
- Scoped Ruff lint and formatting passed on 29 implementation/test files;
  formatting also passed on the updated user model. Pylance signature checks
  confirmed all 8 token-generation and 24 audit-helper call sites compatible.
- Validated generated OpenAPI note/timeline/authentication/search contracts,
  all 22 action names, and exclusion of global audit details from timeline
  responses. Confirmed the configured PostgreSQL revision/token tables and
  that no temporary integration-test schemas remained.
- Timeline syntax validation and `git diff --check` passed.
- Existing Starlette/httpx TestClient deprecation warning remains; no
  unrelated dependency upgrade was introduced.

---

## Test Runner Compatibility Fix

- Reproduced the reported `uv run pytest` collection failure:
  `ModuleNotFoundError: No module named 'app'`.
- Added pytest configuration in `pyproject.toml` with `pythonpath = ["."]`
  and `testpaths = ["tests"]`, so the console entry point resolves the
  application from the repository root without manual environment changes.
- Documented that both `uv run pytest` and `uv run python -m pytest` work.
- Verified the exact console-entry-point command: **369 passed, 20 skipped**
  by default; **389 passed** with `RUN_POSTGRES_INTEGRATION=1`.
- The existing Starlette/httpx warning remains unrelated to collection.
  `git diff --check` passed.

---

## HTTPX2 Test Client Migration

- Retained the existing `httpx2>=2.16.0` dependency declaration and removed
  the legacy `httpx` development dependency.
- Migrated all four asynchronous PostgreSQL test-client modules to
  `import httpx2 as httpx`, matching Starlette's compatibility pattern while
  retaining the existing client/ASGI transport calls.
- Ran `uv sync` to update the lockfile/environment. Legacy `httpx` and its
  now-unused dependencies were removed; Starlette selects `httpx2` directly.
- Verified `uv run pytest -q -W error::DeprecationWarning`: **369 passed,
  20 skipped** by default; **389 passed** with PostgreSQL enabled.
- Both runs completed without warnings. The Starlette/httpx warning noted
  in earlier phase reports is now resolved.

---

## Phase 7: Dashboard and Reporting APIs

**Status: Completed (8/8 application modules, with agreed reporting policies).**

### 7.1 Dashboard Summary API - Completed

- Added typed summary schemas and a single aggregate SQL query.
- Added `GET /api/v1/dashboard/summary` with staff role and
  `dashboard:read` checks.
- Reports filtered application counts, awaiting-review/approved/rejected/
  disbursed counts and Decimal requested totals, plus global customer and
  active-user counts.
- Actual approved amounts are explicitly unavailable (`null`), because the
  existing application table does not record approved amounts.

### 7.2 Application Statistics - Completed

- Added status, loan-type, employment-type and UTC-month breakdowns.
- Approval includes current APPROVED and DISBURSED; rate denominators include
  every application in the filtered submission cohort. Empty rates are zero.
- Added inclusive UTC dates and loan-type filters with invalid/reversed range
  checks, and `GET /api/v1/dashboard/application-statistics`.

### 7.3 Loan Type Reports - Completed

- Added application/approval/rejection counts and requested totals per type,
  including zero-activity loan types, with deterministic pagination.
- Added `GET /api/v1/reports/loan-types`; approved amounts remain unavailable.
- Added protected active loan-type catalogue/list and ID retrieval routes
  for staff to discover valid application input values.

### 7.4 Staff Performance - Completed

- Added administrator-only assigned/pending/approved/rejected/disbursed
  counts with current-assignee attribution.
- Average completion time uses first terminal history timestamps, not the
  last application update or an invented approval/disbursement date.
- Added paginated `GET /api/v1/reports/staff-performance`.

### 7.5 Processing Reports - Completed

- Added first contact/approval/rejection averages, old pending counts and
  time-in-current-status stuck application pages.
- Added status, submission-date, loan-type and threshold-day filters.
- Added `GET /api/v1/reports/application-processing`; missing history gives
  null averages, and terminal applications are excluded from pending lists.

### 7.6 Financial Reports - Completed Within Existing Data Model

- Added total/grouped-by-type/grouped-by-month requested NUMERIC/Decimal sums
  via `GET /api/v1/reports/financial-summary`.
- Actual approved/disbursed totals are `null` with
  `actual_amounts_available=false`, never substituted with requested amounts.
- Adding actual approved/disbursed amounts and dates is a separate schema
  and business-policy change, not silently introduced in reporting.

### 7.7 CSV Exports - Completed

- Added administrator-only application, minimal-customer and financial CSV
  exports with date filters, safe quoting and spreadsheet-formula escaping.
- Enforced an exact 5000-data-row cap before returning a successful download.
  Integration tests verify 5001 fails and exactly 5000 succeeds.
- Customer CSV omits email, phone, address and identity data. Financial CSV
  marks missing actual amounts as `UNAVAILABLE`.
- Successful exports record structured `report.exported` audits. Excel was
  optional and is not enabled.

### 7.8 Reporting Access, Bounds and Documentation - Completed

- Added five new permissions across reports, dashboard and notifications;
  dashboard grants go to staff, while reports/exports/history/retry stay admin.
- Tested empty data, combinations of filters, exact rates/money/durations,
  role denials, CSV boundaries and OpenAPI query parameter shapes.
- Capped summary group lists at 5000 with explicit narrowing errors rather
  than truncating totals silently.
- Fixed a reporting-coupled timestamp defect: `created_at` previously had an
  ORM `onupdate`, moving records into a new submission cohort after edits.
  It is now immutable; `updated_at` still changes. Regression tests verify
  edits preserve submission dates. Existing corrupted historical dates
  cannot be reconstructed automatically.
- Documented metric definitions, permissions, filters and unavailable data
  in README. Existing repository query helpers are used directly without an
  unnecessary pass-through service layer.

---

## Phase 8: Notifications and Communication

**Status: Completed (8/8 application modules; real SMTP delivery remains an
operator validation gate).**

### 8.1 Architecture - Completed

- Chose email through configurable SMTP; optional SMS/in-app channels were
  not added.
- Added a reusable transactional enqueue service and separately executed
  durable PostgreSQL outbox worker, rather than request-bound background tasks.
- Notifications are disabled by default: no queueing and no network delivery
  until explicitly enabled. Enabling later does not replay old events.

### 8.2 Persistent Model and Migration - Completed

- Added recipient/channel/event/subject/template, unique event key, status,
  attempt count, provider reference, safe error class, timestamps and leases.
- Added foreign key, event-key uniqueness, allowed status/channel checks,
  nonnegative attempts and due-job lookup index.
- Applied revision `d74b2c59f136` to development PostgreSQL. Tested isolated
  downgrade/upgrade and ORM metadata constraints.

### 8.3 SMTP Email Service - Completed

- Added plain-text/HTML MIME messages, sender configuration, stable
  Message-ID, TLS, optional credentials and socket timeouts.
- SMTP/provider failures are explicit; exception text containing recipient
  addresses or credentials is not persisted/logged.
- Tests use mocked SMTP/fake providers, not real recipient delivery.

### 8.4 Business Event Integration - Completed

- Submission and upload/replacement notify active admins and assignees;
  assignment notifies the assignee.
- Status changes notify customers with an email address, using dedicated
  document-request/approval/rejection/disbursement messages where applicable.
- Rejected/resubmission-required document reviews request corrected documents.
- Missing/invalid recipient addresses are explicitly logged/skipped without
  exposing the address. No nonexistent enquiry API was invented.
- Outbox writes share the business transaction; commit failures roll back
  application, history, audit and queued messages together.

### 8.5 Durable Processing and Retry - Completed

- Implemented SKIP LOCKED claims, committed leases, fenced acknowledgements,
  expiry recovery, bounded exponential retries and exhausted-job handling.
- Added continuous and bounded `--once --limit` worker modes.
- Tested concurrent claims, duplicate enqueueing, rollback, SMTP errors,
  timeout/network failures, delayed retry, exhaustion, crashed final attempts,
  expired lease recovery and stale acknowledgement rejection.
- Delivery is explicitly **at least once**. Event-key deduplication and a
  stable Message-ID cannot eliminate the SMTP-acceptance/database-ack crash
  window; exactly-once or guaranteed inbox delivery is not claimed.

### 8.6 Templates - Completed

- Added separate templates for all eight supported events, including uploads.
- Templates exclude customer names, identity details, amounts, attachments,
  tokens and internal notes; HTML text is escaped.
- Unknown templates fail explicitly. All templates have rendering tests.

### 8.7 Administrator History and Retry - Completed

- Added filtered, paginated list/details and failed-notification retry routes.
- Enforced administrator role plus read/retry grants. Responses omit event
  deduplication keys and internal lease tokens.
- Retry starts a fresh bounded cycle and records `notification.retried`.

### 8.8 Testing and Documentation - Completed

- Verified authorization, event integration, safe recipient handling, SMTP
  options, generic content, provider failure privacy and worker recovery.
- Documented environment variables, recipient policy, retries, history APIs,
  disabled-mode semantics and at-least-once limitations.
- Production sender-domain setup, bounce handling and real-provider delivery
  are external gates, not silently marked tested.

---

## Phase 9: API Testing, Security and Performance

**Status: Application implementation and local verification completed through
9.10; production infrastructure/release gates remain open.**

### 9.1 API Coverage - Completed for Implemented Backend

- Retained existing auth, RBAC, user/customer/application, lifecycle, notes,
  audit and document suites; added report, catalogue and notification APIs.
- Added positive/negative filters, limits, missing resources, role denials,
  CSV output shapes and standardized failure-path checks.
- Updated existing audit-failure API tests to expect safe HTTP 500 responses
  rather than raw internal exceptions, retaining rollback/file-close checks.

### 9.2 Dedicated Database and End-to-End Workflow - Completed

- Integration tests now require a dedicated `TEST_DATABASE_URL` or ignored
  `.env.test`; production configuration and the application database name
  are refused. Test database names must end in `_test`.
- Added explicit local setup helper; created `loan_management_test` without
  changing application records. Existing test configuration is not overwritten.
- Migrated the original submission test away from the development public
  schema. All integration suites create/drop private schemas in the test DB.
- Verified real login, customer creation, submission, assignment, note,
  document upload/review, lifecycle to DISBURSED, history/timeline/audit,
  dashboard, administrator retries and fake-provider queue delivery.

### 9.3 Authentication and Authorization Hardening - Completed Locally

- Added atomic PostgreSQL login-IP counters: 10/minute/direct peer by default.
  Counters commit independently of failed authentication and audits.
- Concurrent tests verify exactly ten accepted attempts, 429/Retry-After,
  persisted rejected counts and window reset.
- Kept Argon2 hashing, short-lived JWTs, revocation/token-version checks and
  role/permission gates; refresh-token rotation is not applicable.
- Added explicit CORS/production checks and tests for trusted/untrusted
  origins and disabled production docs. Proxy trust requires deployment policy.

### 9.4 Input and Data Protection - Completed Locally

- Retained existing UUID, financial input, document parser/size/path,
  mass-assignment and protected-document tests.
- Validation errors omit raw input/context; internal SQL/provider details
  are not returned. New private endpoints reject customer/non-admin access.
- Added safe no-store/nosniff headers, protected exports and generic email
  content. Staff-wide internal access remains the deliberate authorization
  model; no customer-ownership portal is claimed.

### 9.5 Integrity and Transaction Safety - Completed Locally

- Tested new FK/unique/check constraints and migration roundtrip alongside
  existing application/document history, optimistic version and rollback tests.
- Verified transactional outbox/business/audit rollback and immutable creation
  timestamps needed for accurate reporting.
- Retained Decimal/NUMERIC precision and non-destructive document history.

### 9.6 Performance Evidence - Completed for Local Regression Scope

- Added explicit pool sizing/overflow/timeouts and bounded page/group/export
  outputs. SQL parameter hiding is enabled; SQL echo is disabled.
- Query-budget tests assert one summary, two staff-report and five statistics
  queries, not per-record relationship fetches.
- Executed read-only EXPLAIN ANALYZE/BUFFERS on the dedicated test dataset.
- Measured 20 concurrent summary queries over 1200 applications:
  local observed p95 **860.14 ms**; regression ceiling **5000 ms**.
  This measures database summary calls on local hardware, not production
  HTTP capacity or an accepted production SLA.
- Added due-job/rate-window indexes justified by claim/maintenance patterns;
  did not add speculative application indexes without query evidence.
- Existing uploads remain bounded to the configured default 10 MiB;
  streaming/quarantine and representative production load remain future gates.

### 9.7 Errors and Logging - Completed

- Standardized errors with compatible `detail`, stable `code`, UUID
  `request_id` and matching response header; documented the schema in OpenAPI.
- Added safe validation, database conflict/unavailability and unexpected-error
  handlers. The outer request boundary logs exception class rather than
  allowing server traceback logging to expose exception text.
- Added JSON request logs containing template/method/status/elapsed time,
  excluding bodies, query values, tokens and customer identifiers.
- Verified safe 422/500/503 responses, request IDs and provider failure logs.

### 9.8 API Documentation - Completed

- Updated README with new endpoint/access tables, metric definitions, filters,
  unavailable fields, CSV semantics, notification configuration and examples.
- Documented rate limits, test DB isolation, error shapes and worker operation.
- Added OPERATIONS.md for deployment, monitoring, retention, recovery and
  explicit external production sign-off requirements.

### 9.9 Code Quality - Completed

- Full `ruff check app tests alembic` and Ruff formatting check passed.
- Added missing TYPE_CHECKING relationship imports and explicit model exports,
  and cleaned lint/format findings without changing relationship behavior.
- Full default suite: **415 passed, 32 PostgreSQL tests skipped**.
- Full dedicated-PostgreSQL suite: **447 passed**.
- Both suites ran with deprecation warnings treated as errors.
- Inspected Pylance diagnostics for new/changed report, notification, config,
  HTTP, setup, document and application wiring surfaces; inspected files
  reported no errors. No blanket project-wide strict typing claim is made.
- Reviewed recent Git history/worktree; no commits made and no user changes
  reverted. `.env.test` is ignored, not committed.

### 9.10 Production Readiness - Prepared; External Gates Still Pending

- Added non-root Docker image, development Compose wiring, private document
  volume, separate worker and API readiness health check.
- Added production config guards, disabled production interactive docs,
  explicit pool/CORS settings, and deployment/rollback instructions.
- Final read-only security review found **no exploitable vulnerabilities in
  reviewed changes**; this is source-review evidence, not a penetration test
  or dependency/container certification.
- Verified development health live/ready respond 200 and new protected APIs
  return 401 without authentication. Seeder rerun twice; persisted four roles,
  26 permissions, five loan types, and no notification messages.
- **Still pending operator approval/evidence:** production credentials and
  secret management, HTTPS/network/database TLS, target-platform container
  build/image scan, real SMTP delivery/domain setup, monitoring/alerts,
  encrypted backup and restoration rehearsal, approved audit/log/document
  retention, malware scanning and production load acceptance.
- Docker and PostgreSQL backup CLI tools were not available in this terminal;
  no container build or restoration rehearsal is falsely claimed.

---

## Overall Project Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Backend Foundation | Completed |
| Phase 2 | Database and ORM Setup | Completed |
| Phase 3 | Backend API Development | Completed |
| Phase 4 | Loan Application Engine | Completed (8/8 modules) |
| Phase 5 | Document Management System | Completed (8/8 modules) |
| Phase 6 | Application Notes, Audit Logs and Activity Tracking | Completed (7/7 modules) |
| Phase 7 | Dashboard and Reporting APIs | Completed (8/8 application modules) |
| Phase 8 | Notifications and Communication | Completed (8/8 application modules; live provider gate open) |
| Phase 9 | API Testing, Security and Performance | Implemented through 9.10; external production gates pending |

**Current task:** Phases 7-9 backend implementation verified; production rollout
requires the external sign-offs documented above and in OPERATIONS.md.

**Current Alembic revision:** `d74b2c59f136`




```
All 32 integration tests failed for the same reason: PostgreSQL rejected the password when the tests tried to connect to loan_management_test. They fail during database setup in test_phase4_postgres.py:107, before reaching the test logic. The other 415 tests passed.

The traceback shows the test connection is using credentials that don’t match the .env you showed. With integration tests enabled, conftest.py:16 takes TEST_DATABASE_URL from .env.test and uses it instead of the app’s DATABASE_URL. The setup helper deliberately does not overwrite an existing .env.test, so it may still contain an old password.

Update .env.test so TEST_DATABASE_URL has the password your local PostgreSQL server currently accepts, and still points to loan_management_test. Don’t point it at loan_management_db. Then rerun the integration tests. If the password in .env was recently changed, make sure PostgreSQL’s postgres role password was changed too; editing .env alone does not change the server password.

Also, the traceback includes a database password. Treat it as exposed and rotate it, along with the JWT secret you shared earlier.

```
