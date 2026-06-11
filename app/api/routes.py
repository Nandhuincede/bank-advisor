import logging
from flask import Blueprint, request, jsonify, Response
from app.services.financial_calculator import validate_inputs, compute_financial_metrics
from app.services.agent import run_analysis_agent, run_chat_agent
from app.db import database

logger = logging.getLogger(__name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/analyze", methods=["POST"])
def analyze() -> tuple[Response, int]:
    """
    Accept financial form data, compute metrics, invoke AI agent,
    persist to DB, and return the report.

    Returns:
        JSON response with success flag, analysis_id, metrics, and report.
    """
    data: dict = request.get_json(force=True, silent=True) or {}

    # 1. Validate inputs
    valid: bool
    error_msg: str
    valid, error_msg = validate_inputs(data)
    if not valid:
        logger.warning("Validation failed: %s", error_msg)
        return jsonify({"success": False, "error": error_msg}), 400

    # 2. Parse — credit card fields optional, default to 0
    try:
        customer_name:     str   = str(data["customer_name"]).strip()
        monthly_income:    float = float(data["monthly_income"])
        monthly_expense:   float = float(data["monthly_expense"])
        existing_loan_emi: float = float(data["existing_loan_emi"])
        credit_card_limit: float = float(data.get("credit_card_limit") or 0)
        credit_card_used:  float = float(data.get("credit_card_used") or 0)
        savings_goal:      float = float(data["savings_goal"])
    except (ValueError, TypeError) as e:
        logger.error("Failed to parse request fields: %s", e)
        return jsonify({"success": False, "error": "Invalid numeric value in request."}), 400

    # 3. Pure-Python calculations (no LLM)
    try:
        metrics = compute_financial_metrics(
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
            existing_loan_emi=existing_loan_emi,
            credit_card_limit=credit_card_limit,
            credit_card_used=credit_card_used,
        )
    except (ValueError, TypeError) as e:
        logger.error("Financial calculation error: %s", e)
        return jsonify({"success": False, "error": str(e)}), 400

    # 4. LangChain Agent generates the report
    try:
        ai_report: str = run_analysis_agent(
            customer_name=customer_name,
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
            existing_loan_emi=existing_loan_emi,
            credit_card_limit=credit_card_limit,
            credit_card_used=credit_card_used,
            savings_goal=savings_goal,
        )
    except RuntimeError as e:
        logger.error("Agent error during analysis: %s", e)
        return jsonify({"success": False, "error": f"LLM error: {str(e)}"}), 500

    # 5. Persist to SQLite
    try:
        analysis_id: int = database.save_analysis(
            customer_name=customer_name,
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
            existing_loan_emi=existing_loan_emi,
            credit_card_limit=credit_card_limit,
            credit_card_used=credit_card_used,
            savings_goal=savings_goal,
            emi_ratio=metrics.emi_ratio,
            savings_rate=metrics.savings_rate,
            credit_utilization=metrics.credit_utilization,
            projected_annual_savings=metrics.projected_annual_savings,
            ai_report=ai_report,
        )
    except RuntimeError as e:
        logger.error("Database error saving analysis: %s", e)
        return jsonify({"success": False, "error": "Failed to save analysis to database."}), 500

    return jsonify({
        "success":     True,
        "analysis_id": analysis_id,
        "metrics":     metrics.to_dict(),
        "report":      ai_report,
    }), 200


# POST /api/chat
@api_bp.route("/chat", methods=["POST"])
def chat() -> tuple[Response, int]:
    """
    Accept a follow-up question, retrieve context from DB,
    invoke AI agent, save the exchange, and return the answer.

    Returns:
        JSON response with success flag and answer string.
    """
    data: dict = request.get_json(force=True, silent=True) or {}
    analysis_id = data.get("analysis_id")
    question: str = str(data.get("question", "")).strip()

    if not analysis_id:
        return jsonify({"success": False, "error": "analysis_id is required."}), 400
    if not question:
        return jsonify({"success": False, "error": "question cannot be empty."}), 400

    try:
        analysis_id_int: int = int(analysis_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "analysis_id must be an integer."}), 400

    # Verify the analysis exists
    try:
        record: dict | None = database.get_analysis(analysis_id_int)
    except RuntimeError as e:
        logger.error("DB error fetching analysis id=%s: %s", analysis_id_int, e)
        return jsonify({"success": False, "error": "Database error."}), 500

    if not record:
        return jsonify({"success": False, "error": "Analysis not found."}), 404

    # Fetch chat history
    try:
        history: list[dict] = database.get_chat_history(analysis_id_int)
    except RuntimeError as e:
        logger.error("DB error fetching chat history: %s", e)
        return jsonify({"success": False, "error": "Failed to fetch chat history."}), 500

    # Run agent
    try:
        answer: str = run_chat_agent(
            analysis_id=analysis_id_int,
            user_question=question,
            chat_history=history,
        )
    except (ValueError, RuntimeError) as e:
        logger.error("Chat agent error: %s", e)
        return jsonify({"success": False, "error": f"LLM error: {str(e)}"}), 500

    # Persist conversation
    try:
        database.save_chat_message(analysis_id_int, "user", question)
        database.save_chat_message(analysis_id_int, "assistant", answer)
    except RuntimeError as e:
        logger.warning("Failed to persist chat message: %s", e)
        # Non-fatal — return the answer even if saving fails

    return jsonify({"success": True, "answer": answer}), 200

# GET /api/history
@api_bp.route("/history", methods=["GET"])
def history() -> tuple[Response, int]:
    """
    Return a summary list of all past analyses.

    Returns:
        JSON response with success flag and list of analysis summaries.
    """
    try:
        records: list[dict] = database.list_analyses()
        return jsonify({"success": True, "analyses": records}), 200
    except RuntimeError as e:
        logger.error("Failed to list analyses: %s", e)
        return jsonify({"success": False, "error": "Failed to retrieve history."}), 500

# GET /api/analysis/<id>
@api_bp.route("/analysis/<int:analysis_id>", methods=["GET"])
def get_analysis(analysis_id: int) -> tuple[Response, int]:
    """
    Return the full analysis record including AI report and chat history.

    Args:
        analysis_id: The analysis record primary key from the URL path.

    Returns:
        JSON response with analysis dict and chat_history list.
    """
    try:
        record: dict | None = database.get_analysis(analysis_id)
    except RuntimeError as e:
        logger.error("DB error fetching analysis id=%d: %s", analysis_id, e)
        return jsonify({"success": False, "error": "Database error."}), 500

    if not record:
        return jsonify({"success": False, "error": "Not found."}), 404

    try:
        chat: list[dict] = database.get_chat_history(analysis_id)
    except RuntimeError as e:
        logger.error("DB error fetching chat history for id=%d: %s", analysis_id, e)
        return jsonify({"success": False, "error": "Failed to retrieve chat history."}), 500

    return jsonify({"success": True, "analysis": record, "chat_history": chat}), 200
