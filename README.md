# NextEvent AI

A multi-tenant web app for developer-community organizers: matches members'
warm connections to the org's growth goals, scores past events against a
rubric, and turns that into a next-event plan (format, venue, sponsor fit) --
with every proposed action requiring human approval before it's treated as
real, and a chat interface that learns from what the organizer likes/dislikes
over time, the way a recommendation feed learns from what you skip.

Built for the AI Agent Hackathon (Coffee & Code, Sept 20-22 2026).

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full agent/data-flow diagram
and data dictionary, or the [tiered pipeline poster](https://claude.ai/artifact/14c8JYqvW6ETcAs5ep8kq1)
for a one-glance visual summary.

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
   strongest 1-2 matches -- drafting (never sending) an intro-request, in
   plain chat-style text.
2. **`agents/retrospective_agent.py`** -- aggregates one past event's
   feedback into a rubric scorecard: numeric scores per category plus a
   synthesized "what worked / what didn't."
3. **`agents/planning_agent.py`** -- combines the organizer's own
   retrospective notes (their first-hand read of an event -- treated as the
   primary signal over the attendee survey), sponsor-contribution patterns,
   and any *already human-approved* outreach into a next-event plan.

Two more things the chat can do aren't a 4th/5th agent, since neither carries
the risk a real recommendation does -- both skip the `pending_approval` gate:

- **Creating an event** ("create an event for...") -- the same lightweight
  intent router (`backend/main.py::classify_intent`), extended with a plain
  field-extraction call, writing the event directly.
- **"What should I try next?"** -- reads chat history, past feedback, and
  the learned weights back in and synthesizes suggestions in one Claude
  call, folded into the chat thread rather than a separate panel.

All agents (plus the router and event-extraction calls) log to `action_log`
(agent, action, inputs/outputs, estimated cost) -- the raw observability
trail behind the demo.

## Chat sessions

The chat is organized into sessions, not one endless thread -- "+ New chat"
starts a fresh one, older ones stay in the sidebar with a preview, and any
one can be deleted. A "new chat" also means slot-filling for event creation
(e.g. "what's the venue?") only looks at that session's own history, so it
never mixes up two unrelated conversations.

## The learning loop

Every agent-proposed recommendation is tagged with the features it drew on
(`company_type` for contacts, `sponsor_type` for sponsors -- see
`agents/weights.py`). Two signals nudge those weights: a 👍/👎 on a chat
suggestion, or an approve/reject via the dashboard/CLI -- both call the same
`apply_feedback()`, so a CLI approval and a chat dislike feed one shared,
per-company learned-weight table (`weight *= 1.2` on like/approve, `*= 0.8`
on dislike/reject, floored at `0.1`). `network_intel_agent` and
`planning_agent` read those weights back in on every run, so repeated
feedback measurably re-ranks future suggestions instead of just gating them.

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

# Put your key in a .env file at the project root (loaded automatically via
# python-dotenv -- no manual `export` needed in every new shell):
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

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
window to run real OAuth consent flows with a community's real members. See
"Future features" below for the priority order to replace it with real data.

## Sponsors used

See [docs/sponsors.docx](./docs/sponsors.docx) for details and screenshots.

- **Anthropic Claude** (Sonnet 5) -- every agent, the chat router, and the
  suggestions feature run on it: reasoning, ranking, drafting, and scoring.
- **Quirq / XO Space** -- observability. XO Space independently tracks the
  actual agent development sessions that built this project, separate from
  the app's own `action_log` table. Local install
  (`curl -fsSL https://quirq.ai/install | sh`), pointed at this repo via
  `XO_PROJECTS_ROOT` (kept outside the repo itself, with this repo adopted
  into it via a symlink -- see `ARCHITECTURE.md` if setting this up fresh).
- **The Code Registry** -- post-hackathon static analysis of this public
  repo; no extra integration needed beyond the repo staying public.
- **GalaxyGate** -- not used for this submission (see below); plain VPS
  hosting, not an observability platform like Quirq.

## GalaxyGate

Not required for the Quirq track -- GalaxyGate is plain VPS hosting. This
submission runs locally; deploying the FastAPI backend + Postgres (+
optionally the Next.js frontend) to a GalaxyGate VPS so the dashboard is a
real public link is the top item in "Future features" below.

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

## Future features

Roughly in priority order -- highest-value/lowest-effort first:

1. **Public hosting on GalaxyGate** -- so the dashboard is a real link
   instead of `localhost`, for anyone to try without a local setup.
2. **Real sponsor history** -- organizers already have a real form for this
   (`/dashboard`'s "Add sponsor"); just needs real data entered per company
   instead of relying on the seed script.
3. **Real team rosters** -- `/team` is already a real CRUD form; same as
   above, needs real people instead of seeded ones.
4. **Gmail + Calendar OAuth** for `contacts` -- populate the contact graph
   from real interaction metadata instead of synthetic data (Google Cloud
   Console "Testing" mode supports up to 100 users, no verification review
   needed to start).
5. **New-sponsor discovery agent** -- reads public sponsor pages of other
   local hackathons/meetups (Devpost, Eventbrite, Meetup) to surface
   sponsors the organizer doesn't already have a relationship with -- fully
   public data, no auth needed. Not built yet.
6. **Optional real outreach send** -- today every draft is copy-paste only;
   an explicit, opt-in "send via Gmail" button on an *already-approved*
   recommendation, still never automatic.
7. **Vector-embedding matching** -- once an embeddings API key is
   available, add a similarity pass ahead of Claude's judgment call for
   larger contact pools where an unfiltered candidate list stops being
   practical to hand the model directly.
8. **Cross-event trend view** -- a dashboard chart of rubric scores and
   turnout over time per company, not just per-event detail pages.
9. **Per-member roles** -- today it's one shared company login; a lightweight
   role layer (e.g. read-only vs. can-approve) for larger teams that want to
   restrict who can approve outreach.
10. **Retrospective reminders** -- a nudge (email or in-app) when an event's
    date has passed but its retrospective fields are still empty, since
    Agent 3's plan quality depends entirely on that being filled in.
