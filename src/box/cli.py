"""Box CLI — thin wrapper over the Box SDK."""

import os
import sys
from datetime import datetime, timezone

import click

from box.box import Box


@click.group()
@click.version_option(version="0.1.0", prog_name="box")
def main():
    """Secure, ephemeral sandboxed execution environments."""
    pass


def _parse_envs(env_list: tuple[str, ...]) -> dict[str, str]:
    """Parse -e KEY=VALUE flags into a dict."""
    envs = {}
    for item in env_list:
        if "=" in item:
            key, value = item.split("=", 1)
            envs[key] = value
        else:
            # Pull from host environment
            envs[item] = os.environ.get(item, "")
    return envs


def _parse_volumes(vol_list: tuple[str, ...]) -> dict[str, str]:
    """Parse -v HOST:CONTAINER flags into a dict."""
    volumes = {}
    for item in vol_list:
        if ":" in item:
            host, container = item.split(":", 1)
            volumes[container] = host
        else:
            # Mount at same path
            volumes[item] = item
    return volumes


def _parse_ports(port_list: tuple[str, ...]) -> dict[int, int]:
    """Parse -p HOST:CONTAINER or just CONTAINER flags."""
    ports = {}
    for item in port_list:
        if ":" in item:
            host, container = item.split(":", 1)
            ports[int(container)] = int(host)
        else:
            ports[int(item)] = 0  # auto-assign
    return ports


@main.command()
@click.argument("image")
@click.option("--name", "-n", default=None, help="Name for the sandbox")
@click.option("--memory", "-m", default="512M", help="Memory limit")
@click.option("--pids", default=256, type=int, help="Max PID count")
@click.option("--no-network", is_flag=True, help="Disable network access")
@click.option("-e", "--env", "envs", multiple=True, help="Set env var (KEY=VALUE)")
@click.option("-v", "--volume", "volumes", multiple=True, help="Mount volume (HOST:CONTAINER)")
@click.option("--port", "ports", multiple=True, help="Map port (HOST:CONTAINER or CONTAINER)")
@click.option("--timeout", "-t", type=int, default=None, help="Auto-destroy after N seconds")
@click.option("-w", "--workdir", default=None, help="Working directory inside sandbox")
def up(image, name, memory, pids, no_network, envs, volumes, ports, timeout, workdir):
    """Create a sandbox and print its ID."""
    try:
        sb = Box(
            image,
            name=name,
            memory=memory,
            pids=pids,
            network=not no_network,
            envs=_parse_envs(envs),
            volumes=_parse_volumes(volumes),
            ports=_parse_ports(ports),
            timeout=timeout,
            workdir=workdir,
        )
        click.echo(sb.id if not name else f"{sb.id} ({name})")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("image")
@click.argument("command", nargs=-1, required=True)
@click.option("--memory", "-m", default="512M")
@click.option("--no-network", is_flag=True)
@click.option("-e", "--env", "envs", multiple=True, help="Set env var (KEY=VALUE)")
@click.option("-v", "--volume", "volumes", multiple=True, help="Mount volume (HOST:CONTAINER)")
@click.option("-w", "--workdir", default=None, help="Working directory inside sandbox")
def run(image, command, memory, no_network, envs, volumes, workdir):
    """One-shot: create sandbox, run command, destroy."""
    try:
        with Box(
            image,
            memory=memory,
            network=not no_network,
            envs=_parse_envs(envs),
            volumes=_parse_volumes(volumes),
            workdir=workdir,
        ) as sb:
            result = sb.run(" ".join(command))
            if result.stdout:
                click.echo(result.stdout, nl=False)
            if result.stderr:
                click.echo(result.stderr, nl=False, err=True)
            sys.exit(result.exit_code)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command("do")
