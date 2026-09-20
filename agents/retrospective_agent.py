"""Agent 2: Event Retrospective / Rubric.

Aggregates feedback ratings and free-text comments for one past event
into a rubric scorecard: numeric scores per category plus a synthesized
"what worked / what didn't" summary. Writes to rubric_scores.

Multi-tenant: takes company_id so it only reads/writes that company's event.
"""
import argparse
import statistics

from common import call_claude, get_db, log_action

AGENT_NAME = "retrospective_agent"
CATEGORIES = ["turnout", "connection_relevance", "format", "logistics", "sponsor_value"]
CONNECTION_RATE_BENCHMARK = 0.50  # all-along.com field notes: aim for 50%+

SYSTEM_PROMPT = """You are scoring a past developer community event from attendee feedback. \
The headline metric is Relevant Connection Rate -- the share of attendees who report \
leaving with at least one connection they'd genuinely follow up with (benchmark: 50%+) -- \
not a generic "engagement" score, because a vague satisfaction rating doesn't tell you \
whether the event actually did its job: helping people meet someone useful. You'll also get \
average ratings for turnout, connection relevance, format, logistics, and sponsor value, \
plus free-text comments. Write a concise scorecard: 1) call out the Relevant Connection Rate \
against the 50% benchmark first, 2) a one-line verdict per other category (strong/mixed/weak \
with why), 3) a short "what worked" list, 4) a short "what didn't" list. Be specific -- pull \
directly from the comments, don't generalize."""


def run(company_id: int, event_id: int) -> str:
    conn = get_db()
    event = conn.execute(
        "SELECT * FROM events WHERE id = %s AND company_id = %s", (event_id, company_id)
    ).fetchone()
    if not event:
        return f"No event with id {event_id}"

    rows = conn.execute(
        "SELECT * FROM feedback WHERE event_id = %s AND company_id = %s", (event_id, company_id)
    ).fetchall()
    if not rows:
        return f"No feedback yet for event {event_id}"

    connection_rate = round(sum(r["had_relevant_connection"] for r in rows) / len(rows), 2)

    col_map = {
        "turnout": "rating_turnout",
        "connection_relevance": "connection_relevance_rating",
        "format": "rating_format",
        "logistics": "rating_logistics",
        "sponsor_value": "rating_sponsor_value",
    }
    averages = {cat: round(statistics.mean(r[col] for r in rows), 2) for cat, col in col_map.items()}

    comments = "\n".join(f"- {r['free_text']}" for r in rows)
    vs_benchmark = "above" if connection_rate >= CONNECTION_RATE_BENCHMARK else "below"
    user_prompt = (
        f"Event: {event['name']} ({event['format']} at {event['venue']}, {event['date']})\n"
        f"Relevant Connection Rate: {connection_rate:.0%} ({vs_benchmark} the 50% benchmark)\n"
        f"Average ratings (1-5): {averages}\n\nComments:\n{comments}"
    )
    text, cost = call_claude(SYSTEM_PROMPT, user_prompt, max_tokens=2048)

    conn.execute(
        "INSERT INTO rubric_scores (company_id, event_id, category, score, notes) VALUES (%s, %s, %s, %s, %s)",
        (company_id, event_id, "relevant_connection_rate", connection_rate, text[:500]),
    )
    for cat, score in averages.items():
        conn.execute(
            "INSERT INTO rubric_scores (company_id, event_id, category, score, notes) VALUES (%s, %s, %s, %s, %s)",
            (company_id, event_id, cat, score, text[:500]),
        )
    conn.commit()
    log_action(conn, company_id, AGENT_NAME, "score_event", user_prompt[:200], text[:200], cost)
    conn.close()
    return (
        f"Scorecard for '{event['name']}':\n\n"
        f"Relevant Connection Rate: {connection_rate:.0%} ({vs_benchmark} benchmark)\n"
        f"Ratings: {averages}\n\n{text}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("company_id", type=int, help="the company/tenant to run this for")
    parser.add_argument("event_id", type=int)
    args = parser.parse_args()
    print(run(args.company_id, args.event_id))
