"""
Core package for Python packaging tool.

Modules:
    - analyzer_constants: 依赖分析器常量定义
    - dependency_analyzer: 依赖分析器
    - packager: 打包器
    - nuitka_config: Nuitka 最佳实践配置
    - version_info: 版本信息处理
"""

from .analyzer_constants import (
    CONFIGURED_LIBRARIES,
    DEV_PACKAGES,
    FRAMEWORKS_WITH_DATA_FILES,
    GUI_FRAMEWORK_MAPPING,
    KNOWN_SINGLE_FILE_MODULES,
    KNOWN_STDLIB_PACKAGES,
    LARGE_PACKAGES,
    PACKAGE_IMPORT_MAP,
    QT_BINDINGS,
    STDLIB_MODULES,
)
from .dependency_analyzer import DependencyAnalyzer
from .nuitka_config import (
    AntiBloatConfig,
    AntiBlockMode,
    CacheConfig,
    CompilationMode,
    ConsoleMode,
    DataFileConfig,
    MacOSConfig,
    ModuleConfig,
    NuitkaBestPractices,
    NuitkaConfig,
    NuitkaVersionInfo,
    OnefileConfig,
    PluginConfig,
    PythonFlags,
    ReportConfig,
    WindowsConfig,
    create_user_package_config,
)
from .packager import Packager
from .version_info import (
    RceditHandler,
    VersionInfoHandler,
    WindowsResourceHandler,
)

__all__ = [
    # 常量
    "STDLIB_MODULES",
    "LARGE_PACKAGES",
    "DEV_PACKAGES",
    "GUI_FRAMEWORK_MAPPING",
    "FRAMEWORKS_WITH_DATA_FILES",
    "QT_BINDINGS",
    "CONFIGURED_LIBRARIES",
    "PACKAGE_IMPORT_MAP",
    "KNOWN_SINGLE_FILE_MODULES",
    "KNOWN_STDLIB_PACKAGES",
    # 依赖分析器
    "DependencyAnalyzer",
    # 打包器
    "Packager",
    # 版本信息处理
    "VersionInfoHandler",
    "WindowsResourceHandler",
    "RceditHandler",
    # Nuitka 配置
    "NuitkaConfig",
    "NuitkaBestPractices",
    "NuitkaVersionInfo",
    "CompilationMode",
    "ConsoleMode",
    "AntiBlockMode",
    "PythonFlags",
    "AntiBloatConfig",
    "OnefileConfig",
    "WindowsConfig",
    "MacOSConfig",
    "ReportConfig",
    "CacheConfig",
    "PluginConfig",
    "DataFileConfig",
    "ModuleConfig",
    "create_user_package_config",
]
