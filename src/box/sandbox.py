"""Sandbox state management — internal module."""

import json
import shutil
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from box.config import sandboxes_dir


@dataclass
class SandboxState:
    """Persisted sandbox state (state.json)."""
    id: str
    pid: str  # Docker container ID
    image: str
    status: str  # "running", "stopped", "dead"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    config: dict = field(default_factory=dict)
    name: str | None = None

    def save(self):
        path = sandboxes_dir() / self.id / "state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, sandbox_id: str) -> "SandboxState":
        path = sandboxes_dir() / sandbox_id / "state.json"
        data = json.loads(path.read_text())
        return cls(**data)

    @classmethod
    def list_all(cls) -> list["SandboxState"]:
        sdir = sandboxes_dir()
        if not sdir.exists():
            return []
        states = []
        for d in sorted(sdir.iterdir()):
            state_file = d / "state.json"
            if state_file.exists():
                try:
                    state = cls.load(d.name)
                    if state.status == "running" and not state._container_alive():
                        state.status = "dead"
                        state.save()
                    states.append(state)
                except (json.JSONDecodeError, TypeError, KeyError):
                    continue
        return states

    def _container_alive(self) -> bool:
        from box.runtime.container import container_running
        return container_running(self.id)

    def cleanup(self):
        sandbox_dir = sandboxes_dir() / self.id
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir, ignore_errors=True)
