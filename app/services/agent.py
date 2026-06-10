import logging
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel

from app.services.llm_factory import get_llm
from app.tools.financial_tools import ALL_TOOLS

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are an expert AI Personal Banking & Financial Advisor with deep expertise \
in Indian personal finance, investments, credit management, and vehicle financing.

Your responsibilities:
1. Use the `compute_financial_metrics_tool` to calculate key ratios — NEVER compute them yourself.
2. Interpret the computed metrics and produce a structured financial report.
3. When answering follow-up questions, use `fetch_stored_analysis_tool` and \
`fetch_chat_history_tool` to ground your answers in the user's actual data.
4. When the user asks about buying a car or vehicle loan, use `evaluate_20_4_10_rule_tool`.

## Strict Topic Restriction
You are ONLY allowed to answer questions related to personal finance, banking, loans,
investments, savings, credit cards, EMI, budgeting, and financial planning.

If the user asks ANYTHING outside of finance — such as sports, politics, cooking,
technology, entertainment, general knowledge, or any other non-financial topic —
you must respond with EXACTLY this message and nothing else:

"I am sorry, but I can only answer questions directly related to financial questions."

Do NOT try to be helpful outside of finance. Do NOT partially answer then redirect.
Just return that exact message and stop.

## Report Structure (for /api/analyze)
Always produce a report with these exact sections:

### 🏦 Financial Health Assessment
Rate the overall health as EXCELLENT / GOOD / FAIR / POOR / CRITICAL.
Explain the rating in 2-3 sentences using the computed metrics.

### 💳 Loan Eligibility
Based on EMI ratio and income, state whether the user qualifies for new credit and estimate \
a rough eligible loan amount (use a standard 40% EMI-to-income guideline).

### 💰 Savings Recommendations
3-5 concrete, actionable steps to improve savings rate and hit the stated savings goal.

### 📈 Investment Suggestions
3-5 investment options appropriate for the user's risk profile (derived from their surplus \
and credit health). Include approximate allocation percentages.

### 🔄 Loan Prepayment Advice
Advise on whether to prepay existing loans given the current EMI ratio and surplus.

## Critical Financial Condition
If `is_deficit` is True (expenses exceed income), classify the condition as CRITICAL and:
- Recommend immediate reduction of discretionary spending
- Advise against taking any new loans
- Focus exclusively on budget stabilisation before any investment discussion

## 20/4/10 Car Loan Rule
If the user asks anything about buying a car, car loan, vehicle finance, or car EMI
during follow-up chat:
1. Use the values they provide: car price, down payment, loan tenure, monthly EMI.
2. Get their monthly_income from `fetch_stored_analysis_tool`.
3. Call `evaluate_20_4_10_rule_tool` with all those values.
4. Present the result clearly in this format:

### 🚗 20/4/10 Car Buying Rule Evaluation
- **Rule 1 — 20% Down Payment**: PASS/FAIL — paid X%, minimum 20% required
- **Rule 2 — Max 4 Year Tenure**: PASS/FAIL — X years chosen, max 4 years allowed
- **Rule 3 — Max 10% of Income**: PASS/FAIL — EMI is X% of income, max 10% allowed
- **Overall**: PASS or FAIL

Then list the suggestions returned by the tool to help the user improve their plan.

If the user asks about the 20/4/10 rule without providing car details, explain the rule \
clearly and ask them for: car price, down payment amount, loan tenure in years, and expected monthly EMI.

## Tone & Style
- Be empathetic, clear, and specific — avoid generic platitudes.
- Use Indian Rupee (₹) formatting throughout.
- Keep the report scannable: use bullet points within each section.
- For follow-up chat: be conversational, friendly, and reference specific numbers from the analysis.
"""

ANALYSIS_HUMAN_TEMPLATE = """Please analyse the following financial profile and generate a \
complete structured report.

Customer: {customer_name}
Monthly Income: ₹{monthly_income}
Monthly Expense: ₹{monthly_expense}
Existing Loan EMI: ₹{existing_loan_emi}
Credit Card Limit: ₹{credit_card_limit}
Credit Card Used: ₹{credit_card_used}
Savings Goal: ₹{savings_goal}

