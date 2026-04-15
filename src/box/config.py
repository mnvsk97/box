"""Global configuration and paths."""

import os
from pathlib import Path


def box_home() -> Path:
    """Return the box data directory (~/.box/)."""
    return Path(os.environ.get("BOX_HOME", Path.home() / ".box"))


def sandboxes_dir() -> Path:
    return box_home() / "sandboxes"


def history_file() -> Path:
    return box_home() / "history.json"


def ensure_dirs():
    """Create all required directories if they don't exist."""
    for d in [box_home(), sandboxes_dir()]:
        d.mkdir(parents=True, exist_ok=True)
