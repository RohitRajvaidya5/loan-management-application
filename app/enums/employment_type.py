from enum import StrEnum


class EmploymentType(StrEnum):
    SALARIED = "SALARIED"
    SELF_EMPLOYED = "SELF_EMPLOYED"
    BUSINESS = "BUSINESS"
    UNEMPLOYED = "UNEMPLOYED"
    RETIRED = "RETIRED"
    OTHER = "OTHER"
