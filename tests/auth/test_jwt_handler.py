"""Unit tests for JWT token creation and validation."""

import pytest
from datetime import timedelta
from jose import JWTError, ExpiredSignatureError

from fs_flowstate_svc.auth.jwt_handler import create_access_token, decode_token


class TestJWTHandler:
    """Test suite for JWT handler functions."""
    
    def test_create_access_token_valid_jwt(self, monkeypatch):
        """Test that create_access_token generates a valid JWT."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        data = {"sub": "test_user_id"}
        token = create_access_token(data)
        
        # Token should be non-empty string
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Should be able to decode the token
        payload = decode_token(token)
        assert payload["sub"] == "test_user_id"
        assert "exp" in payload
    
    def test_decode_token_success(self, monkeypatch):
        """Test that decode_token successfully decodes a valid token."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        test_data = {"sub": "user_123", "role": "admin"}
        token = create_access_token(test_data)
        
        payload = decode_token(token)
        
        assert payload["sub"] == "user_123"
        assert payload["role"] == "admin"
        assert "exp" in payload
    
    def test_decode_token_invalid_raises(self, monkeypatch):
        """Test that decode_token raises JWTError for invalid tokens."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        invalid_token = "invalid.token.here"
        
        with pytest.raises(JWTError):
            decode_token(invalid_token)
    
    def test_decode_token_expired_raises(self, monkeypatch):
        """Test that decode_token raises ExpiredSignatureError for expired tokens."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        data = {"sub": "test_user"}
        # Create token with negative expiration (already expired)
        expired_token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        
        with pytest.raises(ExpiredSignatureError):
            decode_token(expired_token)
    
    def test_create_access_token_custom_expiry(self, monkeypatch):
        """Test that create_access_token respects custom expiration delta."""
        # Set required environment variables
        monkeypatch.setenv("SECRET_KEY", "x" * 32)
        monkeypatch.setenv("JWT_SECRET_KEY", "y" * 32)
        
        data = {"sub": "test_user"}
        custom_expiry = timedelta(minutes=60)
        token = create_access_token(data, expires_delta=custom_expiry)
        
        payload = decode_token(token)
        
        # Token should be valid and decodable
        assert payload["sub"] == "test_user"
        assert "exp" in payload
