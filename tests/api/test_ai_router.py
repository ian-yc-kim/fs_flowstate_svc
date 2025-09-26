"""Unit tests for ai router."""

import pytest
import asyncio
from fastapi import APIRouter
from fs_flowstate_svc.api.ai_router import ai_router, read_ai_status


class TestAiRouter:
    """Test cases for ai router configuration and endpoints."""
    
    def test_module_importability(self):
        """Test that the ai router module can be imported successfully."""
        from fs_flowstate_svc.api.ai_router import ai_router
        assert ai_router is not None
    
    def test_router_is_api_router_instance(self):
        """Test that ai_router is an instance of APIRouter."""
        assert isinstance(ai_router, APIRouter)
    
    def test_router_prefix(self):
        """Test that router has correct prefix."""
        assert ai_router.prefix == "/ai"
    
    def test_router_tags(self):
        """Test that router has correct tags."""
        assert ai_router.tags == ["AI Assist"]
    
    def test_get_route_exists(self):
        """Test that GET route exists at root path."""
        # Check if the GET route exists by inspecting the router's routes
        routes = ai_router.routes
        # Look for APIRoute objects with GET method at the prefixed path
        get_routes = []
        for route in routes:
            if hasattr(route, 'methods') and 'GET' in route.methods:
                # The route path should be /ai/ (prefix + root)
                if hasattr(route, 'path') and route.path == '/ai/':
                    get_routes.append(route)
        
        assert len(get_routes) > 0, f"No GET route found at path '/ai/'. Available routes: {[(getattr(route, 'path', 'no path attr'), getattr(route, 'methods', 'no methods')) for route in routes]}"
    
    def test_read_ai_status_function_call(self):
        """Test that read_ai_status function returns expected placeholder data."""
        result = asyncio.run(read_ai_status())
        expected = [{"message": "Placeholder for AI assist status"}]
        assert result == expected
    
    def test_read_ai_status_return_type(self):
        """Test that read_ai_status is an async function."""
        import inspect
        assert inspect.iscoroutinefunction(read_ai_status)
