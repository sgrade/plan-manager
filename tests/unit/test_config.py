# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

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

    def test_allowed_hosts_include_docker_host(self):
        """Sibling containers reach the server via host.docker.internal by default."""
        from plan_manager.config import ALLOWED_HOSTS

        assert "host.docker.internal:*" in ALLOWED_HOSTS

    def test_env_list_parsing(self, monkeypatch):
        """_env_list splits on commas, trims, and drops empties."""
        from plan_manager.config import _env_list

        monkeypatch.setenv("PM_TEST_LIST", " a:* , b ,, c ")
        assert _env_list("PM_TEST_LIST", ["x"]) == ["a:*", "b", "c"]

    def test_env_list_default_when_unset(self, monkeypatch):
        """_env_list returns the default when the variable is unset."""
        from plan_manager.config import _env_list

        monkeypatch.delenv("PM_TEST_LIST_MISSING", raising=False)
        assert _env_list("PM_TEST_LIST_MISSING", ["d"]) == ["d"]
