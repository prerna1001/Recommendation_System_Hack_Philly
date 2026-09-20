-- Code & Coffee Connector schema
-- SQLite. One file, no infra, fast to seed and demo.

CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT
);

-- Union of every member's real-world contacts (Gmail/Calendar/self-reported).
-- For the hackathon build this is populated with synthetic data; the OAuth
-- ingestion path is documented in README but not wired up for the demo.
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY,
    member_id INTEGER REFERENCES members(id),
    contact_name TEXT,
    contact_email TEXT,
    contact_company TEXT,
    contact_title TEXT,
    strength_score REAL,       -- recency/frequency-derived, 0-10
    last_interaction TEXT,
    source TEXT                 -- 'gmail' | 'calendar' | 'self_reported'
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    name TEXT,
    date TEXT,
    format TEXT,
    venue TEXT
);

-- First-party history: what each past sponsor actually gave and how the
-- relationship came about. This is the strongest fit-predictor we have.
CREATE TABLE IF NOT EXISTS sponsor_history (
    id INTEGER PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    sponsor_name TEXT,
    sponsor_type TEXT,          -- e.g. 'devtools_startup' | 'local_business' | 'agency' | 'infra'
    contribution_type TEXT,     -- 'cash' | 'credits' | 'food' | 'venue' | 'swag'
    contact_person TEXT,
    how_connected TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    respondent TEXT,
    rating_turnout INTEGER,
    -- Networking-specific questions (not a generic "engagement" rating) --
    -- see https://www.all-along.com/field-notes/measure-event-networking-success
    had_relevant_connection INTEGER,   -- 0/1: "did you connect with someone you'd genuinely like to speak to again?"
    connection_relevance_rating INTEGER, -- 1-5: "how relevant were the people you met to your professional goals?"
    rating_format INTEGER,
    rating_logistics INTEGER,
    rating_sponsor_value INTEGER,
    free_text TEXT
);

CREATE TABLE IF NOT EXISTS rubric_scores (
    id INTEGER PRIMARY KEY,
    event_id INTEGER REFERENCES events(id),
    category TEXT,
    score REAL,
    notes TEXT
);

-- Every action an agent proposes lands here with status='pending_approval'.
-- Nothing is ever executed (message sent, venue booked) from this table
-- directly -- a human flips the status first. This is the safeguard.
CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY,
    type TEXT,                  -- 'outreach' | 'format' | 'venue' | 'sponsor_match'
    content TEXT,
    reasoning TEXT,
    status TEXT DEFAULT 'pending_approval',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Structured log of every agent action: satisfies the observability
-- requirement (environment, actions, cost, results) independent of
-- whatever the XO platform captures at the session level.
CREATE TABLE IF NOT EXISTS action_log (
    id INTEGER PRIMARY KEY,
    agent TEXT,
    action_type TEXT,
    input_summary TEXT,
    output_summary TEXT,
    cost_estimate REAL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
