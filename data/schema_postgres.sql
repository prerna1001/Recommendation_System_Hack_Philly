-- Code & Coffee Connector schema (PostgreSQL)
-- Multi-tenant: one shared login per company (see `companies`/`sessions`),
-- every tenant-scoped table carries a direct company_id column rather than
-- requiring deep joins to scope a query.

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Looked up from the session_token httpOnly cookie on every request (see
-- backend/auth.py::get_current_company). Revocable by deleting the row --
-- chosen over a signed JWT to avoid needing a second way to invalidate one.
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- The company's team roster -- what the Team screen (formerly a single
-- "Profile" page) reads/writes. linkedin_url/photo_url are per member now,
-- since "profile" stopped meaning the one login-holder and started meaning
-- each of the company's members.
CREATE TABLE IF NOT EXISTS members (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    linkedin_url TEXT,
    photo_url TEXT
);

-- Union of every member's real-world contacts (Gmail/Calendar/self-reported).
CREATE TABLE IF NOT EXISTS contacts (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    member_id INTEGER REFERENCES members(id),
    contact_name TEXT,
    contact_email TEXT,
    contact_company TEXT,
    contact_title TEXT,
    company_type TEXT,           -- e.g. 'devtools_startup' | 'local_business' | 'agency' | 'infra' | 'enterprise' | 'vc_agency'
    strength_score REAL,
    last_interaction TEXT,
    source TEXT
);

-- registered_count/attended_count/weather_tag/turnout_reason/success_assessment
-- are organizer-entered manual fields (see PUT /events/{id}/retro), not derived.
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    name TEXT,
    date TEXT,
    format TEXT,
    venue TEXT,
    registered_count INTEGER,
    attended_count INTEGER,
    weather_tag TEXT,
    turnout_reason TEXT,
    success_assessment TEXT,
    photo_url TEXT
);

CREATE TABLE IF NOT EXISTS sponsor_history (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    event_id INTEGER REFERENCES events(id),
    sponsor_name TEXT,
    sponsor_type TEXT,
    contribution_type TEXT,
    contact_person TEXT,
    how_connected TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    event_id INTEGER REFERENCES events(id),
    respondent TEXT,
    rating_turnout INTEGER,
    had_relevant_connection INTEGER,
    connection_relevance_rating INTEGER,
    rating_format INTEGER,
    rating_logistics INTEGER,
    rating_sponsor_value INTEGER,
    free_text TEXT
);

CREATE TABLE IF NOT EXISTS rubric_scores (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    event_id INTEGER REFERENCES events(id),
    category TEXT,
    score REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    type TEXT,
    content TEXT,
    reasoning TEXT,
    status TEXT DEFAULT 'pending_approval',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_log (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    agent TEXT,
    action_type TEXT,
    input_summary TEXT,
    output_summary TEXT,
    cost_estimate REAL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- A chat thread. An organizer can start a new one or delete an old one;
-- each holds its own ordered chat_messages.
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- The chat thread: organizer messages and assistant replies, in order.
-- recommendation_id links an assistant reply back to the recommendations
-- row it produced (if any), so feedback can be tied to a concrete action.
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    session_id INTEGER REFERENCES chat_sessions(id) NOT NULL,
    role TEXT NOT NULL,                 -- 'organizer' | 'assistant'
    content TEXT NOT NULL,
    recommendation_id INTEGER REFERENCES recommendations(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Like/dislike + optional reason on an assistant chat message. The reason is
-- what feeds the feature_weights update (see agents/weights.py). Scoped
-- indirectly through chat_message_id -> chat_messages.company_id.
CREATE TABLE IF NOT EXISTS message_feedback (
    id SERIAL PRIMARY KEY,
    chat_message_id INTEGER REFERENCES chat_messages(id),
    liked BOOLEAN NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Which feature values a recommendation drew on (e.g. company_type=devtools_startup
-- for a contact that got surfaced). Lets feedback on a message push weight
-- updates back onto the specific features involved, not just the message as a
-- whole. Scoped indirectly through recommendation_id -> recommendations.company_id.
CREATE TABLE IF NOT EXISTS recommendation_features (
    id SERIAL PRIMARY KEY,
    recommendation_id INTEGER REFERENCES recommendations(id),
    feature_type TEXT NOT NULL,         -- 'company_type' | 'sponsor_type' | 'title'
    feature_value TEXT NOT NULL
);

-- The learned weight table. Starts neutral (1.0); nudged by like/dislike and
-- approve/reject via agents/weights.py::apply_feedback(). Unique per
-- (company, feature) so tenants learn independently of each other.
CREATE TABLE IF NOT EXISTS feature_weights (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id) NOT NULL,
    feature_type TEXT NOT NULL,
    feature_value TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (company_id, feature_type, feature_value)
);
