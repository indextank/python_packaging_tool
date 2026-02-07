"""
文件处理器 Mixin

本模块包含 MainWindow 中与文件浏览和路径处理相关的方法。
从 main_window.py 拆分出来，遵循单一职责原则。
"""

import os
from typing import Optional

from PyQt6.QtWidgets import QFileDialog, QMessageBox


class FileHandlerMixin:
    """
    文件处理器 Mixin 类

    提供文件浏览和路径处理相关的方法。
    设计为与 MainWindow 一起使用的 Mixin。

    注意：此类使用 Mixin 模式，self 实际上是 MainWindow 实例
    """

    def browse_project_dir(self) -> None:
        """浏览项目目录"""
        path = QFileDialog.getExistingDirectory(self, "选择项目目录")  # type: ignore[arg-type]
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.project_dir_edit.setText(os.path.normpath(path))  # type: ignore[attr-defined]

    def browse_script(self) -> None:
        """浏览脚本文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择运行脚本", "", "Python Files (*.py);;All Files (*)"  # type: ignore[arg-type]
        )
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.script_path_edit.setText(os.path.normpath(path))  # type: ignore[attr-defined]

    def browse_output_dir(self) -> None:
        """浏览输出目录"""
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")  # type: ignore[arg-type]
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.output_dir_edit.setText(os.path.normpath(path))  # type: ignore[attr-defined]

    def browse_icon(self) -> None:
        """浏览图标文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择程序图标", "",  # type: ignore[arg-type]
            "Icon Files (*.ico *.png *.svg *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.icon_path_edit.setText(os.path.normpath(path))  # type: ignore[attr-defined]
            # 标记用户手动选择了图标，防止自动加载覆盖
            self._icon_manually_set = True  # type: ignore[attr-defined]

    def browse_python(self) -> None:
        """浏览Python可执行文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择Python解释器", "", "Executable (*.exe);;All Files (*)"  # type: ignore[arg-type]
        )
        if path:
            # 规范化路径，统一使用系统默认的路径分隔符
            self.python_path_edit.setText(os.path.normpath(path))  # type: ignore[attr-defined]

    def browse_gcc(self) -> None:
        """浏览GCC工具链（mingw64或mingw32目录）"""
        from utils.gcc_downloader import GCCDownloader, validate_mingw_directory

        # 选择目录而不是文件
        path = QFileDialog.getExistingDirectory(
            self, "选择GCC工具链目录 (mingw64 或 mingw32)",  # type: ignore[arg-type]
            GCCDownloader.get_nuitka_cache_dir()
        )
        if path:
            # 验证mingw目录
            is_valid, msg = validate_mingw_directory(path)
            if not is_valid:
                QMessageBox.critical(
                    self,  # type: ignore[arg-type]
                    "GCC工具链验证失败",
                    f"所选目录不是有效的GCC工具链：\n\n{msg}\n\n"
                    "请选择有效的 mingw64 或 mingw32 目录。\n"
                    "该目录应包含 bin 子目录，且 bin 目录下应存在 gcc.exe、g++.exe 等文件。",
                )
                return
            # 规范化路径，统一使用系统默认的路径分隔符
            self.gcc_path_edit.setText(os.path.normpath(path))  # type: ignore[attr-defined]
            self._show_info("验证通过", "GCC工具链目录验证通过！")  # type: ignore[attr-defined]

    def auto_load_project_icon(
        self,
        project_dir: str,
        force_update: bool = False
    ) -> None:
        """
        自动从项目目录加载图标

        支持多种格式和位置的图标文件查找。

        优先级:
        1. icon.ico 在项目根目录
        2. app.ico 在项目根目录
        3. logo.ico 在项目根目录
        4. 项目根目录中的任意 .ico 文件（找到的第一个）
        5. icon.png 在项目根目录
        6. resources/icons/ 目录中的图标
        7. assets/ 目录中的图标

        Args:
            project_dir: 项目目录路径
            force_update: 是否强制更新（即使已有图标）
        """
        if not project_dir or not os.path.isdir(project_dir):
            return

        # 如果已经有图标且不强制更新，则跳过
        current_icon = getattr(self, 'icon_path_edit', None)
        if current_icon and current_icon.text().strip() and not force_update:
            return

        # 按优先级查找图标文件
        icon_candidates = [
            # 项目根目录的常见图标名称
            os.path.join(project_dir, "icon.ico"),
            os.path.join(project_dir, "app.ico"),
            os.path.join(project_dir, "logo.ico"),
            os.path.join(project_dir, "icon.png"),
            os.path.join(project_dir, "app.png"),
            os.path.join(project_dir, "logo.png"),
            # resources 目录
            os.path.join(project_dir, "resources", "icon.ico"),
            os.path.join(project_dir, "resources", "icons", "icon.ico"),
            os.path.join(project_dir, "resources", "icon.png"),
            os.path.join(project_dir, "resources", "icons", "icon.png"),
            # assets 目录
            os.path.join(project_dir, "assets", "icon.ico"),
            os.path.join(project_dir, "assets", "icons", "icon.ico"),
            os.path.join(project_dir, "assets", "icon.png"),
            os.path.join(project_dir, "assets", "icons", "icon.png"),
        ]

        # 先尝试固定名称的图标
        for icon_path in icon_candidates:
            if os.path.exists(icon_path):
                self.icon_path_edit.setText(os.path.normpath(icon_path))  # type: ignore[attr-defined]
                return

        # 然后尝试查找项目根目录中的任意 .ico 文件
        try:
            for filename in os.listdir(project_dir):
                if filename.lower().endswith('.ico'):
                    icon_path = os.path.join(project_dir, filename)
                    self.icon_path_edit.setText(os.path.normpath(icon_path))  # type: ignore[attr-defined]
                    return
        except OSError:
            pass

        # 查找 resources 目录中的任意 .ico 文件
        resources_dir = os.path.join(project_dir, "resources")
        if os.path.isdir(resources_dir):
            try:
                for filename in os.listdir(resources_dir):
                    if filename.lower().endswith('.ico'):
                        icon_path = os.path.join(resources_dir, filename)
                        self.icon_path_edit.setText(os.path.normpath(icon_path))  # type: ignore[attr-defined]
                        return
            except OSError:
                pass

    def find_main_script(self, project_dir: str) -> Optional[str]:
        """
        在项目目录中查找主脚本文件

        按优先级查找常见的主脚本名称。

        Args:
            project_dir: 项目目录路径

        Returns:
            找到的主脚本路径，未找到返回 None
        """
        if not project_dir or not os.path.isdir(project_dir):
            return None

        # 按优先级查找主脚本
        possible_scripts = [
            'main.py',
            'app.py',
            'run.py',
            '__main__.py',
            'start.py',
            'launcher.py',
        ]

        for script in possible_scripts:
            script_path = os.path.join(project_dir, script)
            if os.path.exists(script_path):
                return os.path.normpath(script_path)

        return None

    def validate_paths(self) -> tuple[bool, str]:
        """
        验证所有必需的路径是否有效

        Returns:
            (是否有效, 错误消息)
        """
        errors = []

        # 检查项目目录或脚本路径
        project_dir = self.project_dir_edit.text().strip()  # type: ignore[attr-defined]
        script_path = self.script_path_edit.text().strip()  # type: ignore[attr-defined]

        if not project_dir and not script_path:
            errors.append("请选择项目目录或脚本文件")
        elif project_dir and not os.path.isdir(project_dir):
            errors.append(f"项目目录不存在: {project_dir}")
        elif script_path and not os.path.isfile(script_path):
            errors.append(f"脚本文件不存在: {script_path}")

        # 检查输出目录
        output_dir = self.output_dir_edit.text().strip()  # type: ignore[attr-defined]
        if not output_dir:
            errors.append("请选择输出目录")

        # 检查图标文件（如果指定）
        icon_path = self.icon_path_edit.text().strip()  # type: ignore[attr-defined]
        if icon_path and not os.path.isfile(icon_path):
            errors.append(f"图标文件不存在: {icon_path}")

        # 检查 Python 解释器（如果指定）
        python_path = self.python_path_edit.text().strip()  # type: ignore[attr-defined]
        if python_path and not os.path.isfile(python_path):
            errors.append(f"Python 解释器不存在: {python_path}")

        # 检查 GCC 路径（如果使用 Nuitka）
        if hasattr(self, 'nuitka_radio') and self.nuitka_radio.isChecked():  # type: ignore[attr-defined]
            gcc_path = self.gcc_path_edit.text().strip()  # type: ignore[attr-defined]
            if gcc_path and not os.path.isdir(gcc_path):
                errors.append(f"GCC 工具链目录不存在: {gcc_path}")

        if errors:
            return False, "\n".join(errors)

        return True, ""

    def normalize_path(self, path: str) -> str:
        """
        规范化路径

        Args:
            path: 原始路径

        Returns:
            规范化后的路径
        """
        if not path:
            return path
        return os.path.normpath(path.strip())

    def get_relative_path(self, path: str, base_dir: str) -> str:
        """
        获取相对于基准目录的相对路径

        Args:
            path: 目标路径
            base_dir: 基准目录

        Returns:
            相对路径，如果无法计算则返回原路径
        """
        if not path or not base_dir:
            return path

        try:
            return os.path.relpath(path, base_dir)
        except ValueError:
            # Windows 上跨盘符时可能出错
            return path
