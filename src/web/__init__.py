"""Web package initialization."""

from src.web.state_manager import StateManager
from src.web.components.sidebar import render_sidebar

__all__ = ["StateManager", "render_sidebar"]