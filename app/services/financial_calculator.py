import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FinancialMetrics:
    emi_ratio: float                  # %  of income consumed by EMI
    savings_rate: float               # %  of income saved each month
    credit_utilization: float         # %  of credit limit used (0 if no card)
    projected_annual_savings: float   # ₹  saved over 12 months
    monthly_surplus: float            # ₹  income − expenses
    is_deficit: bool                  # True when expenses > income
    has_credit_card: bool             # False when no credit card provided

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to a plain dictionary for JSON serialization."""
        return {
            "emi_ratio":                round(self.emi_ratio, 2),
            "savings_rate":             round(self.savings_rate, 2),
            "credit_utilization":       round(self.credit_utilization, 2),
            "projected_annual_savings": round(self.projected_annual_savings, 2),
            "monthly_surplus":          round(self.monthly_surplus, 2),
            "is_deficit":               self.is_deficit,
            "has_credit_card":          self.has_credit_card,
        }


def compute_financial_metrics(
    monthly_income: float,
    monthly_expense: float,
    existing_loan_emi: float,
    credit_card_limit: float = 0.0,
    credit_card_used: float = 0.0,
) -> FinancialMetrics:
    """
    Perform all financial calculations using pure Python — zero LLM involvement.

    Formulae
    --------
    EMI Ratio            = existing_loan_emi / monthly_income × 100
    Savings Rate         = (monthly_income - monthly_expense) / monthly_income × 100
    Credit Utilization   = credit_card_used / credit_card_limit × 100 (0 if no card)
    Projected Ann. Sav.  = (monthly_income - monthly_expense) × 12

    Args:
        monthly_income:    Gross monthly income in ₹. Must be > 0.
        monthly_expense:   Total monthly expenses in ₹. Must be >= 0.
        existing_loan_emi: Current monthly loan EMI in ₹. Must be >= 0.
        credit_card_limit: Credit card limit in ₹. 0 means no credit card.
        credit_card_used:  Credit card outstanding balance in ₹. Must be >= 0.

    Returns:
        FinancialMetrics dataclass with all computed ratios and flags.

    Raises:
        ValueError: If monthly_income <= 0 or any value is negative.
        TypeError: If any argument is not a numeric type.
    """
    try:
        monthly_income    = float(monthly_income)
        monthly_expense   = float(monthly_expense)
        existing_loan_emi = float(existing_loan_emi)
        credit_card_limit = float(credit_card_limit)
        credit_card_used  = float(credit_card_used)
    except (TypeError, ValueError) as e:
        raise TypeError(f"All financial inputs must be numeric values: {e}") from e

    if monthly_income <= 0:
        raise ValueError("monthly_income must be greater than zero.")
    if monthly_expense < 0:
        raise ValueError("monthly_expense cannot be negative.")
    if existing_loan_emi < 0:
        raise ValueError("existing_loan_emi cannot be negative.")
    if credit_card_limit < 0:
        raise ValueError("credit_card_limit cannot be negative.")
    if credit_card_used < 0:
        raise ValueError("credit_card_used cannot be negative.")
    if credit_card_limit > 0 and credit_card_used > credit_card_limit:
        raise ValueError("credit_card_used cannot exceed credit_card_limit.")

    monthly_surplus: float = monthly_income - monthly_expense
    is_deficit: bool       = monthly_surplus < 0
    has_credit_card: bool  = credit_card_limit > 0

    emi_ratio: float                = (existing_loan_emi / monthly_income) * 100
    savings_rate: float             = (monthly_surplus / monthly_income) * 100
    credit_utilization: float       = (
        (credit_card_used / credit_card_limit) * 100 if has_credit_card else 0.0
    )
    projected_annual_savings: float = monthly_surplus * 12

    logger.debug(
        "Metrics computed — EMI ratio: %.2f%%, savings rate: %.2f%%, "
        "credit util: %.2f%%, surplus: ₹%.2f",
        emi_ratio, savings_rate, credit_utilization, monthly_surplus,
    )

    return FinancialMetrics(
        emi_ratio=emi_ratio,
        savings_rate=savings_rate,
        credit_utilization=credit_utilization,
        projected_annual_savings=projected_annual_savings,
        monthly_surplus=monthly_surplus,
        is_deficit=is_deficit,
        has_credit_card=has_credit_card,
    )


def validate_inputs(data: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate that required fields are present and financially sensible.
    Credit card fields are optional — default to 0 if not provided.

    Args:
        data: Dictionary of raw form/JSON input from the user.

    Returns:
        Tuple of (is_valid: bool, error_message: str).
        error_message is empty string when is_valid is True.
    """
    if not isinstance(data, dict):
        return False, "Input must be a valid JSON object."

    required: list[str] = [
        "customer_name", "monthly_income", "monthly_expense",
        "existing_loan_emi", "savings_goal",
    ]
    for field in required:
        if field not in data or data[field] is None or str(data[field]).strip() == "":
            return False, f"Missing required field: {field}"

    if not str(data["customer_name"]).strip():
        return False, "Customer name cannot be blank."

    try:
        monthly_income:    float = float(data["monthly_income"])
        monthly_expense:   float = float(data["monthly_expense"])
        existing_loan_emi: float = float(data["existing_loan_emi"])
        credit_card_limit: float = float(data.get("credit_card_limit") or 0)
        credit_card_used:  float = float(data.get("credit_card_used") or 0)
        savings_goal:      float = float(data["savings_goal"])
    except (ValueError, TypeError):
        return False, "All numeric fields must be valid numbers."

    if monthly_income <= 0:
        return False, "Monthly income must be greater than zero."
    if monthly_expense < 0:
        return False, "Monthly expense cannot be negative."
    if existing_loan_emi < 0:
        return False, "Existing loan EMI cannot be negative."
    if existing_loan_emi > monthly_income:
        return False, "Existing loan EMI cannot exceed monthly income."
    if credit_card_limit < 0:
        return False, "Credit card limit cannot be negative."
    if credit_card_used < 0:
        return False, "Credit card used cannot be negative."
    if credit_card_limit > 0 and credit_card_used > credit_card_limit:
        return False, "Credit card used cannot exceed the credit card limit."
    if savings_goal < 0:
        return False, "Savings goal cannot be negative."

    return True, ""
