"""Tests for API documentation file."""

import pytest
from pathlib import Path


class TestAPIDocumentation:
    """Tests for API.md documentation file."""
    
    def test_api_md_exists(self):
        """Test that API.md file exists in project root."""
        api_md_path = Path("API.md")
        assert api_md_path.exists(), "API.md file should exist in project root"
    
    def test_api_md_contains_authentication_section(self):
        """Test that API.md contains Authentication section with required endpoints."""
        api_md_path = Path("API.md")
        content = api_md_path.read_text()
        
        # Check for Authentication section
        assert "## Authentication" in content, "API.md should contain Authentication section"
        
        # Check for all required authentication endpoints
        required_endpoints = [
            "POST /auth/register",
            "POST /auth/login", 
            "GET /auth/me",
            "POST /auth/request-password-reset",
            "POST /auth/reset-password"
        ]
        
        for endpoint in required_endpoints:
            assert endpoint in content, f"API.md should document {endpoint} endpoint"
    
    def test_api_md_contains_schema_definitions(self):
        """Test that API.md contains schema definitions."""
        api_md_path = Path("API.md")
        content = api_md_path.read_text()
        
        # Check for Schema Definitions section
        assert "## Schema Definitions" in content, "API.md should contain Schema Definitions section"
        
        # Check for required schemas
        required_schemas = [
            "### UserCreate",
            "### UserLogin",
            "### UserResponse", 
            "### Token",
            "### PasswordResetRequest",
            "### PasswordResetConfirm"
        ]
        
        for schema in required_schemas:
            assert schema in content, f"API.md should define {schema} schema"
    
    def test_api_md_contains_authentication_requirements(self):
        """Test that API.md documents authentication requirements for each endpoint."""
        api_md_path = Path("API.md")
        content = api_md_path.read_text()
        
        # Check that authentication requirements are documented
        assert "**Authentication:** None" in content, "API.md should document endpoints with no authentication"
        assert "**Authentication:** Required (Bearer Token)" in content, "API.md should document endpoints requiring Bearer token"
        
        # Check that Bearer token usage is explained
        assert "Authorization: Bearer <access_token>" in content, "API.md should show how to use Bearer tokens"
