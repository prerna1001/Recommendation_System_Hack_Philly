"""Shared helpers: DB access, structured action logging, Claude calls.

Every agent writes to action_log before returning. That table is what
makes agent activity observable independent of whatever XO's own
session view captures -- it's the raw evidence for the demo video.

DB: Postgres (see data/schema_postgres.sql), via psycopg with a dict_row
factory so `row["column"]` access -- the pattern every agent already uses --
works unchanged from the earlier SQLite build.
"""
import os

import anthropic
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql:///coffee_connector")
MODEL = "claude-sonnet-5"

_client = None


def get_db() -> psycopg.Connection:
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)
    return conn


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. export it before running any agent."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def call_claude(system: str, user: str, max_tokens: int = 1024) -> tuple[str, float]:
    """Returns (text, estimated_cost_usd)."""
    client = get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    # Sonnet 5 list pricing: $3/M input, $15/M output -- rough estimate for the
    # observability log, not a billing-grade figure.
    cost = (resp.usage.input_tokens * 3 + resp.usage.output_tokens * 15) / 1_000_000
    return text, cost


def log_action(conn: psycopg.Connection, company_id: int, agent: str, action_type: str,
                input_summary: str, output_summary: str, cost_estimate: float) -> None:
    conn.execute(
        """INSERT INTO action_log (company_id, agent, action_type, input_summary, output_summary, cost_estimate)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (company_id, agent, action_type, input_summary, output_summary, cost_estimate),
    )
    conn.commit()


def add_recommendation(conn: psycopg.Connection, company_id: int, rec_type: str, content: str, reasoning: str) -> int:
    cur = conn.execute(
        """INSERT INTO recommendations (company_id, type, content, reasoning, status)
           VALUES (%s, %s, %s, %s, 'pending_approval') RETURNING id""",
        (company_id, rec_type, content, reasoning),
    )
    conn.commit()
    return cur.fetchone()["id"]
