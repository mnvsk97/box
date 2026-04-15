"""Box — the public SDK interface. This is the only file users need to know."""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

from box.config import ensure_dirs
from box.sandbox import SandboxState


@dataclass
class RunResult:
    """Result of running a command inside a sandbox."""
    exit_code: int
    stdout: str
    stderr: str

    def __bool__(self):
        return self.exit_code == 0

    def __str__(self):
        return self.stdout


class FileSystem:
    """File operations inside a sandbox."""

    def __init__(self, sandbox_id: str):
        self._id = sandbox_id

    def read(self, path: str) -> str:
        from box.runtime.container import read_file
        return read_file(self._id, path)

    def write(self, path: str, content: str) -> None:
        from box.runtime.container import write_file
        write_file(self._id, path, content)

    def list(self, path: str = "/") -> list[str]:
        from box.runtime.container import list_files
        return list_files(self._id, path)

    def exists(self, path: str) -> bool:
        from box.runtime.container import file_exists
        return file_exists(self._id, path)

    def delete(self, path: str) -> None:
        from box.runtime.container import exec_in_container
        result = exec_in_container(self._id, "", f"rm -rf {path}", timeout=10)
        if result.exit_code != 0:
            raise IOError(f"Failed to delete {path}: {result.stderr}")

    def upload(self, local_path: str, remote_path: str) -> None:
        """Copy a local file into the sandbox."""
        from box.runtime.container import copy_to_container
        copy_to_container(self._id, local_path, remote_path)

    def download(self, remote_path: str, local_path: str) -> None:
        """Copy a file from the sandbox to local filesystem."""
        from box.runtime.container import copy_from_container
        copy_from_container(self._id, remote_path, local_path)


