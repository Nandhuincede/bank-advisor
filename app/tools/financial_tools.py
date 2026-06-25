import json
import logging
from langchain.tools import tool
from app.services.financial_calculator import compute_financial_metrics
from app.db import database

logger = logging.getLogger(__name__)


# Tool 1 — Compute Financial Metrics
@tool
def compute_financial_metrics_tool(
    monthly_income: float,
    monthly_expense: float,
    existing_loan_emi: float,
    credit_card_limit: float = 0.0,
    credit_card_used: float = 0.0,
) -> str:
    """
    Compute all financial metrics from the user's raw financial data.

    Use this tool to calculate:
    - EMI ratio (FOIR): existing_loan_emi / monthly_income * 100
    - Savings rate: (monthly_income - monthly_expense) / monthly_income * 100
    - Credit utilization: credit_card_used / credit_card_limit * 100
    - Projected annual savings: (monthly_income - monthly_expense) * 12
    - Monthly surplus and deficit flag

    Args:
        monthly_income: Gross monthly income in rupees. Must be > 0.
        monthly_expense: Total monthly expenses in rupees.
        existing_loan_emi: Current monthly loan EMI in rupees. Use 0 if no loan.
        credit_card_limit: Credit card limit in rupees. Use 0 if no credit card.
        credit_card_used: Credit card outstanding amount in rupees. Use 0 if no credit card.

    Returns:
        JSON string with all computed metrics.
    """
    try:
        metrics = compute_financial_metrics(
            monthly_income=float(monthly_income),
            monthly_expense=float(monthly_expense),
            existing_loan_emi=float(existing_loan_emi),
            credit_card_limit=float(credit_card_limit),
            credit_card_used=float(credit_card_used),
        )
        logger.info("Metrics computed successfully via tool")
        return json.dumps(metrics.to_dict())
    except Exception as e:
        logger.error("compute_financial_metrics_tool error: %s", e)
        return json.dumps({"error": str(e)})


# Tool 2 — Fetch Stored Analysis
@tool
def fetch_stored_analysis_tool(analysis_id: int) -> str:
    """
    Retrieve a previously stored financial analysis from the database.

    Use this tool during follow-up chat to get the user's stored financial
    data, computed metrics, and AI report summary.

    Args:
        analysis_id: The integer ID of the analysis record to retrieve.

    Returns:
        JSON string of the analysis record, or an error message if not found.
    """
    try:
        record = database.get_analysis(int(analysis_id))
        if record:
            summary = {k: v for k, v in record.items() if k != "ai_report"}
            summary["ai_report_preview"] = record["ai_report"][:500] + "..."
            return json.dumps(summary)
        return json.dumps({"error": f"No analysis found with id={analysis_id}"})
    except Exception as e:
        logger.error("fetch_stored_analysis_tool error: %s", e)
        return json.dumps({"error": str(e)})


# Tool 3 — Fetch Chat History

@tool
def fetch_chat_history_tool(analysis_id: int) -> str:
    """
    Retrieve the full conversation history for a financial analysis session.

    Use this tool during follow-up chat to understand what was previously
    discussed so you can give contextual, consistent answers.

    Args:
        analysis_id: The integer ID of the analysis session.

    Returns:
        JSON list of messages with role and content fields.
    """
    try:
        history = database.get_chat_history(int(analysis_id))
        return json.dumps(history)
    except Exception as e:
        logger.error("fetch_chat_history_tool error: %s", e)
        return json.dumps({"error": str(e)})


# Tool 4 — 20/4/10 Car Loan Rule Evaluator

@tool
def evaluate_20_4_10_rule_tool(
    car_price: float,
    down_payment: float,
    loan_tenure_years: float,
    monthly_emi: float,
    monthly_income: float,
) -> str:
    """
    Evaluate whether a car purchase follows the 20/4/10 rule.

    The 20/4/10 rule:
    - 20: Down payment must be at least 20% of the car price
    - 4:  Loan tenure must not exceed 4 years
    - 10: Monthly car EMI must not exceed 10% of monthly income

    Use this tool whenever the user asks about buying a car, car loan,
    vehicle finance, or whether a car purchase is affordable.

    Args:
        car_price: Total on-road price of the car in rupees.
        down_payment: Upfront amount the user will pay in rupees.
        loan_tenure_years: Loan duration in years (e.g. 3, 4, 5).
        monthly_emi: Expected monthly car loan EMI in rupees.
        monthly_income: User's gross monthly income in rupees.

    Returns:
        JSON string with pass/fail for each rule and improvement suggestions.
    """
    try:
        car_price         = float(car_price)
        down_payment      = float(down_payment)
        loan_tenure_years = float(loan_tenure_years)
        monthly_emi       = float(monthly_emi)
        monthly_income    = float(monthly_income)

        down_payment_pct = (down_payment / car_price) * 100
        down_payment_ok  = down_payment_pct >= 20
        tenure_ok        = loan_tenure_years <= 4
        car_expense_pct  = (monthly_emi / monthly_income) * 100
        car_expense_ok   = car_expense_pct <= 10
        overall_pass     = down_payment_ok and tenure_ok and car_expense_ok

        suggestions = []
        if not down_payment_ok:
            needed = car_price * 0.20
            shortfall = needed - down_payment
            suggestions.append(
                f"Increase down payment by Rs.{shortfall:,.0f} to reach the 20% minimum (Rs.{needed:,.0f})."
            )
        if not tenure_ok:
            suggestions.append(
                f"Reduce loan tenure from {loan_tenure_years} years to 4 years maximum."
            )
        if not car_expense_ok:
            max_emi = monthly_income * 0.10
            suggestions.append(
                f"Your EMI of Rs.{monthly_emi:,.0f} exceeds 10% of income. "
                f"Target a maximum EMI of Rs.{max_emi:,.0f}."
            )
        if overall_pass:
            suggestions.append("Your car purchase plan follows the 20/4/10 rule. Good decision!")

        return json.dumps({
            "down_payment_pct":  round(down_payment_pct, 2),
            "down_payment_ok":   down_payment_ok,
            "tenure_ok":         tenure_ok,
            "car_expense_pct":   round(car_expense_pct, 2),
            "car_expense_ok":    car_expense_ok,
            "overall_pass":      overall_pass,
            "loan_amount":       round(car_price - down_payment, 2),
            "suggestions":       suggestions,
        })
    except Exception as e:
        logger.error("evaluate_20_4_10_rule_tool error: %s", e)
        return json.dumps({"error": str(e)})


# Exported list
ALL_TOOLS = [
    compute_financial_metrics_tool,
    fetch_stored_analysis_tool,
    fetch_chat_history_tool,
    evaluate_20_4_10_rule_tool,
]
