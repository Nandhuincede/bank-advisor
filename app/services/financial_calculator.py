from dataclasses import dataclass
from typing import Any


@dataclass
class FinancialMetrics:
    emi_ratio: float                 # %  of income consumed by EMI
    savings_rate: float              # %  of income saved each month
    credit_utilization: float        # %  of credit limit used (0 if no card)
    projected_annual_savings: float  # ₹  saved over 12 months
    monthly_surplus: float           # ₹  income − expenses
    is_deficit: bool                 # True when expenses > income
    has_credit_card: bool            # False when no credit card provided

    def to_dict(self) -> dict[str, Any]:
        return {
            "emi_ratio": round(self.emi_ratio, 2),
            "savings_rate": round(self.savings_rate, 2),
            "credit_utilization": round(self.credit_utilization, 2),
            "projected_annual_savings": round(self.projected_annual_savings, 2),
            "monthly_surplus": round(self.monthly_surplus, 2),
            "is_deficit": self.is_deficit,
            "has_credit_card": self.has_credit_card,
        }


def compute_financial_metrics(
    monthly_income: float,
    monthly_expense: float,
    existing_loan_emi: float,
    credit_card_limit: float = 0,
    credit_card_used: float = 0,
) -> FinancialMetrics:
    """
    Pure-Python financial calculations — zero LLM involvement.

    Formulae
    --------
    EMI Ratio            = existing_loan_emi / monthly_income × 100
    Savings Rate         = (monthly_income - monthly_expense) / monthly_income × 100
    Credit Utilization   = credit_card_used / credit_card_limit × 100  (0 if no card)
    Projected Ann. Sav.  = (monthly_income - monthly_expense) × 12
    """
    if monthly_income <= 0:
        raise ValueError("monthly_income must be greater than zero.")

    monthly_surplus = monthly_income - monthly_expense
    is_deficit = monthly_surplus < 0
    has_credit_card = credit_card_limit > 0

    emi_ratio = (existing_loan_emi / monthly_income) * 100
    savings_rate = (monthly_surplus / monthly_income) * 100
    credit_utilization = (credit_card_used / credit_card_limit) * 100 if has_credit_card else 0.0
    projected_annual_savings = monthly_surplus * 12

    return FinancialMetrics(
        emi_ratio=emi_ratio,
        savings_rate=savings_rate,
        credit_utilization=credit_utilization,
        projected_annual_savings=projected_annual_savings,
        monthly_surplus=monthly_surplus,
        is_deficit=is_deficit,
        has_credit_card=has_credit_card,
    )


def validate_inputs(data: dict) -> tuple[bool, str]:
    """
    Validate that required fields are present and financially sensible.
    Credit card fields are optional — defaults to 0 if not provided.
    Returns (is_valid, error_message).
    """
    # Required fields (credit card fields are NOT in this list)
    required = [
        "customer_name", "monthly_income", "monthly_expense",
        "existing_loan_emi", "savings_goal",
    ]
    for field in required:
        if field not in data or data[field] is None or data[field] == "":
            return False, f"Missing required field: {field}"

    try:
        monthly_income    = float(data["monthly_income"])
        monthly_expense   = float(data["monthly_expense"])
        existing_loan_emi = float(data["existing_loan_emi"])
        credit_card_limit = float(data.get("credit_card_limit") or 0)
        credit_card_used  = float(data.get("credit_card_used") or 0)
        savings_goal      = float(data["savings_goal"])
    except (ValueError, TypeError):
        return False, "All numeric fields must be valid numbers."

    if monthly_income <= 0:
        return False, "Monthly income must be greater than zero."
    if monthly_expense < 0:
        return False, "Monthly expense cannot be negative."
    if existing_loan_emi < 0:
        return False, "Existing loan EMI cannot be negative."
    if credit_card_limit < 0:
        return False, "Credit card limit cannot be negative."
    if credit_card_used < 0:
        return False, "Credit card used cannot be negative."
    if credit_card_limit > 0 and credit_card_used > credit_card_limit:
        return False, "Credit card used cannot exceed the credit card limit."
    if savings_goal < 0:
        return False, "Savings goal cannot be negative."

    return True, ""
