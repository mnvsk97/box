# Box — Product Requirements Document

## One-liner

Simple, ephemeral sandboxed environments powered by Docker. CLI + Python SDK.

## Problem

When you want to test a pip package, run untrusted code, or validate something in a clean environment, your options are:

1. **Hosted services** (E2B, Daytona, CodeSandbox) — cost money, require internet, your code leaves your machine
2. **Raw Docker** — works but verbose for quick throwaway tasks, no ergonomic SDK
3. **Virtual environments** — only isolate Python dependencies, not the filesystem/network/processes

There's no simple local tool that makes ephemeral sandboxing as easy as `Box("python")`.

## Solution

**Box** wraps Docker with a clean interface:

- A **CLI** for quick use (`box up`, `box do`, `box down`)
- A **Python SDK** for programmatic use (`Box("python")` as a context manager)

Docker does the heavy lifting (isolation, resource limits, networking). Box provides the UX.

## Target Users

1. **Developers** testing packages, scripts, or tools in clean environments
2. **AI agent builders** who need sandboxed code execution for LLM-generated code
3. **Claude Code users** who want to test things in isolation via the `/box` skill

## Non-goals

- Not building container primitives from scratch (no custom namespaces/cgroups/seccomp)
- Not a container orchestrator
- Not a CI/CD system
- Not a hosted service — local only, always free

---

## Core Concepts

### Sandbox

An ephemeral Docker container with a clean interface. Created from any Docker image, destroyed when done. Nothing persists unless explicitly exported.

### Image Aliases

Shorthand names that map to Docker images:
- `python` -> `python:3.12-slim`
- `node` -> `node:22-slim`
- `go` -> `golang:1.22-alpine`
- Any Docker image reference also works directly

---

## Features

### CLI

```bash
box up python -n my-lab                 # create sandbox
box do my-lab -- pip install flask      # run command
box shell my-lab                        # interactive shell
box run python -- python -c "print(1)" # one-shot: create, run, destroy
box ps                                  # list running sandboxes
box down my-lab                         # destroy
box down --all                          # destroy all
box images                              # list image aliases
```

### Python SDK

```python
from box import Box

# Context manager (auto-cleanup)
with Box("python") as sb:
    result = sb.run("pip install requests")
    print(result.stdout)

# Long-lived
sb = Box("python", name="lab", memory="256M")
sb.run("pip install flask")
sb.kill()

# File operations
sb.fs.write("/tmp/test.py", "print('hello')")
sb.fs.read("/tmp/test.py")
sb.fs.upload("local.py", "/app/local.py")
sb.fs.download("/app/output.txt", "./output.txt")
```

### Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `image` | `alpine` | Docker image or alias |
| `name` | auto-generated | Human-readable name |
| `memory` | `512M` | Memory limit |
| `pids` | `256` | Max process count |
| `cpu` | unlimited | CPU limit |
| `network` | `True` | Network access |
| `envs` | `{}` | Environment variables |
| `volumes` | `{}` | Volume mounts |
| `ports` | `{}` | Port mappings |
| `timeout` | `None` | Auto-destroy timer (seconds) |
| `workdir` | `None` | Working directory |

### Security Defaults

Docker handles isolation. Box adds:
- `--cap-drop ALL` — no Linux capabilities
- `--security-opt no-new-privileges` — no privilege escalation
- Network disabled when `network=False`
- Memory and PID limits enforced

---

## Architecture

```
┌─────────────────────────────┐
│     CLI (Click)             │
│     box up / do / down      │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│     Python SDK              │
│     Box class               │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│     Docker CLI              │
│     docker run/exec/rm      │
└─────────────────────────────┘
```

Simple three-layer stack. No daemon, no server, no complex runtime.

---

## Success Metrics

- **Sandbox startup** < 2s for cached images
- **API surface** small enough to learn in 5 minutes
- **Zero configuration** needed for basic use — just `Box("python")`
- **Clean teardown** — no zombie containers, no leaked state

---

## Dependencies

- Python >= 3.12
- Docker (or Podman)
- click, pyyaml

---

## Future (maybe)

- API server for remote/multi-user access
- Snapshot and restore
- Sandbox networking (connect sandboxes to each other)
- Image pre-warming for faster startup
