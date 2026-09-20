"""Agent 1: Network Intelligence.

Given a goal ("expand to NYC", "get a sponsor for print/swag"), ranks the
union of every member's contacts by relationship strength weighted by the
learned per-company-type weight (see weights.py), then lets Claude pick and
explain the strongest 1-3 matches from that pool -- drafting (but never
sending) an intro-request. Writes to recommendations with
status='pending_approval'; nothing here contacts a real person.

Matching note: earlier versions filtered candidates with a SQL `LIKE` on
company/title text, which missed semantically related matches (e.g.
"fintech" wouldn't find a company tagged "banking API"). There's no
Anthropic embeddings endpoint and no other embeddings API key configured in
this project, so instead of a vector-similarity pass, topical relevance
judgment is delegated entirely to Claude over an unfiltered, weight-ranked
candidate pool -- SQL only ranks by strength * learned weight; Claude does
100% of the "is this actually relevant to the goal" reasoning.

Multi-tenant: every function takes company_id so contacts, weights, and
recommendations all stay scoped to the logged-in company.
"""
import argparse

from common import add_recommendation, call_claude, get_db, log_action
from weights import get_weights_map, tag_recommendation

AGENT_NAME = "network_intel_agent"
CANDIDATE_POOL_SIZE = 20

SYSTEM_PROMPT = """You help a developer community figure out who to ask for a warm \
introduction toward a stated goal. You will be given a goal and a list of candidate \
contacts (each already known to one of the community's members), ranked by relationship \
strength and a learned relevance weight -- but NOT pre-filtered for topical relevance, so \
judge that yourself: some candidates in the list may have nothing to do with the goal, and \
you should ignore those even if their relationship strength is high. Use your own judgment \
about company/role fit -- e.g. a "banking API" company is relevant to a "fintech" goal even \
though the words don't match. Pick the strongest 1-3 candidates and, for each, explain in \
2-3 sentences why they're a good fit and draft a short, casual intro-request message the \
member could send -- but make clear it is a DRAFT for human review, not something to send \
automatically. If truly nothing in the list fits the goal, say so plainly instead of \
forcing a pick."""


def find_candidates(conn, company_id: int, limit: int = CANDIDATE_POOL_SIZE):
    """Weight-ranked candidate pool: strength_score * learned company_type weight.
    No topical filtering here -- Claude judges relevance to the goal itself."""
    weights = get_weights_map(conn, company_id, "company_type")
    rows = conn.execute(
        """SELECT c.contact_name, c.contact_company, c.contact_title, c.company_type,
                  c.strength_score, m.name AS member_name
           FROM contacts c JOIN members m ON c.member_id = m.id
           WHERE c.company_id = %s""",
        (company_id,),
    ).fetchall()
    for r in rows:
        weight = weights.get(r["company_type"], 1.0)
        r["weighted_score"] = round((r["strength_score"] or 0) * weight, 2)
    rows.sort(key=lambda r: r["weighted_score"], reverse=True)
    return rows[:limit]


def run(company_id: int, goal_query: str) -> str:
    conn = get_db()
    candidates = find_candidates(conn, company_id)

    if not candidates:
        summary = f"No contacts on record yet to match against '{goal_query}'."
        log_action(conn, company_id, AGENT_NAME, "search_contacts", goal_query, summary, 0.0)
        conn.close()
        return summary

    candidate_text = "\n".join(
        f"- {r['contact_name']} ({r['contact_title']} at {r['contact_company']}, "
        f"type={r['company_type']}), known via {r['member_name']}, "
        f"relationship strength {r['strength_score']}/10 (weighted {r['weighted_score']})"
        for r in candidates
    )
    user_prompt = f"Goal: {goal_query}\n\nCandidates:\n{candidate_text}"

    text, cost = call_claude(SYSTEM_PROMPT, user_prompt)
    log_action(conn, company_id, AGENT_NAME, "draft_outreach", user_prompt[:200], text[:200], cost)
    rec_id = add_recommendation(conn, company_id, "outreach", text, f"goal={goal_query}")

    # Tag only the top slice of the pool (roughly matching how many Claude
    # tends to pick from) so like/dislike nudges the types that were actually
    # in contention, not every type that happened to appear anywhere in the
    # 20-candidate pool passed to the prompt.
    top_slice = candidates[:5]
    for company_type in {r["company_type"] for r in top_slice if r["company_type"]}:
        tag_recommendation(conn, rec_id, "company_type", company_type)

    conn.close()
    return f"[recommendation #{rec_id}, pending_approval]\n\n{text}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("company_id", type=int, help="the company/tenant to run this for")
    parser.add_argument("goal", help="e.g. 'sponsor credits' or 'expand to NYC'")
    args = parser.parse_args()
    print(run(args.company_id, args.goal))
