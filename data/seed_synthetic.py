"""Seed the coffee_connector Postgres database with synthetic-but-realistic data.

Real member/contact/sponsor data requires OAuth consent flows and a
Code & Coffee sponsorship-history spreadsheet that don't exist yet (see
README "Getting real data" section). This script generates plausible
stand-in data so the three agents have something real to reason over
for the hackathon demo.

Multi-tenant: creates one `companies` row (the shared login for this demo
tenant) and scopes every other row under it via company_id.
"""
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

import bcrypt
import psycopg

random.seed(7)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql:///coffee_connector")
SCHEMA_PATH = Path(__file__).parent / "schema_postgres.sql"

DEMO_COMPANY_NAME = "Code & Coffee Philadelphia"
DEMO_COMPANY_EMAIL = "team@codeandcoffeephilly.org"
DEMO_COMPANY_PASSWORD = "coffee2026"  # demo/dev credential only, printed at seed time

MEMBER_NAMES = [
    "Alice Chen", "Bob Okafor", "Carla Reyes", "Dev Patel", "Erin Walsh",
    "Farid Haidari", "Grace Kim", "Hassan Ali", "Ivy Nguyen", "Jamal Brooks",
    "Kira Novak", "Liam O'Connor", "Maya Singh", "Noah Fitzgerald", "Omar Saleh",
    "Priya Rao", "Quinn Sullivan", "Rosa Delgado", "Sam Levine", "Tara Byrne",
    "Umar Sheikh", "Vivian Wu", "Will Anderson",
]

COMPANIES = [
    ("Acme Devtools", "devtools_startup"), ("Northbank Capital", "vc_agency"),
    ("Tony's Pizza Philly", "local_business"), ("GridWorks API", "devtools_startup"),
    ("Comcast NBCUniversal", "enterprise"), ("Vanguard", "enterprise"),
    ("Two Fifty Studio", "agency"), ("Philly Print Co", "local_business"),
    ("Quirq", "infra"), ("Naftiko", "infra"), ("Independence Blue Cross", "enterprise"),
    ("Fishtown Analytics", "devtools_startup"), ("City Hall Coffee", "local_business"),
    ("Drexel Ventures", "vc_agency"), ("SEPTA Labs", "enterprise"),
]

TITLES = ["Engineering Manager", "Founder", "Owner", "Developer Relations Lead",
          "VP Partnerships", "Software Engineer", "Head of Marketing", "CTO"]

CONTRIBUTION_BY_COMPANY_TYPE = {
    "devtools_startup": "credits",
    "vc_agency": "cash",
    "local_business": "food",
    "enterprise": "cash",
    "agency": "cash",
    "infra": "credits",
}


def reset_schema(conn: psycopg.Connection) -> None:
    tables = [
        "message_feedback", "recommendation_features", "chat_messages",
        "feature_weights", "action_log", "recommendations",
        "rubric_scores", "feedback", "sponsor_history", "events",
        "contacts", "members", "sessions", "companies",
    ]
    conn.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE")


def seed_company(conn: psycopg.Connection) -> int:
    password_hash = bcrypt.hashpw(DEMO_COMPANY_PASSWORD.encode(), bcrypt.gensalt()).decode()
    cur = conn.execute(
        "INSERT INTO companies (name, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
        (DEMO_COMPANY_NAME, DEMO_COMPANY_EMAIL, password_hash),
    )
    return cur.fetchone()["id"]


def seed_members(conn: psycopg.Connection, company_id: int) -> list[int]:
    ids = []
    for name in MEMBER_NAMES:
        slug = name.lower().replace(" ", "-").replace("'", "")
        email = name.lower().replace(" ", ".").replace("'", "") + "@example.com"
        cur = conn.execute(
            """INSERT INTO members (company_id, name, email, linkedin_url, photo_url)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (company_id, name, email, f"https://linkedin.com/in/{slug}", ""),
        )
        ids.append(cur.fetchone()["id"])
    return ids


def seed_contacts(conn: psycopg.Connection, company_id: int, member_ids: list[int]) -> None:
    today = datetime.now()
    for member_id in member_ids:
        for _ in range(random.randint(4, 9)):
            company, ctype = random.choice(COMPANIES)
            contact_name = random.choice(
                ["Jordan", "Taylor", "Morgan", "Casey", "Riley", "Drew", "Sam", "Avery"]
            ) + " " + random.choice(
                ["Smith", "Lee", "Garcia", "Patel", "Kim", "Brown", "Diaz", "Murphy"]
            )
            days_ago = random.randint(3, 700)
            interactions = random.randint(1, 40)
            strength = round(min(10, interactions / 4 + max(0, (30 - days_ago) / 30 * 3)), 1)
            conn.execute(
                """INSERT INTO contacts
                   (company_id, member_id, contact_name, contact_email, contact_company,
                    contact_title, company_type, strength_score, last_interaction, source)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    company_id, member_id, contact_name,
                    contact_name.lower().replace(" ", ".") + "@" + company.lower().replace(" ", "").replace("'", "") + ".com",
                    company, random.choice(TITLES), ctype, strength,
                    (today - timedelta(days=days_ago)).date().isoformat(),
                    random.choice(["gmail", "calendar", "self_reported"]),
                ),
            )


