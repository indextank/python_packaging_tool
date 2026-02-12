import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from utils.constants import CREATE_NO_WINDOW


class PythonFinder:
    """Python环境查找工具"""

    def __init__(self):
        self.python_path = None

    @staticmethod
    def is_bundled_environment() -> bool:
        """
        检测当前是否运行在 PyInstaller/Nuitka 打包后的环境中

        PyInstaller 单文件模式运行时，sys.executable 指向临时目录中的
        bundled python.exe，该文件不是完整的 Python 解释器，不能用于
        创建虚拟环境或执行 pip 操作。

        Returns:
            True 表示当前处于打包环境中
        """
        # PyInstaller 设置的标志属性
        if getattr(sys, 'frozen', False):
            return True

        # PyInstaller 单文件模式的临时解压目录标志
        if getattr(sys, '_MEIPASS', None):
            return True

        # Nuitka 编译后的标志
        if "__compiled__" in dir():
            return True

        # 检测 sys.executable 是否在临时目录中（PyInstaller 单文件模式特征）
        try:
            exe_path = os.path.normpath(sys.executable)
            temp_dir = os.path.normpath(tempfile.gettempdir())
            if exe_path.startswith(temp_dir):
                return True
        except Exception:
            pass

        return False

    @staticmethod
    def is_valid_python_interpreter(python_path: str) -> bool:
        """
        检测给定的 Python 路径是否是一个可用于打包的完整 Python 解释器

        排除以下情况：
        - PyInstaller 临时目录中的 bundled python.exe
        - 不存在的路径
        - 无法执行 'python -c "import venv"' 的解释器

        Args:
            python_path: Python 解释器路径

        Returns:
            True 表示是有效的完整 Python 解释器
        """
        if not python_path or not os.path.exists(python_path):
            return False

        # 检查是否在临时目录中（PyInstaller 单文件解压目录）
        try:
            exe_path = os.path.normpath(python_path)
            temp_dir = os.path.normpath(tempfile.gettempdir())
            if exe_path.startswith(temp_dir):
                return False
        except Exception:
            pass

        # 检查是否能执行基本的 Python 命令，并且有 venv 模块
        try:
            result = subprocess.run(
                [python_path, "-c", "import venv; import pip; print('ok')"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except Exception:
            return False

    def find_python(self) -> Optional[str]:
        """
        查找系统中的Python安装路径

        Returns:
            Python可执行文件的路径，未找到则返回None
        """
        # 1. 尝试使用当前运行的Python（仅在非打包环境下）
        if not self.is_bundled_environment():
            current_python = sys.executable
            if current_python and os.path.exists(current_python):
                if self._verify_python(current_python):
                    self.python_path = current_python
                    return current_python

        # 2. 尝试从PATH环境变量查找
        path_python = self._find_in_path()
        if path_python:
            self.python_path = path_python
            return path_python

        # 3. Windows特定路径查找
        if sys.platform == "win32":
            windows_python = self._find_in_windows()
            if windows_python:
                self.python_path = windows_python
                return windows_python

        return None

    def _verify_python(self, python_path: str) -> bool:
        """验证Python路径是否有效"""
        try:
            result = subprocess.run(
                [python_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _find_in_path(self) -> Optional[str]:
        """从PATH环境变量中查找Python"""
        try:
            # Windows
            if sys.platform == "win32":
                result = subprocess.run(
                    ["where", "python"],
                    capture_output=True,
                    text=True,
                    creationflags=CREATE_NO_WINDOW,
                )
            # Unix-like
            else:
                result = subprocess.run(
                    ["which", "python3"],
                    capture_output=True,
                    text=True,
                    creationflags=CREATE_NO_WINDOW,
                )
                if result.returncode != 0:
                    result = subprocess.run(
                        ["which", "python"],
                        capture_output=True,
                        text=True,
                        creationflags=CREATE_NO_WINDOW,
                    )

            if result.returncode == 0:
                python_path = result.stdout.strip().split("\n")[0]
                if os.path.exists(python_path) and self._verify_python(python_path):
                    return python_path

        except Exception:
            pass

        return None

    def _find_in_windows(self) -> Optional[str]:
        """在Windows系统中查找Python"""
        # 常见的Windows Python安装路径
        common_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python",
            Path(os.environ.get("PROGRAMFILES", "")) / "Python",
            Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Python",
            Path("C:/") / "Python",
        ]

        # 搜索Python版本目录
        for base_path in common_paths:
            if not base_path.exists():
                continue

            # 查找Python3x目录
            try:
                for item in base_path.iterdir():
                    if item.is_dir() and item.name.startswith("Python3"):
                        python_exe = item / "python.exe"
                        if python_exe.exists() and self._verify_python(str(python_exe)):
                            return str(python_exe)
            except Exception:
                continue

        # 尝试从注册表查找（Windows）
        try:
            import winreg

            python_path = self._find_in_registry(winreg)
            if python_path:
                return python_path
        except ImportError:
            pass

        return None

    def _find_in_registry(self, winreg) -> Optional[str]:
        """从Windows注册表查找Python"""
        registry_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Python\PythonCore"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Python\PythonCore"),
        ]

        for hkey, subkey in registry_paths:
            try:
                key = winreg.OpenKey(hkey, subkey)
                num_subkeys = winreg.QueryInfoKey(key)[0]

                # 遍历所有Python版本
                versions = []
                for i in range(num_subkeys):
                    try:
                        version = winreg.EnumKey(key, i)
                        versions.append(version)
                    except Exception:
                        continue

                # 按版本号排序，优先使用最新版本
                versions.sort(reverse=True)

                for version in versions:
                    try:
                        install_path_key = winreg.OpenKey(
                            key, rf"{version}\InstallPath"
                        )
                        install_path = winreg.QueryValue(install_path_key, "")
                        python_exe = os.path.join(install_path, "python.exe")

                        if os.path.exists(python_exe) and self._verify_python(
                            python_exe
                        ):
                            return python_exe
                    except Exception:
                        continue

            except Exception:
                continue

        return None

    def get_python_version(self, python_path: str) -> Optional[str]:
        """获取Python版本信息"""
        try:
            result = subprocess.run(
                [python_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                return result.stdout.strip() or result.stderr.strip()
        except Exception:
            pass

        return None
