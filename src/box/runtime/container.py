"""Container lifecycle via Docker.

All Docker interaction goes through this module.
The rest of the codebase is Docker-agnostic.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from box.box import RunResult


def _docker_bin() -> str:
    """Find docker or podman binary."""
    for name in ("docker", "podman"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(
        "Docker (or Podman) is required but not found on PATH.\n"
        "Install Docker: https://docs.docker.com/get-docker/"
    )


def _run(args: list[str], timeout: int | None = None) -> subprocess.CompletedProcess:
    """Run a docker command and return the result."""
    return subprocess.run(
        [_docker_bin()] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def create_container(sandbox_id: str, image: str, config: dict) -> str:
    """Create and start a Docker container. Returns the container ID."""
    cmd = ["run", "-d", "--name", f"box-{sandbox_id}"]

    # Resource limits
    if memory := config.get("memory"):
        cmd += ["--memory", memory]

    if pids := config.get("pids"):
        cmd += ["--pids-limit", str(pids)]

    if cpu := config.get("cpu"):
        if "%" in str(cpu):
            cpus = int(str(cpu).strip("%")) / 100
            cmd += ["--cpus", str(cpus)]
        else:
            cmd += ["--cpus", str(cpu)]

    # Network
    if not config.get("network", True):
        cmd += ["--network", "none"]

    # Environment variables
    for key, value in config.get("envs", {}).items():
        cmd += ["-e", f"{key}={value}"]

    # Volume mounts: {container_path: host_path}
    for container_path, host_path in config.get("volumes", {}).items():
        abs_host = os.path.abspath(host_path)
        cmd += ["-v", f"{abs_host}:{container_path}"]

    # Port mappings: {container_port: host_port} or {container_port: 0} for auto
    for container_port, host_port in config.get("ports", {}).items():
        if host_port == 0:
            cmd += ["-p", str(container_port)]  # auto-assign host port
        else:
            cmd += ["-p", f"{host_port}:{container_port}"]

    # Working directory
    if workdir := config.get("workdir"):
        cmd += ["-w", workdir]

    # Security hardening
    cmd += [
        "--security-opt", "no-new-privileges",
        "--cap-drop", "ALL",
    ]

    cmd += [image, "sleep", "infinity"]

    result = _run(cmd)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create container: {result.stderr.strip()}")

    return result.stdout.strip()


def exec_in_container(
    sandbox_id: str,
    container_id: str,
    command: str,
    timeout: int = 30,
    envs: dict[str, str] | None = None,
) -> RunResult:
    """Execute a command inside a running container."""
    cmd = ["exec"]

    # Per-command env vars
    for key, value in (envs or {}).items():
        cmd += ["-e", f"{key}={value}"]

    cmd += [f"box-{sandbox_id}", "sh", "-c", command]

    result = _run(cmd, timeout=timeout)
    return RunResult(
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def shell_into_container(sandbox_id: str) -> None:
    """Open an interactive shell inside a container (TTY)."""
    subprocess.run(
        [_docker_bin(), "exec", "-it", f"box-{sandbox_id}", "sh"],
    )


def stop_container(sandbox_id: str):
    _run(["stop", f"box-{sandbox_id}", "-t", "10"])


def start_container(sandbox_id: str):
    _run(["start", f"box-{sandbox_id}"])


def destroy_container(sandbox_id: str, container_id: str) -> None:
    _run(["rm", "-f", f"box-{sandbox_id}"])


def list_containers() -> list[dict]:
    result = _run([
        "ps", "-a",
        "--filter", "name=box-",
        "--format", '{{json .}}',
    ])
    if result.returncode != 0:
        return []
    containers = []
    for line in result.stdout.strip().splitlines():
        if line:
            containers.append(json.loads(line))
    return containers


def container_running(sandbox_id: str) -> bool:
    result = _run(["inspect", "-f", "{{.State.Running}}", f"box-{sandbox_id}"])
    return result.returncode == 0 and result.stdout.strip() == "true"


def get_port_mapping(sandbox_id: str, container_port: int) -> str | None:
    """Get the host address for a mapped container port."""
    result = _run(["port", f"box-{sandbox_id}", str(container_port)])
    if result.returncode != 0:
        return None
    # Returns something like "0.0.0.0:32768" — take first line
    mapping = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
    return mapping


def copy_to_container(sandbox_id: str, local_path: str, remote_path: str) -> None:
    """Copy a local file into the container via stdin (avoids permission issues)."""
    with open(local_path, "r") as f:
        content = f.read()
    write_file(sandbox_id, remote_path, content)


def copy_from_container(sandbox_id: str, remote_path: str, local_path: str) -> None:
    """Copy a file/dir from the container to local filesystem."""
    result = _run(["cp", f"box-{sandbox_id}:{remote_path}", local_path])
    if result.returncode != 0:
        raise IOError(f"Failed to copy from container: {result.stderr.strip()}")


def read_file(sandbox_id: str, path: str) -> str:
    result = _run(["exec", f"box-{sandbox_id}", "cat", path])
    if result.returncode != 0:
        raise FileNotFoundError(f"{path}: {result.stderr.strip()}")
    return result.stdout


def write_file(sandbox_id: str, path: str, content: str) -> None:
    result = subprocess.run(
        [_docker_bin(), "exec", "-i", f"box-{sandbox_id}", "sh", "-c", f"cat > {path}"],
        input=content,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise IOError(f"Failed to write {path}: {result.stderr.strip()}")


def list_files(sandbox_id: str, path: str = "/") -> list[str]:
    result = _run(["exec", f"box-{sandbox_id}", "ls", "-1", path])
    if result.returncode != 0:
        raise FileNotFoundError(f"{path}: {result.stderr.strip()}")
    return [f for f in result.stdout.strip().splitlines() if f]


def file_exists(sandbox_id: str, path: str) -> bool:
    result = _run(["exec", f"box-{sandbox_id}", "test", "-e", path])
    return result.returncode == 0
