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

**Status: Pending**

Planned tasks:

- [ ] Design initial role seed data.
- [ ] Define initial permissions.
- [ ] Map permissions to roles.
- [ ] Create initial loan type records.
- [ ] Implement an idempotent database seeding process.
- [ ] Verify seeded records in PostgreSQL.

### 3.2 Authentication and Password Hashing

**Status: Pending**

- [ ] Select password hashing approach.
- [ ] Implement password hashing.
- [ ] Implement password verification.
- [ ] Add authentication schemas and services.

### 3.3 JWT Access-Token Authentication

**Status: Pending**

- [ ] Configure JWT.
- [ ] Implement access-token generation.
- [ ] Implement token validation.
- [ ] Create current-user dependency.
- [ ] Protect authenticated API endpoints.

### 3.4 Role-Based Access Control

**Status: Pending**

- [ ] Implement permission checking.
- [ ] Implement role-based authorization.
- [ ] Restrict API access according to user permissions.

### 3.5 User Management APIs

**Status: Pending**

- [ ] Create user.
- [ ] Retrieve users.
- [ ] Retrieve user by ID.
- [ ] Update user.
- [ ] Activate and deactivate users.

### 3.6 Customer Management APIs

**Status: Pending**

- [ ] Create customer.
- [ ] Retrieve customers.
- [ ] Retrieve customer by ID.
- [ ] Update customer.
- [ ] Search and filter customers.

### 3.7 Loan Application APIs

**Status: Pending**

- [ ] Create loan application.
- [ ] Retrieve loan applications.
- [ ] Retrieve application by ID.
- [ ] Update application.
- [ ] Assign application to staff.
- [ ] Implement application filtering and pagination.

### 3.8 Application Workflow and Supporting APIs

**Status: Pending**

- [ ] Implement application status updates.
- [ ] Record status history.
- [ ] Implement internal application notes.
- [ ] Implement document metadata management.
- [ ] Integrate document storage.
- [ ] Implement audit logging.

---

## Overall Project Status

| Phase | Description | Status |
|---|---|---|
| Phase 1 | Backend Foundation | Completed |
| Phase 2 | Database and ORM Setup | Completed |
| Phase 3 | Backend API Development | In Progress |

**Current task:** Phase 3.1 - Database Seed Data

**Current Alembic revision:** `0cca17cb8963`
