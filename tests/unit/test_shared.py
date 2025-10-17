"""Unit tests for shared service utilities."""

import pytest
from plan_manager.services.shared import generate_slug, ensure_unique_id_from_set


class TestGenerateSlug:
    """Test slug generation from titles."""

    def test_simple_title(self):
        """Test slug generation from simple title."""
        result = generate_slug("Simple Title")
        assert result == "simple_title"

    def test_title_with_special_chars(self):
        """Test that special characters are removed."""
        result = generate_slug("Title with Special!@#$ Characters")
        assert "!" not in result
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result

    def test_title_with_multiple_spaces(self):
        """Test that multiple spaces are collapsed."""
        result = generate_slug("Title    with    spaces")
        assert result == "title_with_spaces"

    def test_title_with_hyphens(self):
        """Test that hyphens are converted to underscores."""
        result = generate_slug("Title-with-hyphens")
        assert result == "title_with_hyphens"

    def test_title_with_underscores(self):
        """Test underscore handling."""
        result = generate_slug("Title_with_underscores")
        assert "_" in result or "-" in result

    def test_empty_title(self):
        """Test empty title raises ValueError."""
        with pytest.raises(ValueError, match="Title cannot be empty"):
            generate_slug("")

    def test_unicode_title(self):
        """Test Unicode character handling."""
        result = generate_slug("Title with Üñíçödé")
        assert result is not None
        assert len(result) > 0


class TestEnsureUniqueId:
    """Test unique ID generation."""

    def test_unique_id_no_collision(self):
        """Test that unique ID is returned when no collision."""
        result = ensure_unique_id_from_set("test-id", {"other-id"})
        assert result == "test-id"

    def test_unique_id_with_collision(self):
        """Test that unique ID is generated on collision."""
        result = ensure_unique_id_from_set("test-id", {"test-id"})
        assert result != "test-id"
        assert result.startswith("test-id")

    def test_unique_id_with_multiple_collisions(self):
        """Test multiple collision handling."""
        existing = {"test-id", "test-id-2", "test-id-3"}
        result = ensure_unique_id_from_set("test-id", existing)
        assert result not in existing
        assert result.startswith("test-id")

    def test_unique_id_empty_set(self):
        """Test with empty set of existing IDs."""
        result = ensure_unique_id_from_set("test-id", set())
        assert result == "test-id"

    def test_unique_id_preserves_original(self):
        """Test that original ID is preserved when possible."""
        result = ensure_unique_id_from_set("unique-id", {"other-1", "other-2"})
        assert result == "unique-id"
