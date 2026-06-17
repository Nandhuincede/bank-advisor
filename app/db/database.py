import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DATABASE_PATH: str = os.getenv("DATABASE_PATH", "banking_advisor.db")


def get_connection() -> sqlite3.Connection:
    """
    Open and return a SQLite connection with WAL mode enabled.

    Raises:
        RuntimeError: If the database connection cannot be established.
    """
    try:
        conn: sqlite3.Connection = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except sqlite3.Error as e:
        logger.error("Failed to connect to database at '%s': %s", DATABASE_PATH, e)
        raise RuntimeError(f"Database connection failed: {e}") from e


def init_db() -> None:
    """
    Create tables if they don't exist.

    Raises:
        RuntimeError: If table creation fails.
    """
    try:
        with get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS analysis (
                    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_name            TEXT NOT NULL,
                    monthly_income           REAL NOT NULL,
                    monthly_expense          REAL NOT NULL,
                    existing_loan_emi        REAL NOT NULL,
                    credit_card_limit        REAL NOT NULL,
                    credit_card_used         REAL NOT NULL,
                    savings_goal             REAL NOT NULL,
                    emi_ratio                REAL NOT NULL,
                    savings_rate             REAL NOT NULL,
                    credit_utilization       REAL NOT NULL,
                    projected_annual_savings REAL NOT NULL,
                    monthly_surplus          REAL NOT NULL,
                    ai_report                TEXT NOT NULL,
                    created_at               TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chat_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_id INTEGER NOT NULL,
                    role        TEXT NOT NULL CHECK(role IN ('user','assistant')),
                    content     TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    FOREIGN KEY (analysis_id) REFERENCES analysis(id)
                );
            """)
            # Migrate existing databases that pre-date the monthly_surplus column.
            cols = {row[1] for row in conn.execute("PRAGMA table_info(analysis)").fetchall()}
            if "monthly_surplus" not in cols:
                conn.execute(
                    "ALTER TABLE analysis ADD COLUMN monthly_surplus REAL NOT NULL DEFAULT 0.0"
                )
                logger.info("Migrated analysis table: added monthly_surplus column")
        logger.info("Database initialised at '%s'", DATABASE_PATH)
    except sqlite3.Error as e:
        logger.error("Failed to initialise database: %s", e)
        raise RuntimeError(f"Database initialisation failed: {e}") from e


def save_analysis(
    customer_name: str,
    monthly_income: float,
    monthly_expense: float,
    existing_loan_emi: float,
    credit_card_limit: float,
    credit_card_used: float,
    savings_goal: float,
    emi_ratio: float,
    savings_rate: float,
    credit_utilization: float,
    projected_annual_savings: float,
    monthly_surplus: float,
    ai_report: str,
) -> int:
    """
    Persist an analysis record and return the new row ID.

    Args:
        customer_name: Name of the customer.
        monthly_income: Monthly income in ₹.
        monthly_expense: Monthly expenses in ₹.
        existing_loan_emi: Existing loan EMI in ₹.
        credit_card_limit: Credit card limit in ₹ (0 if no card).
        credit_card_used: Credit card amount used in ₹ (0 if no card).
        savings_goal: Target savings amount in ₹.
        emi_ratio: Computed EMI-to-income ratio %.
        savings_rate: Computed savings rate %.
        credit_utilization: Computed credit utilization %.
        projected_annual_savings: Computed annual savings projection ₹.
        monthly_surplus: Computed monthly surplus (income − expenses) ₹.
        ai_report: Full AI-generated financial report text.

    Returns:
        int: The auto-incremented ID of the newly inserted row.

    Raises:
        RuntimeError: If the insert operation fails.
    """
    now: str = datetime.utcnow().isoformat()
    try:
        with get_connection() as conn:
            cur: sqlite3.Cursor = conn.execute(
                """INSERT INTO analysis (
                    customer_name, monthly_income, monthly_expense,
                    existing_loan_emi, credit_card_limit, credit_card_used,
                    savings_goal, emi_ratio, savings_rate,
                    credit_utilization, projected_annual_savings,
                    monthly_surplus, ai_report, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    customer_name, monthly_income, monthly_expense,
                    existing_loan_emi, credit_card_limit, credit_card_used,
                    savings_goal, emi_ratio, savings_rate,
                    credit_utilization, projected_annual_savings,
                    monthly_surplus, ai_report, now,
                ),
            )
            row_id: int = cur.lastrowid
            logger.info("Saved analysis id=%d for customer='%s'", row_id, customer_name)
            return row_id
    except sqlite3.Error as e:
        logger.error("Failed to save analysis for '%s': %s", customer_name, e)
        raise RuntimeError(f"Failed to save analysis: {e}") from e


