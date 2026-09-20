"""Thin sequencer over the three agents -- no framework, just calls in order.

Multi-tenant: requires --company-id since this predates auth and has no
session/cookie to resolve a company from (it's an operator tool run outside
the browser). Look the id up with `psql -c "SELECT id, name FROM companies"`.

Examples:
    python orchestrator/run_pipeline.py --company-id 1 --goal "sponsor credits"
    python orchestrator/run_pipeline.py --company-id 1 --event 3
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

import network_intel_agent
import planning_agent
import retrospective_agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-id", type=int, required=True, help="the company/tenant to run this for")
    parser.add_argument("--goal", help="Run Agent 1 standalone: find warm-intro candidates for this goal")
    parser.add_argument("--event", type=int, help="Run Agent 2 then Agent 3 for this event id")
    args = parser.parse_args()

    if args.goal:
        print("=== Agent 1: Network Intelligence ===")
        print(network_intel_agent.run(args.company_id, args.goal))

    if args.event:
        print("=== Agent 2: Event Retrospective ===")
        print(retrospective_agent.run(args.company_id, args.event))
        print("\n=== Agent 3: Recommendation & Planning ===")
        print(planning_agent.run(args.company_id, args.event))

    if not args.goal and not args.event:
        parser.print_help()


if __name__ == "__main__":
    main()
