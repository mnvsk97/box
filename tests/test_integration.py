"""Integration tests — require Docker to be running.

Run with: pytest tests/test_integration.py -v
"""

import shutil
import subprocess

import pytest

from box.box import Box, RunResult


def docker_available():
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not docker_available(),
    reason="Docker daemon not running",
)


class TestBoxLifecycle:
    def test_create_and_kill(self):
        sb = Box("alpine:latest", memory="64M")
        assert sb.status == "running"
        assert len(sb.id) == 8
        sb.kill()
        assert sb.status == "dead"

    def test_context_manager(self):
        with Box("alpine:latest") as sb:
            assert sb.status == "running"
            sandbox_id = sb.id
        # Should be killed after exiting context
        assert sb.status == "dead"

    def test_run_command(self):
        with Box("alpine:latest") as sb:
            result = sb.run("echo hello")
            assert result.exit_code == 0
            assert result.stdout.strip() == "hello"
            assert bool(result) is True

    def test_run_failing_command(self):
        with Box("alpine:latest") as sb:
            result = sb.run("false")
            assert result.exit_code != 0
            assert bool(result) is False

    def test_run_multiline(self):
        with Box("alpine:latest") as sb:
            result = sb.run("echo line1 && echo line2")
            assert "line1" in result.stdout
            assert "line2" in result.stdout

    def test_no_network(self):
        with Box("alpine:latest", network=False) as sb:
            result = sb.run("wget -q -O- http://example.com 2>&1 || echo 'no network'")
            assert "no network" in result.stdout

    def test_filesystem_ops(self):
        with Box("alpine:latest") as sb:
            sb.fs.write("/tmp/test.txt", "hello box")
            content = sb.fs.read("/tmp/test.txt")
            assert content == "hello box"
            assert sb.fs.exists("/tmp/test.txt")
            files = sb.fs.list("/tmp")
            assert "test.txt" in files

    def test_stop_and_start(self):
        sb = Box("alpine:latest")
        try:
            sb.stop()
            assert sb.status == "stopped"
            sb.start()
            assert sb.status == "running"
            result = sb.run("echo alive")
            assert result.stdout.strip() == "alive"
        finally:
            sb.kill()

    def test_ps_and_get(self):
        sb = Box("alpine:latest")
        try:
            sandboxes = Box.ps()
            assert any(s.id == sb.id for s in sandboxes)

            found = Box.get(sb.id[:4])
            assert found.id == sb.id
        finally:
            sb.kill()

    def test_nuke(self):
        sb1 = Box("alpine:latest")
        sb2 = Box("alpine:latest")
        Box.nuke()
        sandboxes = Box.ps()
        assert not any(s.id in (sb1.id, sb2.id) for s in sandboxes)
