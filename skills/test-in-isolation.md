---
name: test-in-isolation
description: "Test code, packages, or scripts in an isolated Docker sandbox. Triggers on: test in isolation, run in sandbox, try in container, test safely, run untrusted code, test in clean env."
allowed-tools: Bash(python*) Bash(pip*) Bash(box*) Bash(docker*)
---

# Box — Isolated Sandbox Execution

When the user wants to test something in isolation, spin up a Box sandbox, run the task, report results, and destroy the container. No residue on the host.

## When This Skill Triggers

- "test this in isolation"
- "run this in a sandbox"
- "try this in a clean environment"
- "test this safely"
- "can you run this in a container"
- "test this package"
- "run this script somewhere safe"
- Any request where code should NOT run on the host machine

## How It Works

Box wraps Docker. Every sandbox is a Docker container that auto-destroys.

```python
from box import Box

with Box("python") as sb:
    result = sb.run("echo hello")
    print(result.stdout)
# container is gone
```

## Decision Tree

### 1. User wants to test a Python package

```python
from box import Box

with Box("python") as sb:
    install = sb.run("pip install <package>", timeout=120)
    if not install:
        print(f"Install failed:\n{install.stderr}")
    else:
        # Verify import
        verify = sb.run("python -c 'import <module>; print(<module>.__version__)'")
        print(verify.stdout)

        # Test CLI if applicable
        cli = sb.run("<cli-command> --help")
        if cli:
            print(cli.stdout[:300])
```

### 2. User wants to test the current project

Look for `pyproject.toml` or `setup.py` in the working directory. Mount it into the sandbox.

```python
from box import Box

with Box("python", volumes={"/pkg": "."}) as sb:
    install = sb.run("pip install /pkg", timeout=120)
    if not install:
        print(f"Install failed:\n{install.stderr}")
    else:
        sb.run("python -c 'import <module>; print(\"OK\")'")
        # Run tests if they exist
        sb.run("pip install pytest", timeout=60)
        result = sb.run("cd /pkg && python -m pytest -v", timeout=120)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
```

### 3. User wants to run a script safely

Write the script into the sandbox and execute it.

```python
from box import Box

with Box("python") as sb:
    sb.fs.write("/tmp/script.py", """<user's code here>""")
    result = sb.run("python /tmp/script.py", timeout=30)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
```

### 4. User wants to test a Node.js package or script

```python
from box import Box

with Box("node") as sb:
    sb.run("npm install <package>", timeout=120)
    result = sb.run("node -e '<test code>'")
    print(result.stdout)
```

### 5. User wants to run a shell command in isolation

```python
from box import Box

with Box("alpine") as sb:
    result = sb.run("<command>")
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
```

### 6. User wants to test across multiple Python versions

```python
from box import Box

for image in ["python:3.11-slim", "python:3.12-slim", "python:3.13-slim"]:
    with Box(image) as sb:
        ver = sb.run("python --version").stdout.strip()
        result = sb.run("<test command>", timeout=120)
        status = "PASS" if result else "FAIL"
        print(f"{ver}: {status}")
```

### 7. User wants to test with specific env vars or network restrictions

```python
from box import Box

with Box("python", network=False, envs={"MODE": "test"}) as sb:
    result = sb.run("<command>")
    print(result.stdout)
```

## Image Aliases

Pick the right image for the task:

| Task | Image |
|------|-------|
| Python anything | `python` |
| Node.js/npm | `node` |
| Shell scripts | `alpine` |
| Go code | `go` |
| Rust code | `rust` |
| Ruby code | `ruby` |
| Java code | `java` |
| AWS CLI | `aws` |
| Terraform | `terraform` |
| General Linux | `ubuntu` |

Any Docker image works: `Box("postgres:16")`, `Box("redis:7")`, etc.

## Box API Quick Reference

```python
sb = Box(image, name=None, memory="512M", network=True,
         envs={}, volumes={}, ports={}, timeout=None, workdir=None)

result = sb.run(command, timeout=30)    # RunResult
result.stdout / result.stderr / result.exit_code / bool(result)

sb.fs.write(path, content)              # write file into sandbox
sb.fs.read(path)                        # read file from sandbox
sb.fs.upload(local, remote)             # copy file in
sb.fs.download(remote, local)           # copy file out
sb.fs.exists(path) / sb.fs.list(path)

sb.kill()                               # destroy immediately
```

## Rules

1. ALWAYS use `with Box(...) as sb:` — ensures cleanup even on errors
2. Use `timeout=120` for package installs (compilation can be slow)
3. Pick the right image for the language/tool
4. Mount the current directory (`volumes={"/app": "."}`) when testing local projects
5. Show stdout AND stderr to the user
6. If install fails, show the full error — don't swallow it
7. Use `network=False` when the user wants to test offline behavior or run untrusted code
8. Report a clear summary: what was tested, pass/fail, key output
