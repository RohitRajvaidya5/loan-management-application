import asyncio

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal, engine
from app.enums.document import DocumentType
from app.models import DocumentRequirement, LoanType, Permission, Role, role_permissions

ROLES = (
    ("administrator", "Full access to all application features."),
    ("loan_officer", "Manages customer records and loan applications."),
    ("underwriter", "Reviews loan applications and updates their status."),
    ("customer", "Submits and views personal loan applications."),
)

PERMISSIONS = (
    ("users:create", "Create application users."),
    ("users:read", "View application users."),
    ("users:update", "Update application users."),
    ("users:deactivate", "Activate or deactivate application users."),
    ("customers:create", "Create customer records."),
    ("customers:read", "View customer records."),
    ("customers:update", "Update customer records."),
    ("customers:search", "Search and filter customer records."),
    ("loan_applications:create", "Create loan applications."),
    ("loan_applications:read", "View loan applications."),
    ("loan_applications:update", "Update loan applications."),
    ("loan_applications:assign", "Assign loan applications to staff."),
    ("loan_applications:status_update", "Update loan application statuses."),
    ("application_notes:create", "Add internal application notes."),
    ("application_notes:read", "View application notes."),
    ("documents:create", "Add application document metadata."),
    ("documents:read", "View application document metadata."),
    ("documents:verify", "Review application documents."),
    ("documents:delete", "Soft delete application documents."),
    ("documents:configure", "Configure loan-specific document requirements."),
    ("audit_logs:read", "View audit log entries."),
    ("dashboard:read", "View aggregate operational dashboard."),
    ("reports:read", "View administrative reports."),
    ("reports:export", "Export bounded administrative reports."),
    ("notifications:read", "View private notification delivery history."),
    ("notifications:retry", "Retry failed notifications."),
)

ROLE_PERMISSIONS = {
    "administrator": tuple(permission for permission, _ in PERMISSIONS),
    "loan_officer": (
        "dashboard:read",
        "customers:create",
        "customers:read",
        "customers:update",
        "customers:search",
        "loan_applications:create",
        "loan_applications:read",
        "loan_applications:update",
        "loan_applications:assign",
        "application_notes:create",
        "application_notes:read",
        "documents:create",
        "documents:read",
    ),
    "underwriter": (
        "dashboard:read",
        "loan_applications:read",
        "loan_applications:update",
        "loan_applications:status_update",
        "application_notes:create",
        "application_notes:read",
        "documents:read",
        "documents:verify",
    ),
    "customer": (
        "customers:read",
        "loan_applications:create",
        "loan_applications:read",
        "documents:create",
        "documents:read",
    ),
}

LOAN_TYPES = (
    ("Personal Loan", "Unsecured financing for personal expenses."),
    ("Auto Loan", "Financing for the purchase of a vehicle."),
    ("Home Loan", "Financing for the purchase or renovation of a home."),
    ("Business Loan", "Financing for business purposes."),
    ("Education Loan", "Financing for education-related expenses."),
)


async def seed_initial_data(session: AsyncSession) -> None:
    await session.execute(
        insert(Role)
        .values(
            [{"name": name, "description": description} for name, description in ROLES]
        )
        .on_conflict_do_nothing(index_elements=[Role.name])
    )
    await session.execute(
        insert(Permission)
        .values(
            [
                {"name": name, "description": description}
                for name, description in PERMISSIONS
            ]
        )
        .on_conflict_do_nothing(index_elements=[Permission.name])
    )

    role_ids = dict(
        (
            await session.execute(
                select(Role.name, Role.id).where(
                    Role.name.in_([name for name, _ in ROLES])
                )
            )
        ).all()
    )
    permission_ids = dict(
        (
            await session.execute(
                select(Permission.name, Permission.id).where(
                    Permission.name.in_([name for name, _ in PERMISSIONS])
                )
            )
        ).all()
    )

    mappings = [
        {
            "role_id": role_ids[role_name],
            "permission_id": permission_ids[permission_name],
        }
        for role_name, permission_names in ROLE_PERMISSIONS.items()
        for permission_name in permission_names
    ]
    await session.execute(
        insert(role_permissions)
        .values(mappings)
        .on_conflict_do_nothing(
            index_elements=[
                role_permissions.c.role_id,
                role_permissions.c.permission_id,
            ]
        )
    )

    await session.execute(
        insert(LoanType)
        .values(
            [
                {"name": name, "description": description, "is_active": True}
                for name, description in LOAN_TYPES
            ]
        )
        .on_conflict_do_nothing(index_elements=[LoanType.name])
    )
    loan_types = await session.scalars(
        select(LoanType)
        .where(
            LoanType.name.in_([name for name, _ in LOAN_TYPES]),
            LoanType.document_requirements_configured.is_(False),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    for loan_type in loan_types:
        # A concurrent seeder may have configured this row before the lock.
        if loan_type.document_requirements_configured:
            continue
        await session.execute(
            insert(DocumentRequirement)
            .values(
                [
                    {
                        "loan_type_id": loan_type.id,
                        "document_type": category.value,
                        "is_required": category
                        in {
                            DocumentType.PAN_CARD,
                            DocumentType.AADHAAR_CARD,
                            DocumentType.BANK_STATEMENT,
                        }
                        or (
                            category == DocumentType.PROPERTY_DOCUMENTS
                            and loan_type.name == "Home Loan"
                        ),
                    }
                    for category in DocumentType
                ]
            )
            .on_conflict_do_nothing(index_elements=["loan_type_id", "document_type"])
        )
        loan_type.document_requirements_configured = True


async def main() -> None:
    try:
        async with AsyncSessionLocal() as session, session.begin():
            await seed_initial_data(session)
    finally:
        await engine.dispose()

    print("Initial database seed data applied.")


if __name__ == "__main__":
    asyncio.run(main())
