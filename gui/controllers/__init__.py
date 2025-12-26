"""
GUI Controllers Module

This module provides controller classes and worker threads for PyQt6 applications.
Following PyQt6 best practices by separating business logic from UI components.

Key components:
- WorkerSignals: Signal definitions for thread communication
- BaseWorker: Base class for QRunnable-based workers
- PackagingWorker: Worker for packaging operations
- DependencyAnalysisWorker: Worker for dependency analysis
- DownloadWorker: Worker for file downloads
- GenericWorker: Generic worker for any callable
- LongRunningWorker: QThread-based worker for complex tasks
"""

from .workers import (
    BaseWorker,
    DependencyAnalysisWorker,
    DownloadWorker,
    GenericWorker,
    LongRunningWorker,
    PackagingWorker,
    WorkerSignals,
)

__all__ = [
    "WorkerSignals",
    "BaseWorker",
    "PackagingWorker",
    "DependencyAnalysisWorker",
    "DownloadWorker",
    "GenericWorker",
    "LongRunningWorker",
]