First, call the `compute_financial_metrics_tool` with the numeric fields above to get the \
precise ratios. Then interpret those ratios to produce the structured report."""


def _build_agent() -> AgentExecutor:
    
    try:
        llm: BaseChatModel = get_llm()
        prompt: ChatPromptTemplate = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])
        agent = create_tool_calling_agent(llm, ALL_TOOLS, prompt)
        return AgentExecutor(
            agent=agent,
            tools=ALL_TOOLS,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=8,
        )
    except Exception as e:
        logger.error("Failed to build agent: %s", e)
        raise RuntimeError(f"Agent initialisation failed: {e}") from e


def run_analysis_agent(
    customer_name: str,
    monthly_income: float,
    monthly_expense: float,
    existing_loan_emi: float,
    credit_card_limit: float,
    credit_card_used: float,
    savings_goal: float,
) -> str:
    """
    Invoke the LangChain agent for a fresh financial analysis.

    Args:
        customer_name:     Full name of the customer.
        monthly_income:    Monthly income in ₹.
        monthly_expense:   Monthly expenses in ₹.
        existing_loan_emi: Existing loan EMI in ₹.
        credit_card_limit: Credit card limit in ₹ (0 if no card).
        credit_card_used:  Credit card used amount in ₹ (0 if no card).
        savings_goal:      Target savings amount in ₹.

    Returns:
        str: The AI-generated structured financial report.

    Raises:
        ValueError: If customer_name is blank.
        RuntimeError: If the agent invocation fails.
    """
    if not customer_name or not customer_name.strip():
        raise ValueError("customer_name cannot be empty.")

    try:
        executor: AgentExecutor = _build_agent()
        human_msg: str = ANALYSIS_HUMAN_TEMPLATE.format(
            customer_name=customer_name,
            monthly_income=monthly_income,
            monthly_expense=monthly_expense,
            existing_loan_emi=existing_loan_emi,
            credit_card_limit=credit_card_limit,
            credit_card_used=credit_card_used,
            savings_goal=savings_goal,
        )
        logger.info("Running analysis agent for customer='%s'", customer_name)
        result: dict = executor.invoke({
            "input": human_msg,
            "chat_history": [],
        })
        return result["output"]
    except KeyError as e:
        logger.error("Agent response missing 'output' key: %s", e)
        raise RuntimeError("Agent returned an unexpected response format.") from e
    except Exception as e:
        logger.error("Analysis agent failed for customer='%s': %s", customer_name, e)
        raise RuntimeError(f"Analysis agent failed: {e}") from e


def run_chat_agent(
    analysis_id: int,
    user_question: str,
    chat_history: list[dict],
) -> str:
    """
    Invoke the LangChain agent for a follow-up question with full context.

    Args:
        analysis_id:   The stored analysis session ID (used to fetch context).
        user_question: The follow-up question from the user.
        chat_history:  List of {role, content} dicts from the DB (may be empty).

    Returns:
        str: The AI-generated contextual answer.

    Raises:
        ValueError: If user_question is blank or analysis_id is invalid.
        RuntimeError: If the agent invocation fails.
    """
    if not user_question or not user_question.strip():
        raise ValueError("user_question cannot be empty.")
    if not isinstance(analysis_id, int) or analysis_id <= 0:
        raise ValueError(f"analysis_id must be a positive integer, got {analysis_id!r}.")

    try:
        executor: AgentExecutor = _build_agent()

        lc_history: list[BaseMessage] = []
        for msg in chat_history:
            if msg.get("role") == "user":
                lc_history.append(HumanMessage(content=msg["content"]))
            elif msg.get("role") == "assistant":
                lc_history.append(AIMessage(content=msg["content"]))

        system_context: str = (
            f"The user is asking a follow-up question about their financial analysis "
            f"(analysis_id={analysis_id}). Use `fetch_stored_analysis_tool` with "
            f"'{analysis_id}' and `fetch_chat_history_tool` if you need context. "
            f"If the question is about buying a car or vehicle loan, use "
            f"`evaluate_20_4_10_rule_tool` with the car details they provide and "
            f"their monthly_income from the stored analysis. "
            f"Then answer the user's question concisely and helpfully."
        )

        logger.info("Running chat agent for analysis_id=%d", analysis_id)
        result: dict = executor.invoke({
            "input": f"{system_context}\n\nUser question: {user_question}",
            "chat_history": lc_history,
        })
        return result["output"]
    except KeyError as e:
        logger.error("Chat agent response missing 'output' key: %s", e)
        raise RuntimeError("Agent returned an unexpected response format.") from e
    except Exception as e:
        logger.error("Chat agent failed for analysis_id=%d: %s", analysis_id, e)
        raise RuntimeError(f"Chat agent failed: {e}") from e
