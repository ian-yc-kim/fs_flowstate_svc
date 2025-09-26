"""API integration tests for inbox item to event conversion endpoint."""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from uuid import uuid4


def register_user(client, username: str, email: str, password: str) -> Dict[str, Any]:
    """Helper to register a user and return user data."""
    response = client.post("/users/register", json={
        "username": username,
        "email": email,
        "password": password
    })
    assert response.status_code == 200
    return response.json()


def login(client, username_or_email: str, password: str) -> str:
    """Helper to login and return access token."""
    response = client.post("/users/login", json={
        "username_or_email": username_or_email,
        "password": password
    })
    assert response.status_code == 200
    return response.json()["access_token"]


def get_auth_headers(token: str) -> Dict[str, str]:
    """Helper to build Authorization headers."""
    return {"Authorization": f"Bearer {token}"}


def create_inbox_item(client, headers: Dict[str, str], content: str = "Test item", category: str = "TODO") -> Dict[str, Any]:
    """Helper to create an inbox item and return the response data."""
    response = client.post("/api/inbox/", json={
        "content": content,
        "category": category,
        "priority": 3,
        "status": "PENDING"
    }, headers=headers)
    assert response.status_code == 201
    return response.json()


def create_event(client, headers: Dict[str, str], start_time: datetime, end_time: datetime, title: str = "Test Event") -> Dict[str, Any]:
    """Helper to create an event and return the response data."""
    response = client.post("/api/events/", json={
        "title": title,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat()
    }, headers=headers)
    assert response.status_code == 201
    return response.json()


