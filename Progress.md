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
