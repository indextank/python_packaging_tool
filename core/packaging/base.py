"""
打包器基础模块

提供打包器共享的常量、工具函数和基类。
避免在多个打包器模块中重复定义相同的代码。
"""

import ast
import os
import subprocess
from typing import Callable, Optional, Set, Tuple

from utils.constants import CREATE_NO_WINDOW, SKIP_DIRECTORIES


def is_package_installed(
    python_path: str,
    package_name: str,
    timeout: int = 5,
) -> bool:
    """
    检查包是否已安装

    Args:
        python_path: Python 解释器路径
        package_name: 包名
        timeout: 超时时间（秒）

    Returns:
        是否已安装
    """
    try:
        result = subprocess.run(
            [python_path, "-c", f"import {package_name}"],
            capture_output=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        return result.returncode == 0
    except Exception:
        return False


def detect_actual_imports(
    script_path: str,
    project_dir: Optional[str] = None,
) -> Set[str]:
    """
    使用 AST 精确检测项目中实际导入的模块

    Args:
        script_path: 主脚本路径
        project_dir: 项目目录

    Returns:
        实际导入的模块名集合
    """
    imports: Set[str] = set()
    scan_dir = project_dir if project_dir else os.path.dirname(script_path)

    try:
        for root, dirs, files in os.walk(scan_dir):
            # 跳过虚拟环境和构建目录
            dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]

            for file in files:
                if not file.endswith('.py'):
                    continue

                file_path = os.path.join(root, file)
                file_imports = _extract_imports_from_file(file_path)
                imports.update(file_imports)
    except Exception:
        pass

    return imports


def _extract_imports_from_file(file_path: str) -> Set[str]:
    """
    从单个 Python 文件中提取导入

    Args:
        file_path: 文件路径

    Returns:
        导入的模块名集合
    """
    imports: Set[str] = set()

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    imports.add(module_name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_name = node.module.split('.')[0]
                    imports.add(module_name)
    except (SyntaxError, Exception):
        pass

    return imports


def verify_tool(
    python_path: str,
    tool_module: str,
    timeout: int = 30,
) -> Tuple[bool, str]:
    """
    验证打包工具是否可用

    Args:
        python_path: Python 解释器路径
        tool_module: 工具模块名（如 "PyInstaller" 或 "nuitka"）
        timeout: 超时时间（秒）

    Returns:
        (是否可用, 版本信息或错误信息)
    """
    try:
        result = subprocess.run(
            [python_path, "-m", tool_module, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )

        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            return True, version
        else:
            return False, result.stderr

    except Exception as e:
        return False, str(e)


class BasePackager:
    """打包器基类，提供共享功能"""

    def __init__(self):
        """初始化基类"""
        self.log: Callable = print
        self.cancel_flag: Optional[Callable] = None
        self.process_callback: Optional[Callable] = None
        self._last_exe_path: Optional[str] = None

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback

    def set_cancel_flag(self, cancel_flag: Callable) -> None:
        """设置取消标志回调函数"""
        self.cancel_flag = cancel_flag

    def set_process_callback(self, callback: Callable) -> None:
        """设置进程回调函数"""
        self.process_callback = callback

    def get_last_exe_path(self) -> Optional[str]:
        """获取最后生成的 exe 路径"""
        return self._last_exe_path

    def is_package_installed(self, python_path: str, package_name: str) -> bool:
        """检查包是否已安装（委托给模块级函数）"""
        return is_package_installed(python_path, package_name)

    def detect_actual_imports(
        self,
        script_path: str,
        project_dir: Optional[str] = None,
    ) -> Set[str]:
        """检测实际导入（委托给模块级函数）"""
        return detect_actual_imports(script_path, project_dir)

    def _is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self.cancel_flag is not None and self.cancel_flag()

    def _read_process_output(self, process: subprocess.Popen) -> Tuple[bool, str]:
        """
        读取进程输出并检查取消状态

        Args:
            process: 子进程对象

        Returns:
            (是否被取消, 取消消息)
        """
        while True:
            if self._is_cancelled():
                process.terminate()
                return True, "打包已取消"

            line = process.stdout.readline() if process.stdout else ""
            if not line and process.poll() is not None:
                break

            if line:
                self.log(line.rstrip())

        return False, ""