def get_analysis(analysis_id: int) -> Optional[dict]:
    """
    Fetch a single analysis record by ID.

    Args:
        analysis_id: The primary key of the analysis record.

    Returns:
        dict if found, None if no record exists with that ID.

    Raises:
        RuntimeError: If the query fails.
    """
    try:
        with get_connection() as conn:
            row: Optional[sqlite3.Row] = conn.execute(
                "SELECT * FROM analysis WHERE id = ?", (analysis_id,)
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error("Failed to fetch analysis id=%d: %s", analysis_id, e)
        raise RuntimeError(f"Failed to fetch analysis id={analysis_id}: {e}") from e


def get_latest_analysis() -> Optional[dict]:
    """
    Return the most recent analysis record.

    Returns:
        dict if any record exists, None if table is empty.

    Raises:
        RuntimeError: If the query fails.
    """
    try:
        with get_connection() as conn:
            row: Optional[sqlite3.Row] = conn.execute(
                "SELECT * FROM analysis ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        logger.error("Failed to fetch latest analysis: %s", e)
        raise RuntimeError(f"Failed to fetch latest analysis: {e}") from e


def save_chat_message(analysis_id: int, role: str, content: str) -> None:
    """
    Append a chat message to the history.

    Args:
        analysis_id: The analysis session this message belongs to.
        role: Either 'user' or 'assistant'.
        content: The message text.

    Raises:
        ValueError: If role is not 'user' or 'assistant'.
        RuntimeError: If the insert fails.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid role '{role}'. Must be 'user' or 'assistant'.")
    if not content or not content.strip():
        raise ValueError("Chat message content cannot be empty.")

    now: str = datetime.utcnow().isoformat()
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO chat_history (analysis_id, role, content, created_at) VALUES (?,?,?,?)",
                (analysis_id, role, content, now),
            )
    except sqlite3.Error as e:
        logger.error("Failed to save chat message for analysis_id=%d: %s", analysis_id, e)
        raise RuntimeError(f"Failed to save chat message: {e}") from e


def get_chat_history(analysis_id: int) -> list[dict]:
    """
    Return ordered chat history for an analysis session.

    Args:
        analysis_id: The analysis session ID.

    Returns:
        List of dicts with keys: role, content, created_at.
        Empty list if no messages exist.

    Raises:
        RuntimeError: If the query fails.
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM chat_history "
                "WHERE analysis_id = ? ORDER BY id ASC",
                (analysis_id,),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("Failed to fetch chat history for analysis_id=%d: %s", analysis_id, e)
        raise RuntimeError(f"Failed to fetch chat history: {e}") from e


def list_analyses(limit: int = 20) -> list[dict]:
    """
    Return a summary list of the most recent analyses.

    Args:
        limit: Maximum number of records to return (default 20).

    Returns:
        List of dicts with keys: id, customer_name, monthly_income,
        savings_rate, credit_utilization, created_at.

    Raises:
        ValueError: If limit is not a positive integer.
        RuntimeError: If the query fails.
    """
    if limit <= 0:
        raise ValueError(f"limit must be a positive integer, got {limit}.")
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id, customer_name, monthly_income, savings_rate,
                          credit_utilization, created_at
                   FROM analysis ORDER BY id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
    except sqlite3.Error as e:
        logger.error("Failed to list analyses: %s", e)
        raise RuntimeError(f"Failed to list analyses: {e}") from e