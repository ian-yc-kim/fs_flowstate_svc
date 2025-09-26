"""Unit tests for password hashing and verification utilities."""

import pytest
from fs_flowstate_svc.auth.security import hash_password, verify_password


class TestSecurity:
    """Test suite for security functions."""
    
    def test_hash_password_returns_bcrypt_hash(self):
        """Test that hash_password returns a valid bcrypt hash."""
        password = "test_password_123"
        hashed = hash_password(password)
        
        # Bcrypt hashes should start with $2b$ or $2a$
        assert hashed.startswith(("$2b$", "$2a$"))
        # Hash should be different from original password
        assert hashed != password
        # Hash should be non-empty string
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_verify_password_true_for_correct(self):
        """Test that verify_password returns True for correct password."""
        password = "correct_password_456"
        hashed = hash_password(password)
        
        result = verify_password(password, hashed)
        assert result is True
    
    def test_verify_password_false_for_incorrect(self):
        """Test that verify_password returns False for incorrect password."""
        correct_password = "correct_password_789"
        wrong_password = "wrong_password_123"
        hashed = hash_password(correct_password)
        
        result = verify_password(wrong_password, hashed)
        assert result is False
    
    def test_hash_password_different_results_for_same_input(self):
        """Test that hash_password returns different hashes for same input (due to salt)."""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        # Should be different due to random salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)
