from decimal import ROUND_HALF_UP, Decimal, localcontext

from app.schemas.emi import EMICalculationRequest, EMICalculationResponse


def calculate_emi(payload: EMICalculationRequest) -> EMICalculationResponse:
    with localcontext() as context:
        context.prec = 60
        principal = payload.principal
        monthly_rate = payload.annual_interest_rate / Decimal(1200)
        if monthly_rate == 0:
            emi = principal / payload.tenure_months
            total = principal
        else:
            factor = (1 + monthly_rate) ** payload.tenure_months
            emi = principal * monthly_rate * factor / (factor - 1)
            total = emi * payload.tenure_months
        cents = Decimal("0.01")
        return EMICalculationResponse(
            **payload.model_dump(),
            monthly_emi=emi.quantize(cents, rounding=ROUND_HALF_UP),
            total_repayment=total.quantize(cents, rounding=ROUND_HALF_UP),
            total_interest=(total - principal).quantize(cents, rounding=ROUND_HALF_UP),
        )
