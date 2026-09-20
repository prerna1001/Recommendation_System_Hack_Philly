# Code & Coffee Connector

A multi-tenant web app for developer-community organizers: matches members'
warm connections to the org's growth goals, scores past events against a
rubric, and turns that into a next-event plan (format, venue, sponsor fit) --
with every proposed action requiring human approval before it's treated as
real, and a chat interface that learns from what the organizer likes/dislikes
over time.

Built for the AI Agent Hackathon (Coffee & Code, Sept 20-22 2026).

## Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) -- login/signup, team roster, event dashboard, chat |
| Backend | Python (FastAPI) -- session auth, event/team CRUD, wraps the 3 agents |
| Database | PostgreSQL, one shared login per company (multi-tenant, `company_id` on every table) |
| LLM | Claude (Sonnet 5), Anthropic API |

## Access model

One shared login per company, not per individual member -- whoever has the
company's email/password can see and edit that company's team roster, event
history, and chat. Every table carries `company_id`; every backend route
resolves it from a session cookie (`backend/auth.py::get_current_company`)
and scopes its queries by it, so two companies' data never mixes.

## The three agents

1. **`agents/network_intel_agent.py`** -- given a goal ("sponsor credits",
   "expand to NYC"), ranks the company's contacts by relationship strength ×
   a learned per-company-type weight, and lets Claude pick and explain the
   strongest 1-3 matches -- drafting (never sending) an intro-request.
2. **`agents/retrospective_agent.py`** -- aggregates one past event's
   feedback into a rubric scorecard: numeric scores per category plus a
   synthesized "what worked / what didn't."
3. **`agents/planning_agent.py`** -- combines the organizer's own
   retrospective notes (their first-hand read of an event -- treated as the
   primary signal over the attendee survey), sponsor-contribution patterns,
   and any *already human-approved* outreach into a next-event plan.

Creating an event from the chat ("create an event for...") is **not** a
fourth agent -- it's the same lightweight intent router the chat already
uses (`backend/main.py::classify_intent`), extended with one more intent
plus a plain field-extraction call. It doesn't carry the risk the three
agents' recommendations do (no external contact, fully reversible), so it
skips the `pending_approval` gate and writes the event directly.

All three agents (plus the router and event-extraction calls) log to
`action_log` (agent, action, inputs/outputs, estimated cost) -- the raw
observability trail behind the demo.

## The learning loop

Every agent-proposed recommendation is tagged with the features it drew on
(`company_type` for contacts, `sponsor_type` for sponsors -- see
`agents/weights.py`). Two signals nudge those weights: a 👍/👎 on a chat
suggestion, or an approve/reject via the dashboard/CLI -- both call the same
`apply_feedback()`, so a CLI approval and a chat dislike feed one shared,
per-company learned-weight table. `network_intel_agent` and `planning_agent`
read those weights back in on every run, so repeated feedback measurably
re-ranks future suggestions instead of just gating them.

Matching note: contact/goal relevance is judged entirely by Claude reasoning
over an unfiltered, weight-ranked candidate pool, not a SQL `LIKE` or a
vector-embedding pass -- there's no Anthropic embeddings endpoint and no
other embeddings API key configured in this project.

## Safeguards & permission controls

Every agent output lands in the `recommendations` table with
`status='pending_approval'`. No agent in this project sends a real message,
books a venue, or contacts a real person directly -- that only happens after
a human reviews it via the dashboard or `orchestrator/approve.py` and flips
the status to `approved`. `planning_agent` only reads *approved* outreach
recommendations as input, so an unreviewed draft can never propagate into
the next stage.

## Setup

```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

brew install postgresql@14   # or any local Postgres
createdb coffee_connector
python data/seed_synthetic.py   # creates schema, seeds one demo company + data,
                                 # prints its login email/password

# Frontend
cd frontend
cp .env.local.example .env.local
npm install
```

## Running it

**Web app** (the primary way to use this):
```bash
# Terminal 1 -- backend
cd backend && uvicorn main:app --port 8010

# Terminal 2 -- frontend
cd frontend && npm run dev
```
Open `http://localhost:3000`, log in with the credentials the seed script
printed.

**CLI** (predates the web app, still works -- useful for scripting/demos):
```bash
python orchestrator/run_pipeline.py --company-id 1 --goal "sponsor credits"
python orchestrator/run_pipeline.py --company-id 1 --event 1

python orchestrator/approve.py --company-id 1 list
python orchestrator/approve.py --company-id 1 show 1
python orchestrator/approve.py --company-id 1 approve 1
```
Look up a company's id with `psql coffee_connector -c "SELECT id, name FROM companies"`.

## Data: what's real vs. synthetic right now

`data/seed_synthetic.py` generates all member/contact/sponsor-history/
feedback data for this build -- there was no time during the hackathon
window to run real OAuth consent flows with a community's real members.
Priority order to replace it with real data:

1. **Sponsor history** -- manual entry from the organizers' own memory into
   `sponsor_history` (via the dashboard's "Add sponsor" form); highest-value,
   lowest-effort real data available.
2. **Team roster** -- already a real form (`/team`); just needs real people
   entered per company instead of relying on the seed script.
3. **Member contact graph** -- Gmail + Calendar OAuth (Google Cloud Console,
   "Testing" mode supports up to 100 users, no verification review needed) to
   populate `contacts` from real interaction metadata.
4. **New-sponsor discovery** -- an agent that reads public sponsor pages of
   other local hackathons/meetups (Devpost, Eventbrite, Meetup) -- fully
   public data, no auth needed. Not built yet.

## Running on Quirq / XO

Quirq: Build It requires the submission to run on Quirq, via the managed
cloud at app.xo.builders or a local install (`curl -fsSL https://quirq.ai/install | sh`,
pointed at this repo via `XO_PROJECTS_ROOT`). This repo's `action_log` table
already captures per-agent actions/costs/results at the application level
independent of whatever XO's own session view captures.

## GalaxyGate

Not required for the Quirq track -- GalaxyGate is plain VPS hosting (not an
observability platform like Quirq). If time allows, deploy the FastAPI
backend + Postgres (+ optionally the Next.js frontend) on a GalaxyGate VPS so
the dashboard is a real public link instead of `localhost`.

## Judging-criteria alignment (Quirq: Build It)

- **Agentic design (30%)** -- three agents with distinct responsibilities and
  structured handoffs through Postgres, not one big prompt; a shared,
  per-company learned-weight table that measurably shifts future
  recommendations based on organizer feedback (approve/reject and chat
  like/dislike feed the same signal).
- **Observability (25%)** -- `action_log` table + XO session view.
- **Impact (25%)** -- built for the actual community hosting this event,
  from a real conversation with Code & Coffee's CTO about their real process
  and pain points; multi-tenant from the start so other communities can use
  it too.
- **Reliability & safety (20%)** -- `pending_approval` gate on every
  agent-proposed action, per-company data isolation, session-based auth; see
  "Safeguards" above.
