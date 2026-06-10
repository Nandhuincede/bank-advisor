
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from app.services.llm_factory import get_llm
from app.tools.financial_tools import ALL_TOOLS



# System prompt — injected once, defines agent personality
SYSTEM_PROMPT = """You are an expert AI Personal Banking & Financial Advisor with deep expertise \
in Indian personal finance, investments, and credit management.

Your responsibilities:
1. Use the `compute_financial_metrics_tool` to calculate key ratios — NEVER compute them yourself.
2. Interpret the computed metrics and produce a structured financial report.
3. When answering follow-up questions, use `fetch_stored_analysis_tool` and \
`fetch_chat_history_tool` to ground your answers in the user's actual data.

## Report Structure (for /api/analyze)
Always produce a report with these exact sections:

### 🏦 Financial Health Assessment
Rate the overall health as EXCELLENT / GOOD / FAIR / POOR / CRITICAL.
Explain the rating in 2-3 sentences using the computed metrics.

### 💳 Loan Eligibility
Based on EMI ratio and income, state whether the user qualifies for new credit and estimate \
a rough eligible loan amount (use a standard 40 % EMI-to-income guideline).

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
    """Construct a fresh AgentExecutor (stateless — state lives in DB)."""
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages([
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
        max_iterations=6,
    )


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
    Invoke the agent for a fresh financial analysis.
    Returns the AI-generated report as a string.
    """
    executor = _build_agent()
    human_msg = ANALYSIS_HUMAN_TEMPLATE.format(
        customer_name=customer_name,
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        existing_loan_emi=existing_loan_emi,
        credit_card_limit=credit_card_limit,
        credit_card_used=credit_card_used,
        savings_goal=savings_goal,
    )
    result = executor.invoke({
        "input": human_msg,
        "chat_history": [],
    })
    return result["output"]


def run_chat_agent(
    analysis_id: int,
    user_question: str,
    chat_history: list[dict],
) -> str:
    """
    Invoke the agent for a follow-up question, with full context.
    chat_history: list of {role, content} dicts from the DB.
    Returns the AI response string.
    """
    executor = _build_agent()

    # Convert DB history to LangChain message objects
    lc_history = []
    for msg in chat_history:
        if msg["role"] == "user":
            lc_history.append(HumanMessage(content=msg["content"]))
        else:
            lc_history.append(AIMessage(content=msg["content"]))

    system_context = (
        f"The user is asking a follow-up question about their financial analysis "
        f"(analysis_id={analysis_id}). Use `fetch_stored_analysis_tool` with "
        f"'{analysis_id}' and `fetch_chat_history_tool` if you need context. "
        f"Then answer the user's question concisely and helpfully."
    )

    result = executor.invoke({
        "input": f"{system_context}\n\nUser question: {user_question}",
        "chat_history": lc_history,
    })
    return result["output"]
