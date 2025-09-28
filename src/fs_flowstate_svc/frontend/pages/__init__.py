# frontend.pages package initializer
# Avoid importing submodules at package import time to prevent
# side-effects (Streamlit imports) and to allow lazy importing.

# Public submodules (import them when needed)
__all__ = [
    "inbox_page",
    "inbox_drag",
    "timeline_calendar",
]
