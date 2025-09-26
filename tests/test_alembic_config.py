import pytest
from unittest.mock import patch
from fs_flowstate_svc.config import settings, Settings


class TestAlembicConfiguration:
    """Test database configuration access for Alembic env.py."""

    def test_settings_database_url_access(self):
        """Test that settings.DATABASE_URL can be accessed successfully."""
        # This tests the basic functionality that env.py relies on
        database_url = settings.DATABASE_URL
        assert isinstance(database_url, str)
        assert len(database_url) > 0

    def test_settings_with_custom_database_url(self):
        """Test that a custom DATABASE_URL is properly accessible."""
        test_url = "postgresql://test:test@localhost:5432/test_db"
        test_secret = "x" * 32  # Valid 32-character secret key
        
        test_settings = Settings(
            DATABASE_URL=test_url,
            SECRET_KEY=test_secret
        )
        
        assert test_settings.DATABASE_URL == test_url
        assert isinstance(test_settings.DATABASE_URL, str)

    def test_settings_with_sqlite_database_url(self):
        """Test that SQLite DATABASE_URL is properly accessible."""
        test_url = "sqlite:///./test.db"
        test_secret = "x" * 32  # Valid 32-character secret key
        
        test_settings = Settings(
            DATABASE_URL=test_url,
            SECRET_KEY=test_secret
        )
        
        assert test_settings.DATABASE_URL == test_url
        assert test_settings.DATABASE_URL.startswith("sqlite:")

    @patch('fs_flowstate_svc.config.Settings')
    def test_settings_import_works(self, mock_settings_class):
        """Test that the settings import used by env.py works."""
        # This verifies the import path that env.py uses
        from fs_flowstate_svc.config import settings
        
        # Just verify we can import it - the actual settings object
        # will be the real one, not the mock, but this confirms
        # the import path works
        assert settings is not None

    def test_database_url_non_empty(self):
        """Test that DATABASE_URL is not empty (required for Alembic)."""
        # Alembic will fail if DATABASE_URL is empty, so this is important
        database_url = settings.DATABASE_URL
        assert database_url.strip() != ""
        assert database_url is not None
