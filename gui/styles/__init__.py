"""
GUI Styles Module

This module provides centralized theme and style management for PyQt6 applications.
Following PyQt6 best practices by separating style definitions from UI logic.
"""

from .themes import (
    DARK_COLORS,
    LIGHT_COLORS,
    ThemeColors,
    ThemeManager,
    ThemeMode,
    detect_system_dark_mode,
    generate_base_stylesheet,
    get_danger_button_stylesheet,
    get_message_box_stylesheet,
)

__all__ = [
    "ThemeMode",
    "ThemeColors",
    "ThemeManager",
    "LIGHT_COLORS",
    "DARK_COLORS",
    "detect_system_dark_mode",
    "generate_base_stylesheet",
    "get_danger_button_stylesheet",
    "get_message_box_stylesheet",
]
