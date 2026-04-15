"""Security profiles — named configurations for sandbox isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml

from box.config import profiles_dir


@dataclass
class Profile:
    """A named security configuration for a sandbox."""
    name: str
    filesystem: str = "readwrite"       # "readwrite" or "readonly"
    network: str = "host"               # "none" or "host"
    memory: str = "512M"
    pids: int = 256
    cpu: str | None = None
    syscalls: str = "moderate"          # "strict", "moderate", "permissive"
    capabilities: list[str] = field(default_factory=list)


# Built-in profiles
BUILTIN_PROFILES = {
    "default": Profile(
        name="default",
        filesystem="readwrite",
        network="host",
        memory="512M",
        pids=256,
        syscalls="moderate",
    ),
    "strict": Profile(
        name="strict",
        filesystem="readonly",
        network="none",
        memory="256M",
        pids=64,
        syscalls="strict",
        capabilities=[],
    ),
    "network": Profile(
        name="network",
        filesystem="readwrite",
        network="host",
        memory="512M",
        pids=256,
        syscalls="moderate",
    ),
    "unrestricted": Profile(
        name="unrestricted",
        filesystem="readwrite",
        network="host",
        memory="4G",
        pids=4096,
        syscalls="permissive",
        capabilities=["NET_BIND_SERVICE", "DAC_OVERRIDE", "CHOWN", "FOWNER"],
    ),
}


def load_profile(name: str) -> Profile:
    """Load a profile by name. Checks built-ins first, then user profiles."""
    if name in BUILTIN_PROFILES:
        return BUILTIN_PROFILES[name]

    # Check user profile directory
    user_profile = profiles_dir() / f"{name}.yaml"
    if user_profile.exists():
        data = yaml.safe_load(user_profile.read_text())
        return Profile(**data)

    available = ", ".join(sorted(BUILTIN_PROFILES.keys()))
    raise ValueError(f"Unknown profile '{name}'. Available: {available}")


def resolve_profile(name: str, overrides: dict) -> Profile:
    """Load a profile and apply CLI flag overrides."""
    profile = load_profile(name)

    if "memory" in overrides and overrides["memory"] is not None:
        profile.memory = overrides["memory"]
    if "pids" in overrides and overrides["pids"] is not None:
        profile.pids = overrides["pids"]
    if "cpu" in overrides and overrides["cpu"] is not None:
        profile.cpu = overrides["cpu"]
    if "network" in overrides:
        profile.network = "host" if overrides["network"] else "none"

    return profile
