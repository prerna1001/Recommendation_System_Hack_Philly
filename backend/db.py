"""DB access for the FastAPI backend -- reuses agents/common.py's get_db()
rather than duplicating the Postgres connection logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))

from common import get_db  # noqa: E402
