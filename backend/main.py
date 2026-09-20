"""FastAPI backend: auth, team, event dashboard, chat, and suggestions routes.

Wraps the existing agent functions (agents/network_intel_agent.py,
retrospective_agent.py, planning_agent.py) rather than reimplementing their
logic -- this is the same code the CLI pipeline uses, just reached over HTTP.

Multi-tenant: one shared login per company (see auth.py). Every route below
depends on get_current_company and scopes its queries by company_id.
"""
import json
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

import network_intel_agent  # noqa: E402
import planning_agent  # noqa: E402
from common import call_claude  # noqa: E402
from db import get_db  # noqa: E402
from weights import apply_feedback, get_weights_map  # noqa: E402

from auth import (  # noqa: E402
    SESSION_COOKIE,
    create_session,
    get_current_company,
    hash_password,
    set_session_cookie,
    verify_password,
)

app = FastAPI(title="NextEvent AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Auth ---

class SignupIn(BaseModel):
    company_name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


@app.post("/auth/signup")
def signup(body: SignupIn, response: Response):
    conn = get_db()
    existing = conn.execute("SELECT id FROM companies WHERE email = %s", (body.email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(409, "A company with that email already exists")
    cur = conn.execute(
        "INSERT INTO companies (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id, name, email",
        (body.company_name, body.email, hash_password(body.password)),
    )
    company = cur.fetchone()
    conn.commit()
    token = create_session(conn, company["id"])
    conn.close()
    set_session_cookie(response, token)
    return company


@app.post("/auth/login")
def login(body: LoginIn, response: Response):
    conn = get_db()
    company = conn.execute(
        "SELECT id, name, email, password_hash FROM companies WHERE email = %s", (body.email,)
    ).fetchone()
    if not company or not verify_password(body.password, company["password_hash"]):
        conn.close()
        raise HTTPException(401, "Invalid email or password")
    token = create_session(conn, company["id"])
    conn.close()
    set_session_cookie(response, token)
    return {"id": company["id"], "name": company["name"], "email": company["email"]}


@app.post("/auth/logout")
def logout(response: Response, company_id: int = Depends(get_current_company)):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/auth/me")
def me(company_id: int = Depends(get_current_company)):
    conn = get_db()
    company = conn.execute("SELECT id, name, email FROM companies WHERE id = %s", (company_id,)).fetchone()
    conn.close()
    return company


# --- Team (the company's members -- replaces the old single-organizer profile) ---

class MemberIn(BaseModel):
    name: str
    email: str = ""
    linkedin_url: str = ""
    photo_url: str = ""


@app.get("/members")
def list_members(company_id: int = Depends(get_current_company)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM members WHERE company_id = %s ORDER BY id", (company_id,)
    ).fetchall()
    conn.close()
    return rows


@app.post("/members")
def add_member(member: MemberIn, company_id: int = Depends(get_current_company)):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO members (company_id, name, email, linkedin_url, photo_url)
           VALUES (%s, %s, %s, %s, %s) RETURNING *""",
        (company_id, member.name, member.email, member.linkedin_url, member.photo_url),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return row


@app.put("/members/{member_id}")
def update_member(member_id: int, member: MemberIn, company_id: int = Depends(get_current_company)):
    conn = get_db()
    row = conn.execute(
        """UPDATE members SET name = %s, email = %s, linkedin_url = %s, photo_url = %s
           WHERE id = %s AND company_id = %s RETURNING *""",
        (member.name, member.email, member.linkedin_url, member.photo_url, member_id, company_id),
    ).fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise HTTPException(404, f"No member with id {member_id}")
    return row


@app.delete("/members/{member_id}")
def delete_member(member_id: int, company_id: int = Depends(get_current_company)):
    conn = get_db()
    row = conn.execute(
        "DELETE FROM members WHERE id = %s AND company_id = %s RETURNING id", (member_id, company_id)
    ).fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise HTTPException(404, f"No member with id {member_id}")
    return {"ok": True}


# --- Event dashboard ---

def random_event_photo() -> str:
    """A random placeholder photo, stable once assigned (stored on the row)."""
    return f"https://picsum.photos/seed/{uuid.uuid4().hex[:10]}/800/450"


class EventIn(BaseModel):
    name: str
    date: str
    format: str
    venue: str


@app.post("/events")
def create_event(event: EventIn, company_id: int = Depends(get_current_company)):
    conn = get_db()
    cur = conn.execute(
        """INSERT INTO events (company_id, name, date, format, venue, photo_url)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
        (company_id, event.name, event.date, event.format, event.venue, random_event_photo()),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return row


@app.get("/events")
def list_events(company_id: int = Depends(get_current_company)):
    conn = get_db()
    events = conn.execute(
        "SELECT * FROM events WHERE company_id = %s ORDER BY date DESC", (company_id,)
    ).fetchall()
    result = []
    for e in events:
        sponsor_count = conn.execute(
            "SELECT COUNT(*) AS n FROM sponsor_history WHERE event_id = %s AND company_id = %s",
            (e["id"], company_id),
        ).fetchone()["n"]
        connection_rate = conn.execute(
            """SELECT score FROM rubric_scores
               WHERE event_id = %s AND company_id = %s AND category = 'relevant_connection_rate'""",
            (e["id"], company_id),
        ).fetchone()
        result.append({
            **e,
            "sponsor_count": sponsor_count,
            "relevant_connection_rate": connection_rate["score"] if connection_rate else None,
        })
    conn.close()
    return result


@app.get("/events/{event_id}")
def get_event(event_id: int, company_id: int = Depends(get_current_company)):
    conn = get_db()
    event = conn.execute(
        "SELECT * FROM events WHERE id = %s AND company_id = %s", (event_id, company_id)
    ).fetchone()
    if not event:
        conn.close()
        raise HTTPException(404, f"No event with id {event_id}")
    sponsors = conn.execute(
        "SELECT * FROM sponsor_history WHERE event_id = %s AND company_id = %s", (event_id, company_id)
    ).fetchall()
    feedback = conn.execute(
        "SELECT * FROM feedback WHERE event_id = %s AND company_id = %s", (event_id, company_id)
    ).fetchall()
    rubric = conn.execute(
        "SELECT * FROM rubric_scores WHERE event_id = %s AND company_id = %s", (event_id, company_id)
    ).fetchall()
    conn.close()
    return {"event": event, "sponsors": sponsors, "feedback": feedback, "rubric_scores": rubric}


class SponsorIn(BaseModel):
    sponsor_name: str
    sponsor_type: str
    contribution_type: str
    contact_person: str = ""
    how_connected: str = ""


@app.delete("/events/{event_id}")
def delete_event(event_id: int, company_id: int = Depends(get_current_company)):
    conn = get_db()
    event = conn.execute(
        "SELECT id FROM events WHERE id = %s AND company_id = %s", (event_id, company_id)
    ).fetchone()
    if not event:
        conn.close()
        raise HTTPException(404, f"No event with id {event_id}")
    # sponsor_history/feedback/rubric_scores reference event_id without ON DELETE
    # CASCADE, so clear those explicitly before removing the event itself.
    conn.execute("DELETE FROM sponsor_history WHERE event_id = %s AND company_id = %s", (event_id, company_id))
    conn.execute("DELETE FROM feedback WHERE event_id = %s AND company_id = %s", (event_id, company_id))
    conn.execute("DELETE FROM rubric_scores WHERE event_id = %s AND company_id = %s", (event_id, company_id))
    conn.execute("DELETE FROM events WHERE id = %s AND company_id = %s", (event_id, company_id))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/events/{event_id}/sponsors")
def add_sponsor(event_id: int, sponsor: SponsorIn, company_id: int = Depends(get_current_company)):
    conn = get_db()
    event = conn.execute(
        "SELECT id FROM events WHERE id = %s AND company_id = %s", (event_id, company_id)
    ).fetchone()
    if not event:
        conn.close()
        raise HTTPException(404, f"No event with id {event_id}")
    cur = conn.execute(
        """INSERT INTO sponsor_history
           (company_id, event_id, sponsor_name, sponsor_type, contribution_type, contact_person, how_connected)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
        (
            company_id, event_id, sponsor.sponsor_name, sponsor.sponsor_type,
            sponsor.contribution_type, sponsor.contact_person, sponsor.how_connected,
        ),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return row


@app.delete("/sponsors/{sponsor_id}")
def delete_sponsor(sponsor_id: int, company_id: int = Depends(get_current_company)):
    conn = get_db()
    row = conn.execute(
        "DELETE FROM sponsor_history WHERE id = %s AND company_id = %s RETURNING id",
        (sponsor_id, company_id),
    ).fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise HTTPException(404, f"No sponsor with id {sponsor_id}")
    return {"ok": True}


class RetroIn(BaseModel):
    registered_count: Optional[int] = None
    attended_count: Optional[int] = None
    weather_tag: Optional[str] = None
    turnout_reason: Optional[str] = None
    success_assessment: Optional[str] = None
    photo_url: Optional[str] = None


@app.put("/events/{event_id}/retro")
def update_retro(event_id: int, retro: RetroIn, company_id: int = Depends(get_current_company)):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM events WHERE id = %s AND company_id = %s", (event_id, company_id)
    ).fetchone()
    if not existing:
        conn.close()
        raise HTTPException(404, f"No event with id {event_id}")
    conn.execute(
        """UPDATE events SET registered_count = COALESCE(%s, registered_count),
               attended_count = COALESCE(%s, attended_count),
               weather_tag = COALESCE(%s, weather_tag),
               turnout_reason = COALESCE(%s, turnout_reason),
               success_assessment = COALESCE(%s, success_assessment),
               photo_url = COALESCE(%s, photo_url)
           WHERE id = %s AND company_id = %s""",
        (
            retro.registered_count, retro.attended_count, retro.weather_tag,
            retro.turnout_reason, retro.success_assessment, retro.photo_url, event_id, company_id,
        ),
    )
    conn.commit()
    updated = conn.execute(
        "SELECT * FROM events WHERE id = %s AND company_id = %s", (event_id, company_id)
    ).fetchone()
    conn.close()
    return updated


# --- Chat: describe a next-event idea, get contact/plan recommendations ---

ROUTER_SYSTEM_PROMPT = """Classify an event organizer's chat message about planning a \
community event. Return ONLY compact JSON, no prose: \
{"intent": "network" | "planning" | "create_event" | "suggestions", "goal": "<short goal \
phrase, e.g. 'sponsor for pizza' or 'engineering manager intro'>"}. Use "network" when \
they're asking who to reach out to, what sponsor to approach, or who could introduce them to \
someone for a specific goal. Use "planning" when they're asking for a broader plan for the \
next event overall (format, venue, which sponsor types to prioritize). Use "create_event" \
when they explicitly want to create/schedule/add a new event to the calendar (e.g. "create \
an event for...", "let's schedule our next meetup on...", "add an event called...") -- this \
is about actually adding a new event record, not planning advice about one. Use \
"suggestions" when they're asking generally what to try next, for advice, or what they \
should do now, without naming a specific goal, person, or event to plan (e.g. "what should \
I try next?", "any suggestions?", "what should we do now?")."""

CHAT_INTENTS = ("network", "planning", "create_event", "suggestions")


def classify_intent(message: str, conn) -> tuple[str, str]:
    text, _cost = call_claude(ROUTER_SYSTEM_PROMPT, message, max_tokens=200)
    try:
        parsed = json.loads(text.strip())
        intent = parsed.get("intent", "network")
        goal = parsed.get("goal", message)
    except (json.JSONDecodeError, AttributeError):
        intent, goal = "network", message
    return intent if intent in CHAT_INTENTS else "network", goal


EVENT_EXTRACTION_SYSTEM_PROMPT = """You extract structured event-creation details from an \
organizer's chat conversation for a community-events platform. Given today's date and the \
recent conversation, extract: name (a short event title), date (ISO YYYY-MM-DD -- resolve \
relative dates like "next Friday" using today's date), format (e.g. "open co-working", \
"pitch competition", "hackathon", "talk + co-working"), venue (a place name). Return ONLY \
compact JSON: {"name": "..." or null, "date": "YYYY-MM-DD" or null, "format": "..." or null, \
"venue": "..." or null}. Use null for anything not stated or not confidently inferable from \
the conversation -- never guess a venue or date that wasn't actually mentioned."""

REQUIRED_EVENT_FIELDS = ["name", "date", "format", "venue"]


def extract_event_fields(conn, company_id: int, session_id: int) -> dict:
    """Re-reads recent chat history from this session (not just the latest
    message) so a multi-turn slot-filling exchange ("what's the venue?" ->
    "Pennovation Works") accumulates correctly without needing separate
    draft-state storage. Scoped to the session so a fresh "new chat" doesn't
    inherit half-filled fields from an unrelated older conversation."""
    recent = conn.execute(
        "SELECT role, content FROM chat_messages WHERE company_id = %s AND session_id = %s ORDER BY id DESC LIMIT 10",
        (company_id, session_id),
    ).fetchall()
    history_text = "\n".join(f"[{m['role']}] {m['content'][:300]}" for m in reversed(recent))
    user_prompt = f"Today's date: {date.today().isoformat()}\n\nConversation:\n{history_text}"
    text, _cost = call_claude(EVENT_EXTRACTION_SYSTEM_PROMPT, user_prompt, max_tokens=300)
    try:
        parsed = json.loads(text.strip())
    except (json.JSONDecodeError, AttributeError):
        parsed = {}
    return {k: parsed.get(k) for k in REQUIRED_EVENT_FIELDS}


def handle_create_event(conn, company_id: int, session_id: int) -> str:
    fields = extract_event_fields(conn, company_id, session_id)
    missing = [k for k in REQUIRED_EVENT_FIELDS if not fields.get(k)]
    if missing:
        known = ", ".join(f"{k}={v}" for k, v in fields.items() if v) or "nothing yet"
        return (
            f"Got it so far -- {known}. Still need: {', '.join(missing)}. "
            f"What should I put for {'those' if len(missing) > 1 else missing[0]}?"
        )
    cur = conn.execute(
        """INSERT INTO events (company_id, name, date, format, venue, photo_url)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (company_id, fields["name"], fields["date"], fields["format"], fields["venue"], random_event_photo()),
    )
    conn.commit()
    new_id = cur.fetchone()["id"]
    return (
        f"Created event #{new_id}: {fields['name']} ({fields['format']} at "
        f"{fields['venue']}, {fields['date']}). Add sponsors and fill in the retrospective "
        f"from its dashboard page once it's happened."
    )


class ChatIn(BaseModel):
    message: str
    session_id: int


@app.get("/chat/sessions")
def list_chat_sessions(company_id: int = Depends(get_current_company)):
    conn = get_db()
    rows = conn.execute(
        """SELECT s.id, s.title, s.created_at,
                  (SELECT content FROM chat_messages WHERE session_id = s.id ORDER BY id LIMIT 1) AS preview
           FROM chat_sessions s WHERE s.company_id = %s ORDER BY s.id DESC""",
        (company_id,),
    ).fetchall()
    conn.close()
    return rows


@app.post("/chat/sessions")
def create_chat_session(company_id: int = Depends(get_current_company)):
    conn = get_db()
    row = conn.execute(
        "INSERT INTO chat_sessions (company_id, title) VALUES (%s, 'New chat') RETURNING *",
        (company_id,),
    ).fetchone()
    conn.commit()
    conn.close()
    return row


@app.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: int, company_id: int = Depends(get_current_company)):
    conn = get_db()
    conn.execute(
        """DELETE FROM message_feedback WHERE chat_message_id IN
           (SELECT id FROM chat_messages WHERE session_id = %s AND company_id = %s)""",
        (session_id, company_id),
    )
    conn.execute(
        "DELETE FROM chat_messages WHERE session_id = %s AND company_id = %s", (session_id, company_id)
    )
    row = conn.execute(
        "DELETE FROM chat_sessions WHERE id = %s AND company_id = %s RETURNING id", (session_id, company_id)
    ).fetchone()
    conn.commit()
    conn.close()
    if not row:
        raise HTTPException(404, f"No chat session with id {session_id}")
    return {"ok": True}


@app.get("/chat")
def get_chat_history(session_id: int, company_id: int = Depends(get_current_company)):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM chat_messages WHERE company_id = %s AND session_id = %s ORDER BY id",
        (company_id, session_id),
    ).fetchall()
    conn.close()
    return rows


@app.post("/chat")
def post_chat(chat: ChatIn, company_id: int = Depends(get_current_company)):
    conn = get_db()
    session_id = chat.session_id
    conn.execute(
        "INSERT INTO chat_messages (company_id, session_id, role, content) VALUES (%s, %s, 'organizer', %s)",
        (company_id, session_id, chat.message),
    )
    conn.commit()

    intent, goal = classify_intent(chat.message, conn)
    rec_id = None

    if intent == "create_event":
        reply_text = handle_create_event(conn, company_id, session_id)
    elif intent == "suggestions":
        reply_text = suggestions_text(conn, company_id)
    elif intent == "planning":
        latest = conn.execute(
            "SELECT id FROM events WHERE company_id = %s ORDER BY date DESC LIMIT 1", (company_id,)
        ).fetchone()
        if not latest:
            reply_text = "No events on record yet to plan from -- log a past event first."
        else:
            reply_text, rec_id = planning_agent.run(company_id, latest["id"])
    else:
        reply_text, rec_id = network_intel_agent.run(company_id, goal)
    cur = conn.execute(
        """INSERT INTO chat_messages (company_id, session_id, role, content, recommendation_id)
           VALUES (%s, %s, 'assistant', %s, %s) RETURNING id""",
        (company_id, session_id, reply_text, rec_id),
    )
    conn.commit()
    msg_id = cur.fetchone()["id"]
    conn.close()
    return {"id": msg_id, "role": "assistant", "content": reply_text, "recommendation_id": rec_id}


class FeedbackIn(BaseModel):
    liked: bool
    reason: Optional[str] = None


@app.post("/chat/{message_id}/feedback")
def post_chat_feedback(message_id: int, feedback: FeedbackIn, company_id: int = Depends(get_current_company)):
    conn = get_db()
    msg = conn.execute(
        "SELECT id, recommendation_id FROM chat_messages WHERE id = %s AND company_id = %s AND role = 'assistant'",
        (message_id, company_id),
    ).fetchone()
    if not msg:
        conn.close()
        raise HTTPException(404, f"No assistant message with id {message_id}")

    conn.execute(
        "INSERT INTO message_feedback (chat_message_id, liked, reason) VALUES (%s, %s, %s)",
        (message_id, feedback.liked, feedback.reason),
    )
    conn.commit()

    touched = []
    if msg["recommendation_id"]:
        touched = apply_feedback(conn, company_id, msg["recommendation_id"], feedback.liked)

    conn.close()
    return {"message_id": message_id, "liked": feedback.liked, "weights_updated": touched}


# --- Suggestions: synthesized from past chat history + learned weights ---

SUGGESTIONS_SYSTEM_PROMPT = """You advise an organizer of a developer community. You'll get \
a log of their recent chat messages (ideas they've floated, what they liked/disliked and why) \
and the community's current learned preference weights per company/sponsor type (higher = \
features they've responded well to before, lower = features they've pushed back on). Write \
3-5 short, concrete "things to try next" suggestions -- new angles on outreach, event \
formats, or sponsor types worth experimenting with -- grounded in what the history actually \
shows, not generic advice. If there's too little history to say anything specific, say that \
plainly instead of inventing detail."""


def suggestions_text(conn, company_id: int) -> str:
    """Synthesizes 'what to try next' from chat history + learned weights.
    Shared by the /suggestions intent (in-chat) and the standalone endpoint."""
    messages = conn.execute(
        "SELECT role, content, created_at FROM chat_messages WHERE company_id = %s ORDER BY id DESC LIMIT 20",
        (company_id,),
    ).fetchall()
    if not messages:
        return "No chat history yet -- describe a next-event idea to get started."

    feedback_rows = conn.execute(
        """SELECT mf.liked, mf.reason, cm.content AS message_content
           FROM message_feedback mf JOIN chat_messages cm ON mf.chat_message_id = cm.id
           WHERE cm.company_id = %s
           ORDER BY mf.id DESC LIMIT 20""",
        (company_id,),
    ).fetchall()
    company_weights = get_weights_map(conn, company_id, "company_type")
    sponsor_weights = get_weights_map(conn, company_id, "sponsor_type")

    history_text = "\n".join(f"[{m['role']}] {m['content'][:300]}" for m in reversed(messages))
    feedback_text = "\n".join(
        f"- {'liked' if f['liked'] else 'disliked'}: {(f['message_content'] or '')[:150]}"
        + (f" (reason: {f['reason']})" if f["reason"] else "")
        for f in feedback_rows
    ) or "(no feedback given yet)"
    weights_text = (
        f"company_type weights: {company_weights}\nsponsor_type weights: {sponsor_weights}"
    )

    user_prompt = f"Recent chat:\n{history_text}\n\nFeedback given:\n{feedback_text}\n\n{weights_text}"
    text, _cost = call_claude(SUGGESTIONS_SYSTEM_PROMPT, user_prompt, max_tokens=500)
    return text


@app.get("/suggestions")
def get_suggestions(company_id: int = Depends(get_current_company)):
    conn = get_db()
    text = suggestions_text(conn, company_id)
    conn.close()
    return {"suggestions": text}
