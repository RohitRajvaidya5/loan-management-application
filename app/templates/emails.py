from html import escape

MESSAGES = {
    "application_submitted": (
        "Application received",
        "A new application has been received. Sign in to the loan management system to review it.",
    ),
    "application_assigned": (
        "Application assigned",
        "An application has been assigned to you. Sign in to review the next steps.",
    ),
    "status_updated": (
        "Application update",
        "Your application status has changed. Please contact your loan adviser for details.",
    ),
    "document_requested": (
        "Documents requested",
        "Additional or corrected documents are required. Please contact your loan adviser through your usual secure channel.",
    ),
    "document_uploaded": (
        "Document received",
        "A document has been received for an application. Sign in to review it.",
    ),
    "application_approved": (
        "Application approved",
        "Your application has been approved. Please contact your loan adviser for the next steps.",
    ),
    "application_rejected": (
        "Application decision",
        "A decision has been made on your application. Please contact your loan adviser for details.",
    ),
    "application_disbursed": (
        "Application disbursement update",
        "Your application has been marked as disbursed. Please contact your loan adviser for details.",
    ),
}


def render_email(template: str) -> tuple[str, str, str]:
    if template not in MESSAGES:
        raise ValueError("Unknown email template.")
    subject, text = MESSAGES[template]
    return (
        subject,
        text,
        f"<!doctype html><html><body><p>{escape(text)}</p></body></html>",
    )