class TestInboxConvertToEventAPI:
    """Integration tests for inbox item to event conversion endpoint."""
    
    def test_convert_endpoint_success_201_returns_event_and_updates_inbox(self, client):
        """Test successful conversion returns 201 with EventResponse and updates inbox item status."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create inbox item
        inbox_item = create_inbox_item(client, headers, content="Meeting with client", category="TODO")
        
        # Prepare conversion request
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        
        conversion_payload = {
            "item_id": inbox_item["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "event_title": "Client Meeting",
            "event_description": "Important discussion with client",
            "is_all_day": False,
            "is_recurring": False,
            "event_category": "WORK",
            "event_metadata": {"priority": "high", "location": "office"}
        }
        
        # Execute conversion
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload, headers=headers)
        
        # Assert response
        assert response.status_code == 201
        event_data = response.json()
        
        # Verify event properties
        assert event_data["title"] == "Client Meeting"
        assert event_data["description"] == "Important discussion with client"
        assert event_data["category"] == "WORK"
        assert event_data["is_all_day"] is False
        assert event_data["is_recurring"] is False
        assert event_data["user_id"] == user["id"]
        assert "id" in event_data
        assert "created_at" in event_data
        assert "updated_at" in event_data
        
        # Verify metadata includes both custom data and inbox item ID
        assert event_data["metadata"] is not None
        assert event_data["metadata"]["priority"] == "high"
        assert event_data["metadata"]["location"] == "office"
        assert event_data["metadata"]["converted_from_inbox_item_id"] == inbox_item["id"]
        
        # Verify inbox item status was updated to SCHEDULED
        inbox_response = client.get(f"/api/inbox/{inbox_item['id']}", headers=headers)
        assert inbox_response.status_code == 200
        updated_inbox_item = inbox_response.json()
        assert updated_inbox_item["status"] == "SCHEDULED"
    
    def test_convert_endpoint_with_defaults_uses_inbox_item_content(self, client):
        """Test conversion with minimal data uses inbox item content for defaults."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create inbox item with specific content and category
        inbox_item = create_inbox_item(client, headers, content="Review quarterly reports", category="NOTE")
        
        # Prepare minimal conversion request
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        conversion_payload = {
            "item_id": inbox_item["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
            # No event_title, event_description, event_category provided
        }
        
        # Execute conversion
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload, headers=headers)
        
        # Assert response
        assert response.status_code == 201
        event_data = response.json()
        
        # Should use inbox item content as title and description
        assert event_data["title"] == "Review quarterly reports"
        assert event_data["description"] == "Review quarterly reports"
        # Should use inbox item category as event category
        assert event_data["category"] == "NOTE"
        # Should include inbox item ID in metadata
        assert event_data["metadata"]["converted_from_inbox_item_id"] == inbox_item["id"]
    
    def test_convert_endpoint_404_for_missing_or_unowned_item(self, client):
        """Test conversion returns 404 for non-existent or unowned items."""
        # Setup
        user1 = register_user(client, "user1", "user1@example.com", "password1")
        token1 = login(client, "user1", "password1")
        headers1 = get_auth_headers(token1)
        
        user2 = register_user(client, "user2", "user2@example.com", "password2")
        token2 = login(client, "user2", "password2")
        headers2 = get_auth_headers(token2)
        
        # Test with non-existent item ID
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        random_item_id = str(uuid4())
        conversion_payload = {
            "item_id": random_item_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload, headers=headers1)
        assert response.status_code == 404
        assert "Inbox item not found or not owned" in response.json()["detail"]
        
        # Test with another user's item
        user2_item = create_inbox_item(client, headers2, content="User 2 item")
        
        conversion_payload_other_user = {
            "item_id": user2_item["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload_other_user, headers=headers1)
        assert response.status_code == 404
        assert "Inbox item not found or not owned" in response.json()["detail"]
        
        # Verify user 2's item remains unchanged
        user2_item_check = client.get(f"/api/inbox/{user2_item['id']}", headers=headers2)
        assert user2_item_check.json()["status"] == "PENDING"
    
    def test_convert_endpoint_conflict_409(self, client):
        """Test conversion returns 409 when event times conflict with existing events."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create inbox item
        inbox_item = create_inbox_item(client, headers, content="New meeting")
        
        # Create existing event that will conflict
        conflict_start = datetime.now(timezone.utc) + timedelta(hours=1)
        conflict_end = conflict_start + timedelta(hours=2)
        existing_event = create_event(client, headers, conflict_start, conflict_end, "Existing Event")
        
        # Try to convert inbox item with overlapping times
        conversion_payload = {
            "item_id": inbox_item["id"],
            "start_time": (conflict_start + timedelta(minutes=30)).isoformat(),  # Overlaps
            "end_time": (conflict_end + timedelta(minutes=30)).isoformat()
        }
        
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload, headers=headers)
        
        # Assert conflict response
        assert response.status_code == 409
        assert "Event time conflicts with existing events" in response.json()["detail"]
        
        # Verify inbox item status remains unchanged
        inbox_response = client.get(f"/api/inbox/{inbox_item['id']}", headers=headers)
        assert inbox_response.json()["status"] == "PENDING"
    
    def test_convert_endpoint_validation_errors_400(self, client):
        """Test conversion returns 400 for validation errors."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create inbox item
        inbox_item = create_inbox_item(client, headers)
        
        # Test with end_time before start_time
        start_time = datetime.now(timezone.utc) + timedelta(hours=2)
        end_time = datetime.now(timezone.utc) + timedelta(hours=1)  # Before start_time
        
        conversion_payload = {
            "item_id": inbox_item["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload, headers=headers)
        
        # Should return 400 for invalid time order
        assert response.status_code == 400
        assert "Event start time must be before end time" in response.json()["detail"]
        
        # Verify inbox item status remains unchanged
        inbox_response = client.get(f"/api/inbox/{inbox_item['id']}", headers=headers)
        assert inbox_response.json()["status"] == "PENDING"
    
    def test_convert_endpoint_missing_auth_token_403(self, client):
        """Test conversion returns 403 when no Authorization header provided."""
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        conversion_payload = {
            "item_id": str(uuid4()),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload)
        assert response.status_code == 403
    
    def test_convert_endpoint_invalid_auth_token_401(self, client):
        """Test conversion returns 401 with invalid token."""
        headers = get_auth_headers("invalid_token_123")
        
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        conversion_payload = {
            "item_id": str(uuid4()),
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload, headers=headers)
        assert response.status_code == 401
    
    def test_convert_endpoint_malformed_request_422(self, client):
        """Test conversion returns 422 for malformed request data."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test with invalid UUID format
        invalid_payload = {
            "item_id": "not-a-uuid",
            "start_time": "not-a-datetime",
            "end_time": "also-not-a-datetime"
        }
        
        response = client.post("/api/inbox/convert_to_event", json=invalid_payload, headers=headers)
        assert response.status_code == 422
    
    def test_convert_endpoint_with_all_day_event(self, client):
        """Test conversion with all-day event settings."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create inbox item
        inbox_item = create_inbox_item(client, headers, content="All day conference")
        
        # Prepare all-day conversion request
        start_date = datetime.now(timezone.utc).date() + timedelta(days=1)
        start_time = datetime.combine(start_date, datetime.min.time(), timezone.utc)
        end_time = datetime.combine(start_date, datetime.max.time().replace(microsecond=0), timezone.utc)
        
        conversion_payload = {
            "item_id": inbox_item["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "event_title": "Conference Day",
            "is_all_day": True
        }
        
        # Execute conversion
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload, headers=headers)
        
        # Assert response
        assert response.status_code == 201
        event_data = response.json()
        
        assert event_data["title"] == "Conference Day"
        assert event_data["is_all_day"] is True
        assert event_data["is_recurring"] is False  # Default value
        
        # Verify inbox item updated
        inbox_response = client.get(f"/api/inbox/{inbox_item['id']}", headers=headers)
        assert inbox_response.json()["status"] == "SCHEDULED"
    
    def test_convert_endpoint_with_recurring_event(self, client):
        """Test conversion with recurring event settings."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create inbox item
        inbox_item = create_inbox_item(client, headers, content="Weekly team meeting")
        
        # Prepare recurring conversion request
        start_time = datetime.now(timezone.utc) + timedelta(hours=1)
        end_time = start_time + timedelta(hours=1)
        
        conversion_payload = {
            "item_id": inbox_item["id"],
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "event_title": "Weekly Team Meeting",
            "is_recurring": True,
            "event_metadata": {"recurrence_pattern": "weekly"}
        }
        
        # Execute conversion
        response = client.post("/api/inbox/convert_to_event", json=conversion_payload, headers=headers)
        
        # Assert response
        assert response.status_code == 201
        event_data = response.json()
        
        assert event_data["title"] == "Weekly Team Meeting"
        assert event_data["is_recurring"] is True
        assert event_data["is_all_day"] is False  # Default value
        assert event_data["metadata"]["recurrence_pattern"] == "weekly"
        
        # Verify inbox item updated
        inbox_response = client.get(f"/api/inbox/{inbox_item['id']}", headers=headers)
        assert inbox_response.json()["status"] == "SCHEDULED"
