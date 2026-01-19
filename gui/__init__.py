"""
GUI Module - Python Packaging Tool

This module provides the graphical user interface for the Python packaging tool.
Following PyQt6 best practices with modular architecture:

- main_window: Main application window
- styles: Theme and stylesheet management
- widgets: Custom widgets and icon generation
- controllers: Worker threads and background task management

Architecture Overview:
    MainWindow
    ├── ThemeManager (styles.themes)
    ├── IconGenerator (widgets.icons)
    ├── WorkerSignals (controllers.workers)
    └── Various Workers (controllers.workers)
"""

from gui.controllers import (
    BaseWorker,
    DependencyAnalysisWorker,
    GenericWorker,
    PackagingWorker,
    WorkerSignals,
)
from gui.main_window import MainWindow

# Re-export commonly used components for convenience
from gui.styles import (
    DARK_COLORS,
    LIGHT_COLORS,
    ThemeColors,
    ThemeManager,
    ThemeMode,
)
from gui.widgets import (
    IconGenerator,
    create_themed_checkbox_icons,
    create_themed_radio_icons,
)

__all__ = [
    # Main window
    "MainWindow",
    # Theme management
    "ThemeMode",
    "ThemeColors",
    "ThemeManager",
    "LIGHT_COLORS",
    "DARK_COLORS",
    # Widgets
    "IconGenerator",
    "create_themed_checkbox_icons",
    "create_themed_radio_icons",
    # Workers
    "WorkerSignals",
    "BaseWorker",
    "PackagingWorker",
    "DependencyAnalysisWorker",
    "GenericWorker",
]

# 从统一的版本模块导入版本号
from version import __version__
