import pytest
import logging
from fastapi import HTTPException
from pydantic import BaseModel
from fs_flowstate_svc.app import app

# Define a simple Pydantic model for validation testing
class TestModel(BaseModel):
    required_field: str

# Add test-only routes to the app for triggering exceptions
@app.get("/__test__/raise_http_error")
async def raise_http_error():
    """Test endpoint that raises HTTPException."""
    raise HTTPException(status_code=404, detail="Not Found")

@app.post("/__test__/validate")
async def validate_input(data: TestModel):
    """Test endpoint that accepts a Pydantic model to trigger validation errors."""
    return {"received": data.required_field}

@app.get("/__test__/unhandled")
async def raise_unhandled_error():
    """Test endpoint that raises an unhandled exception."""
    raise ValueError("Oops!")

class TestExceptionHandlers:
    """Test suite for centralized exception handlers."""

    def test_http_exception_handler_returns_json(self, client):
        """Test that HTTPException is handled correctly."""
        response = client.get("/__test__/raise_http_error")
        
        assert response.status_code == 404
        assert response.json() == {"detail": "Not Found"}

    def test_validation_exception_handler_returns_json(self, client):
        """Test that RequestValidationError is handled correctly."""
        response = client.post("/__test__/validate", json={})
        
        assert response.status_code == 422
        response_data = response.json()
        assert "message" in response_data
        assert response_data["message"] == "Validation Error"
        assert "detail" in response_data
        assert isinstance(response_data["detail"], list)
        assert len(response_data["detail"]) > 0

    def test_generic_exception_handler_returns_500_and_logs_critical(self, client, caplog):
        """Test that unhandled exceptions are handled correctly and logged as critical."""
        with caplog.at_level(logging.CRITICAL):
            response = client.get("/__test__/unhandled")
        
        # Verify response
        assert response.status_code == 500
        assert response.json() == {"detail": "Internal Server Error"}
        
        # Verify logging
        critical_logs = [record for record in caplog.records if record.levelno == logging.CRITICAL]
        assert len(critical_logs) > 0
        
        log_message = critical_logs[0].message
        assert "Unhandled Exception" in log_message
        assert "Oops!" in log_message

    def test_validation_exception_with_multiple_errors(self, client):
        """Test validation error handling with malformed JSON to trigger multiple validation errors."""
        # Send invalid JSON that will trigger validation errors
        response = client.post("/__test__/validate", json={"required_field": None})
        
        assert response.status_code == 422
        response_data = response.json()
        assert response_data["message"] == "Validation Error"
        assert "detail" in response_data
        assert isinstance(response_data["detail"], list)

    def test_http_exception_with_different_status_code(self, client):
        """Test HTTPException handler with different status codes."""
        # Add a temporary route for testing different status codes
        @app.get("/__test__/raise_forbidden")
        async def raise_forbidden():
            raise HTTPException(status_code=403, detail="Access Denied")
        
        response = client.get("/__test__/raise_forbidden")
        
        assert response.status_code == 403
        assert response.json() == {"detail": "Access Denied"}
