"""
Analyzer 子包

本包包含依赖分析相关的模块：
- package_detection: 包检测功能
- gui_detection: GUI 框架检测功能
- hidden_imports: 隐藏导入配置
- dynamic_tracing: 动态导入追踪
- optimization: 优化建议生成
"""

from .dynamic_tracing import DynamicImportTracer
from .gui_detection import GUIDetector
from .hidden_imports import HiddenImportsManager
from .optimization import OptimizationAdvisor
from .package_detection import PackageDetector

__all__ = [
    "PackageDetector",
    "GUIDetector",
    "HiddenImportsManager",
    "DynamicImportTracer",
    "OptimizationAdvisor",
]
