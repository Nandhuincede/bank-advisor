"""
db/database.py — SQLite database layer
Handles schema creation, analysis storage, and chat history.
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

DATABASE_PATH = os.getenv("DATABASE_PATH", "banking_advisor.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS analysis (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name       TEXT NOT NULL,
                monthly_income      REAL NOT NULL,
                monthly_expense     REAL NOT NULL,
                existing_loan_emi   REAL NOT NULL,
                credit_card_limit   REAL NOT NULL,
                credit_card_used    REAL NOT NULL,
                savings_goal        REAL NOT NULL,
                emi_ratio           REAL NOT NULL,
                savings_rate        REAL NOT NULL,
                credit_utilization  REAL NOT NULL,
                projected_annual_savings REAL NOT NULL,
                ai_report           TEXT NOT NULL,
                created_at          TEXT NOT NULL
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
    ai_report: str,
) -> int:
    """Persist an analysis record. Returns the new row ID."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        cur = conn.execute(
            """INSERT INTO analysis (
                customer_name, monthly_income, monthly_expense,
                existing_loan_emi, credit_card_limit, credit_card_used,
                savings_goal, emi_ratio, savings_rate,
                credit_utilization, projected_annual_savings,
                ai_report, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                customer_name, monthly_income, monthly_expense,
                existing_loan_emi, credit_card_limit, credit_card_used,
                savings_goal, emi_ratio, savings_rate,
                credit_utilization, projected_annual_savings,
                ai_report, now,
            ),
        )
        return cur.lastrowid


def get_analysis(analysis_id: int) -> Optional[dict]:
    """Fetch a single analysis record by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analysis WHERE id = ?", (analysis_id,)
        ).fetchone()
        return dict(row) if row else None


def get_latest_analysis() -> Optional[dict]:
    """Return the most recent analysis record."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM analysis ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def save_chat_message(analysis_id: int, role: str, content: str) -> None:
    """Append a chat message to the history."""
    now = datetime.utcnow().isoformat()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_history (analysis_id, role, content, created_at) VALUES (?,?,?,?)",
            (analysis_id, role, content, now),
        )


def get_chat_history(analysis_id: int) -> list[dict]:
    """Return ordered chat history for an analysis session."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_history WHERE analysis_id = ? ORDER BY id ASC",
            (analysis_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def list_analyses(limit: int = 20) -> list[dict]:
    """Return the most recent analyses (summary only)."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, customer_name, monthly_income, savings_rate,
                      credit_utilization, created_at
               FROM analysis ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
