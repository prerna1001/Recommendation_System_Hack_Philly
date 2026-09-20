# NextEvent AI — Architecture

Multi-tenant, multi-agent pipeline for developer-community organizers.
Matches community members' warm connections to organizational goals, scores
past events against a research-grounded rubric, turns that into a next-event
plan, and learns from organizer feedback over time -- with every proposed
action requiring human approval before it's treated as real.

## Stack

| Layer | Choice | Role |
|---|---|---|
| Frontend | Next.js (App Router) | Login/signup, team roster (`/team`), event dashboard (`/dashboard`), chat (`/chat`) |
| Backend | Python (FastAPI) | Session auth, event/team/sponsor CRUD, hosts the 3 agents as routes, owns all DB/Claude access |
| Database | PostgreSQL | Single source of truth all agents/routes read/write through; every table carries `company_id` |
| LLM | Claude (Sonnet 5), Anthropic API | Reasoning/drafting/scoring calls inside each agent, the chat router, and field extraction |

Agents never call each other directly. They only read/write rows in
Postgres, through functions the FastAPI backend (or the CLI) calls directly
in-process.

## Multi-tenancy & auth

One shared login per company, not per individual member (`companies` table:
`id, name, email, password_hash`). A session token (`sessions` table) is
handed to the browser as an httpOnly cookie; `backend/auth.py::get_current_company`
resolves it on every request and every route depends on it via FastAPI's
`Depends()`. Every tenant-scoped table carries `company_id` directly
(denormalized, not requiring deep joins to scope a query), so two companies'
data is fully isolated -- verified by creating a second company and
confirming its `/events`/`/members` return empty while the first company's
data stays intact.

## Chat router

