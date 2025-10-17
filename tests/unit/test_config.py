"""Unit tests for configuration module."""


class TestConfig:
    """Test configuration loading and defaults."""

    def test_config_imports(self):
        """Test that config module can be imported."""
        from plan_manager import config

        assert config is not None

    def test_workspace_root_exists(self):
        """Test that WORKSPACE_ROOT is defined."""
        from plan_manager.config import WORKSPACE_ROOT

        assert WORKSPACE_ROOT is not None
        assert isinstance(WORKSPACE_ROOT, str)

    def test_todo_dir_exists(self):
        """Test that TODO_DIR is defined."""
        from plan_manager.config import TODO_DIR

        assert TODO_DIR is not None
        assert isinstance(TODO_DIR, str)

    def test_enable_browser_is_bool(self):
        """Test that ENABLE_BROWSER is a boolean."""
        from plan_manager.config import ENABLE_BROWSER

        assert isinstance(ENABLE_BROWSER, bool)

    def test_port_is_int(self):
        """Test that PORT is an integer."""
        from plan_manager.config import PORT

        assert isinstance(PORT, int)
        assert PORT > 0
        assert PORT < 65536

    def test_host_is_string(self):
        """Test that HOST is a string."""
        from plan_manager.config import HOST

        assert isinstance(HOST, str)
