from flask import Blueprint, request, jsonify

from app.services.financial_calculator import validate_inputs, compute_financial_metrics
from app.services.agent import run_analysis_agent, run_chat_agent
from app.db import database

api_bp = Blueprint("api", __name__, url_prefix="/api")



# POST /api/analyze


@api_bp.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True, silent=True) or {}

    # 1. Validate inputs
    valid, error_msg = validate_inputs(data)
    if not valid:
        return jsonify({"success": False, "error": error_msg}), 400

    # 2. Parse — credit card fields optional, default to 0
    customer_name     = str(data["customer_name"]).strip()
    monthly_income    = float(data["monthly_income"])
    monthly_expense   = float(data["monthly_expense"])
    existing_loan_emi = float(data["existing_loan_emi"])
    credit_card_limit = float(data.get("credit_card_limit") or 0)
    credit_card_used  = float(data.get("credit_card_used") or 0)
    savings_goal      = float(data["savings_goal"])

    # 3. Pure-Python calculations (no LLM)
    metrics = compute_financial_metrics(
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        existing_loan_emi=existing_loan_emi,
        credit_card_limit=credit_card_limit,
        credit_card_used=credit_card_used,
    )

    # 4. LangChain Agent generates the report
    try:
        ai_report = run_analysis_agent(
            customer_name=customer_name,
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
            existing_loan_emi=existing_loan_emi,
            credit_card_limit=credit_card_limit,
            credit_card_used=credit_card_used,
            savings_goal=savings_goal,
        )
    except Exception as exc:
        return jsonify({"success": False, "error": f"LLM error: {str(exc)}"}), 500

    # 5. Persist to SQLite
    analysis_id = database.save_analysis(
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

    return jsonify({
        "success": True,
        "analysis_id": analysis_id,
        "metrics": metrics.to_dict(),
        "report": ai_report,
    })



# POST /api/chat


@api_bp.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    analysis_id = data.get("analysis_id")
    question    = str(data.get("question", "")).strip()

    if not analysis_id:
        return jsonify({"success": False, "error": "analysis_id is required."}), 400
    if not question:
        return jsonify({"success": False, "error": "question cannot be empty."}), 400

    record = database.get_analysis(int(analysis_id))
    if not record:
        return jsonify({"success": False, "error": "Analysis not found."}), 404

    history = database.get_chat_history(int(analysis_id))

    try:
        answer = run_chat_agent(
            analysis_id=int(analysis_id),
            user_question=question,
            chat_history=history,
        )
    except Exception as exc:
        return jsonify({"success": False, "error": f"LLM error: {str(exc)}"}), 500

    database.save_chat_message(int(analysis_id), "user", question)
    database.save_chat_message(int(analysis_id), "assistant", answer)

    return jsonify({"success": True, "answer": answer})



# GET /api/history


@api_bp.route("/history", methods=["GET"])
def history():
    records = database.list_analyses()
    return jsonify({"success": True, "analyses": records})



# GET /api/analysis/<id>


@api_bp.route("/analysis/<int:analysis_id>", methods=["GET"])
def get_analysis(analysis_id: int):
    record = database.get_analysis(analysis_id)
    if not record:
        return jsonify({"success": False, "error": "Not found."}), 404
    chat = database.get_chat_history(analysis_id)
    return jsonify({"success": True, "analysis": record, "chat_history": chat})
