import importlib
import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings
from pydantic import Field


class TestConfig:
    """Test configuration management using Pydantic BaseSettings."""

    def test_settings_defaults_with_required_secret(self, monkeypatch):
        """Test that default values are used when environment variables are not set."""
        # Create a test Settings class without env_file to test pure defaults
        class TestSettings(BaseSettings):
            DATABASE_URL: str = "sqlite:///:memory:"
            SERVICE_PORT: int = 8000
            OPENAI_API_KEY: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
            SECRET_KEY: str = Field(default="development_secret_key_minimum_32_chars", validation_alias="SECRET_KEY", min_length=32)
        
        # Set required SECRET_KEY
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        
        # Clear other environment variables that might interfere
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("SERVICE_PORT", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        # Create settings instance
        test_settings = TestSettings()
        
        # Verify default values are used
        assert test_settings.DATABASE_URL == "sqlite:///:memory:"
        assert test_settings.SERVICE_PORT == 8000
        assert test_settings.OPENAI_API_KEY is None
        assert test_settings.SECRET_KEY == "x" * 32

    def test_settings_from_env(self, monkeypatch):
        """Test that environment variables override default values."""
        # Set all environment variables
        test_db_url = "postgresql://test:test@localhost:5432/testdb"
        test_port = "9000"
        test_api_key = "test_openai_key"
        test_secret = "test_secret_key_at_least_32_chars"
        
        monkeypatch.setenv("DATABASE_URL", test_db_url)
        monkeypatch.setenv("SERVICE_PORT", test_port)
        monkeypatch.setenv("OPENAI_API_KEY", test_api_key)
        monkeypatch.setenv("SECRET_KEY", test_secret)
        
        # Reload config module to pick up new environment
        from fs_flowstate_svc import config
        importlib.reload(config)
        
        # Verify environment values are used
        assert config.settings.DATABASE_URL == test_db_url
        assert config.settings.SERVICE_PORT == 9000  # Should be int
        assert config.settings.OPENAI_API_KEY == test_api_key
        assert config.settings.SECRET_KEY == test_secret

    def test_secret_key_validation_missing(self, monkeypatch):
        """Test that SECRET_KEY validation fails when not provided and no default exists."""
        # Create a test Settings class that requires SECRET_KEY
        class TestSettings(BaseSettings):
            SECRET_KEY: str = Field(..., validation_alias="SECRET_KEY", min_length=32)
        
        # Clear SECRET_KEY environment variable
        monkeypatch.delenv("SECRET_KEY", raising=False)
        
        # Try to create settings - should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            TestSettings()
        
        # Verify the error is about SECRET_KEY
        errors = exc_info.value.errors()
        assert any("SECRET_KEY" in str(error) for error in errors)
        assert any(error["type"] == "missing" for error in errors)

    def test_secret_key_min_length_validation(self, monkeypatch):
        """Test that SECRET_KEY must be at least 32 characters long."""
        # Create a test Settings class that requires SECRET_KEY
        class TestSettings(BaseSettings):
            SECRET_KEY: str = Field(..., validation_alias="SECRET_KEY", min_length=32)
        
        # Set a SECRET_KEY that's too short
        monkeypatch.setenv("SECRET_KEY", "short_key")
        
        # Try to create settings - should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            TestSettings()
        
        # Verify the error is about minimum length
        errors = exc_info.value.errors()
        assert any(error["type"] == "string_too_short" for error in errors)

    def test_service_port_type_validation(self, monkeypatch):
        """Test that SERVICE_PORT is properly converted to int."""
        # Set required SECRET_KEY and SERVICE_PORT as string
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("SERVICE_PORT", "3000")
        
        # Reload config module
        from fs_flowstate_svc import config
        importlib.reload(config)
        
        # Verify SERVICE_PORT is converted to int
        assert isinstance(config.settings.SERVICE_PORT, int)
        assert config.settings.SERVICE_PORT == 3000

    def test_openai_api_key_optional(self, monkeypatch):
        """Test that OPENAI_API_KEY is optional and can be None."""
        # Set required SECRET_KEY only
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        # Reload config module
        from fs_flowstate_svc import config
        importlib.reload(config)
        
        # Verify OPENAI_API_KEY is None when not set
        assert config.settings.OPENAI_API_KEY is None
        
        # Now set it and verify it's loaded
        monkeypatch.setenv("OPENAI_API_KEY", "test_api_key")
        importlib.reload(config)
        
        assert config.settings.OPENAI_API_KEY == "test_api_key"

    def test_config_module_accessible(self):
        """Test that config module settings are accessible and have correct types."""
        from fs_flowstate_svc.config import settings
        
        # Verify settings instance exists and has expected attributes
        assert hasattr(settings, 'DATABASE_URL')
        assert hasattr(settings, 'SERVICE_PORT')
        assert hasattr(settings, 'OPENAI_API_KEY')
        assert hasattr(settings, 'SECRET_KEY')
        
        # Verify types
        assert isinstance(settings.DATABASE_URL, str)
        assert isinstance(settings.SERVICE_PORT, int)
        assert settings.OPENAI_API_KEY is None or isinstance(settings.OPENAI_API_KEY, str)
        assert isinstance(settings.SECRET_KEY, str)
        
        # Verify SECRET_KEY meets minimum length requirement
        assert len(settings.SECRET_KEY) >= 32
