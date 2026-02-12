"""
虚拟环境管理模块

本模块负责虚拟环境的创建和管理，包括：
- 检测已存在的虚拟环境
- 创建新的虚拟环境
- 获取虚拟环境中的 Python 路径

功能：
- 支持 venv 和 .venv 目录
- 跨平台支持（Windows/Linux/macOS）
"""

import os
import subprocess
import sys
from typing import Callable, Optional

from core.packaging.base import CREATE_NO_WINDOW


class VenvManager:
    """虚拟环境管理器"""

    # 常见的虚拟环境目录名
    VENV_DIRS = [".venv", "venv", ".env", "env"]

    def __init__(self):
        """初始化虚拟环境管理器"""
        self.log: Callable = print

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback

    def check_existing_venv(self, project_dir: str) -> Optional[str]:
        """
        检查项目目录中是否已存在虚拟环境

        Args:
            project_dir: 项目目录

        Returns:
            虚拟环境路径，如果不存在则返回 None
        """
        for venv_name in self.VENV_DIRS:
            venv_path = os.path.join(project_dir, venv_name)
            if os.path.isdir(venv_path):
                # 验证是否是有效的虚拟环境
                python_path = self.get_venv_python(venv_path)
                if os.path.exists(python_path):
                    return venv_path
        return None

    def get_venv_python(self, venv_path: str, verify: bool = False) -> str:
        """
        获取虚拟环境中的 Python 路径

        Args:
            venv_path: 虚拟环境路径
            verify: 是否验证路径存在

        Returns:
            Python 可执行文件路径
        """
        if sys.platform == "win32":
            python_path = os.path.join(venv_path, "Scripts", "python.exe")
        else:
            python_path = os.path.join(venv_path, "bin", "python")

        if verify and not os.path.exists(python_path):
            self.log(f"警告: Python 解释器不存在: {python_path}")
            self.log(f"  虚拟环境路径: {venv_path}")
            self.log(f"  虚拟环境目录是否存在: {os.path.exists(venv_path)}")
            if os.path.exists(venv_path):
                try:
                    contents = os.listdir(venv_path)
                    self.log(f"  虚拟环境目录内容: {contents}")
                    if sys.platform == "win32":
                        scripts_dir = os.path.join(venv_path, "Scripts")
                        if os.path.exists(scripts_dir):
                            scripts_contents = os.listdir(scripts_dir)
                            self.log(f"  Scripts 目录内容: {scripts_contents}")
                except Exception as e:
                    self.log(f"  无法列出目录内容: {e}")

        return python_path

    def setup_venv(
        self,
        project_dir: str,
        python_path: str,
        venv_name: str = ".venv",
    ) -> Optional[str]:
        """
        创建虚拟环境

        Args:
            project_dir: 项目目录
            python_path: 用于创建虚拟环境的 Python 解释器路径
            venv_name: 虚拟环境目录名

        Returns:
            虚拟环境路径，失败返回 None
        """
        # 验证 python_path 是否存在
        if not os.path.exists(python_path):
            self.log(f"错误: Python 解释器不存在: {python_path}")
            return None

        # 验证 python_path 是否是可用的完整解释器（能执行 venv 模块）
        try:
            check_result = subprocess.run(
                [python_path, "-c", "import venv; print('ok')"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
            )
            if check_result.returncode != 0:
                self.log(f"错误: Python 解释器无法使用 venv 模块: {python_path}")
                self.log(f"  错误信息: {check_result.stderr.strip()}")
                # 检测是否是打包环境中的临时文件
                import tempfile
                temp_dir = os.path.normpath(tempfile.gettempdir())
                if os.path.normpath(python_path).startswith(temp_dir):
                    self.log("  原因: 该解释器位于临时目录中，可能是 PyInstaller 打包后的运行时文件")
                    self.log("  建议: 请在工具界面中手动指定系统安装的 Python 路径")
                return None
        except FileNotFoundError:
            self.log(f"错误: 无法执行 Python 解释器: {python_path}")
            self.log("  该文件可能不是有效的 Python 解释器")
            import tempfile
            temp_dir = os.path.normpath(tempfile.gettempdir())
            if os.path.normpath(python_path).startswith(temp_dir):
                self.log("  原因: 该路径位于临时目录中，可能是 PyInstaller 单文件模式的运行时文件")
                self.log("  建议: 请在工具界面中手动指定系统安装的 Python 路径")
            return None
        except subprocess.TimeoutExpired:
            self.log(f"警告: 验证 Python 解释器超时: {python_path}")
        except Exception as e:
            self.log(f"警告: 验证 Python 解释器时出错: {e}")

        venv_path = os.path.join(project_dir, venv_name)

        # 如果已存在，直接返回
        if os.path.isdir(venv_path):
            venv_python = self.get_venv_python(venv_path)
            if os.path.exists(venv_python):
                self.log(f"虚拟环境已存在: {venv_path}")
                return venv_path

        self.log(f"创建虚拟环境: {venv_path}")

        try:
            # 使用 venv 模块创建虚拟环境
            result = subprocess.run(
                [python_path, "-m", "venv", venv_path],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=CREATE_NO_WINDOW,
            )

            if result.returncode != 0:
                self.log(f"创建虚拟环境失败: {result.stderr}")
                return None

            # 验证虚拟环境是否创建成功
            venv_python = self.get_venv_python(venv_path)
            if not os.path.exists(venv_python):
                self.log("错误: 虚拟环境创建后未找到 Python 解释器")
                self.log(f"  期望路径: {venv_python}")
                self.log(f"  虚拟环境目录: {venv_path}")
                # 详细诊断信息
                self.get_venv_python(venv_path, verify=True)
                return None

            self.log(f"✓ 虚拟环境创建成功: {venv_path}")
            self.log(f"  Python 解释器: {venv_python}")
            return venv_path

        except subprocess.TimeoutExpired:
            self.log("创建虚拟环境超时")
            return None
        except Exception as e:
            self.log(f"创建虚拟环境时出错: {str(e)}")
            return None

    def upgrade_pip(self, venv_path: str) -> bool:
        """
        升级虚拟环境中的 pip

        Args:
            venv_path: 虚拟环境路径

        Returns:
            是否成功
        """
        python_path = self.get_venv_python(venv_path)

        # 验证 Python 解释器是否存在
        if not os.path.exists(python_path):
            self.log("错误: Python 解释器不存在，无法升级 pip")
            self.log(f"  期望路径: {python_path}")
            self.log(f"  虚拟环境路径: {venv_path}")
            # 尝试列出虚拟环境目录内容以帮助诊断
            self.get_venv_python(venv_path, verify=True)
            return False

        try:
            self.log("升级 pip...")
            result = subprocess.run(
                [python_path, "-m", "pip", "install", "--upgrade", "pip"],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=CREATE_NO_WINDOW,
            )

            if result.returncode == 0:
                self.log("✓ pip 升级成功")
                return True
            else:
                self.log(f"pip 升级失败: {result.stderr}")
                return False

        except FileNotFoundError as e:
            self.log("错误: 找不到 Python 解释器文件")
            self.log(f"  路径: {python_path}")
            self.log(f"  详细错误: {str(e)}")
            return False
        except Exception as e:
            self.log(f"升级 pip 时出错: {str(e)}")
            self.log(f"  错误类型: {type(e).__name__}")
            return False

    def get_installed_packages(self, venv_path: str) -> dict:
        """
        获取虚拟环境中已安装的包

        Args:
            venv_path: 虚拟环境路径

        Returns:
            包名到版本的映射字典
        """
        python_path = self.get_venv_python(venv_path)
        packages = {}

        try:
            result = subprocess.run(
                [python_path, "-m", "pip", "list", "--format=json"],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=CREATE_NO_WINDOW,
            )

            if result.returncode == 0:
                import json
                package_list = json.loads(result.stdout)
                for pkg in package_list:
                    packages[pkg["name"].lower()] = pkg["version"]

        except Exception as e:
            self.log(f"获取已安装包列表时出错: {str(e)}")

        return packages

    def is_package_installed(
        self,
        venv_path: str,
        package_name: str,
    ) -> bool:
        """
        检查包是否已安装在虚拟环境中

        Args:
            venv_path: 虚拟环境路径
            package_name: 包名

        Returns:
            是否已安装
        """
        packages = self.get_installed_packages(venv_path)
        return package_name.lower() in packages

    def validate_venv(self, venv_path: str, verbose: bool = False) -> bool:
        """
        验证虚拟环境是否有效

        Args:
            venv_path: 虚拟环境路径
            verbose: 是否输出详细日志

        Returns:
            是否有效
        """
        if not os.path.isdir(venv_path):
            if verbose:
                self.log(f"虚拟环境目录不存在: {venv_path}")
            return False

        python_path = self.get_venv_python(venv_path)
        if not os.path.exists(python_path):
            if verbose:
                self.log(f"Python 解释器不存在: {python_path}")
                self.get_venv_python(venv_path, verify=True)
            return False

        # 尝试运行 Python 验证
        try:
            result = subprocess.run(
                [python_path, "-c", "import sys; print(sys.version)"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode == 0:
                if verbose:
                    self.log(f"✓ 虚拟环境有效: {result.stdout.strip()}")
                return True
            else:
                if verbose:
                    self.log(f"虚拟环境 Python 执行失败: {result.stderr}")
                return False
        except Exception as e:
            if verbose:
                self.log(f"验证虚拟环境时出错: {str(e)}")
            return False

    def get_python_version(self, venv_path: str) -> Optional[str]:
        """
        获取虚拟环境中的 Python 版本

        Args:
            venv_path: 虚拟环境路径

        Returns:
            Python 版本字符串，失败返回 None
        """
        python_path = self.get_venv_python(venv_path)

        try:
            result = subprocess.run(
                [python_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
            )

            if result.returncode == 0:
                # 输出格式通常是 "Python 3.x.x"
                version = result.stdout.strip() or result.stderr.strip()
                return version
            return None

        except Exception:
            return None
