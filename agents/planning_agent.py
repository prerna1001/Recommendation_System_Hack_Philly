"""Agent 3: Recommendation & Planning.

Combines the organizer's own retrospective on the latest event (their read of
why turnout was what it was and whether it worked -- entered via the
dashboard, see events.turnout_reason/success_assessment/weather_tag), the
attendee-survey-derived rubric scorecard, sponsor-history patterns (what type
of company tends to give cash vs. credits vs. food), and any already-approved
outreach contacts into a next-event plan: format, venue, and a sponsor-type
match. Writes a 'venue'/'sponsor_match' recommendation -- still
pending_approval, never auto-booked.

The organizer's own retrospective is the primary signal here, not a side
note: it's their first-hand read of what happened (a bad turnout because of
a competing street festival reads very differently than a bad turnout
because the format flopped), and the rubric/survey data is supporting
evidence, not a replacement for it.

Multi-tenant: every function takes company_id so sponsor history, rubric
scores, weights, and recommendations all stay scoped to the logged-in company.
"""
import argparse

from common import add_recommendation, call_claude, get_db, log_action
from weights import get_weights_map, tag_recommendation

AGENT_NAME = "planning_agent"

SYSTEM_PROMPT = """You help plan the next event for a developer community. You'll get the \
organizer's OWN retrospective on the most recent event (their first-hand read of turnout, \
why it was what it was, and whether it worked) -- treat this as the primary signal, since \
it's ground truth from the person who ran it, not a generic survey average. You'll also get \
the attendee-survey-derived rubric scorecard as supporting evidence, historical \
sponsor-contribution patterns (which sponsor types tend to give cash vs. credits vs. food), \
and a list of already human-approved outreach contacts. If the organizer's retrospective and \
the rubric scorecard seem to disagree, trust the organizer's account and say so explicitly \
rather than silently averaging them.

Reply the way you'd actually message the organizer in chat -- plain sentences, no markdown \
(no #, *, >, no headers or bullet lists). Cover three things, each as a short line starting \
with its label followed by a colon: "Format:", "Venue:", "Sponsor focus:" -- one or two \
sentences each, giving the pick and the one-line reason behind it (grounded in the \
organizer's retrospective and the historical pattern, not generic advice). Keep the whole \
reply short and actionable -- this will be reviewed by a human organizer before anything is \
booked."""


def sponsor_patterns(conn, company_id: int):
    """Historical sponsor-contribution patterns, weighted by the learned
    sponsor_type weight (see weights.py) so types the organizer has previously
    liked/approved surface first, not just whichever gave most often before."""
    weights = get_weights_map(conn, company_id, "sponsor_type")
    rows = conn.execute(
        """SELECT sponsor_type, contribution_type, COUNT(*) as n
           FROM sponsor_history WHERE company_id = %s
           GROUP BY sponsor_type, contribution_type
           ORDER BY sponsor_type, n DESC""",
        (company_id,),
    ).fetchall()
    for r in rows:
        r["weighted_n"] = round(r["n"] * weights.get(r["sponsor_type"], 1.0), 2)
    rows.sort(key=lambda r: r["weighted_n"], reverse=True)
    text = "\n".join(
        f"- {r['sponsor_type']} -> {r['contribution_type']} ({r['n']}x, weighted {r['weighted_n']})"
        for r in rows
    )
    top_sponsor_types = {r["sponsor_type"] for r in rows[:3]}
    return text, top_sponsor_types


def organizer_retrospective_text(conn, company_id: int, event_id: int) -> str:
    event = conn.execute(
        """SELECT registered_count, attended_count, weather_tag, turnout_reason, success_assessment
           FROM events WHERE id = %s AND company_id = %s""",
        (event_id, company_id),
    ).fetchone()
    if not event or not any(
        (event["turnout_reason"], event["success_assessment"], event["weather_tag"])
    ):
        return "(organizer hasn't filled in a retrospective for this event yet -- ask them to before planning from it, or proceed cautiously from the survey data alone)"

    parts = []
    if event["registered_count"] is not None and event["attended_count"] is not None:
        parts.append(f"Registered vs. attended: {event['attended_count']}/{event['registered_count']}")
    if event["weather_tag"]:
        parts.append(f"Weather/day tag: {event['weather_tag']}")
    if event["turnout_reason"]:
        parts.append(f"Organizer's read on turnout: {event['turnout_reason']}")
    if event["success_assessment"]:
        parts.append(f"Organizer's success assessment: {event['success_assessment']}")
    return "\n".join(f"- {p}" for p in parts)


def run(company_id: int, latest_event_id: int) -> tuple[str, int | None]:
    """Returns (reply_text, recommendation_id). recommendation_id is None
    when there's nothing to plan from yet (no rubric scores for the event)."""
    conn = get_db()
    latest_scores = conn.execute(
        "SELECT category, score, notes FROM rubric_scores WHERE event_id = %s AND company_id = %s",
        (latest_event_id, company_id),
    ).fetchall()
    if not latest_scores:
        return f"No rubric scores for event {latest_event_id} yet -- run retrospective_agent first.", None

    approved = conn.execute(
        "SELECT content FROM recommendations WHERE company_id = %s AND type = 'outreach' AND status = 'approved'",
        (company_id,),
    ).fetchall()

    organizer_text = organizer_retrospective_text(conn, company_id, latest_event_id)
    scores_text = "\n".join(f"- {r['category']}: {r['score']}/5" for r in latest_scores)
    patterns_text, top_sponsor_types = sponsor_patterns(conn, company_id)
    approved_text = "\n".join(f"- {r['content'][:150]}" for r in approved) or "(none approved yet)"

    user_prompt = (
        f"Organizer's own retrospective on this event (primary signal):\n{organizer_text}\n\n"
        f"Attendee-survey-derived rubric scorecard (supporting evidence):\n{scores_text}\n\n"
        f"Historical sponsor patterns (weighted by past organizer feedback):\n{patterns_text}\n\n"
        f"Human-approved outreach contacts available:\n{approved_text}"
    )
    text, cost = call_claude(SYSTEM_PROMPT, user_prompt, max_tokens=2048)
    log_action(conn, company_id, AGENT_NAME, "plan_next_event", user_prompt[:200], text[:200], cost)
    rec_id = add_recommendation(conn, company_id, "venue", text, f"based_on_event={latest_event_id}")

    for sponsor_type in top_sponsor_types:
        tag_recommendation(conn, rec_id, "sponsor_type", sponsor_type)

    conn.close()
    return text, rec_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("company_id", type=int, help="the company/tenant to run this for")
    parser.add_argument("latest_event_id", type=int)
    args = parser.parse_args()
    reply, rec_id = run(args.company_id, args.latest_event_id)
    print(f"[recommendation #{rec_id}]\n\n{reply}" if rec_id else reply)
