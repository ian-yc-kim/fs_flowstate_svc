"""Integration tests for event API endpoints."""

import pytest
from datetime import datetime, timezone, date
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


def create_event_payload(
    title: str = "Test Event",
    description: str = "Test Description", 
    start_time: str = "2024-01-15T10:00:00Z",
    end_time: str = "2024-01-15T11:00:00Z",
    category: str = "work",
    is_all_day: bool = False,
    is_recurring: bool = False,
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Helper to construct valid EventCreate json payload."""
    payload = {
        "title": title,
        "description": description,
        "start_time": start_time,
        "end_time": end_time,
        "category": category,
        "is_all_day": is_all_day,
        "is_recurring": is_recurring
    }
    if metadata is not None:
        payload["metadata"] = metadata
    return payload


class TestEventAPI:
    """Integration tests for event management endpoints."""
    
    def test_create_event_success(self, client):
        """Test successful event creation."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test
        event_payload = create_event_payload(
            title="Meeting",
            description="Team sync",
            start_time="2024-01-15T10:00:00Z",
            end_time="2024-01-15T11:00:00Z",
            category="work",
            metadata={"priority": "high"}
        )
        
        response = client.post("/api/events/", json=event_payload, headers=headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "Meeting"
        assert data["description"] == "Team sync"
        assert data["category"] == "work"
        assert data["user_id"] == user["id"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["metadata"]["priority"] == "high"
    
    def test_get_event_success(self, client):
        """Test successful event retrieval."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create event
        event_payload = create_event_payload(title="Test Event")
        create_response = client.post("/api/events/", json=event_payload, headers=headers)
        created_event = create_response.json()
        
        # Test
        response = client.get(f"/api/events/{created_event['id']}", headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_event["id"]
        assert data["title"] == "Test Event"
        assert data["user_id"] == user["id"]
    
    def test_get_events_with_filters(self, client):
        """Test event retrieval with filtering."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create multiple events
        events_data = [
            {"title": "Work Event 1", "category": "work", "start_time": "2024-01-15T10:00:00Z", "end_time": "2024-01-15T11:00:00Z"},
            {"title": "Work Event 2", "category": "work", "start_time": "2024-01-16T10:00:00Z", "end_time": "2024-01-16T11:00:00Z"},
            {"title": "Personal Event", "category": "personal", "start_time": "2024-01-17T10:00:00Z", "end_time": "2024-01-17T11:00:00Z"},
            {"title": "Future Event", "category": "work", "start_time": "2024-02-15T10:00:00Z", "end_time": "2024-02-15T11:00:00Z"},
        ]
        
        for event_data in events_data:
            payload = create_event_payload(**event_data)
            client.post("/api/events/", json=payload, headers=headers)
        
        # Test: Filter by category
        response = client.get("/api/events/?category=work", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # 3 work events
        assert all(event["category"] == "work" for event in data)
        
        # Test: Filter by date range
        response = client.get("/api/events/?start_date=2024-01-15&end_date=2024-01-17", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # Events on 15th, 16th, 17th
        
        # Test: Filter by category and date range
        response = client.get("/api/events/?category=work&start_date=2024-01-15&end_date=2024-01-17", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # 2 work events in date range
        
        # Verify ordering (by start_time ascending)
        assert data[0]["title"] == "Work Event 1"
        assert data[1]["title"] == "Work Event 2"
    
    def test_update_event_success(self, client):
        """Test successful event update."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create event
        event_payload = create_event_payload(title="Original Title")
        create_response = client.post("/api/events/", json=event_payload, headers=headers)
        created_event = create_response.json()
        
        # Test
        update_payload = {
            "title": "Updated Title",
            "start_time": "2024-01-15T14:00:00Z",
            "end_time": "2024-01-15T15:00:00Z"
        }
        response = client.put(f"/api/events/{created_event['id']}", json=update_payload, headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert "2024-01-15T14:00:00" in data["start_time"]
        assert "2024-01-15T15:00:00" in data["end_time"]
    
    def test_delete_event_success(self, client):
        """Test successful event deletion."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create event
        event_payload = create_event_payload()
        create_response = client.post("/api/events/", json=event_payload, headers=headers)
        created_event = create_response.json()
        
        # Test delete
        response = client.delete(f"/api/events/{created_event['id']}", headers=headers)
        assert response.status_code == 204
        
        # Verify deletion - subsequent GET should return 404
        get_response = client.get(f"/api/events/{created_event['id']}", headers=headers)
        assert get_response.status_code == 404
    
    def test_auth_missing_token_all_endpoints(self, client):
        """Test all endpoints return 403 when no Authorization header provided."""
        event_id = str(uuid4())
        
        # POST /api/events/
        response = client.post("/api/events/", json=create_event_payload())
        assert response.status_code == 403
        
        # GET /api/events/{event_id}
        response = client.get(f"/api/events/{event_id}")
        assert response.status_code == 403
        
        # GET /api/events/
        response = client.get("/api/events/")
        assert response.status_code == 403
        
        # PUT /api/events/{event_id}
        response = client.put(f"/api/events/{event_id}", json={"title": "Updated"})
        assert response.status_code == 403
        
        # DELETE /api/events/{event_id}
        response = client.delete(f"/api/events/{event_id}")
        assert response.status_code == 403
    
    def test_auth_invalid_token(self, client):
        """Test all endpoints return 401 with invalid token."""
        headers = get_auth_headers("invalid_token_123")
        event_id = str(uuid4())
        
        # POST /api/events/
        response = client.post("/api/events/", json=create_event_payload(), headers=headers)
        assert response.status_code == 401
        
        # GET /api/events/{event_id}
        response = client.get(f"/api/events/{event_id}", headers=headers)
        assert response.status_code == 401
        
        # GET /api/events/
        response = client.get("/api/events/", headers=headers)
        assert response.status_code == 401
        
        # PUT /api/events/{event_id}
        response = client.put(f"/api/events/{event_id}", json={"title": "Updated"}, headers=headers)
        assert response.status_code == 401
        
        # DELETE /api/events/{event_id}
        response = client.delete(f"/api/events/{event_id}", headers=headers)
        assert response.status_code == 401
    
    def test_authorization_forbidden_cross_user(self, client):
        """Test user B cannot access user A's events."""
        # Setup users
        user_a = register_user(client, "usera", "a@example.com", "password")
        token_a = login(client, "usera", "password")
        headers_a = get_auth_headers(token_a)
        
        user_b = register_user(client, "userb", "b@example.com", "password")
        token_b = login(client, "userb", "password")
        headers_b = get_auth_headers(token_b)
        
        # User A creates an event
        event_payload = create_event_payload(title="User A Event")
        create_response = client.post("/api/events/", json=event_payload, headers=headers_a)
        assert create_response.status_code == 201
        event_id = create_response.json()["id"]
        
        # User B attempts to access User A's event
        get_response = client.get(f"/api/events/{event_id}", headers=headers_b)
        assert get_response.status_code == 403
        assert "Access forbidden" in get_response.json()["detail"]
        
        # User B attempts to update User A's event
        update_response = client.put(f"/api/events/{event_id}", json={"title": "Hacked"}, headers=headers_b)
        assert update_response.status_code == 403
        assert "Access forbidden" in update_response.json()["detail"]
        
        # User B attempts to delete User A's event
        delete_response = client.delete(f"/api/events/{event_id}", headers=headers_b)
        assert delete_response.status_code == 403
        assert "Access forbidden" in delete_response.json()["detail"]
    
    def test_validation_error_time_order(self, client):
        """Test validation error when end time is before start time."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test invalid time order
        event_payload = create_event_payload(
            start_time="2024-01-15T15:00:00Z",  # Later time
            end_time="2024-01-15T10:00:00Z"    # Earlier time
        )
        
        response = client.post("/api/events/", json=event_payload, headers=headers)
        assert response.status_code == 400
        assert "start time must be before end time" in response.json()["detail"]
    
    def test_conflict_detection(self, client):
        """Test conflict detection for overlapping events."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create first event
        event1_payload = create_event_payload(
            title="First Event",
            start_time="2024-01-15T10:00:00Z",
            end_time="2024-01-15T12:00:00Z"
        )
        response1 = client.post("/api/events/", json=event1_payload, headers=headers)
        assert response1.status_code == 201
        
        # Try to create overlapping event
        event2_payload = create_event_payload(
            title="Overlapping Event",
            start_time="2024-01-15T11:00:00Z",  # Overlaps with first event
            end_time="2024-01-15T13:00:00Z"
        )
        response2 = client.post("/api/events/", json=event2_payload, headers=headers)
        assert response2.status_code == 409
        assert "conflicts with existing events" in response2.json()["detail"]
    
    def test_all_day_normalization_rounding(self, client):
        """Test all-day event time normalization."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create all-day event
        event_payload = create_event_payload(
            title="All Day Event",
            start_time="2024-01-15T14:30:00Z",  # Mid-day time
            end_time="2024-01-15T16:45:00Z",    # Mid-day time
            is_all_day=True
        )
        
        response = client.post("/api/events/", json=event_payload, headers=headers)
        assert response.status_code == 201
        data = response.json()
        
        # Verify normalization: should be 00:00:00 to 23:59:59
        assert "00:00:00" in data["start_time"]
        assert "23:59:59" in data["end_time"]
        assert data["is_all_day"] is True
    
    def test_not_found(self, client):
        """Test 404 responses for non-existent events."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        random_uuid = str(uuid4())
        
        # GET non-existent event
        response = client.get(f"/api/events/{random_uuid}", headers=headers)
        assert response.status_code == 404
        assert "Event not found" in response.json()["detail"]
        
        # UPDATE non-existent event
        response = client.put(f"/api/events/{random_uuid}", json={"title": "Updated"}, headers=headers)
        assert response.status_code == 404
        assert "Event not found" in response.json()["detail"]
        
        # DELETE non-existent event
        response = client.delete(f"/api/events/{random_uuid}", headers=headers)
        assert response.status_code == 404
        assert "Event not found" in response.json()["detail"]
    
    def test_validation_empty_title(self, client):
        """Test validation error for empty event title."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test empty title
        event_payload = create_event_payload(title="")
        response = client.post("/api/events/", json=event_payload, headers=headers)
        assert response.status_code == 400
        assert "title cannot be empty" in response.json()["detail"]
        
        # Test whitespace-only title
        event_payload = create_event_payload(title="   ")
        response = client.post("/api/events/", json=event_payload, headers=headers)
        assert response.status_code == 400
        assert "title cannot be empty" in response.json()["detail"]
    
    def test_iso8601_datetime_handling(self, client):
        """Test handling of ISO 8601 datetime strings with and without timezone."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test with UTC timezone
        event_payload = create_event_payload(
            title="UTC Event",
            start_time="2024-01-15T10:00:00Z",
            end_time="2024-01-15T11:00:00Z"
        )
        response = client.post("/api/events/", json=event_payload, headers=headers)
        assert response.status_code == 201
        
        # Test with offset timezone
        event_payload = create_event_payload(
            title="Offset Event",
            start_time="2024-01-16T10:00:00+05:00",
            end_time="2024-01-16T11:00:00+05:00"
        )
        response = client.post("/api/events/", json=event_payload, headers=headers)
        assert response.status_code == 201
        
        # Test with naive datetime (should be treated as UTC)
        event_payload = create_event_payload(
            title="Naive Event",
            start_time="2024-01-17T10:00:00",
            end_time="2024-01-17T11:00:00"
        )
        response = client.post("/api/events/", json=event_payload, headers=headers)
        assert response.status_code == 201
