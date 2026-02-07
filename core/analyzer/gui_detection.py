"""
GUI 框架检测模块

本模块负责检测 Python 项目中使用的 GUI 框架，包括：
- Qt 系列（PyQt5, PyQt6, PySide2, PySide6）
- Tkinter 系列（tkinter, customtkinter）
- 其他 GUI 框架（wxPython, Kivy, Flet, DearPyGui 等）

功能：
- 检测主要使用的 Qt 框架（避免多 Qt 绑定冲突）
- 获取需要排除的 Qt 绑定列表
- 检测所有使用的 GUI 框架
- 检测脚本是否是 GUI 程序（通过主循环调用）
"""

import ast
import os
from typing import Dict, List, Optional, Set, Tuple

from core.analyzer_constants import (
    FRAMEWORKS_WITH_DATA_FILES,
    GUI_FRAMEWORK_MAPPING,
    QT_BINDINGS,
)


class GUIDetector:
    """GUI 框架检测器"""

    # GUI 主循环调用模式 - 只有真正运行 GUI 的程序才会调用这些
    GUI_MAINLOOP_PATTERNS: Dict[str, List[str]] = {
        # Tkinter - 检测 mainloop() 调用
        'tkinter': ['.mainloop(', 'mainloop()'],
        # PyQt/PySide - 检测 exec() 或 exec_() 调用
        'PyQt6': ['.exec()', '.exec_()', 'app.exec()', 'app.exec_()'],
        'PyQt5': ['.exec()', '.exec_()', 'app.exec()', 'app.exec_()'],
        'PySide6': ['.exec()', '.exec_()', 'app.exec()', 'app.exec_()'],
        'PySide2': ['.exec()', '.exec_()', 'app.exec()', 'app.exec_()'],
        # wxPython - 检测 MainLoop() 调用
        'wx': ['.MainLoop()', 'app.MainLoop()'],
        # Kivy - 检测 run() 调用
        'kivy': ['.run()', 'App().run()', 'runTouchApp('],
        # PyGame - 检测 display.set_mode 或游戏循环
        'pygame': ['pygame.display.set_mode(', 'pygame.init()'],
        # CustomTkinter - 同 tkinter
        'customtkinter': ['.mainloop(', 'mainloop()'],
        # DearPyGui
        'dearpygui': ['dpg.start_dearpygui(', 'dearpygui.start_dearpygui('],
        # Flet
        'flet': ['ft.app(', 'flet.app('],
        # Toga
        'toga': ['.main_loop()', 'app.main_loop()'],
        # Eel
        'eel': ['eel.start('],
        # PySimpleGUI
        'PySimpleGUI': ['.read()', 'window.read('],
    }

    # GUI 导入模式
    GUI_IMPORT_PATTERNS: Dict[str, List[str]] = {
        'tkinter': ['import tkinter', 'from tkinter'],
        'PyQt6': ['from PyQt6', 'import PyQt6'],
        'PyQt5': ['from PyQt5', 'import PyQt5'],
        'PySide6': ['from PySide6', 'import PySide6'],
        'PySide2': ['from PySide2', 'import PySide2'],
        'wx': ['import wx', 'from wx'],
        'kivy': ['import kivy', 'from kivy'],
        'pygame': ['import pygame', 'from pygame'],
        'customtkinter': ['import customtkinter', 'from customtkinter'],
        'dearpygui': ['import dearpygui', 'from dearpygui'],
        'flet': ['import flet', 'from flet'],
        'toga': ['import toga', 'from toga'],
        'eel': ['import eel', 'from eel'],
        'PySimpleGUI': ['import PySimpleGUI', 'from PySimpleGUI'],
    }

    def __init__(self):
        """初始化 GUI 检测器"""
        self.detected_gui_frameworks: Set[str] = set()
        self.primary_qt_framework: Optional[str] = None

    def detect_primary_qt_framework(
        self, script_path: str, project_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        从源代码中检测主要使用的 Qt 框架

        这个方法会扫描源代码中的 import 语句，确定实际使用的是哪个 Qt 框架。
        这对于避免 PyInstaller 的多 Qt 绑定冲突非常重要。

        Args:
            script_path: 主脚本路径
            project_dir: 项目目录（可选）

        Returns:
            检测到的主要 Qt 框架名称，如 "PyQt6"、"PyQt5" 等，未检测到返回 None
        """
        qt_import_counts: Dict[str, int] = {
            "PyQt6": 0,
            "PyQt5": 0,
            "PySide6": 0,
            "PySide2": 0,
        }

        # 确定扫描目录
        scan_dir = project_dir if project_dir else os.path.dirname(script_path)

        try:
            for root, dirs, files in os.walk(scan_dir):
                # 跳过虚拟环境和构建目录
                dirs[:] = [
                    d for d in dirs
                    if d not in {
                        '.venv', 'venv', 'build', 'dist', '__pycache__',
                        '.git', 'node_modules', 'site-packages'
                    }
                ]

                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                                # 计算每个 Qt 框架的导入次数
                                for qt_name in qt_import_counts.keys():
                                    # 匹配 import PyQt6 或 from PyQt6
                                    import_count = (
                                        content.count(f'import {qt_name}') +
                                        content.count(f'from {qt_name}')
                                    )
                                    qt_import_counts[qt_name] += import_count
                        except Exception:
                            pass
        except Exception:
            pass

        # 找出导入次数最多的 Qt 框架
        max_count = 0
        primary_qt = None
        for qt_name, count in qt_import_counts.items():
            if count > max_count:
                max_count = count
                primary_qt = qt_name

        self.primary_qt_framework = primary_qt
        return primary_qt

    def get_qt_exclusion_list(self) -> List[str]:
        """
        获取需要排除的 Qt 绑定包列表

        基于检测到的主要 Qt 框架，返回其他需要排除的 Qt 绑定包。
        这可以避免 PyInstaller 的多 Qt 绑定冲突错误。

        Returns:
            需要排除的 Qt 包名列表
        """
        if not self.primary_qt_framework:
            return []

        exclude_list = []
        for qt_binding in QT_BINDINGS:
            if qt_binding != self.primary_qt_framework:
                exclude_list.append(qt_binding)
                # 也排除相关的子模块
                exclude_list.append(f"{qt_binding}.QtCore")
                exclude_list.append(f"{qt_binding}.QtGui")
                exclude_list.append(f"{qt_binding}.QtWidgets")

        # 排除 shiboken（PySide 的依赖）
        if self.primary_qt_framework not in ("PySide6", "PySide2"):
            exclude_list.extend(["shiboken6", "shiboken2"])
        elif self.primary_qt_framework == "PySide6":
            exclude_list.append("shiboken2")
        elif self.primary_qt_framework == "PySide2":
            exclude_list.append("shiboken6")

        return exclude_list

    def detect_gui_frameworks(
        self, dependencies: Set[str], all_imports: Set[str]
    ) -> Set[str]:
        """
        获取检测到的 GUI 框架列表

        Args:
            dependencies: 依赖包集合
            all_imports: 所有导入的模块集合

        Returns:
            检测到的 GUI 框架集合
        """
        self.detected_gui_frameworks = set()

        # 检查所有已知的 GUI 框架
        all_deps_lower = {dep.lower() for dep in dependencies}
        all_imports_lower = {imp.lower() for imp in all_imports}
        combined = all_deps_lower | all_imports_lower

        # Qt 系列 - 只添加主要使用的 Qt 框架（如果已检测）
        if self.primary_qt_framework:
            self.detected_gui_frameworks.add(self.primary_qt_framework)
        else:
            # 如果未检测主要框架，则按优先级添加（PyQt6 > PySide6 > PyQt5 > PySide2）
            if "pyqt6" in combined:
                self.detected_gui_frameworks.add("PyQt6")
            elif "pyside6" in combined:
                self.detected_gui_frameworks.add("PySide6")
            elif "pyqt5" in combined:
                self.detected_gui_frameworks.add("PyQt5")
            elif "pyside2" in combined:
                self.detected_gui_frameworks.add("PySide2")

        # wxPython 系列
        if "wx" in combined or "wxpython" in combined:
            self.detected_gui_frameworks.add("wxPython")
        if "wax" in combined:
            self.detected_gui_frameworks.add("Wax")

        # Tkinter 系列
        if "tkinter" in combined:
            self.detected_gui_frameworks.add("Tkinter")
        if "customtkinter" in combined:
            self.detected_gui_frameworks.add("CustomTkinter")

        # PySimpleGUI 系列
        if "pysimplegui" in combined:
            self.detected_gui_frameworks.add("PySimpleGUI")
        if "pysimpleguiqt" in combined:
            self.detected_gui_frameworks.add("PySimpleGUIQt")
        if "pysimpleguiwx" in combined:
            self.detected_gui_frameworks.add("PySimpleGUIWx")

        # 其他 GUI 框架
        if "kivy" in combined:
            self.detected_gui_frameworks.add("Kivy")
        if "flet" in combined:
            self.detected_gui_frameworks.add("Flet")
        if "dearpygui" in combined:
            self.detected_gui_frameworks.add("DearPyGui")
        if "eel" in combined:
            self.detected_gui_frameworks.add("Eel")
        if "toga" in combined:
            self.detected_gui_frameworks.add("Toga")
        if "textual" in combined:
            self.detected_gui_frameworks.add("Textual")
        if "pyforms" in combined or "pyforms_gui" in combined:
            self.detected_gui_frameworks.add("PyForms")
        if "libavg" in combined:
            self.detected_gui_frameworks.add("Libavg")
        if "gui" in combined:  # PyGUI
            self.detected_gui_frameworks.add("PyGUI")
        if "pygame" in combined:
            self.detected_gui_frameworks.add("Pygame")

        return self.detected_gui_frameworks

    def get_framework_data_files(self) -> List[Tuple[str, str]]:
        """
        获取需要包含的框架数据文件

        Returns:
            (源路径模式, 目标路径) 列表
        """
        data_files = []
        detected_lower = {f.lower() for f in self.detected_gui_frameworks}

        for framework_name, files in FRAMEWORKS_WITH_DATA_FILES.items():
            # 检查是否检测到该框架
            if framework_name.lower() in detected_lower:
                data_files.extend(files)

        return data_files

    def detect_gui_in_script(self, script_path: str) -> Tuple[bool, str]:
        """
        检测脚本是否是 GUI 程序（通过检测主循环调用）

        仅检测导入是不够的，因为很多非 GUI 程序也会导入 GUI 库用于其他目的。
        这里检测的是实际调用 GUI 主循环的代码。

        Args:
            script_path: 脚本路径

        Returns:
            (是否是GUI程序, GUI框架名称)
        """
        try:
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            for framework, mainloop_patterns in self.GUI_MAINLOOP_PATTERNS.items():
                # 首先检查是否导入了这个框架
                import_patterns = self.GUI_IMPORT_PATTERNS.get(framework, [])
                has_import = any(pattern in content for pattern in import_patterns)

                if has_import:
                    # 然后检查是否调用了主循环
                    for pattern in mainloop_patterns:
                        if pattern in content:
                            return True, framework
        except Exception:
            pass

        return False, ""

    def detect_actual_imports(
        self, script_path: str, project_dir: Optional[str] = None
    ) -> Set[str]:
        """
        使用 AST 精确检测项目中实际导入的模块

        这个方法只检测真正的 import 语句，避免匹配到注释、字符串等

        Args:
            script_path: 主脚本路径
            project_dir: 项目目录（可选）

        Returns:
            实际导入的模块名集合
        """
        imports = set()
        scan_dir = project_dir if project_dir else os.path.dirname(script_path)

        try:
            for root, dirs, files in os.walk(scan_dir):
                # 跳过虚拟环境和构建目录
                dirs[:] = [
                    d for d in dirs
                    if d not in {
                        '.venv', 'venv', 'build', 'dist', '__pycache__',
                        '.git', 'node_modules', 'site-packages'
                    }
                ]

                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                            # 使用 AST 解析
                            try:
                                tree = ast.parse(content)
                                for node in ast.walk(tree):
                                    if isinstance(node, ast.Import):
                                        for alias in node.names:
                                            # 获取顶级模块名
                                            module_name = alias.name.split('.')[0]
                                            imports.add(module_name)
                                    elif isinstance(node, ast.ImportFrom):
                                        if node.module:
                                            # 获取顶级模块名
                                            module_name = node.module.split('.')[0]
                                            imports.add(module_name)
                            except SyntaxError:
                                # 如果 AST 解析失败，跳过该文件
                                pass
                        except Exception:
                            pass
        except Exception:
            pass

        return imports

    def get_gui_framework_mapping(self) -> Dict[str, str]:
        """
        获取 GUI 框架映射表

        Returns:
            PyPI 包名到 Python 导入名的映射
        """
        return GUI_FRAMEWORK_MAPPING.copy()
