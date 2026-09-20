"""Learned feature weights -- the "Instagram-style" recommendation-shaping
layer discussed for this project: every like/dislike on a chat suggestion and
every approve/reject of a recommendation nudges the weight for the feature(s)
(company_type / sponsor_type) that recommendation drew on. network_intel_agent
and planning_agent read these back in to re-rank candidates, so repeated
feedback measurably shifts future suggestions -- not just gates them.

Multi-tenant: feature_weights is unique per (company_id, feature_type,
feature_value), so each company learns independently of every other tenant.
"""
import psycopg

LIKE_MULTIPLIER = 1.2
DISLIKE_MULTIPLIER = 0.8
MIN_WEIGHT = 0.1


def get_weights_map(conn: psycopg.Connection, company_id: int, feature_type: str) -> dict[str, float]:
    rows = conn.execute(
        "SELECT feature_value, weight FROM feature_weights WHERE company_id = %s AND feature_type = %s",
        (company_id, feature_type),
    ).fetchall()
    return {r["feature_value"]: r["weight"] for r in rows}


def tag_recommendation(conn: psycopg.Connection, recommendation_id: int,
                        feature_type: str, feature_value: str) -> None:
    conn.execute(
        """INSERT INTO recommendation_features (recommendation_id, feature_type, feature_value)
           VALUES (%s, %s, %s)""",
        (recommendation_id, feature_type, feature_value),
    )
    conn.commit()


def _nudge(conn: psycopg.Connection, company_id: int, feature_type: str, feature_value: str, multiplier: float) -> float:
    row = conn.execute(
        "SELECT weight FROM feature_weights WHERE company_id = %s AND feature_type = %s AND feature_value = %s",
        (company_id, feature_type, feature_value),
    ).fetchone()
    current = row["weight"] if row else 1.0
    new_weight = max(MIN_WEIGHT, round(current * multiplier, 4))
    conn.execute(
        """INSERT INTO feature_weights (company_id, feature_type, feature_value, weight, updated_at)
           VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
           ON CONFLICT (company_id, feature_type, feature_value)
           DO UPDATE SET weight = EXCLUDED.weight, updated_at = CURRENT_TIMESTAMP""",
        (company_id, feature_type, feature_value, new_weight),
    )
    conn.commit()
    return new_weight


def apply_feedback(conn: psycopg.Connection, company_id: int, recommendation_id: int, liked: bool) -> list[dict]:
    """Nudge every feature tagged on this recommendation. Returns what moved,
    for the caller to surface back to the organizer (e.g. in the API response)."""
    features = conn.execute(
        """SELECT DISTINCT feature_type, feature_value FROM recommendation_features
           WHERE recommendation_id = %s""",
        (recommendation_id,),
    ).fetchall()
    multiplier = LIKE_MULTIPLIER if liked else DISLIKE_MULTIPLIER
    touched = []
    for f in features:
        new_weight = _nudge(conn, company_id, f["feature_type"], f["feature_value"], multiplier)
        touched.append({"feature_type": f["feature_type"], "feature_value": f["feature_value"], "new_weight": new_weight})
    return touched