def seed_events_and_sponsors(conn: psycopg.Connection, company_id: int) -> list[int]:
    event_specs = [
        ("Code & Coffee: Spring Build Night", "2025-04-10", "open co-working", "Pennovation Works"),
        ("Code & Coffee: Founder Pitch Night", "2025-06-19", "pitch competition", "WeWork Philly"),
        ("Code & Coffee: Summer Hack Day", "2025-08-14", "1-day hackathon", "Comcast Technology Center"),
        ("Code & Coffee x AI Agents Night", "2025-11-06", "talk + co-working", "Pennovation Works"),
    ]
    event_ids = []
    for name, date, fmt, venue in event_specs:
        cur = conn.execute(
            "INSERT INTO events (company_id, name, date, format, venue) VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (company_id, name, date, fmt, venue),
        )
        event_ids.append(cur.fetchone()["id"])

    for event_id in event_ids:
        for company, ctype in random.sample(COMPANIES, k=random.randint(2, 4)):
            contribution = CONTRIBUTION_BY_COMPANY_TYPE[ctype]
            conn.execute(
                """INSERT INTO sponsor_history
                   (company_id, event_id, sponsor_name, sponsor_type, contribution_type,
                    contact_person, how_connected)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    company_id, event_id, company, ctype, contribution,
                    random.choice(MEMBER_NAMES) + "'s contact",
                    random.choice(["warm intro", "cold outreach", "sponsor reached out first", "prior event"]),
                ),
            )
    return event_ids


def seed_feedback(conn: psycopg.Connection, company_id: int, event_ids: list[int]) -> None:
    comments_pool = [
        "Loved the format, wish there was more time for pairing.",
        "Venue was cramped, hard to hear announcements.",
        "Sponsor swag table was a nice touch.",
        "Would love more structured project matchmaking at the start.",
        "The pitch night ran long, timeboxing would help.",
        "Great energy, met three people I'm now collaborating with.",
        "Food ran out early.",
        "Wifi was unreliable for the hack day.",
    ]
    for event_id in event_ids:
        for _ in range(random.randint(5, 10)):
            had_connection = 1 if random.random() < 0.55 else 0  # near the 50%+ benchmark
            conn.execute(
                """INSERT INTO feedback
                   (company_id, event_id, respondent, rating_turnout, had_relevant_connection,
                    connection_relevance_rating, rating_format, rating_logistics,
                    rating_sponsor_value, free_text)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    company_id, event_id, random.choice(MEMBER_NAMES),
                    random.randint(2, 5), had_connection,
                    random.randint(3, 5) if had_connection else random.randint(1, 3),
                    random.randint(2, 5), random.randint(1, 5), random.randint(2, 5),
                    random.choice(comments_pool),
                ),
            )


def main() -> None:
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    conn.execute(SCHEMA_PATH.read_text())
    reset_schema(conn)
    from psycopg.rows import dict_row
    conn.row_factory = dict_row

    company_id = seed_company(conn)
    member_ids = seed_members(conn, company_id)
    seed_contacts(conn, company_id, member_ids)
    event_ids = seed_events_and_sponsors(conn, company_id)
    seed_feedback(conn, company_id, event_ids)
    conn.close()
    print(f"Seeded {DATABASE_URL} with {len(member_ids)} members, {len(event_ids)} events.")
    print(f"Login -- email: {DEMO_COMPANY_EMAIL}  password: {DEMO_COMPANY_PASSWORD}")


if __name__ == "__main__":
    main()
