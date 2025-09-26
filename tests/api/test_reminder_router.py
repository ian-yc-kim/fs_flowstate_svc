"""Unit tests for reminder router."""

import pytest
import asyncio
from fastapi import APIRouter
from fs_flowstate_svc.api.reminder_router import reminder_router, read_reminders


class TestReminderRouter:
    """Test cases for reminder router configuration and endpoints."""
    
    def test_module_importability(self):
        """Test that the reminder router module can be imported successfully."""
        from fs_flowstate_svc.api.reminder_router import reminder_router
        assert reminder_router is not None
    
    def test_router_is_api_router_instance(self):
        """Test that reminder_router is an instance of APIRouter."""
        assert isinstance(reminder_router, APIRouter)
    
    def test_router_prefix(self):
        """Test that router has correct prefix."""
        assert reminder_router.prefix == "/reminders"
    
    def test_router_tags(self):
        """Test that router has correct tags."""
        assert "Reminders" in reminder_router.tags
    
    def test_get_route_exists(self):
        """Test that GET route exists at root path."""
        # Check if the GET route exists by inspecting the router's routes
        routes = reminder_router.routes
        # Look for APIRoute objects with GET method at the prefixed path
        get_routes = []
        for route in routes:
            if hasattr(route, 'methods') and 'GET' in route.methods:
                # The route path should be /reminders/ (prefix + root)
                if hasattr(route, 'path') and route.path == '/reminders/':
                    get_routes.append(route)
        
        assert len(get_routes) > 0, f"No GET route found at path '/reminders/'. Available routes: {[(getattr(route, 'path', 'no path attr'), getattr(route, 'methods', 'no methods')) for route in routes]}"
    
    def test_read_reminders_function_call(self):
        """Test that read_reminders function returns expected placeholder data."""
        result = asyncio.run(read_reminders())
        expected = [{"message": "Placeholder for reminder list"}]
        assert result == expected
    
    def test_read_reminders_return_type(self):
        """Test that read_reminders is an async function."""
        import inspect
        assert inspect.iscoroutinefunction(read_reminders)
