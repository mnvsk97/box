"""Image resolution — shorthand aliases and Docker image references."""

from __future__ import annotations

# Shorthand aliases → Docker image references
# Users can say Box("python") instead of Box("python:3.12-slim")
IMAGE_ALIASES: dict[str, str] = {
    # Base
    "alpine": "alpine:latest",
    "ubuntu": "ubuntu:24.04",
    "debian": "debian:bookworm-slim",

    # Languages
    "python": "python:3.12-slim",
    "python3": "python:3.12-slim",
    "python3.12": "python:3.12-slim",
    "python3.11": "python:3.11-slim",
    "python3.13": "python:3.13-slim",
    "node": "node:22-slim",
    "node20": "node:20-slim",
    "node22": "node:22-slim",
    "bun": "oven/bun:slim",
    "go": "golang:1.22-alpine",
    "golang": "golang:1.22-alpine",
    "rust": "rust:1.77-slim",
    "ruby": "ruby:3.3-slim",
    "java": "eclipse-temurin:21-jdk-alpine",
    "java21": "eclipse-temurin:21-jdk-alpine",
    "java17": "eclipse-temurin:17-jdk-alpine",

    # Tools
    "aws": "amazon/aws-cli:latest",
    "terraform": "hashicorp/terraform:latest",
    "kubectl": "bitnami/kubectl:latest",
    "gcloud": "google/cloud-sdk:slim",
    "azure": "mcr.microsoft.com/azure-cli:latest",
}

# Default image when nothing is specified
DEFAULT_IMAGE = "alpine:latest"


def resolve_image(image: str) -> str:
    """Resolve an image shorthand to a full Docker image reference.

    Supports:
        "python"       → "python:3.12-slim"
        "node"         → "node:22-slim"
        "aws"          → "amazon/aws-cli:latest"
        "python:3.11"  → passed through as-is
        "myimage:tag"  → passed through as-is
    """
    # Check aliases first
    if image in IMAGE_ALIASES:
        return IMAGE_ALIASES[image]

    # Otherwise pass through as a Docker image reference
    return image


def list_aliases() -> dict[str, str]:
    """Return all available image aliases."""
    return dict(IMAGE_ALIASES)
