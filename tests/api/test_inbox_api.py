import pytest
from datetime import datetime
from typing import Dict, Any
from uuid import uuid4
import time # Import time module


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


def create_inbox_item_payload(
    content: str = "Test inbox item",
    category: str = "TODO",
    priority: int = 3,
    status: str = "PENDING"
) -> Dict[str, Any]:
    """Helper to construct valid InboxItemCreate json payload."""
    return {
        "content": content,
        "category": category,
        "priority": priority,
        "status": status
    }


class TestInboxAPI:
    """Integration tests for inbox management endpoints."""
    
    def test_create_inbox_item_success(self, client):
        """Test successful inbox item creation."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test
        item_payload = create_inbox_item_payload(
            content="Important task",
            category="TODO",
            priority=1,
            status="PENDING"
        )
        
        response = client.post("/api/inbox/", json=item_payload, headers=headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Important task"
        assert data["category"] == "TODO"
        assert data["priority"] == 1
        assert data["status"] == "PENDING"
        assert data["user_id"] == user["id"]
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
    
    def test_create_inbox_item_with_defaults(self, client):
        """Test inbox item creation with default values."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test - only provide content, should use defaults
        item_payload = {"content": "Just content"}
        
        response = client.post("/api/inbox/", json=item_payload, headers=headers)
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Just content"
        assert data["category"] == "TODO"  # default
        assert data["priority"] == 3  # default
        assert data["status"] == "PENDING"  # default
    
    def test_create_inbox_item_empty_content(self, client):
        """Test inbox item creation fails with empty content."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test empty content
        item_payload = create_inbox_item_payload(content="")
        response = client.post("/api/inbox/", json=item_payload, headers=headers)
        assert response.status_code == 400
        assert "Content cannot be empty" in response.json()["detail"]
        
        # Test whitespace-only content
        item_payload = create_inbox_item_payload(content="   ")
        response = client.post("/api/inbox/", json=item_payload, headers=headers)
        assert response.status_code == 400
        assert "Content cannot be empty" in response.json()["detail"]
    
    def test_get_inbox_item_success(self, client):
        """Test successful inbox item retrieval."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create item
        item_payload = create_inbox_item_payload(content="Test retrieval")
        create_response = client.post("/api/inbox/", json=item_payload, headers=headers)
        created_item = create_response.json()
        
        # Test
        response = client.get(f"/api/inbox/{created_item['id']}", headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == created_item["id"]
        assert data["content"] == "Test retrieval"
        assert data["user_id"] == user["id"]
    
    def test_list_inbox_items_basic(self, client):
        """Test basic inbox item listing."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create multiple items
        items_data = [
            {"content": "First item", "category": "TODO", "priority": 1},
            {"content": "Second item", "category": "IDEA", "priority": 2},
            {"content": "Third item", "category": "NOTE", "priority": 3},
        ]
        
        created_items = []
        for item_data in items_data:
            payload = create_inbox_item_payload(**item_data)
            response = client.post("/api/inbox/", json=payload, headers=headers)
            created_items.append(response.json())
            time.sleep(0.01) # Add a small delay to ensure distinct created_at timestamps
        
        # Test - list all items
        response = client.get("/api/inbox/", headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        # Verify ordering (by created_at desc - newest first)
        assert data[0]["content"] == "Third item"  # Last created
        assert data[1]["content"] == "Second item"
        assert data[2]["content"] == "First item"  # First created
    
    def test_list_inbox_items_with_filters(self, client):
        """Test inbox item retrieval with filtering."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create multiple items with different attributes
        items_data = [
            {"content": "High priority TODO", "category": "TODO", "priority": 1, "status": "PENDING"},
            {"content": "Medium priority TODO", "category": "TODO", "priority": 3, "status": "PENDING"},
            {"content": "Low priority TODO", "category": "TODO", "priority": 5, "status": "DONE"},
            {"content": "Important IDEA", "category": "IDEA", "priority": 2, "status": "PENDING"},
            {"content": "Archived NOTE", "category": "NOTE", "priority": 4, "status": "ARCHIVED"},
        ]
        
        for item_data in items_data:
            payload = create_inbox_item_payload(**item_data)
            client.post("/api/inbox/", json=payload, headers=headers)
        
        # Test: Filter by categories (single)
        response = client.get("/api/inbox/?categories=TODO", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # 3 TODO items
        assert all(item["category"] == "TODO" for item in data)
        
        # Test: Filter by statuses (single)
        response = client.get("/api/inbox/?statuses=PENDING", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # 3 PENDING items
        assert all(item["status"] == "PENDING" for item in data)
        
        # Test: Filter by priority range
        response = client.get("/api/inbox/?priority_min=1&priority_max=3", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # priorities 1, 2, 3
        assert all(1 <= item["priority"] <= 3 for item in data)
        
        # Test: Combined filters (AND)
        response = client.get("/api/inbox/?categories=TODO&statuses=PENDING", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # 2 TODO PENDING items
        assert all(item["category"] == "TODO" and item["status"] == "PENDING" for item in data)
    
    def test_list_inbox_items_pagination(self, client):
        """Test inbox item listing with pagination."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create multiple items
        for i in range(10):
            payload = create_inbox_item_payload(content=f"Item {i+1}")
            client.post("/api/inbox/", json=payload, headers=headers)
            time.sleep(0.01) # Add a small delay
        
        # Test pagination
        response = client.get("/api/inbox/?skip=0&limit=3", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        response = client.get("/api/inbox/?skip=3&limit=3", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        response = client.get("/api/inbox/?skip=9&limit=3", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Only 1 item remaining
    
    def test_update_inbox_item_success(self, client):
        """Test successful inbox item update."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create item
        item_payload = create_inbox_item_payload(content="Original content")
        create_response = client.post("/api/inbox/", json=item_payload, headers=headers)
        created_item = create_response.json()
        
        # Test - partial update
        update_payload = {
            "content": "Updated content",
            "status": "DONE"
        }
        response = client.put(f"/api/inbox/{created_item['id']}", json=update_payload, headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated content"
        assert data["status"] == "DONE"
        assert data["category"] == "TODO"  # unchanged
        assert data["priority"] == 3  # unchanged
        # updated_at should be more recent than created_at
        assert data["updated_at"] >= data["created_at"]
    
    def test_update_inbox_item_empty_content(self, client):
        """Test inbox item update fails with empty content."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create item
        item_payload = create_inbox_item_payload(content="Original content")
        create_response = client.post("/api/inbox/", json=item_payload, headers=headers)
        created_item = create_response.json()
        
        # Test - update with empty content
        update_payload = {"content": ""}
        response = client.put(f"/api/inbox/{created_item['id']}", json=update_payload, headers=headers)
        
        assert response.status_code == 400
        assert "Content cannot be empty" in response.json()["detail"]
    
    def test_delete_inbox_item_success(self, client):
        """Test successful inbox item deletion."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create item
        item_payload = create_inbox_item_payload()
        create_response = client.post("/api/inbox/", json=item_payload, headers=headers)
        created_item = create_response.json()
        
        # Test delete
        response = client.delete(f"/api/inbox/{created_item['id']}", headers=headers)
        assert response.status_code == 204
        
        # Verify deletion - subsequent GET should return 404
        get_response = client.get(f"/api/inbox/{created_item['id']}", headers=headers)
        assert get_response.status_code == 404
    
    def test_bulk_update_status_success(self, client):
        """Test successful bulk status update."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create multiple items
        item_ids = []
        for i in range(3):
            payload = create_inbox_item_payload(content=f"Item {i+1}")
            response = client.post("/api/inbox/", json=payload, headers=headers)
            item_ids.append(response.json()["id"])
        
        # Test bulk update
        bulk_payload = {
            "item_ids": item_ids,
            "new_status": "DONE"
        }
        response = client.post("/api/inbox/bulk/status", json=bulk_payload, headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "3 items updated"
        
        # Verify status changes
        for item_id in item_ids:
            get_response = client.get(f"/api/inbox/{item_id}", headers=headers)
            item = get_response.json()
            assert item["status"] == "DONE"
    
    def test_bulk_update_status_empty_list(self, client):
        """Test bulk status update with empty item list."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test bulk update with empty list
        bulk_payload = {
            "item_ids": [],
            "new_status": "DONE"
        }
        response = client.post("/api/inbox/bulk/status", json=bulk_payload, headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "0 items updated"
    
    def test_bulk_archive_items_success(self, client):
        """Test successful bulk archiving."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Create multiple items
        item_ids = []
        for i in range(3):
            payload = create_inbox_item_payload(content=f"Item {i+1}")
            response = client.post("/api/inbox/", json=payload, headers=headers)
            item_ids.append(response.json()["id"])
        
        # Test bulk archive
        bulk_payload = {"item_ids": item_ids}
        response = client.post("/api/inbox/bulk/archive", json=bulk_payload, headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "3 items archived"
        
        # Verify items are archived
        for item_id in item_ids:
            get_response = client.get(f"/api/inbox/{item_id}", headers=headers)
            item = get_response.json()
            assert item["status"] == "ARCHIVED"
    
    def test_bulk_archive_empty_list(self, client):
        """Test bulk archive with empty item list."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test bulk archive with empty list
        bulk_payload = {"item_ids": []}
        response = client.post("/api/inbox/bulk/archive", json=bulk_payload, headers=headers)
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "0 items archived"
    
    def test_auth_missing_token_all_endpoints(self, client):
        """Test all endpoints return 403 when no Authorization header provided."""
        item_id = str(uuid4())
        
        # POST /api/inbox/
        response = client.post("/api/inbox/", json=create_inbox_item_payload())
        assert response.status_code == 403
        
        # GET /api/inbox/{item_id}
        response = client.get(f"/api/inbox/{item_id}")
        assert response.status_code == 403
        
        # GET /api/inbox/
        response = client.get("/api/inbox/")
        assert response.status_code == 403
        
        # PUT /api/inbox/{item_id}
        response = client.put(f"/api/inbox/{item_id}", json={"content": "Updated"})
        assert response.status_code == 403
        
        # DELETE /api/inbox/{item_id}
        response = client.delete(f"/api/inbox/{item_id}")
        assert response.status_code == 403
        
        # POST /api/inbox/bulk/status
        response = client.post("/api/inbox/bulk/status", json={"item_ids": [item_id], "new_status": "DONE"})
        assert response.status_code == 403
        
        # POST /api/inbox/bulk/archive
        response = client.post("/api/inbox/bulk/archive", json={"item_ids": [item_id]})
        assert response.status_code == 403
    
    def test_auth_invalid_token(self, client):
        """Test all endpoints return 401 with invalid token."""
        headers = get_auth_headers("invalid_token_123")
        item_id = str(uuid4())
        
        # POST /api/inbox/
        response = client.post("/api/inbox/", json=create_inbox_item_payload(), headers=headers)
        assert response.status_code == 401
        
        # GET /api/inbox/{item_id}
        response = client.get(f"/api/inbox/{item_id}", headers=headers)
        assert response.status_code == 401
        
        # GET /api/inbox/
        response = client.get("/api/inbox/", headers=headers)
        assert response.status_code == 401
        
        # PUT /api/inbox/{item_id}
        response = client.put(f"/api/inbox/{item_id}", json={"content": "Updated"}, headers=headers)
        assert response.status_code == 401
        
        # DELETE /api/inbox/{item_id}
        response = client.delete(f"/api/inbox/{item_id}", headers=headers)
        assert response.status_code == 401
        
        # POST /api/inbox/bulk/status
        response = client.post("/api/inbox/bulk/status", json={"item_ids": [item_id], "new_status": "DONE"}, headers=headers)
        assert response.status_code == 401
        
        # POST /api/inbox/bulk/archive
        response = client.post("/api/inbox/bulk/archive", json={"item_ids": [item_id]}, headers=headers)
        assert response.status_code == 401
    
    def test_authorization_forbidden_cross_user(self, client):
        """Test user B cannot access user A's inbox items."""
        # Setup users
        user_a = register_user(client, "usera", "a@example.com", "password")
        token_a = login(client, "usera", "password")
        headers_a = get_auth_headers(token_a)
        
        user_b = register_user(client, "userb", "b@example.com", "password")
        token_b = login(client, "userb", "password")
        headers_b = get_auth_headers(token_b)
        
        # User A creates an inbox item
        item_payload = create_inbox_item_payload(content="User A item")
        create_response = client.post("/api/inbox/", json=item_payload, headers=headers_a)
        assert create_response.status_code == 201
        item_id = create_response.json()["id"]
        
        # User B attempts to access User A's item
        get_response = client.get(f"/api/inbox/{item_id}", headers=headers_b)
        assert get_response.status_code == 404
        assert "Inbox item not found or not owned" in get_response.json()["detail"]
        
        # User B attempts to update User A's item
        update_response = client.put(f"/api/inbox/{item_id}", json={"content": "Hacked"}, headers=headers_b)
        assert update_response.status_code == 404
        assert "Inbox item not found or not owned" in update_response.json()["detail"]
        
        # User B attempts to delete User A's item
        delete_response = client.delete(f"/api/inbox/{item_id}", headers=headers_b)
        assert delete_response.status_code == 404
        assert "Inbox item not found or not owned" in delete_response.json()["detail"]
        
        # User B attempts bulk operations with User A's item ID
        bulk_status_response = client.post("/api/inbox/bulk/status", json={"item_ids": [item_id], "new_status": "DONE"}, headers=headers_b)
        assert bulk_status_response.status_code == 200
        assert bulk_status_response.json()["message"] == "0 items updated"  # Should ignore items not owned
        
        bulk_archive_response = client.post("/api/inbox/bulk/archive", json={"item_ids": [item_id]}, headers=headers_b)
        assert bulk_archive_response.status_code == 200
        assert bulk_archive_response.json()["message"] == "0 items archived"  # Should ignore items not owned
    
    def test_bulk_operations_mixed_ownership(self, client):
        """Test bulk operations only affect user's own items."""
        # Setup users
        user_a = register_user(client, "usera", "a@example.com", "password")
        token_a = login(client, "usera", "password")
        headers_a = get_auth_headers(token_a)
        
        user_b = register_user(client, "userb", "b@example.com", "password")
        token_b = login(client, "userb", "password")
        headers_b = get_auth_headers(token_b)
        
        # User A creates items
        item_a1_response = client.post("/api/inbox/", json=create_inbox_item_payload(content="A item 1"), headers=headers_a)
        item_a2_response = client.post("/api/inbox/", json=create_inbox_item_payload(content="A item 2"), headers=headers_a)
        item_a1_id = item_a1_response.json()["id"]
        item_a2_id = item_a2_response.json()["id"]
        
        # User B creates items
        item_b1_response = client.post("/api/inbox/", json=create_inbox_item_payload(content="B item 1"), headers=headers_b)
        item_b2_response = client.post("/api/inbox/", json=create_inbox_item_payload(content="B item 2"), headers=headers_b)
        item_b1_id = item_b1_response.json()["id"]
        item_b2_id = item_b2_response.json()["id"]
        
        # User A attempts bulk operation with mixed item IDs (including B's items)
        mixed_ids = [item_a1_id, item_a2_id, item_b1_id, item_b2_id]
        bulk_response = client.post("/api/inbox/bulk/status", json={"item_ids": mixed_ids, "new_status": "DONE"}, headers=headers_a)
        
        # Should only update User A's items (2 items)
        assert bulk_response.status_code == 200
        assert bulk_response.json()["message"] == "2 items updated"
        
        # Verify only User A's items were updated
        a1_response = client.get(f"/api/inbox/{item_a1_id}", headers=headers_a)
        a2_response = client.get(f"/api/inbox/{item_a2_id}", headers=headers_a)
        assert a1_response.json()["status"] == "DONE"
        assert a2_response.json()["status"] == "DONE"
        
        # Verify User B's items were not updated
        b1_response = client.get(f"/api/inbox/{item_b1_id}", headers=headers_b)
        b2_response = client.get(f"/api/inbox/{item_b2_id}", headers=headers_b)
        assert b1_response.json()["status"] == "PENDING"  # unchanged
        assert b2_response.json()["status"] == "PENDING"  # unchanged
    
    def test_not_found(self, client):
        """Test 404 responses for non-existent inbox items."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        random_uuid = str(uuid4())
        
        # GET non-existent item
        response = client.get(f"/api/inbox/{random_uuid}", headers=headers)
        assert response.status_code == 404
        assert "Inbox item not found or not owned" in response.json()["detail"]
        
        # UPDATE non-existent item
        response = client.put(f"/api/inbox/{random_uuid}", json={"content": "Updated"}, headers=headers)
        assert response.status_code == 404
        assert "Inbox item not found or not owned" in response.json()["detail"]
        
        # DELETE non-existent item
        response = client.delete(f"/api/inbox/{random_uuid}", headers=headers)
        assert response.status_code == 404
        assert "Inbox item not found or not owned" in response.json()["detail"]
    
    def test_validation_invalid_enums(self, client):
        """Test validation errors for invalid enum values."""
        # Setup
        user = register_user(client, "testuser", "test@example.com", "testpass")
        token = login(client, "testuser", "testpass")
        headers = get_auth_headers(token)
        
        # Test invalid category
        item_payload = create_inbox_item_payload(category="INVALID_CATEGORY")
        response = client.post("/api/inbox/", json=item_payload, headers=headers)
        assert response.status_code == 422  # Unprocessable Entity for validation errors
        
        # Test invalid status
        item_payload = create_inbox_item_payload(status="INVALID_STATUS")
        response = client.post("/api/inbox/", json=item_payload, headers=headers)
        assert response.status_code == 422
        
        # Test invalid priority (out of range)
        item_payload = create_inbox_item_payload(priority=10)
        response = client.post("/api/inbox/", json=item_payload, headers=headers)
        assert response.status_code == 422
    
    def test_user_isolation_list_endpoint(self, client):
        """Test that list endpoint only returns user's own items."""
        # Setup users
        user_a = register_user(client, "usera", "a@example.com", "password")
        token_a = login(client, "usera", "password")
        headers_a = get_auth_headers(token_a)
        
        user_b = register_user(client, "userb", "b@example.com", "password")
        token_b = login(client, "userb", "password")
        headers_b = get_auth_headers(token_b)
        
        # User A creates 2 items
        for i in range(2):
            payload = create_inbox_item_payload(content=f"User A item {i+1}")
            client.post("/api/inbox/", json=payload, headers=headers_a)
        
        # User B creates 3 items
        for i in range(3):
            payload = create_inbox_item_payload(content=f"User B item {i+1}")
            client.post("/api/inbox/", json=payload, headers=headers_b)
        
        # User A should only see their own items
        response_a = client.get("/api/inbox/", headers=headers_a)
        assert response_a.status_code == 200
        data_a = response_a.json()
        assert len(data_a) == 2
        assert all("User A" in item["content"] for item in data_a)
        
        # User B should only see their own items
        response_b = client.get("/api/inbox/", headers=headers_b)
        assert response_b.status_code == 200
        data_b = response_b.json()
        assert len(data_b) == 3
        assert all("User B" in item["content"] for item in data_b)
