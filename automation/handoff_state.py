import json
import os
from datetime import datetime, timezone


STATE_PATH = "evidence/handoff_state.json"


def write_handoff_state(step_id, reason, current_url):
    os.makedirs("evidence", exist_ok=True)

    state = {
        "status": "PAUSED",
        "current_step": step_id,
        "reason": reason,
        "current_url": current_url,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def read_handoff_state():
    if not os.path.exists(STATE_PATH):
        return {
            "status": "IDLE",
            "current_step": None,
            "reason": None,
            "current_url": None,
            "timestamp": None
        }

    with open(STATE_PATH, "r") as f:
        return json.load(f)