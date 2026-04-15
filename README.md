# Box

Simple, ephemeral sandboxed environments powered by Docker. Spin up, use, destroy.

No custom runtimes, no cloud services, no signup. Just Docker containers with a clean interface.

## Install

```bash
pip install box-sandbox
```

Requires Docker running locally.

## Python SDK

```python
from box import Box

# One-shot: create, run, destroy
with Box("python") as sb:
    result = sb.run("pip install requests && python -c 'import requests; print(requests.__version__)'")
    print(result.stdout)

# Long-lived sandbox
sb = Box("node", name="my-app", memory="256M")
sb.run("npm init -y")
sb.run("npm install express")
sb.kill()

# No network access
with Box("python", network=False) as sb:
    sb.run("python -c 'print(1+1)'")  # works
    sb.run("pip install flask")        # fails — no network

# Mount local code
with Box("python", volumes={"/app": "."}) as sb:
    sb.run("cd /app && pip install -e . && pytest")

# Environment variables
with Box("python", envs={"API_KEY": "sk-test"}) as sb:
    sb.run("python app.py")

# Port mapping
with Box("node", ports={3000: 3000}) as sb:
    sb.run("node server.js &")
    print(sb.port(3000))  # "0.0.0.0:3000"
```

## CLI

```bash
box up python -n lab                    # create sandbox
box do lab -- pip install flask         # run command
box do lab -- python -c "print(1)"      # run another
box shell lab                           # interactive shell
box ps                                  # list sandboxes
box down lab                            # destroy
box down --all                          # destroy all

box run python -- python -c "print(1)"  # one-shot: create, run, destroy
box images                              # list image aliases
box history                             # show run history
box history --clear                     # wipe history
```

## Image Aliases

| Alias | Image |
|-------|-------|
| `alpine` | alpine:latest |
| `ubuntu` | ubuntu:24.04 |
| `python` | python:3.12-slim |
| `node` | node:22-slim |
| `go` | golang:1.22-alpine |
| `rust` | rust:1.77-slim |
| `ruby` | ruby:3.3-slim |
| `java` | eclipse-temurin:21-jdk-alpine |
| `bun` | oven/bun:slim |
| `aws` | amazon/aws-cli:latest |
| `terraform` | hashicorp/terraform:latest |

Any Docker image works: `Box("postgres:16")`, `box up nginx:latest`.

## API Reference

### Box

```python
sb = Box(image, name=None, memory="512M", pids=256, cpu=None,
         network=True, envs={}, volumes={}, ports={}, timeout=None, workdir=None)

sb.run(command, timeout=30, envs=None) -> RunResult
sb.shell()                             # interactive TTY
sb.stop() / sb.start()                 # pause/resume
sb.kill()                              # destroy

sb.fs.read(path) -> str
sb.fs.write(path, content)
sb.fs.list(path) -> list[str]
sb.fs.exists(path) -> bool
sb.fs.delete(path)
sb.fs.upload(local, remote)
sb.fs.download(remote, local)

sb.port(container_port) -> str | None

Box.ps() -> list[Box]                  # list all
Box.get(id_or_name) -> Box             # lookup
Box.nuke()                             # kill all
Box.history(limit=50) -> list[dict]    # run history
```

### RunResult

```python
result.exit_code    # int
result.stdout       # str
result.stderr       # str
bool(result)        # True if exit_code == 0
str(result)         # stdout
```

## Claude Code Skill

Box ships with a `/test-in-isolation` skill for Claude Code. When you say things like:

- "test if eyeroll installs correctly"
- "run this in a sandbox"
- "try this in a clean environment"

Claude spins up a Box container, runs the test, reports results, and destroys the container. Nothing touches your host.

## License

MIT
