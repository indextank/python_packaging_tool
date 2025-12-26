import ast
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# Windows 子进程隐藏标志
if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


class DependencyAnalyzer:
    """依赖分析器，用于分析Python项目的依赖包"""

    # Python标准库列表（部分常用的）
    STDLIB_MODULES = {
        "abc",
        "aifc",
        "argparse",
        "array",
        "ast",
        "asynchat",
        "asyncio",
        "asyncore",
        "atexit",
        "audioop",
        "base64",
        "bdb",
        "binascii",
        "binhex",
        "bisect",
        "builtins",
        "bz2",
        "calendar",
        "cgi",
        "cgitb",
        "chunk",
        "cmath",
        "cmd",
        "code",
        "codecs",
        "codeop",
        "collections",
        "colorsys",
        "compileall",
        "concurrent",
        "configparser",
        "contextlib",
        "contextvars",
        "copy",
        "copyreg",
        "crypt",
        "csv",
        "ctypes",
        "curses",
        "dataclasses",
        "datetime",
        "dbm",
        "decimal",
        "difflib",
        "dis",
        "distutils",
        "doctest",
        "email",
        "encodings",
        "ensurepip",
        "enum",
        "errno",
        "faulthandler",
        "fcntl",
        "filecmp",
        "fileinput",
        "fnmatch",
        "formatter",
        "fractions",
        "ftplib",
        "functools",
        "gc",
        "getopt",
        "getpass",
        "gettext",
        "glob",
        "grp",
        "gzip",
        "hashlib",
        "heapq",
        "hmac",
        "html",
        "http",
        "idlelib",
        "imaplib",
        "imghdr",
        "imp",
        "importlib",
        "inspect",
        "io",
        "ipaddress",
        "itertools",
        "json",
        "keyword",
        "lib2to3",
        "linecache",
        "locale",
        "logging",
        "lzma",
        "mailbox",
        "mailcap",
        "marshal",
        "math",
        "mimetypes",
        "mmap",
        "modulefinder",
        "msilib",
        "msvcrt",
        "multiprocessing",
        "netrc",
        "nis",
        "nntplib",
        "numbers",
        "operator",
        "optparse",
        "os",
        "ossaudiodev",
        "parser",
        "pathlib",
        "pdb",
        "pickle",
        "pickletools",
        "pipes",
        "pkgutil",
        "platform",
        "plistlib",
        "poplib",
        "posix",
        "posixpath",
        "pprint",
        "profile",
        "pstats",
        "pty",
        "pwd",
        "py_compile",
        "pyclbr",
        "pydoc",
        "queue",
        "quopri",
        "random",
        "re",
        "readline",
        "reprlib",
        "resource",
        "rlcompleter",
        "runpy",
        "sched",
        "secrets",
        "select",
        "selectors",
        "shelve",
        "shlex",
        "shutil",
        "signal",
        "site",
        "smtpd",
        "smtplib",
        "sndhdr",
        "socket",
        "socketserver",
        "spwd",
        "sqlite3",
        "ssl",
        "stat",
        "statistics",
        "string",
        "stringprep",
        "struct",
        "subprocess",
        "sunau",
        "symbol",
        "symtable",
        "sys",
        "sysconfig",
        "syslog",
        "tabnanny",
        "tarfile",
        "telnetlib",
        "tempfile",
        "termios",
        "test",
        "textwrap",
        "threading",
        "time",
        "timeit",
        "tkinter",
        "token",
        "tokenize",
        "trace",
        "traceback",
        "tracemalloc",
        "tty",
        "turtle",
        "turtledemo",
        "types",
        "typing",
        "unicodedata",
        "unittest",
        "urllib",
        "uu",
        "uuid",
        "venv",
        "warnings",
        "wave",
        "weakref",
        "webbrowser",
        "winreg",
        "winsound",
        "wsgiref",
        "xdrlib",
        "xml",
        "xmlrpc",
        "zipapp",
        "zipfile",
        "zipimport",
        "zlib",
        "__future__",
        "__main__",
    }

    # 常见的大型库及其子模块（打包时可能需要排除）
    LARGE_PACKAGES = {
        "numpy": ["numpy.tests", "numpy.f2py.tests"],
        "pandas": ["pandas.tests", "pandas.io.stata", "pandas.io.clipboard"],
        "scipy": ["scipy.tests"],
        "matplotlib": ["matplotlib.tests", "matplotlib.sphinxext"],
        "sklearn": ["sklearn.tests"],
        "torch": ["torch.testing", "torch.utils.tensorboard"],
        "tensorflow": ["tensorflow.python.debug", "tensorflow.lite"],
        "PIL": ["PIL.tests"],
        "cv2": [],
        "pytest": [],
        "unittest": [],
        "doctest": [],
        "pdb": [],
        "IPython": [],
        "jupyter": [],
        "notebook": [],
    }

    # 开发/测试相关的包（通常不需要打包）
    DEV_PACKAGES = {
        "pytest",
        "unittest",
        "nose",
        "tox",
        "coverage",
        "black",
        "flake8",
        "pylint",
        "mypy",
        "isort",
        "autopep8",
        "yapf",
        "bandit",
        "safety",
        "pip",
        "setuptools",
        "wheel",
        "twine",
        "sphinx",
        "ipython",
        "jupyter",
        "notebook",
        "ipykernel",
        "ipywidgets",
    }

    # GUI 框架映射表（PyPI 包名 -> Python 导入名）
    GUI_FRAMEWORK_MAPPING = {
        # Qt 系列
        "PyQt6": "PyQt6",
        "PyQt5": "PyQt5",
        "PySide6": "PySide6",
        "PySide2": "PySide2",
        # wxPython 系列
        "wxPython": "wx",
        "wax": "wax",
        # Tkinter 系列
        "customtkinter": "customtkinter",
        # PySimpleGUI 系列
        "PySimpleGUI": "PySimpleGUI",
        "PySimpleGUIQt": "PySimpleGUIQt",
        "PySimpleGUIWx": "PySimpleGUIWx",
        "PySimpleGUIWeb": "PySimpleGUIWeb",
        # 其他 GUI 框架
        "kivy": "kivy",
        "flet": "flet",
        "dearpygui": "dearpygui",
        "DearPyGui": "dearpygui",
        "eel": "eel",
        "toga": "toga",
        "textual": "textual",
        "pyforms": "pyforms",
        "pyforms-gui": "pyforms_gui",
        "libavg": "libavg",
        "pygui": "GUI",
    }

    # 需要包含数据文件的框架
    FRAMEWORKS_WITH_DATA_FILES = {
        "customtkinter": [
            # CustomTkinter 需要主题 JSON 文件
            ("customtkinter", "customtkinter"),
        ],
        "kivy": [
            # Kivy 需要 data 目录（字体、图片等）
            ("kivy/data", "kivy/data"),
            ("kivy/tools", "kivy/tools"),
        ],
        "flet": [
            # Flet 需要 Flutter 引擎
            ("flet", "flet"),
            ("flet_core", "flet_core"),
            ("flet_runtime", "flet_runtime"),
        ],
        "dearpygui": [
            # DearPyGui 需要核心 DLL
            ("dearpygui", "dearpygui"),
        ],
        "textual": [
            # Textual 需要 CSS 样式文件
            ("textual", "textual"),
        ],
    }

    # 所有 Qt 绑定包列表（用于冲突检测）
    QT_BINDINGS = {"PyQt6", "PyQt5", "PySide6", "PySide2"}

    def __init__(self):
        self.dependencies: Set[str] = set()
        self.all_imports: Set[str] = set()  # 所有导入的模块
        self.excluded_modules: Set[str] = set()  # 排除的模块
        self.detected_gui_frameworks: Set[str] = set()  # 检测到的 GUI 框架
        self.primary_qt_framework: Optional[str] = None  # 主要使用的 Qt 框架
        self.log = print  # 日志回调函数
        self._project_internal_modules: Set[str] = set()  # 项目内部模块名

    def detect_primary_qt_framework(self, script_path: str, project_dir: Optional[str] = None) -> Optional[str]:
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
        qt_import_counts = {
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
                dirs[:] = [d for d in dirs if d not in {'.venv', 'venv', 'build', 'dist', '__pycache__', '.git', 'node_modules', 'site-packages'}]

                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                                # 计算每个 Qt 框架的导入次数
                                for qt_name in qt_import_counts.keys():
                                    # 匹配 import PyQt6 或 from PyQt6
                                    import_count = content.count(f'import {qt_name}') + content.count(f'from {qt_name}')
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
        for qt_binding in self.QT_BINDINGS:
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

    def get_detected_gui_frameworks(self) -> Set[str]:
        """
        获取检测到的 GUI 框架列表

        Returns:
            检测到的 GUI 框架集合
        """
        self.detected_gui_frameworks = set()

        # 检查所有已知的 GUI 框架
        all_deps_lower = {dep.lower() for dep in self.dependencies}
        all_imports_lower = {imp.lower() for imp in self.all_imports}
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

        return self.detected_gui_frameworks

    def get_framework_data_files(self) -> List[Tuple[str, str]]:
        """
        获取需要包含的框架数据文件

        Returns:
            (源路径模式, 目标路径) 列表
        """
        data_files = []
        detected = self.get_detected_gui_frameworks()

        for framework_name, files in self.FRAMEWORKS_WITH_DATA_FILES.items():
            # 检查是否检测到该框架
            if framework_name in {f.lower() for f in detected}:
                data_files.extend(files)

        return data_files

    def analyze(self, script_path: str, project_dir: Optional[str] = None) -> Set[str]:
        """
        分析脚本及项目的依赖

        Args:
            script_path: Python脚本路径
            project_dir: 项目目录（可选）

        Returns:
            依赖包集合
        """
        self.dependencies = set()
        self._project_internal_modules = set()

        # 先收集项目内部模块名
        if project_dir:
            self._collect_internal_modules(project_dir)
        else:
            # 单脚本模式，收集脚本所在目录的模块
            script_dir = os.path.dirname(script_path)
            if script_dir:
                self._collect_internal_modules(script_dir)

        # 从代码中提取依赖
        if project_dir:
            # 分析整个项目
            self._analyze_project(project_dir)
        else:
            # 只分析单个脚本
            self._analyze_file(script_path)

        # 读取requirements.txt（如果存在）
        requirements = self._read_requirements(script_path, project_dir)

        # 合并依赖
        self.dependencies.update(requirements)

        # 过滤掉标准库和项目内部模块
        self.dependencies = {
            dep for dep in self.dependencies
            if not self._is_stdlib(dep) and not self._is_internal_module(dep)
        }

        return self.dependencies

    def _collect_internal_modules(self, project_dir: str) -> None:
        """
        收集项目内部的模块名

        Args:
            project_dir: 项目目录
        """
        # 跳过的目录
        skip_dirs = {'.venv', 'venv', 'build', 'dist', '__pycache__', '.git',
                     'node_modules', 'site-packages', '.tox', '.pytest_cache',
                     'egg-info', '.eggs'}

        try:
            # 遍历项目目录
            for item in os.listdir(project_dir):
                item_path = os.path.join(project_dir, item)

                if os.path.isdir(item_path):
                    # 跳过特殊目录
                    if item in skip_dirs or item.startswith('.'):
                        continue
                    # 检查是否为Python包（包含__init__.py或任意.py文件）
                    if os.path.exists(os.path.join(item_path, "__init__.py")):
                        self._project_internal_modules.add(item)
                        # 递归收集子模块
                        self._collect_submodules(item_path, item)
                    elif any(f.endswith('.py') for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))):
                        # 目录包含.py文件，也视为可能的模块目录
                        self._project_internal_modules.add(item)

                elif item.endswith('.py') and item != '__init__.py':
                    # 单独的Python文件也是模块
                    module_name = item[:-3]  # 去掉.py扩展名
                    self._project_internal_modules.add(module_name)

        except Exception as e:
            print(f"警告: 收集内部模块时出错: {e}")

    def _collect_submodules(self, dir_path: str, parent_name: str) -> None:
        """
        递归收集子模块名

        Args:
            dir_path: 目录路径
            parent_name: 父模块名
        """
        skip_dirs = {'.venv', 'venv', 'build', 'dist', '__pycache__', '.git'}

        try:
            for item in os.listdir(dir_path):
                item_path = os.path.join(dir_path, item)

                if os.path.isdir(item_path):
                    if item in skip_dirs or item.startswith('.'):
                        continue
                    if os.path.exists(os.path.join(item_path, "__init__.py")):
                        # 子包也添加到内部模块
                        self._project_internal_modules.add(item)
                        self._collect_submodules(item_path, f"{parent_name}.{item}")

                elif item.endswith('.py') and item != '__init__.py':
                    # 子模块文件名也添加（不带.py）
                    module_name = item[:-3]
                    self._project_internal_modules.add(module_name)

        except Exception:
            pass

    def _is_internal_module(self, module_name: str) -> bool:
        """
        判断是否为项目内部模块

        Args:
            module_name: 模块名

        Returns:
            True 表示是内部模块
        """
        # 直接匹配项目内部模块
        if module_name in self._project_internal_modules:
            return True

        # 检查命名模式（PascalCase 且以特定后缀结尾的通常是内部模块）
        if self._is_likely_internal_by_naming(module_name):
            return True

        return False

    def _is_likely_internal_by_naming(self, name: str) -> bool:
        """
        通过命名模式判断是否可能是内部模块

        PyPI 包通常使用小写加下划线或连字符命名，
        而项目内部模块经常使用 PascalCase 命名。

        Args:
            name: 模块名

        Returns:
            True 表示可能是内部模块
        """
        if not name:
            return False

        # 检查是否是 PascalCase（首字母大写，包含多个大写字母）
        if name[0].isupper():
            upper_count = sum(1 for c in name if c.isupper())
            # 多个大写字母且没有下划线/连字符
            if upper_count >= 2 and '_' not in name and '-' not in name:
                # 常见的内部模块后缀
                internal_suffixes = (
                    'Nodes', 'Codes', 'Helpers', 'Generated', 'Specs',
                    'Definitions', 'Bases', 'Utils', 'Mixin', 'Base',
                    'Handler', 'Manager', 'Factory', 'Builder', 'Visitor',
                    'Parser', 'Lexer', 'Analyzer', 'Optimizer', 'Generator',
                    'Transformer', 'Processor', 'Worker', 'Runner', 'Loader',
                    'Service', 'Controller', 'Model', 'View', 'Schema',
                    'Serializer', 'Validator', 'Exception', 'Error', 'Config',
                )
                if any(name.endswith(suffix) for suffix in internal_suffixes):
                    return True

                # 名称很长（超过25字符）且全是字母，很可能是内部模块
                if len(name) > 25 and name.isalpha():
                    return True

                # 包含多个连续的大写字母开头单词（如 AttributeLookupNodes）
                # 统计大写字母后跟小写字母的模式数量
                camel_pattern_count = 0
                for i in range(len(name) - 1):
                    if name[i].isupper() and name[i + 1].islower():
                        camel_pattern_count += 1
                if camel_pattern_count >= 3:
                    return True

        return False

    def get_exclude_modules(self) -> List[str]:
        """
        获取建议排除的模块列表

        Returns:
            建议排除的模块列表
        """
        exclude_list = []

        # 1. 排除开发/测试包
        for dep in self.dependencies:
            if dep in self.DEV_PACKAGES:
                exclude_list.append(dep)
                self.excluded_modules.add(dep)

        # 2. 排除大型包的测试模块
        for dep in self.dependencies:
            if dep in self.LARGE_PACKAGES:
                for submodule in self.LARGE_PACKAGES[dep]:
                    exclude_list.append(submodule)

        # 3. 添加常见的测试和文档模块
        exclude_list.extend(
            [
                "test",
                "tests",
                "testing",
                "*.tests",
                "*.test",
                "*_test",
                "*_tests",
                "setuptools",
                "pip",
                "wheel",
            ]
        )

        return list(set(exclude_list))

    def get_hidden_imports(self) -> List[str]:
        """
        获取可能需要的隐藏导入

        Returns:
            隐藏导入列表
        """
        hidden = []

        # ========== Qt 框架 ==========
        # 只为主要使用的 Qt 框架添加隐藏导入，避免多 Qt 绑定冲突
        primary_qt = self.primary_qt_framework

        # 如果未检测主要框架，从依赖中选择一个（按优先级）
        if not primary_qt:
            for qt in ["PyQt6", "PySide6", "PyQt5", "PySide2"]:
                if qt in self.dependencies:
                    primary_qt = qt
                    break

        # PyQt6相关
        if primary_qt == "PyQt6":
            hidden.extend(
                [
                    "PyQt6.QtCore",
                    "PyQt6.QtGui",
                    "PyQt6.QtWidgets",
                    "PyQt6.sip",
                ]
            )

        # PyQt5相关
        elif primary_qt == "PyQt5":
            hidden.extend(
                [
                    "PyQt5.QtCore",
                    "PyQt5.QtGui",
                    "PyQt5.QtWidgets",
                    "PyQt5.sip",
                ]
            )

        # PySide6相关
        elif primary_qt == "PySide6":
            hidden.extend(
                [
                    "PySide6.QtCore",
                    "PySide6.QtGui",
                    "PySide6.QtWidgets",
                    "shiboken6",
                ]
            )

        # PySide2相关
        elif primary_qt == "PySide2":
            hidden.extend(
                [
                    "PySide2.QtCore",
                    "PySide2.QtGui",
                    "PySide2.QtWidgets",
                    "shiboken2",
                ]
            )

        # ========== PySimpleGUI ==========
        # PySimpleGUI 可以使用多种后端：tkinter, Qt, Wx, Web
        if "PySimpleGUI" in self.dependencies or "pysimplegui" in self.dependencies:
            hidden.extend(
                [
                    "PySimpleGUI",
                    "tkinter",
                    "tkinter.ttk",
                    "tkinter.filedialog",
                    "tkinter.messagebox",
                    "tkinter.colorchooser",
                    "tkinter.font",
                ]
            )
        # PySimpleGUIQt
        if "PySimpleGUIQt" in self.dependencies:
            hidden.extend(
                [
                    "PySimpleGUIQt",
                    "PyQt5.QtCore",
                    "PyQt5.QtGui",
                    "PyQt5.QtWidgets",
                ]
            )
        # PySimpleGUIWx
        if "PySimpleGUIWx" in self.dependencies:
            hidden.extend(
                [
                    "PySimpleGUIWx",
                    "wx",
                    "wx.adv",
                    "wx.lib",
                ]
            )

        # ========== Kivy ==========
        if "kivy" in self.dependencies:
            hidden.extend(
                [
                    "kivy",
                    "kivy.app",
                    "kivy.uix",
                    "kivy.uix.widget",
                    "kivy.uix.label",
                    "kivy.uix.button",
                    "kivy.uix.boxlayout",
                    "kivy.uix.gridlayout",
                    "kivy.uix.floatlayout",
                    "kivy.uix.anchorlayout",
                    "kivy.uix.relativelayout",
                    "kivy.uix.stacklayout",
                    "kivy.uix.scrollview",
                    "kivy.uix.textinput",
                    "kivy.uix.image",
                    "kivy.uix.popup",
                    "kivy.uix.screenmanager",
                    "kivy.uix.spinner",
                    "kivy.uix.slider",
                    "kivy.uix.switch",
                    "kivy.uix.checkbox",
                    "kivy.uix.progressbar",
                    "kivy.uix.dropdown",
                    "kivy.uix.filechooser",
                    "kivy.uix.tabbedpanel",
                    "kivy.uix.accordion",
                    "kivy.uix.carousel",
                    "kivy.uix.video",
                    "kivy.uix.camera",
                    "kivy.uix.recycleview",
                    "kivy.core",
                    "kivy.core.window",
                    "kivy.core.text",
                    "kivy.core.image",
                    "kivy.core.audio",
                    "kivy.core.video",
                    "kivy.core.clipboard",
                    "kivy.graphics",
                    "kivy.graphics.texture",
                    "kivy.graphics.vertex_instructions",
                    "kivy.graphics.context_instructions",
                    "kivy.graphics.fbo",
                    "kivy.graphics.shader",
                    "kivy.graphics.stencil_instructions",
                    "kivy.graphics.svg",
                    "kivy.graphics.cgl",
                    "kivy.graphics.opengl",
                    "kivy.graphics.transformation",
                    "kivy.lang",
                    "kivy.lang.builder",
                    "kivy.lang.parser",
                    "kivy.properties",
                    "kivy.clock",
                    "kivy.base",
                    "kivy.config",
                    "kivy.logger",
                    "kivy.event",
                    "kivy.factory",
                    "kivy.input",
                    "kivy.input.providers",
                    "kivy.input.providers.wm_touch",
                    "kivy.input.providers.wm_pen",
                    "kivy.input.providers.mouse",
                    "kivy.animation",
                    "kivy.atlas",
                    "kivy.cache",
                    "kivy.metrics",
                    "kivy.modules",
                    "kivy.network",
                    "kivy.parser",
                    "kivy.resources",
                    "kivy.storage",
                    "kivy.utils",
                    "kivy.vector",
                    "kivy.weakmethod",
                    # Kivy 依赖
                    "kivy_deps.sdl2",
                    "kivy_deps.glew",
                    "kivy_deps.angle",
                    "kivy_deps.gstreamer",
                    # 其他可能的依赖
                    "PIL",
                    "PIL.Image",
                    "docutils",
                    "pygments",
                ]
            )

        # ========== Flet ==========
        if "flet" in self.dependencies:
            hidden.extend(
                [
                    "flet",
                    "flet.flet",
                    "flet_core",
                    "flet_runtime",
                    "flet.fastapi",
                    "flet.utils",
                    "flet.version",
                    "flet.canvas",
                    "flet.matplotlib_chart",
                    "flet.plotly_chart",
                    # Flet 依赖
                    "httpx",
                    "websockets",
                    "watchdog",
                    "oauthlib",
                    "repath",
                    "cookiecutter",
                    "copier",
                ]
            )

        # ========== DearPyGui ==========
        if "dearpygui" in self.dependencies or "DearPyGui" in self.dependencies:
            hidden.extend(
                [
                    "dearpygui",
                    "dearpygui.dearpygui",
                    "dearpygui.demo",
                    "dearpygui._dearpygui",
                ]
            )

        # ========== CustomTkinter ==========
        if "customtkinter" in self.dependencies:
            hidden.extend(
                [
                    "customtkinter",
                    "customtkinter.windows",
                    "customtkinter.windows.widgets",
                    "customtkinter.windows.ctk_tk",
                    "customtkinter.windows.ctk_toplevel",
                    "darkdetect",
                    "tkinter",
                    "tkinter.ttk",
                    "tkinter.filedialog",
                    "tkinter.messagebox",
                    "tkinter.colorchooser",
                    "tkinter.font",
                    "PIL",
                    "PIL.Image",
                    "PIL.ImageTk",
                ]
            )

        # ========== Eel ==========
        if "eel" in self.dependencies:
            hidden.extend(
                [
                    "eel",
                    "bottle",
                    "bottle_websocket",
                    "gevent",
                    "gevent.ssl",
                    "gevent._ssl3",
                    "gevent.libuv",
                    "geventwebsocket",
                    "geventwebsocket.handler",
                    "geventwebsocket.websocket",
                    "whichcraft",
                    "pyparsing",
                ]
            )

        # ========== Toga (BeeWare) ==========
        if "toga" in self.dependencies:
            hidden.extend(
                [
                    "toga",
                    "toga.app",
                    "toga.window",
                    "toga.widgets",
                    "toga.handlers",
                    "toga.icons",
                    "toga.images",
                    "toga.fonts",
                    "toga.colors",
                    "toga.keys",
                    "toga.platform",
                    "toga_winforms",  # Windows后端
                    "toga_winforms.app",
                    "toga_winforms.window",
                    "toga_winforms.widgets",
                    "System",
                    "System.Windows",
                    "System.Windows.Forms",
                    "System.Drawing",
                    "clr",
                    "pythonnet",
                ]
            )

        # ========== Textual (TUI) ==========
        if "textual" in self.dependencies:
            hidden.extend(
                [
                    "textual",
                    "textual.app",
                    "textual.widgets",
                    "textual.containers",
                    "textual.screen",
                    "textual.binding",
                    "textual.css",
                    "textual.dom",
                    "textual.driver",
                    "textual.events",
                    "textual.geometry",
                    "textual.keys",
                    "textual.message",
                    "textual.reactive",
                    "textual.timer",
                    "textual.worker",
                    "rich",
                    "rich.console",
                    "rich.text",
                    "rich.panel",
                    "rich.table",
                    "rich.syntax",
                    "rich.markdown",
                    "rich.progress",
                    "rich.traceback",
                    "rich.logging",
                ]
            )

        # ========== PyForms ==========
        if "pyforms" in self.dependencies:
            hidden.extend(
                [
                    "pyforms",
                    "pyforms.gui",
                    "pyforms.gui.controls",
                    "pyforms_gui",
                    "pyforms_gui.controls",
                    "AnyQt",
                    "PyQt5.QtCore",
                    "PyQt5.QtGui",
                    "PyQt5.QtWidgets",
                ]
            )

        # ========== wxPython ==========
        if "wx" in self.dependencies or "wxPython" in self.dependencies:
            hidden.extend(
                [
                    "wx",
                    "wx.adv",
                    "wx.lib",
                    "wx.lib.agw",
                    "wx.lib.buttons",
                    "wx.lib.colourdb",
                    "wx.lib.embeddedimage",
                    "wx.lib.expando",
                    "wx.lib.fancytext",
                    "wx.lib.floatcanvas",
                    "wx.lib.imagebrowser",
                    "wx.lib.imageutils",
                    "wx.lib.intctrl",
                    "wx.lib.masked",
                    "wx.lib.mixins",
                    "wx.lib.newevent",
                    "wx.lib.platebtn",
                    "wx.lib.plot",
                    "wx.lib.pubsub",
                    "wx.lib.scrolledpanel",
                    "wx.lib.sized_controls",
                    "wx.lib.statbmp",
                    "wx.lib.stattext",
                    "wx.lib.wordwrap",
                    "wx.html",
                    "wx.html2",
                    "wx.xml",
                    "wx.xrc",
                    "wx.richtext",
                    "wx.stc",
                    "wx.grid",
                    "wx.dataview",
                    "wx.propgrid",
                    "wx.ribbon",
                    "wx.aui",
                    "wx.glcanvas",
                    "wx.media",
                ]
            )

        # ========== Wax (wxPython 包装器) ==========
        if "wax" in self.dependencies:
            hidden.extend(
                [
                    "wax",
                    "wx",
                    "wx.adv",
                    "wx.lib",
                ]
            )

        # ========== PyGUI ==========
        if "GUI" in self.dependencies or "pygui" in self.dependencies:
            hidden.extend(
                [
                    "GUI",
                    "GUI.Application",
                    "GUI.Window",
                    "GUI.View",
                    "GUI.Button",
                    "GUI.Label",
                    "GUI.TextField",
                ]
            )

        # ========== Libavg ==========
        if "libavg" in self.dependencies:
            hidden.extend(
                [
                    "libavg",
                    "libavg.app",
                    "libavg.avg",
                    "libavg.player",
                    "libavg.ui",
                    "libavg.utils",
                ]
            )

        # ========== 其他常用库 ==========
        # requests相关
        if "requests" in self.dependencies:
            hidden.extend(
                [
                    "urllib3",
                    "charset_normalizer",  # chardet已被charset-normalizer替代
                    "certifi",
                    "idna",
                ]
            )

        # pandas相关
        if "pandas" in self.dependencies:
            hidden.extend(
                [
                    "pandas._libs",
                    "pandas._libs.tslibs",
                    "pandas._libs.tslibs.np_datetime",
                    "pandas._libs.tslibs.nattype",
                    "pandas._libs.tslibs.timedeltas",
                ]
            )

        # numpy相关
        if "numpy" in self.dependencies:
            hidden.extend(
                [
                    "numpy.core._multiarray_umath",
                    "numpy.core._dtype_ctypes",
                    "numpy.random.common",
                    "numpy.random.bounded_integers",
                    "numpy.random.entropy",
                ]
            )

        # PIL/Pillow 相关
        if "PIL" in self.dependencies or "Pillow" in self.dependencies:
            hidden.extend(
                [
                    "PIL",
                    "PIL.Image",
                    "PIL.ImageTk",
                    "PIL.ImageDraw",
                    "PIL.ImageFont",
                    "PIL.ImageFilter",
                    "PIL.ImageEnhance",
                    "PIL.ImageOps",
                    "PIL.ImageGrab",
                    "PIL._imaging",
                    "PIL._tkinter_finder",
                ]
            )

        # matplotlib 相关
        if "matplotlib" in self.dependencies:
            hidden.extend(
                [
                    "matplotlib",
                    "matplotlib.pyplot",
                    "matplotlib.backends",
                    "matplotlib.backends.backend_tkagg",
                    "matplotlib.backends.backend_agg",
                    "matplotlib.backends.backend_qt5agg",
                    "matplotlib.figure",
                    "matplotlib.axes",
                ]
            )

        # OpenCV 相关
        if "cv2" in self.dependencies:
            hidden.extend(
                [
                    "cv2",
                    "numpy",
                    "numpy.core._multiarray_umath",
                ]
            )

        # 去重
        return list(set(hidden))

    def get_package_size_info(self, python_path: str) -> Dict[str, Dict[str, float]]:
        """
        获取已安装包的大小信息

        Args:
            python_path: Python可执行文件路径

        Returns:
            包大小信息字典
        """
        size_info = {}

        for dep in self.dependencies:
            try:
                # 使用pip show获取包信息
                result = subprocess.run(
                    [python_path, "-m", "pip", "show", dep],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=5,
                    creationflags=CREATE_NO_WINDOW,
                )

                if result.returncode == 0:
                    lines = result.stdout.split("\n")
                    location = None

                    for line in lines:
                        if line.startswith("Location:"):
                            location = line.split(":", 1)[1].strip()
                            break

                    if location:
                        # 计算包目录大小
                        package_path = Path(location) / dep
                        if package_path.exists():
                            size = self._get_dir_size(package_path)
                            size_info[dep] = {
                                "size": size,
                                "size_mb": round(size / (1024 * 1024), 2),
                                "location": str(package_path),
                            }
            except Exception as e:
                # 忽略错误，继续处理其他包
                pass

        return size_info

    def _get_dir_size(self, path: Path) -> int:
        """递归计算目录大小"""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except:
                        pass
        except:
            pass
        return total

    def get_optimization_suggestions(
        self, python_path: str
    ) -> Tuple[List[str], List[str], Dict[str, Dict[str, float]]]:
        """
        获取打包优化建议

        Args:
            python_path: Python可执行文件路径

        Returns:
            (排除模块列表, 隐藏导入列表, 包大小信息)
        """
        exclude_modules = self.get_exclude_modules()
        hidden_imports = self.get_hidden_imports()
        size_info = self.get_package_size_info(python_path)

        return exclude_modules, hidden_imports, size_info

    def generate_optimization_report(self, python_path: str) -> str:
        """
        生成优化报告

        Args:
            python_path: Python可执行文件路径

        Returns:
            优化报告文本
        """
        exclude_modules, hidden_imports, size_info = self.get_optimization_suggestions(
            python_path
        )

        report = []
        report.append("=" * 60)
        report.append("打包优化分析报告")
        report.append("=" * 60)
        report.append("")

        # 依赖包列表
        report.append(f"检测到 {len(self.dependencies)} 个第三方依赖包:")
        for dep in sorted(self.dependencies):
            if dep in size_info:
                size_mb = size_info[dep]["size_mb"]
                report.append(f"  - {dep} ({size_mb} MB)")
            else:
                report.append(f"  - {dep}")
        report.append("")

        # 大型包警告
        large_packages = [
            dep
            for dep in self.dependencies
            if dep in size_info and size_info[dep]["size_mb"] > 50
        ]
        if large_packages:
            report.append("⚠ 检测到大型包 (>50MB):")
            for pkg in large_packages:
                report.append(f"  - {pkg} ({size_info[pkg]['size_mb']} MB)")
            report.append("  建议: 确认是否真的需要这些大型库")
            report.append("")

        # 排除建议
        if exclude_modules:
            report.append(f"建议排除 {len(exclude_modules)} 个模块/包:")
            for mod in sorted(set(exclude_modules))[:20]:  # 只显示前20个
                if mod in self.DEV_PACKAGES:
                    report.append(f"  - {mod} (开发/测试工具)")
                else:
                    report.append(f"  - {mod}")
            if len(exclude_modules) > 20:
                report.append(f"  ... 还有 {len(exclude_modules) - 20} 个")
            report.append("")

        # 隐藏导入建议
        if hidden_imports:
            report.append(f"建议添加 {len(hidden_imports)} 个隐藏导入:")
            for mod in sorted(hidden_imports)[:10]:
                report.append(f"  - {mod}")
            if len(hidden_imports) > 10:
                report.append(f"  ... 还有 {len(hidden_imports) - 10} 个")
            report.append("")

        # 总体建议
        report.append("优化建议:")
        report.append("  1. 使用虚拟环境，只安装必要的依赖")
        report.append("  2. 自动排除开发/测试相关的包")
        report.append("  3. 排除大型库的测试模块")
        report.append("  4. 使用UPX压缩可进一步减小体积")
        report.append("")

        # 预计优化效果
        total_size = sum(info["size_mb"] for info in size_info.values())
        excluded_size = sum(
            size_info[dep]["size_mb"]
            for dep in self.excluded_modules
            if dep in size_info
        )
        if total_size > 0:
            saved_percent = (excluded_size / total_size) * 100 if total_size > 0 else 0
            report.append(f"预计效果:")
            report.append(f"  - 总依赖大小: {total_size:.2f} MB")
            report.append(f"  - 可排除大小: {excluded_size:.2f} MB")
            report.append(f"  - 预计节省: {saved_percent:.1f}%")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)

    def _analyze_project(self, project_dir: str):
        """分析整个项目目录"""
        project_path = Path(project_dir)

        # 需要跳过的目录
        skip_dirs = {".venv", "venv", "build", "dist", "__pycache__", ".git",
                     "node_modules", "site-packages", ".tox", ".pytest_cache",
                     "egg-info", ".eggs"}

        # 遍历所有Python文件
        for py_file in project_path.rglob("*.py"):
            # 跳过虚拟环境和构建目录
            if any(part in skip_dirs for part in py_file.parts):
                continue

            # 跳过隐藏目录
            if any(part.startswith('.') and part not in {'.', '..'} for part in py_file.parts):
                continue

            try:
                self._analyze_file(str(py_file))
            except Exception as e:
                print(f"警告: 分析文件 {py_file} 时出错: {e}")

    def _analyze_file(self, file_path: str):
        """分析单个Python文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 使用AST解析
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        self.dependencies.add(module_name)

                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module_name = node.module.split(".")[0]
                        self.dependencies.add(module_name)

        except SyntaxError as e:
            print(f"警告: 文件 {file_path} 语法错误: {e}")
        except Exception as e:
            print(f"警告: 分析文件 {file_path} 时出错: {e}")

    def _read_requirements(
        self, script_path: str, project_dir: Optional[str]
    ) -> Set[str]:
        """读取requirements.txt文件"""
        requirements = set()

        # 确定搜索路径
        search_paths = []

        if project_dir:
            search_paths.append(Path(project_dir) / "requirements.txt")

        script_dir = Path(script_path).parent
        search_paths.append(script_dir / "requirements.txt")

        # 读取requirements.txt
        for req_path in search_paths:
            if req_path.exists():
                try:
                    with open(req_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()

                            # 跳过空行和注释
                            if not line or line.startswith("#"):
                                continue

                            # 提取包名（去除版本号和其他选项）
                            # 支持格式: package, package==1.0, package>=1.0, package[extra]
                            match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
                            if match:
                                package_name = match.group(1)
                                requirements.add(package_name)

                except Exception as e:
                    print(f"警告: 读取 {req_path} 时出错: {e}")

                break  # 只读取第一个找到的requirements.txt

        return requirements

    def _is_stdlib(self, module_name: str) -> bool:
        """判断是否为Python标准库"""
        return module_name in self.STDLIB_MODULES

    def get_requirements_content(self) -> str:
        """获取requirements.txt格式的内容"""
        return "\n".join(sorted(self.dependencies))

    def save_requirements(self, output_path: str):
        """保存依赖到requirements.txt文件"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.get_requirements_content())