The organizer doesn't pick an agent by name -- they type free text in
`/chat` ("find a sponsor for pizza," "how'd last week's event go," "create an
event for next Friday"). One Claude call (`backend/main.py::classify_intent`)
classifies intent into one of three buckets and dispatches:

| Intent | Dispatches to |
|---|---|
| `network` | `agents/network_intel_agent.py` |
| `planning` | `agents/planning_agent.py` |
| `create_event` | `handle_create_event()` -- a plain extraction+insert, not a 4th agent (see below) |

After an agent returns, its output is a `recommendations` row with
`status='pending_approval'` -- a state change the organizer confirms in the
UI (👍/👎 in chat, or approve/reject on the dashboard), not an autonomous
action the system takes on its own. There's no live venue-booking API
integration; "book the venue" means the organizer does that in the real
world and marks it done here.

**Why `create_event` isn't a 4th agent:** the three agents each reason over
ranked candidates and produce something risky enough to need a human gate
(an outreach draft to a real person, a sponsor plan). Creating an event
record is just structured data entry into the org's own system -- low risk,
fully reversible (delete exists), no external party involved. It reuses the
same router pattern (one Claude call) for the genuinely language-shaped part
(extracting `{name, date, format, venue}` from free text, resolving relative
dates like "next Friday"), then writes directly instead of going through the
`pending_approval` gate. If a required field is missing, the reply asks for
just that field; `extract_event_fields()` re-reads recent chat history each
turn, so multi-turn slot-filling works without separate draft-state storage.

## The 3 agents

| # | Agent | Reads | Writes | Job |
|---|---|---|---|---|
| 1 | Network Intel | `contacts`, `feature_weights` | `recommendations` (`type=outreach`), `recommendation_features`, `action_log` | Given a goal, ranks contacts by strength × learned company-type weight; Claude judges topical relevance and drafts (never sends) an intro message |
| 2 | Retrospective | `feedback` | `rubric_scores`, `action_log` | Scores one past event against Rubric B, synthesizes "what worked / what didn't" from free-text comments |
| 3 | Planning | organizer's own retrospective notes (`events.turnout_reason`/`success_assessment`/`weather_tag`), `rubric_scores`, `sponsor_history`, `feature_weights`, approved `recommendations` | `recommendations` (`type=venue`), `recommendation_features`, `action_log` | Combines the organizer's first-hand read of the latest event (primary signal) + rubric scorecard (supporting evidence) + weighted sponsor patterns + already-*approved* outreach into a next-event plan |

## The learning loop ("Instagram-style" weighting)

`feature_weights` (unique per `company_id, feature_type, feature_value`,
starts at 1.0) is nudged by two signals that both mean "this worked / didn't":

- A 👍/👎 on a chat message (`POST /chat/{id}/feedback`), optionally with a
  reason
- An approve/reject on a recommendation (dashboard or
  `orchestrator/approve.py`)

Both call `agents/weights.py::apply_feedback()`, which nudges every feature
tagged on that recommendation (`weight *= 1.2` on like/approve, `*= 0.8` on
dislike/reject, floored at 0.1). `network_intel_agent.find_candidates()` and
`planning_agent.sponsor_patterns()` both read the weights back in on every
run and re-rank by `strength/count × weight` -- verified end-to-end: a
dislike measurably dropped affected company-types' weights, and a
follow-up ranking call showed them pushed down in the actual output.

Matching itself has no SQL `LIKE` filter and no embeddings pass (no
Anthropic embeddings endpoint, no other embeddings key configured) --
`network_intel_agent` hands Claude an unfiltered, weight-ranked candidate
pool and lets it judge topical relevance directly (e.g. "fintech" correctly
matching a company tagged "banking API").

## Data dictionary (PostgreSQL)

- **companies** — the tenant: shared login (`email`/`password_hash`) + display name
- **sessions** — session tokens issued on login, deleted on logout
- **members** — a company's team roster (name, email, linkedin_url, photo_url) -- what the `/team` page manages
- **contacts** — union of members' known contacts (`company_type` categorizes each for weighting; source: self-reported/synthetic today)
- **events** — past/future events; `registered_count`/`attended_count`/`weather_tag`/`turnout_reason`/`success_assessment`/`photo_url` are organizer-entered manual fields, not derived
- **sponsor_history** — what each past sponsor gave and how the relationship happened; addable/removable per event via the dashboard
- **feedback** — raw post-event attendee survey responses
- **rubric_scores** — Rubric B results per event, per category (Agent 2's output)
- **recommendations** — every agent-proposed action, `status = pending_approval` until a human reviews it
- **recommendation_features** — which `feature_type`/`feature_value`s a recommendation drew on, for weight updates
- **feature_weights** — the learned weight table, per company
- **chat_messages** — the organizer/assistant chat thread; `recommendation_id` links a reply back to the row it produced
- **message_feedback** — 👍/👎 + optional reason on a chat message
- **action_log** — every agent/router call: agent, action, inputs/outputs, estimated cost — the observability trail

## Request flow (numbered, matches the diagram)

1. Organizer logs in (one shared company login); the session cookie carries `company_id` on every subsequent request.
2. Organizer submits a goal, chat message, sponsor entry, or event feedback via the Next.js frontend.
3. Next.js calls the FastAPI backend with `credentials: "include"`.
4. `get_current_company` resolves the session; the route (or `classify_intent` for chat) dispatches to the relevant agent/handler, scoped by `company_id`.
5. Agent calls Claude for reasoning/drafting/scoring/extraction.
6. Agent writes its result back to Postgres (`rubric_scores` or `recommendations` + `recommendation_features`) and logs the action to `action_log`. (`create_event` writes directly to `events`, no gate.)
7. Frontend shows the result; a `recommendations` row appears with 👍/👎 in chat or in the approve/reject flow.
8. Organizer approves/rejects or likes/dislikes — both call `apply_feedback()`, updating `feature_weights` for next time.
9. Only `approved` outreach rows are ever read back in as input to Agent 3's next planning run — nothing is sent or booked automatically at any point in this flow.

## What's real vs. synthetic right now

`data/seed_synthetic.py` (Postgres) generates one demo company plus all
member/contact/sponsor/feedback data — there wasn't time to run real OAuth
consent flows with real members. Priority order to replace it with real
data: (1) sponsor history via the dashboard's add-sponsor form — highest
value, already built; (2) real people in `/team` instead of seeded members;
(3) Gmail/Calendar OAuth for `contacts`; (4) the public-sponsor-page
discovery agent for Rubric A's "new people" path (not built yet).
