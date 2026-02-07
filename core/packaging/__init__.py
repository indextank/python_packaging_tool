"""
Packaging 子包

本包包含打包相关的模块：
- base: 共享常量、工具函数和基类
- venv_manager: 虚拟环境管理
- dependency_installer: 依赖安装
- icon_processor: 图标处理
- pyinstaller_packager: PyInstaller 打包逻辑
- nuitka_packager: Nuitka 打包逻辑
- network_utils: 网络工具（镜像源管理等）
"""

from .base import (
    CREATE_NO_WINDOW,
    BasePackager,
    detect_actual_imports,
    is_package_installed,
    verify_tool,
)
from .dependency_installer import DependencyInstaller
from .icon_processor import IconProcessor
from .network_utils import NetworkUtils
from .nuitka_packager import NuitkaPackager
from .pyinstaller_packager import PyInstallerPackager
from .venv_manager import VenvManager

__all__ = [
    # 基础工具
    "CREATE_NO_WINDOW",
    "BasePackager",
    "detect_actual_imports",
    "is_package_installed",
    "verify_tool",
    # 子模块
    "VenvManager",
    "DependencyInstaller",
    "IconProcessor",
    "PyInstallerPackager",
    "NuitkaPackager",
    "NetworkUtils",
]