class Box:
    """Secure, ephemeral sandbox.

    Usage:
        sb = Box("python:3.12", memory="256M")
        result = sb.run("echo hello")
        sb.kill()

        # With env vars:
        sb = Box("python:3.12", envs={"API_KEY": "sk-..."})

        # With volume mounts:
        sb = Box("python:3.12", volumes={"/app": "./my-project"})

        # Auto-destroy after 5 minutes:
        sb = Box("python:3.12", timeout=300)

        # Named sandbox:
        sb = Box("python:3.12", name="my-lab")

        # Context manager (auto-cleanup):
        with Box("python:3.12") as sb:
            sb.run("pip install requests")
        # gone
    """

    def __init__(
        self,
        image: str = "alpine",
        *,
        name: str | None = None,
        profile: str = "default",
        memory: str = "512M",
        pids: int = 256,
        cpu: str | None = None,
        network: bool = True,
        envs: dict[str, str] | None = None,
        volumes: dict[str, str] | None = None,
        ports: dict[int, int] | None = None,
        timeout: int | None = None,
        workdir: str | None = None,
    ):
        ensure_dirs()

        from box.image.manager import resolve_image
        self.id = secrets.token_hex(4)
        self.name = name
        self.image = resolve_image(image)
        self.profile = profile
        self.status = "running"
        self._fs = FileSystem(self.id)
        self._timeout_timer: threading.Timer | None = None

        self._config = {
            "memory": memory,
            "pids": pids,
            "cpu": cpu,
            "network": network,
            "envs": envs or {},
            "volumes": volumes or {},
            "ports": ports or {},
            "workdir": workdir,
        }

        # Create the Docker container
        from box.runtime.container import create_container
        self._created_at = time.time()
        self._container_id = create_container(self.id, self.image, self._config)

        from box.history import log_event
        log_event(self.id, "created", image=self.image, name=name)

        # Save state
        self._state = SandboxState(
            id=self.id,
            pid=self._container_id,
            image=self.image,
            profile=self.profile,
            status="running",
            config=self._config,
            name=name,
        )
        self._state.save()

        # Auto-timeout
        if timeout:
            self._start_timeout(timeout)

    def run(self, command: str, timeout: int = 30, envs: dict[str, str] | None = None) -> RunResult:
        """Execute a command inside the sandbox."""
        if self.status != "running":
            raise RuntimeError(f"Sandbox {self.id} is not running (status: {self.status})")

        from box.runtime.container import exec_in_container
        t0 = time.time()
        result = exec_in_container(self.id, self._container_id, command, timeout, envs=envs)

        from box.history import log_event
        log_event(
            self.id, "exec",
            command=command,
            exit_code=result.exit_code,
            duration_ms=int((time.time() - t0) * 1000),
        )
        return result

    def shell(self) -> None:
        """Open an interactive shell inside the sandbox."""
        if self.status != "running":
            raise RuntimeError(f"Sandbox {self.id} is not running (status: {self.status})")

        from box.runtime.container import shell_into_container
        shell_into_container(self.id)

    @property
    def fs(self) -> FileSystem:
        """Access the sandbox filesystem."""
        return self._fs

    def port(self, container_port: int) -> str | None:
        """Get the host address for a mapped container port."""
        from box.runtime.container import get_port_mapping
        return get_port_mapping(self.id, container_port)

    def stop(self) -> None:
        """Stop the sandbox (can be restarted)."""
        if self.status != "running":
            return
        self._cancel_timeout()
        from box.runtime.container import stop_container
        stop_container(self.id)
        self.status = "stopped"
        self._state.status = "stopped"
        self._state.save()

    def start(self) -> None:
        """Resume a stopped sandbox."""
        if self.status != "stopped":
            return
        from box.runtime.container import start_container
        start_container(self.id)
        self.status = "running"
        self._state.status = "running"
        self._state.save()

    def kill(self) -> None:
        """Destroy the sandbox. Removes container, cleans up state."""
        if self.status == "dead":
            return

        self._cancel_timeout()
        from box.runtime.container import destroy_container
        destroy_container(self.id, self._container_id)

        from box.history import log_event
        duration_ms = int((time.time() - self._created_at) * 1000) if hasattr(self, '_created_at') else None
        log_event(self.id, "destroyed", image=self.image, name=self.name, duration_ms=duration_ms)

        self.status = "dead"
        self._state.status = "dead"
        self._state.save()
        self._state.cleanup()

    def _start_timeout(self, seconds: int):
        """Auto-kill after N seconds."""
        self._timeout_timer = threading.Timer(seconds, self._timeout_expired)
        self._timeout_timer.daemon = True
        self._timeout_timer.start()

    def _timeout_expired(self):
        """Called when the timeout fires."""
        try:
            self.kill()
        except Exception:
            pass

    def _cancel_timeout(self):
        if self._timeout_timer:
            self._timeout_timer.cancel()
            self._timeout_timer = None

    def __enter__(self) -> Box:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.kill()

    def __repr__(self) -> str:
        label = self.name or self.id
        return f"Box(id={self.id!r}, name={self.name!r}, image={self.image!r}, status={self.status!r})"

    # --- Class-level operations ---

    @classmethod
    def ps(cls) -> list[Box]:
        """List all sandboxes."""
        states = SandboxState.list_all()
        boxes = []
        for state in states:
            box = object.__new__(cls)
            box.id = state.id
            box.name = state.name
            box.image = state.image
            box.profile = state.profile
            box.status = state.status
            box._container_id = state.pid
            box._config = state.config
            box._state = state
            box._fs = FileSystem(state.id)
            box._timeout_timer = None
            boxes.append(box)
        return boxes

    @classmethod
    def get(cls, sandbox_id: str) -> Box:
        """Get a sandbox by ID, ID prefix, or name."""
        states = SandboxState.list_all()

        # Try exact name match first
        for s in states:
            if s.name and s.name == sandbox_id:
                return cls._from_state(s)

        # Then try ID prefix match
        matches = [s for s in states if s.id.startswith(sandbox_id)]

        if not matches:
            raise ValueError(f"No sandbox found matching '{sandbox_id}'")
        if len(matches) > 1:
            ids = ", ".join(s.id for s in matches)
            raise ValueError(f"Ambiguous ID '{sandbox_id}' matches: {ids}")

        return cls._from_state(matches[0])

    @classmethod
    def _from_state(cls, state: SandboxState) -> Box:
        box = object.__new__(cls)
        box.id = state.id
        box.name = state.name
        box.image = state.image
        box.profile = state.profile
        box.status = state.status
        box._container_id = state.pid
        box._config = state.config
        box._state = state
        box._fs = FileSystem(state.id)
        box._timeout_timer = None
        return box

    @classmethod
    def nuke(cls) -> None:
        """Kill all sandboxes."""
        for box in cls.ps():
            try:
                box.kill()
            except Exception:
                pass

    @classmethod
    def history(cls, limit: int = 50) -> list[dict]:
        """Return recent sandbox history events."""
        from box.history import load_history
        return load_history(limit)
