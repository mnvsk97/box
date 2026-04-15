"""Tests for the Box SDK interface."""

from box.box import Box, RunResult, FileSystem
from box.sandbox import SandboxState


class TestRunResult:
    def test_bool_success(self):
        r = RunResult(exit_code=0, stdout="ok", stderr="")
        assert bool(r) is True

    def test_bool_failure(self):
        r = RunResult(exit_code=1, stdout="", stderr="err")
        assert bool(r) is False

    def test_str(self):
        r = RunResult(exit_code=0, stdout="hello\n", stderr="")
        assert str(r) == "hello\n"


class TestSandboxState:
    def test_create_and_load(self, tmp_path, monkeypatch):
        monkeypatch.setattr("box.sandbox.sandboxes_dir", lambda: tmp_path)
        state = SandboxState(
            id="abc12345",
            pid="deadbeef1234",
            image="python:3.12",
            status="running",
        )
        state.save()
        loaded = SandboxState.load("abc12345")
        assert loaded.id == "abc12345"
        assert loaded.image == "python:3.12"
        assert loaded.pid == "deadbeef1234"

    def test_list_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("box.sandbox.sandboxes_dir", lambda: tmp_path)
        assert SandboxState.list_all() == []


class TestBoxInterface:
    """Test that the Box class has the expected public API."""

    def test_has_class_methods(self):
        assert callable(Box.ps)
        assert callable(Box.get)
        assert callable(Box.nuke)

    def test_has_instance_methods(self):
        assert callable(Box.run)
        assert callable(Box.kill)
        assert callable(Box.stop)
        assert callable(Box.start)

    def test_context_manager_protocol(self):
        assert hasattr(Box, "__enter__")
        assert hasattr(Box, "__exit__")

    def test_filesystem_interface(self):
        fs = FileSystem("test")
        assert callable(fs.read)
        assert callable(fs.write)
        assert callable(fs.list)
        assert callable(fs.exists)
        assert callable(fs.delete)
