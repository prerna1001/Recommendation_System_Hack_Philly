"""The human-in-the-loop gate: list pending recommendations, approve/reject one.

This is the concrete implementation of the 'safeguards and permission
controls' the Quirq: Build It submission asks projects to identify --
no agent output in this project is ever treated as final until a human
flips its status here.

Multi-tenant: requires --company-id since this predates auth and has no
session/cookie to resolve a company from. Look the id up with
`psql -c "SELECT id, name FROM companies"`.

Usage:
    python orchestrator/approve.py --company-id 1 list
    python orchestrator/approve.py --company-id 1 show 3
    python orchestrator/approve.py --company-id 1 approve 3
    python orchestrator/approve.py --company-id 1 reject 3
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
from common import get_db  # noqa: E402
from weights import apply_feedback  # noqa: E402


def cmd_list(conn, company_id):
    rows = conn.execute(
        "SELECT id, type, status, created_at FROM recommendations WHERE company_id = %s ORDER BY id DESC",
        (company_id,),
    ).fetchall()
    for r in rows:
        print(f"#{r['id']:<4} {r['type']:<14} {r['status']:<17} {r['created_at']}")


def cmd_show(conn, company_id, rec_id):
    r = conn.execute(
        "SELECT * FROM recommendations WHERE id = %s AND company_id = %s", (rec_id, company_id)
    ).fetchone()
    if not r:
        print(f"No recommendation #{rec_id}")
        return
    print(f"#{r['id']} [{r['type']}] status={r['status']}\nreasoning: {r['reasoning']}\n\n{r['content']}")


def cmd_set_status(conn, company_id, rec_id, status):
    updated = conn.execute(
        "UPDATE recommendations SET status = %s WHERE id = %s AND company_id = %s RETURNING id",
        (status, rec_id, company_id),
    ).fetchone()
    conn.commit()
    if not updated:
        print(f"No recommendation #{rec_id} for company {company_id}")
        return
    print(f"#{rec_id} -> {status}")
    # approve/reject is also a training signal -- same weight update as a
    # chat like/dislike, so CLI approvals and chat feedback share one learning loop.
    touched = apply_feedback(conn, company_id, rec_id, liked=(status == "approved"))
    for t in touched:
        print(f"  weight[{t['feature_type']}={t['feature_value']}] -> {t['new_weight']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-id", type=int, required=True, help="the company/tenant to run this for")
    parser.add_argument("action", choices=["list", "show", "approve", "reject"])
    parser.add_argument("rec_id", type=int, nargs="?")
    args = parser.parse_args()

    conn = get_db()
    if args.action == "list":
        cmd_list(conn, args.company_id)
    elif args.action == "show":
        cmd_show(conn, args.company_id, args.rec_id)
    elif args.action == "approve":
        cmd_set_status(conn, args.company_id, args.rec_id, "approved")
    elif args.action == "reject":
        cmd_set_status(conn, args.company_id, args.rec_id, "rejected")
    conn.close()


if __name__ == "__main__":
    main()
