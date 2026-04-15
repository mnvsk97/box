---
name: test-pkg
description: Test Python packages in a clean isolated sandbox. Simulates a fresh install — exactly what a new user would experience.
allowed-tools: Bash(python*) Bash(pip*) Bash(box*)
---

# Test Package in Isolation

Test a Python package in a fresh, isolated sandbox. Simulates what a brand new user would experience: clean Python, no pre-installed packages, install from scratch.

## When to use

- User says "test this package", "try installing X", "check if this works"
- User wants to verify a PyPI package installs and imports correctly
- User wants to test their own package in a clean environment
- User wants to test across Python versions

## How to test a PyPI package

```python
from box import Box

with Box("python") as sb:
    # Install
    install = sb.run("pip install <package>", timeout=120)
    if not install:
        print(f"INSTALL FAILED:\n{install.stderr}")
        return
    
    # Verify import
    verify = sb.run("python -c 'import <module>; print(<module>.__version__)'")
    print(f"Version: {verify.stdout.strip()}")
    
    # Test CLI (if applicable)
    cli = sb.run("<cli-name> --help")
    if cli:
        print(f"CLI works: {cli.stdout[:200]}")
```

## How to test the current project

If the current directory has `pyproject.toml` or `setup.py`:

```python
from box import Box

with Box("python", volumes={"/pkg": "."}) as sb:
    # Install from local source
    install = sb.run("pip install /pkg", timeout=120)
    if not install:
        print(f"INSTALL FAILED:\n{install.stderr}")
        return
    
    # Verify
    sb.run("python -c 'import <module>; print(\"OK\")'")
    
    # Run tests if they exist
    sb.run("cd /pkg && pip install pytest && python -m pytest", timeout=120)
```

## How to test a wheel or sdist

```python
from box import Box

with Box("python") as sb:
    sb.fs.upload("./dist/mypackage-0.1.0.whl", "/tmp/pkg.whl")
    sb.run("pip install /tmp/pkg.whl", timeout=60)
    sb.run("python -c 'import mypackage; print(mypackage.__version__)'")
```

## How to test across Python versions

```python
from box import Box

for version in ["python:3.11-slim", "python:3.12-slim", "python:3.13-slim"]:
    print(f"\n--- Testing on {version} ---")
    with Box(version) as sb:
        pyver = sb.run("python --version").stdout.strip()
        install = sb.run("pip install <package>", timeout=120)
        status = "OK" if install else "FAILED"
        print(f"{pyver}: {status}")
```

## How to test a CLI tool

```python
from box import Box

with Box("python") as sb:
    sb.run("pip install ruff", timeout=60)
    
    # Check version
    print(sb.run("ruff --version").stdout)
    
    # Test on sample code
    sb.fs.write("/tmp/test.py", "import os\nimport sys\nimport os\n")
    result = sb.run("ruff check /tmp/test.py")
    print(result.stdout or result.stderr)
```

## Rules

- ALWAYS use `with Box(...) as sb:` for auto-cleanup
- Use `timeout=120` for pip install — compilation can be slow
- Show full error output when installs fail
- If current dir has pyproject.toml/setup.py, suggest testing it as a local package
- Report: Python version, install result, import result, version number, warnings
- For security testing, use `network=False` after install to test offline behavior
