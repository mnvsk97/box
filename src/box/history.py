"""Run history — append-only log of sandbox lifecycle events."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from box.config import history_file


def log_event(
    sandbox_id: str,
    event: str,
    *,
    image: str | None = None,
    name: str | None = None,
    command: str | None = None,
    exit_code: int | None = None,
    error: str | None = None,
    duration_ms: int | None = None,
):
    """Append a single event to the history log."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sandbox_id": sandbox_id,
        "event": event,
    }
    if image is not None:
        entry["image"] = image
    if name is not None:
        entry["name"] = name
    if command is not None:
        entry["command"] = command
    if exit_code is not None:
        entry["exit_code"] = exit_code
    if error is not None:
        entry["error"] = error
    if duration_ms is not None:
        entry["duration_ms"] = duration_ms

    path = history_file()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Append as one JSON line per event (jsonlines format)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_history(limit: int = 50) -> list[dict]:
    """Load the most recent events from history."""
    path = history_file()
    if not path.exists():
        return []

    lines = path.read_text().strip().splitlines()
    entries = []
    for line in lines:
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return entries[-limit:]


def clear_history():
    """Wipe the history log."""
    path = history_file()
    if path.exists():
        path.unlink()