@click.argument("sandbox_id")
@click.argument("command", nargs=-1, required=True)
@click.option("--timeout", "-t", default=30, type=int, help="Command timeout in seconds")
@click.option("-e", "--env", "envs", multiple=True, help="Per-command env var (KEY=VALUE)")
def do_cmd(sandbox_id, command, timeout, envs):
    """Execute a command in an existing sandbox."""
    try:
        sb = Box.get(sandbox_id)
        result = sb.run(" ".join(command), timeout=timeout, envs=_parse_envs(envs))
        if result.stdout:
            click.echo(result.stdout, nl=False)
        if result.stderr:
            click.echo(result.stderr, nl=False, err=True)
        sys.exit(result.exit_code)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("sandbox_id")
def shell(sandbox_id):
    """Open an interactive shell in a sandbox."""
    try:
        sb = Box.get(sandbox_id)
        sb.shell()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
def ps():
    """List running sandboxes."""
    sandboxes = Box.ps()
    if not sandboxes:
        click.echo("No sandboxes running.")
        return

    click.echo(f"{'ID':<12} {'NAME':<15} {'IMAGE':<20} {'STATUS':<10} {'CREATED'}")
    click.echo("-" * 75)

    for sb in sandboxes:
        created = sb._state.created_at
        try:
            dt = datetime.fromisoformat(created)
            age = datetime.now(timezone.utc) - dt
            if age.total_seconds() < 60:
                created_str = f"{int(age.total_seconds())}s ago"
            elif age.total_seconds() < 3600:
                created_str = f"{int(age.total_seconds() / 60)}m ago"
            else:
                created_str = f"{int(age.total_seconds() / 3600)}h ago"
        except (ValueError, TypeError):
            created_str = created

        name = sb.name or "-"
        click.echo(f"{sb.id:<12} {name:<15} {sb.image:<20} {sb.status:<10} {created_str}")


@main.command()
def images():
    """List available image aliases."""
    from box.image.manager import IMAGE_ALIASES
    click.echo(f"{'ALIAS':<16} {'IMAGE'}")
    click.echo("-" * 50)
    for alias, image in sorted(IMAGE_ALIASES.items()):
        click.echo(f"{alias:<16} {image}")


@main.command()
@click.argument("sandbox_id", required=False)
@click.option("--all", "kill_all", is_flag=True, help="Kill all sandboxes")
def down(sandbox_id, kill_all):
    """Tear down sandbox(es)."""
    if kill_all:
        sandboxes = Box.ps()
        if not sandboxes:
            click.echo("No sandboxes to kill.")
            return
        Box.nuke()
        click.echo(f"Killed {len(sandboxes)} sandbox(es).")
        return

    if not sandbox_id:
        click.echo("Error: provide a sandbox ID or use --all", err=True)
        sys.exit(1)

    try:
        sb = Box.get(sandbox_id)
        sb.kill()
        click.echo(f"Killed {sb.id}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--limit", "-n", default=20, type=int, help="Number of events to show")
@click.option("--clear", is_flag=True, help="Clear all history")
def history(limit, clear):
    """Show sandbox run history."""
    from box.history import load_history, clear_history

    if clear:
        clear_history()
        click.echo("History cleared.")
        return

    events = load_history(limit)
    if not events:
        click.echo("No history yet.")
        return

    for e in events:
        ts = e["timestamp"][:19].replace("T", " ")
        sid = e["sandbox_id"]
        event = e["event"]
        parts = [f"{ts}  {sid}  {event:<10}"]

        if image := e.get("image"):
            parts.append(image)
        if cmd := e.get("command"):
            display = cmd if len(cmd) <= 60 else cmd[:57] + "..."
            parts.append(f"$ {display}")
        if (code := e.get("exit_code")) is not None:
            parts.append(f"exit={code}")
        if (ms := e.get("duration_ms")) is not None:
            if ms < 1000:
                parts.append(f"{ms}ms")
            else:
                parts.append(f"{ms / 1000:.1f}s")

        click.echo("  ".join(parts))
