import json
from langchain.tools import tool
from app.services.financial_calculator import compute_financial_metrics
from app.db import database

# Tool 1 — Compute Financial Metrics
@tool
def compute_financial_metrics_tool(input_json: str) -> str:
    """
    Compute financial metrics from raw user input.

    Input must be a JSON string with keys:
      monthly_income, monthly_expense, existing_loan_emi,
      credit_card_limit, credit_card_used

    Returns a JSON string with:
      emi_ratio, savings_rate, credit_utilization,
      projected_annual_savings, monthly_surplus, is_deficit
    """
    try:
        data = json.loads(input_json)
        metrics = compute_financial_metrics(
            monthly_income=float(data["monthly_income"]),
            monthly_expense=float(data["monthly_expense"]),
            existing_loan_emi=float(data["existing_loan_emi"]),
            credit_card_limit=float(data["credit_card_limit"]),
            credit_card_used=float(data["credit_card_used"]),
        )
        return json.dumps(metrics.to_dict())
    except Exception as e:
        return json.dumps({"error": str(e)})

# Tool 2 — Fetch Stored Analysis
@tool
def fetch_stored_analysis_tool(analysis_id: str) -> str:
    """
    Retrieve a previously stored financial analysis from the database.

    Input: analysis_id as a string (integer).
    Returns: JSON string of the full analysis record,
             or an error message if not found.
    """
    try:
        aid = int(analysis_id.strip())
        record = database.get_analysis(aid)
        if record:
            # Exclude the raw ai_report to keep context manageable
            summary = {k: v for k, v in record.items() if k != "ai_report"}
            summary["ai_report_preview"] = record["ai_report"][:500] + "…"
            return json.dumps(summary)
        return json.dumps({"error": f"No analysis found with id={aid}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


# Tool 3 — Fetch Chat History
@tool
def fetch_chat_history_tool(analysis_id: str) -> str:
    """
    Retrieve the chat history for a given financial analysis session.

    Input: analysis_id as a string (integer).
    Returns: JSON list of {role, content, created_at} dicts.
    """
    try:
        aid = int(analysis_id.strip())
        history = database.get_chat_history(aid)
        return json.dumps(history)
    except Exception as e:
        return json.dumps({"error": str(e)})


# Exported list for easy import
ALL_TOOLS = [
    compute_financial_metrics_tool,
    fetch_stored_analysis_tool,
    fetch_chat_history_tool,
]
