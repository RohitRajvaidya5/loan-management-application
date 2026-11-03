# Progress

## Phase 1 : Backend foundation

### 1. Create a project directory

```
mkdir loan-management-application/frontend
mkdir loan-management-application/backend
```


### 2. Configure uv

**Command to install to uv** : `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Check uv version : `uv --version` ( uv 0.13.6 (329bf9448 2026-10-26 x86_64-pc-windows-msvc) )

Check python version : `python --version` ( Python 3.11.9 )

### 3. Initialize python project

uv project creation : `uv init`

Result will be:
    backend/
    │
    ├── .python-version
    ├── main.py
    ├── pyproject.toml
    └── README.md

### 4. Install dependencies

Initial Dependencies

```
uv add fastapi "uvicorn[standard]" pydantic-settings
```

Dev Dependencies

```
uv add --dev pytest httpx ruff
```

### 5. Backend Project Structure

```
backend/
│
├── app/
│   │
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
│   ├── models/
│   ├── schemas/
│   ├── services/
│   ├── repositories/
│   ├── dependencies/
│   └── utils/
│
├── tests/
│
├── .venv/
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
└── uv.lock
```

### 6. Configure environmental variables

Created `.env` and `env.example`

And added following

```
APP_NAME=Loan Management API
APP_ENV=development
DEBUG=true
```

### 7. Create application configuration

`app/core/config.py.`

Added Settings() class which contains environmental variables and use in whole application.


### 8. Added first endpoint - Health Check Endpoint

- Added health check endpoint `/health/live`
- Added details inside application like app name, custom /docs and /redoc links
- health check endpoint returns application name and environment

### 9. Add .gitignore, Run the application and also added some basic code quality checks


---

## Phase 2 : Database and CRUD

### 2.1 Created PostgreSQL Database

### 2.2 SQLAlchemy and asyncpg configuration

### 2.3 Alembic and Database Migrations

**1. Initialize Alembic**

Command:

```powershell
uv run alembic init -t async alembic
```

* Initialized Alembic using the asynchronous migration template.
* Created the `alembic` directory and `alembic.ini` configuration file.

**2. Configure Alembic**

* Updated `alembic/env.py` to use SQLAlchemy's declarative `Base`.
* Configured Alembic to load the database URL from application settings (`.env`).
* Configured asynchronous database migrations using SQLAlchemy's async engine.
* Enabled automatic detection of column type changes using `compare_type=True`.
* Removed the hardcoded database URL from `alembic.ini`.

**3. Verify Alembic Configuration**

Commands:

```powershell
uv run alembic current
```

```powershell
uv run alembic history
```

Results:

* Successfully identified PostgreSQL as the database dialect.
* Verified Alembic database migration context.
* Confirmed Alembic configuration is working correctly.

**Note:** No migration scripts have been generated yet. The first meaningful migration will be created after implementing the SQLAlchemy models.




---

```sql
CREATE ROLE loan_app_user
WITH
    LOGIN
    PASSWORD 'MyNewStrongPassword!';

ALTER DATABASE loan_management_db
OWNER TO loan_app_user;

GRANT ALL PRIVILEGES
ON DATABASE loan_management_db
TO loan_app_user;
```
