from decimal import Decimal

from pydantic import Field

from app.schemas.common import ORMModel


class EMICalculationRequest(ORMModel):
    principal: Decimal = Field(gt=0, max_digits=15, decimal_places=2)
    annual_interest_rate: Decimal = Field(ge=0, le=100, max_digits=10, decimal_places=6)
    tenure_months: int = Field(ge=1, le=600)


class EMICalculationResponse(ORMModel):
    principal: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    monthly_emi: Decimal
    total_repayment: Decimal
    total_interest: Decimal
