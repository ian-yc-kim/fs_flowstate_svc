"""Test module imports to verify package structure is correct."""

import importlib
import pytest


@pytest.mark.parametrize("module_name", [
    "api",
    "auth", 
    "agents",
    "frontend",
    "schemas",
    "services",
    "models",
    "routers"
])
def test_module_imports(module_name):
    """Test that all core modules can be imported successfully.
    
    This ensures the package structure with __init__.py files is correct
    and modules are properly registered as Python packages.
    """
    # Attempt to import each module under fs_flowstate_svc
    full_module_name = f"fs_flowstate_svc.{module_name}"
    
    try:
        imported_module = importlib.import_module(full_module_name)
        # Verify the module was imported successfully
        assert imported_module is not None
    except ModuleNotFoundError as e:
        pytest.fail(f"Failed to import {full_module_name}: {e}")
    except Exception as e:
        pytest.fail(f"Unexpected error importing {full_module_name}: {e}")
