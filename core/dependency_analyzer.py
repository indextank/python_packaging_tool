import ast
import importlib
import os
import pkgutil
import re
import subprocess
import sys
import tempfile
import threading
import time
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

    # 已配置的库列表（用于判断是否使用通用策略）
    CONFIGURED_LIBRARIES = {
        # GUI框架
        "PyQt6", "PyQt5", "PySide6", "PySide2", "tkinter", "customtkinter",
        "wx", "wxPython", "kivy", "flet", "dearpygui", "DearPyGui", "toga",
        "textual", "PySimpleGUI", "PySimpleGUIQt", "PySimpleGUIWx", "eel",
        "pyforms", "GUI", "pygui", "libavg", "wax",
        # Web爬虫
        "selenium", "scrapy", "Scrapy", "playwright", "requests_html",
        "bs4", "beautifulsoup4", "lxml",
        # Web框架
        "flask", "Flask", "django", "Django", "fastapi", "tornado", "aiohttp",
        "gradio", "streamlit", "dash", "bokeh", "altair",
        # 数据科学
        "numpy", "pandas", "scipy", "matplotlib", "seaborn", "plotly",
        "statsmodels",
        # 机器学习
        "sklearn", "scikit-learn", "tensorflow", "tf", "torch", "pytorch",
        "transformers", "xgboost", "lightgbm", "catboost", "onnxruntime",
        # 数据库
        "pymongo", "redis", "pymysql", "psycopg2", "sqlalchemy", "SQLAlchemy",
        "sqlmodel", "alembic", "peewee", "motor", "aiomysql", "aiopg",
        # 办公文档
        "openpyxl", "xlrd", "xlwt", "docx", "python-docx", "pptx", "python-pptx",
        "PyPDF2", "pypdf", "pdfplumber", "fitz", "pymupdf", "reportlab",
        # 任务调度
        "celery", "Celery", "apscheduler", "schedule",
        # 实用工具
        "requests", "httpx", "loguru", "tqdm", "click", "typer", "colorama",
        "arrow", "pendulum", "jieba", "qrcode", "pyqrcode", "barcode",
        "python-barcode", "watchdog", "dotenv", "python-dotenv", "pydantic",
        "marshmallow", "tenacity", "retrying", "faker", "Faker", "attrs", "attr",
        # 网络
        "websocket", "websocket-client", "paramiko", "httptools", "uvloop",
        "gunicorn",
        # 图像
        "PIL", "Pillow", "pillow-simd", "cv2", "imageio", "pytesseract",
        "easyocr",
        # 音频
        "pygame", "pyglet", "arcade", "panda3d", "ursina", "sounddevice",
        "soundfile", "pyaudio", "pydub",
        # 系统交互
        "win32api", "win32com", "win32gui", "win32process", "pywin32",
        "pyautogui", "pynput", "keyboard", "mouse", "comtypes", "pythonnet", "clr",
        # 缓存序列化
        "joblib", "dill", "cloudpickle", "cachetools", "diskcache",
        # 日期时间
        "pytz", "dateutil", "python-dateutil",
        # Markdown
        "markdown", "mistune",
        # 加密
        "cryptography", "Crypto", "pycryptodome",
        # YAML/TOML
        "yaml", "pyyaml", "toml", "tomli",
        # 其他
        "magic", "python-magic",
    }

    def __init__(self):
        self.dependencies: Set[str] = set()
        self.all_imports: Set[str] = set()  # 所有导入的模块
        self.excluded_modules: Set[str] = set()  # 排除的模块
        self.detected_gui_frameworks: Set[str] = set()  # 检测到的 GUI 框架
        self.primary_qt_framework: Optional[str] = None  # 主要使用的 Qt 框架
        self.log = print  # 日志回调函数
        self._project_internal_modules: Set[str] = set()  # 项目内部模块名
        # 新增属性
        self._dynamic_imports: Set[str] = set()  # 动态追踪到的导入
        self._auto_collected_modules: Dict[str, List[str]] = {}  # 自动收集的子模块
        self._unconfigured_libraries: Set[str] = set()  # 未配置的库（使用通用策略）
        self._module_type_cache: Dict[str, bool] = {}  # 缓存模块类型检测结果

    def is_real_package(self, module_name: str, python_path: Optional[str] = None) -> bool:
        """
        检测一个模块是否是真正的包（有 __path__ 属性）。
        单文件模块（如 img2pdf.py）不是包，不能使用 --include-package。

        Args:
            module_name: 模块名
            python_path: Python解释器路径（可选）

        Returns:
            True 如果是真正的包，False 如果是单文件模块
        """
        # 检查缓存
        if module_name in self._module_type_cache:
            return self._module_type_cache[module_name]

        if python_path is None:
            python_path = sys.executable

        check_code = f'''
import sys
import importlib
try:
    mod = importlib.import_module("{module_name}")
    # 真正的包有 __path__ 属性
    if hasattr(mod, "__path__"):
        print("package")
    else:
        print("module")
except:
    print("error")
'''
        try:
            result = subprocess.run(
                [python_path, "-c", check_code],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            output = result.stdout.strip()
            if output == "package":
                self._module_type_cache[module_name] = True
                return True
            elif output == "module":
                self._module_type_cache[module_name] = False
                return False
            else:
                # 导入失败或其他错误，默认假设是包（保守处理）
                self._module_type_cache[module_name] = True
                return True
        except:
            # 默认假设是包，保守处理
            return True

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
                    "matplotlib.backends.backend_qt6agg",
                    "matplotlib.figure",
                    "matplotlib.axes",
                    "mpl_toolkits",
                    "mpl_toolkits.mplot3d",
                ]
            )

        # ========== scipy 相关 ==========
        if "scipy" in self.dependencies:
            hidden.extend(
                [
                    "scipy",
                    "scipy.integrate",
                    "scipy.optimize",
                    "scipy.stats",
                    "scipy.sparse",
                    "scipy.linalg",
                    "scipy.signal",
                    "scipy.interpolate",
                    "scipy.ndimage",
                    "scipy.spatial",
                    "scipy.special",
                ]
            )

        # ========== scikit-learn 相关 ==========
        if "sklearn" in self.dependencies or "scikit-learn" in self.dependencies:
            hidden.extend(
                [
                    "sklearn",
                    "sklearn.ensemble",
                    "sklearn.linear_model",
                    "sklearn.tree",
                    "sklearn.svm",
                    "sklearn.neighbors",
                    "sklearn.naive_bayes",
                    "sklearn.cluster",
                    "sklearn.decomposition",
                    "sklearn.model_selection",
                    "sklearn.preprocessing",
                    "sklearn.feature_extraction",
                    "sklearn.metrics",
                    "sklearn.pipeline",
                    "sklearn.utils",
                    "joblib",
                ]
            )

        # ========== TensorFlow 相关 ==========
        if "tensorflow" in self.dependencies or "tf" in self.dependencies:
            hidden.extend(
                [
                    "tensorflow",
                    "tensorflow.keras",
                    "tensorflow.keras.models",
                    "tensorflow.keras.layers",
                    "tensorflow.keras.optimizers",
                    "tensorflow.keras.callbacks",
                    "tensorflow.python",
                    "tensorflow.python.framework",
                    "tensorflow.python.ops",
                    "tensorflow.python.util",
                    "tensorflow.lite",
                    "tensorboard",
                ]
            )

        # ========== PyTorch 相关 ==========
        if "torch" in self.dependencies or "pytorch" in self.dependencies:
            hidden.extend(
                [
                    "torch",
                    "torch.nn",
                    "torch.nn.functional",
                    "torch.optim",
                    "torch.utils",
                    "torch.utils.data",
                    "torch.autograd",
                    "torch.cuda",
                    "torch.jit",
                    "torchvision",
                    "torchvision.models",
                    "torchvision.transforms",
                    "torchvision.datasets",
                ]
            )

        # ========== transformers 相关 ==========
        if "transformers" in self.dependencies:
            hidden.extend(
                [
                    "transformers",
                    "transformers.models",
                    "transformers.pipelines",
                    "transformers.tokenization_utils",
                    "transformers.modeling_utils",
                    "transformers.configuration_utils",
                    "tokenizers",
                    "huggingface_hub",
                ]
            )

        # ========== plotly 相关 ==========
        if "plotly" in self.dependencies:
            hidden.extend(
                [
                    "plotly",
                    "plotly.graph_objs",
                    "plotly.express",
                    "plotly.figure_factory",
                    "plotly.io",
                    "plotly.offline",
                    "plotly.tools",
                ]
            )

        # ========== seaborn 相关 ==========
        if "seaborn" in self.dependencies:
            hidden.extend(
                [
                    "seaborn",
                    "seaborn.matrix",
                    "seaborn.distributions",
                    "seaborn.categorical",
                    "seaborn.regression",
                ]
            )

        # ========== statsmodels 相关 ==========
        if "statsmodels" in self.dependencies:
            hidden.extend(
                [
                    "statsmodels",
                    "statsmodels.api",
                    "statsmodels.formula",
                    "statsmodels.tsa",
                    "statsmodels.stats",
                    "patsy",
                ]
            )

        # ========== xgboost 相关 ==========
        if "xgboost" in self.dependencies:
            hidden.extend(
                [
                    "xgboost",
                    "xgboost.sklearn",
                    "xgboost.plotting",
                ]
            )

        # ========== lightgbm 相关 ==========
        if "lightgbm" in self.dependencies:
            hidden.extend(
                [
                    "lightgbm",
                    "lightgbm.sklearn",
                ]
            )

        # ========== catboost 相关 ==========
        if "catboost" in self.dependencies:
            hidden.extend(
                [
                    "catboost",
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

        # ========== Selenium 相关 ==========
        if "selenium" in self.dependencies:
            hidden.extend(
                [
                    "selenium",
                    "selenium.webdriver",
                    "selenium.webdriver.common",
                    "selenium.webdriver.common.by",
                    "selenium.webdriver.common.keys",
                    "selenium.webdriver.common.action_chains",
                    "selenium.webdriver.common.desired_capabilities",
                    "selenium.webdriver.support",
                    "selenium.webdriver.support.ui",
                    "selenium.webdriver.support.wait",
                    "selenium.webdriver.support.expected_conditions",
                    "selenium.webdriver.chrome",
                    "selenium.webdriver.chrome.service",
                    "selenium.webdriver.chrome.options",
                    "selenium.webdriver.chrome.webdriver",
                    "selenium.webdriver.firefox",
                    "selenium.webdriver.firefox.service",
                    "selenium.webdriver.firefox.options",
                    "selenium.webdriver.firefox.webdriver",
                    "selenium.webdriver.edge",
                    "selenium.webdriver.edge.service",
                    "selenium.webdriver.edge.options",
                    "selenium.webdriver.safari",
                    "selenium.webdriver.safari.service",
                    "selenium.webdriver.remote",
                    "selenium.webdriver.remote.webdriver",
                    "selenium.webdriver.remote.webelement",
                    "selenium.common",
                    "selenium.common.exceptions",
                    "urllib3",
                    "certifi",
                ]
            )

        # ========== Scrapy 相关 ==========
        if "scrapy" in self.dependencies or "Scrapy" in self.dependencies:
            hidden.extend(
                [
                    "scrapy",
                    "scrapy.spiders",
                    "scrapy.http",
                    "scrapy.selector",
                    "scrapy.item",
                    "scrapy.loader",
                    "scrapy.crawler",
                    "scrapy.settings",
                    "scrapy.exceptions",
                    "scrapy.utils",
                    "scrapy.pipelines",
                    "scrapy.downloadermiddlewares",
                    "scrapy.spidermiddlewares",
                    "scrapy.extensions",
                    "twisted",
                    "twisted.internet",
                    "twisted.web",
                    "w3lib",
                    "parsel",
                    "lxml",
                    "lxml.html",
                    "lxml.etree",
                ]
            )

        # ========== Playwright 相关 ==========
        if "playwright" in self.dependencies:
            hidden.extend(
                [
                    "playwright",
                    "playwright.sync_api",
                    "playwright.async_api",
                    "playwright._impl",
                    "playwright._impl._api_structures",
                    "playwright._impl._browser",
                    "playwright._impl._page",
                    "greenlet",
                ]
            )

        # ========== BeautifulSoup4 相关 ==========
        if "bs4" in self.dependencies or "beautifulsoup4" in self.dependencies:
            hidden.extend(
                [
                    "bs4",
                    "bs4.builder",
                    "bs4.element",
                    "bs4.dammit",
                    "soupsieve",
                    "lxml",
                    "lxml.html",
                    "lxml.etree",
                    "html5lib",
                ]
            )

        # ========== lxml 相关 ==========
        if "lxml" in self.dependencies:
            hidden.extend(
                [
                    "lxml",
                    "lxml.html",
                    "lxml.etree",
                    "lxml.objectify",
                    "lxml._elementpath",
                    "lxml.builder",
                    "lxml.cssselect",
                ]
            )

        # ========== requests-html 相关 ==========
        if "requests_html" in self.dependencies or "requests-html" in self.dependencies:
            hidden.extend(
                [
                    "requests_html",
                    "pyppeteer",
                    "websockets",
                    "pyee",
                    "bs4",
                    "lxml",
                ]
            )

        # ========== PyAutoGUI 相关 ==========
        if "pyautogui" in self.dependencies:
            hidden.extend(
                [
                    "pyautogui",
                    "pymsgbox",
                    "pytweening",
                    "pyscreeze",
                    "pygetwindow",
                    "pyrect",
                    "pyperclip",
                    "mouseinfo",
                    "PIL",
                    "PIL.Image",
                    "PIL.ImageGrab",
                ]
            )

        # ========== pytest 相关 ==========
        if "pytest" in self.dependencies:
            hidden.extend(
                [
                    "pytest",
                    "pytest.unittest",
                    "_pytest",
                    "_pytest.assertion",
                    "_pytest.config",
                    "_pytest.fixtures",
                    "_pytest.main",
                    "_pytest.python",
                    "pluggy",
                    "py",
                ]
            )

        # ========== Flask 相关 ==========
        if "flask" in self.dependencies or "Flask" in self.dependencies:
            hidden.extend(
                [
                    "flask",
                    "flask.app",
                    "flask.blueprints",
                    "flask.ctx",
                    "flask.helpers",
                    "flask.json",
                    "flask.logging",
                    "flask.sessions",
                    "flask.signals",
                    "flask.templating",
                    "flask.views",
                    "flask.wrappers",
                    "werkzeug",
                    "werkzeug.serving",
                    "werkzeug.middleware",
                    "werkzeug.routing",
                    "werkzeug.security",
                    "werkzeug.utils",
                    "jinja2",
                    "jinja2.ext",
                    "jinja2.loaders",
                    "click",
                    "itsdangerous",
                    "markupsafe",
                ]
            )

        # ========== Django 相关 ==========
        if "django" in self.dependencies or "Django" in self.dependencies:
            hidden.extend(
                [
                    "django",
                    "django.apps",
                    "django.conf",
                    "django.contrib",
                    "django.contrib.admin",
                    "django.contrib.auth",
                    "django.contrib.contenttypes",
                    "django.contrib.sessions",
                    "django.contrib.messages",
                    "django.contrib.staticfiles",
                    "django.core",
                    "django.core.management",
                    "django.core.wsgi",
                    "django.db",
                    "django.db.models",
                    "django.forms",
                    "django.http",
                    "django.middleware",
                    "django.shortcuts",
                    "django.template",
                    "django.urls",
                    "django.utils",
                    "django.views",
                    "asgiref",
                    "sqlparse",
                ]
            )

        # ========== FastAPI 相关 ==========
        if "fastapi" in self.dependencies:
            hidden.extend(
                [
                    "fastapi",
                    "fastapi.applications",
                    "fastapi.routing",
                    "fastapi.params",
                    "fastapi.dependencies",
                    "fastapi.security",
                    "fastapi.middleware",
                    "fastapi.responses",
                    "fastapi.encoders",
                    "fastapi.exceptions",
                    "starlette",
                    "starlette.applications",
                    "starlette.routing",
                    "starlette.middleware",
                    "starlette.responses",
                    "starlette.requests",
                    "pydantic",
                    "pydantic.fields",
                    "pydantic.main",
                    "pydantic.types",
                    "uvicorn",
                    "uvicorn.config",
                    "uvicorn.main",
                ]
            )

        # ========== SQLAlchemy 相关 ==========
        if "sqlalchemy" in self.dependencies or "SQLAlchemy" in self.dependencies:
            hidden.extend(
                [
                    "sqlalchemy",
                    "sqlalchemy.engine",
                    "sqlalchemy.orm",
                    "sqlalchemy.pool",
                    "sqlalchemy.sql",
                    "sqlalchemy.ext",
                    "sqlalchemy.ext.declarative",
                    "sqlalchemy.ext.hybrid",
                    "sqlalchemy.dialects",
                    "sqlalchemy.dialects.mysql",
                    "sqlalchemy.dialects.postgresql",
                    "sqlalchemy.dialects.sqlite",
                    "sqlalchemy.dialects.mssql",
                    "sqlalchemy.dialects.oracle",
                ]
            )

        # ========== Redis 相关 ==========
        if "redis" in self.dependencies:
            hidden.extend(
                [
                    "redis",
                    "redis.client",
                    "redis.connection",
                    "redis.exceptions",
                    "redis.sentinel",
                    "redis.cluster",
                ]
            )

        # ========== Celery 相关 ==========
        if "celery" in self.dependencies or "Celery" in self.dependencies:
            hidden.extend(
                [
                    "celery",
                    "celery.app",
                    "celery.worker",
                    "celery.task",
                    "celery.result",
                    "celery.signals",
                    "celery.backends",
                    "celery.backends.redis",
                    "celery.backends.database",
                    "celery.concurrency",
                    "celery.utils",
                    "kombu",
                    "kombu.transport",
                    "kombu.serialization",
                    "billiard",
                    "vine",
                ]
            )

        # ========== openpyxl 相关 ==========
        if "openpyxl" in self.dependencies:
            hidden.extend(
                [
                    "openpyxl",
                    "openpyxl.workbook",
                    "openpyxl.worksheet",
                    "openpyxl.cell",
                    "openpyxl.styles",
                    "openpyxl.chart",
                    "openpyxl.utils",
                    "et_xmlfile",
                ]
            )

        # ========== xlrd/xlwt 相关 ==========
        if "xlrd" in self.dependencies:
            hidden.extend(
                [
                    "xlrd",
                    "xlrd.book",
                    "xlrd.sheet",
                ]
            )
        if "xlwt" in self.dependencies:
            hidden.extend(
                [
                    "xlwt",
                    "xlwt.Workbook",
                    "xlwt.Style",
                ]
            )

        # ========== pywin32 相关 ==========
        if any(dep in self.dependencies for dep in ["win32api", "win32com", "win32gui", "win32process", "pywin32"]):
            hidden.extend(
                [
                    "win32api",
                    "win32con",
                    "win32com",
                    "win32com.client",
                    "win32com.server",
                    "win32gui",
                    "win32process",
                    "win32file",
                    "win32event",
                    "win32security",
                    "win32service",
                    "pywintypes",
                    "pythoncom",
                ]
            )

        # ========== schedule 相关 ==========
        if "schedule" in self.dependencies:
            hidden.extend(
                [
                    "schedule",
                ]
            )

        # ========== apscheduler 相关 ==========
        if "apscheduler" in self.dependencies:
            hidden.extend(
                [
                    "apscheduler",
                    "apscheduler.schedulers",
                    "apscheduler.triggers",
                    "apscheduler.executors",
                    "apscheduler.jobstores",
                    "tzlocal",
                ]
            )

        # ========== cryptography 相关 ==========
        if "cryptography" in self.dependencies:
            hidden.extend(
                [
                    "cryptography",
                    "cryptography.fernet",
                    "cryptography.hazmat",
                    "cryptography.hazmat.primitives",
                    "cryptography.hazmat.backends",
                    "cryptography.x509",
                    "_cffi_backend",
                ]
            )

        # ========== pycryptodome 相关 ==========
        if "Crypto" in self.dependencies or "pycryptodome" in self.dependencies:
            hidden.extend(
                [
                    "Crypto",
                    "Crypto.Cipher",
                    "Crypto.Hash",
                    "Crypto.PublicKey",
                    "Crypto.Random",
                    "Crypto.Signature",
                    "Crypto.Util",
                ]
            )

        # ========== paramiko 相关 ==========
        if "paramiko" in self.dependencies:
            hidden.extend(
                [
                    "paramiko",
                    "paramiko.client",
                    "paramiko.transport",
                    "paramiko.channel",
                    "paramiko.sftp",
                    "paramiko.sftp_client",
                ]
            )

        # ========== pymysql 相关 ==========
        if "pymysql" in self.dependencies:
            hidden.extend(
                [
                    "pymysql",
                    "pymysql.cursors",
                    "pymysql.connections",
                ]
            )

        # ========== psycopg2 相关 ==========
        if "psycopg2" in self.dependencies:
            hidden.extend(
                [
                    "psycopg2",
                    "psycopg2.extensions",
                    "psycopg2.extras",
                    "psycopg2._psycopg",
                ]
            )

        # ========== pymongo 相关 ==========
        if "pymongo" in self.dependencies:
            hidden.extend(
                [
                    "pymongo",
                    "pymongo.collection",
                    "pymongo.database",
                    "pymongo.cursor",
                    "bson",
                    "bson.json_util",
                ]
            )

        # ========== aiohttp 相关 ==========
        if "aiohttp" in self.dependencies:
            hidden.extend(
                [
                    "aiohttp",
                    "aiohttp.client",
                    "aiohttp.web",
                    "aiohttp.connector",
                    "aiohttp.helpers",
                    "multidict",
                    "yarl",
                    "async_timeout",
                    "aiosignal",
                ]
            )

        # ========== tornado 相关 ==========
        if "tornado" in self.dependencies:
            hidden.extend(
                [
                    "tornado",
                    "tornado.web",
                    "tornado.ioloop",
                    "tornado.httpserver",
                    "tornado.websocket",
                ]
            )

        # ========== PyYAML 相关 ==========
        if "yaml" in self.dependencies or "pyyaml" in self.dependencies:
            hidden.extend(
                [
                    "yaml",
                    "yaml.loader",
                    "yaml.dumper",
                ]
            )

        # ========== toml 相关 ==========
        if "toml" in self.dependencies or "tomli" in self.dependencies:
            hidden.extend(
                [
                    "toml",
                    "tomli",
                ]
            )

        # ========== loguru 相关 ==========
        if "loguru" in self.dependencies:
            hidden.extend(
                [
                    "loguru",
                    "loguru._logger",
                ]
            )

        # ========== click 相关 ==========
        if "click" in self.dependencies:
            hidden.extend(
                [
                    "click",
                    "click.core",
                    "click.decorators",
                    "click.types",
                    "click.utils",
                ]
            )

        # ========== typer 相关 ==========
        if "typer" in self.dependencies:
            hidden.extend(
                [
                    "typer",
                    "typer.main",
                    "click",
                ]
            )

        # ========== tqdm 相关 ==========
        if "tqdm" in self.dependencies:
            hidden.extend(
                [
                    "tqdm",
                    "tqdm.auto",
                    "tqdm.std",
                    "tqdm.gui",
                    "tqdm.asyncio",
                ]
            )

        # ========== colorama 相关 ==========
        if "colorama" in self.dependencies:
            hidden.extend(
                [
                    "colorama",
                    "colorama.ansi",
                    "colorama.win32",
                ]
            )

        # ========== arrow 相关 ==========
        if "arrow" in self.dependencies:
            hidden.extend(
                [
                    "arrow",
                    "arrow.arrow",
                    "arrow.factory",
                ]
            )

        # ========== pendulum 相关 ==========
        if "pendulum" in self.dependencies:
            hidden.extend(
                [
                    "pendulum",
                    "pendulum.tz",
                    "pendulum.parsing",
                ]
            )

        # ========== httpx 相关 ==========
        if "httpx" in self.dependencies:
            hidden.extend(
                [
                    "httpx",
                    "httpx._client",
                    "httpx._models",
                    "httpx._transports",
                    "h11",
                    "h2",
                    "httpcore",
                ]
            )

        # ========== websocket-client 相关 ==========
        if "websocket" in self.dependencies or "websocket-client" in self.dependencies:
            hidden.extend(
                [
                    "websocket",
                    "websocket._app",
                    "websocket._core",
                ]
            )

        # ========== Pillow 额外功能 ==========
        if "PIL" in self.dependencies or "Pillow" in self.dependencies:
            # 额外的 Pillow 插件和功能
            hidden.extend(
                [
                    "PIL.BmpImagePlugin",
                    "PIL.GifImagePlugin",
                    "PIL.JpegImagePlugin",
                    "PIL.PngImagePlugin",
                    "PIL.TiffImagePlugin",
                    "PIL.WebPImagePlugin",
                ]
            )

        # ========== pdfplumber / PyPDF2 相关 ==========
        if "pdfplumber" in self.dependencies:
            hidden.extend(
                [
                    "pdfplumber",
                    "pdfplumber.page",
                    "pdfplumber.pdf",
                    "pdfminer",
                    "pdfminer.high_level",
                ]
            )
        if "PyPDF2" in self.dependencies or "pypdf" in self.dependencies:
            hidden.extend(
                [
                    "PyPDF2",
                    "pypdf",
                ]
            )

        # ========== python-docx 相关 ==========
        if "docx" in self.dependencies or "python-docx" in self.dependencies:
            hidden.extend(
                [
                    "docx",
                    "docx.document",
                    "docx.oxml",
                    "docx.shared",
                ]
            )

        # ========== python-pptx 相关 ==========
        if "pptx" in self.dependencies or "python-pptx" in self.dependencies:
            hidden.extend(
                [
                    "pptx",
                    "pptx.presentation",
                    "pptx.slide",
                    "pptx.shapes",
                ]
            )

        # ========== jieba 相关 ==========
        if "jieba" in self.dependencies:
            hidden.extend(
                [
                    "jieba",
                    "jieba.analyse",
                    "jieba.posseg",
                ]
            )

        # ========== PIL/Pillow 图像处理扩展 ==========
        if "imageio" in self.dependencies:
            hidden.extend(
                [
                    "imageio",
                    "imageio.core",
                    "imageio.plugins",
                ]
            )

        # ========== python-magic 相关 ==========
        if "magic" in self.dependencies or "python-magic" in self.dependencies:
            hidden.extend(
                [
                    "magic",
                ]
            )

        # ========== pyqrcode / qrcode 相关 ==========
        if "qrcode" in self.dependencies:
            hidden.extend(
                [
                    "qrcode",
                    "qrcode.image",
                    "qrcode.image.svg",
                    "qrcode.image.pure",
                ]
            )
        if "pyqrcode" in self.dependencies:
            hidden.extend(
                [
                    "pyqrcode",
                ]
            )

        # ========== barcode 相关 ==========
        if "barcode" in self.dependencies or "python-barcode" in self.dependencies:
            hidden.extend(
                [
                    "barcode",
                    "barcode.writer",
                ]
            )

        # ========== watchdog 相关 ==========
        if "watchdog" in self.dependencies:
            hidden.extend(
                [
                    "watchdog",
                    "watchdog.observers",
                    "watchdog.events",
                ]
            )

        # ========== pymupdf (fitz) 相关 ==========
        if "fitz" in self.dependencies or "pymupdf" in self.dependencies:
            hidden.extend(
                [
                    "fitz",
                    "fitz.fitz",
                ]
            )

        # ========== reportlab 相关 ==========
        if "reportlab" in self.dependencies:
            hidden.extend(
                [
                    "reportlab",
                    "reportlab.pdfgen",
                    "reportlab.pdfgen.canvas",
                    "reportlab.lib",
                    "reportlab.lib.pagesizes",
                    "reportlab.lib.styles",
                    "reportlab.lib.units",
                    "reportlab.lib.colors",
                    "reportlab.platypus",
                    "reportlab.platypus.paragraph",
                    "reportlab.platypus.tables",
                    "reportlab.platypus.doctemplate",
                ]
            )

        # ========== markdown 相关 ==========
        if "markdown" in self.dependencies:
            hidden.extend(
                [
                    "markdown",
                    "markdown.extensions",
                    "markdown.preprocessors",
                    "markdown.blockprocessors",
                    "markdown.treeprocessors",
                    "markdown.inlinepatterns",
                    "markdown.postprocessors",
                ]
            )

        # ========== mistune 相关 ==========
        if "mistune" in self.dependencies:
            hidden.extend(
                [
                    "mistune",
                    "mistune.directives",
                    "mistune.plugins",
                ]
            )

        # ========== pytesseract 相关 ==========
        if "pytesseract" in self.dependencies:
            hidden.extend(
                [
                    "pytesseract",
                ]
            )

        # ========== easyocr 相关 ==========
        if "easyocr" in self.dependencies:
            hidden.extend(
                [
                    "easyocr",
                    "easyocr.recognition",
                    "easyocr.detection",
                    "easyocr.utils",
                ]
            )

        # ========== onnxruntime 相关 ==========
        if "onnxruntime" in self.dependencies:
            hidden.extend(
                [
                    "onnxruntime",
                    "onnxruntime.capi",
                    "onnxruntime.capi.onnxruntime_pybind11_state",
                ]
            )

        # ========== gradio 相关 ==========
        if "gradio" in self.dependencies:
            hidden.extend(
                [
                    "gradio",
                    "gradio.interface",
                    "gradio.components",
                    "gradio.blocks",
                    "gradio.routes",
                    "gradio.utils",
                    "gradio.processing_utils",
                    "gradio.external",
                ]
            )

        # ========== streamlit 相关 ==========
        if "streamlit" in self.dependencies:
            hidden.extend(
                [
                    "streamlit",
                    "streamlit.components",
                    "streamlit.elements",
                    "streamlit.delta_generator",
                    "streamlit.runtime",
                    "streamlit.runtime.scriptrunner",
                    "streamlit.web",
                ]
            )

        # ========== dash 相关 ==========
        if "dash" in self.dependencies:
            hidden.extend(
                [
                    "dash",
                    "dash.dependencies",
                    "dash.development",
                    "dash.exceptions",
                    "dash_core_components",
                    "dash_html_components",
                    "dash_table",
                ]
            )

        # ========== bokeh 相关 ==========
        if "bokeh" in self.dependencies:
            hidden.extend(
                [
                    "bokeh",
                    "bokeh.plotting",
                    "bokeh.models",
                    "bokeh.layouts",
                    "bokeh.io",
                    "bokeh.server",
                    "bokeh.palettes",
                    "bokeh.transform",
                ]
            )

        # ========== altair 相关 ==========
        if "altair" in self.dependencies:
            hidden.extend(
                [
                    "altair",
                    "altair.vegalite",
                    "altair.utils",
                ]
            )

        # ========== sqlmodel 相关 ==========
        if "sqlmodel" in self.dependencies:
            hidden.extend(
                [
                    "sqlmodel",
                    "sqlmodel.main",
                    "sqlmodel.engine",
                ]
            )

        # ========== alembic 相关 ==========
        if "alembic" in self.dependencies:
            hidden.extend(
                [
                    "alembic",
                    "alembic.config",
                    "alembic.migration",
                    "alembic.operations",
                    "alembic.autogenerate",
                    "alembic.script",
                ]
            )

        # ========== peewee 相关 ==========
        if "peewee" in self.dependencies:
            hidden.extend(
                [
                    "peewee",
                    "playhouse",
                    "playhouse.migrate",
                    "playhouse.pool",
                    "playhouse.shortcuts",
                ]
            )

        # ========== motor 相关 ==========
        if "motor" in self.dependencies:
            hidden.extend(
                [
                    "motor",
                    "motor.motor_asyncio",
                    "motor.motor_tornado",
                ]
            )

        # ========== aiomysql 相关 ==========
        if "aiomysql" in self.dependencies:
            hidden.extend(
                [
                    "aiomysql",
                    "aiomysql.cursors",
                    "aiomysql.connection",
                    "aiomysql.pool",
                ]
            )

        # ========== aiopg 相关 ==========
        if "aiopg" in self.dependencies:
            hidden.extend(
                [
                    "aiopg",
                    "aiopg.pool",
                    "aiopg.connection",
                    "aiopg.cursor",
                ]
            )

        # ========== httptools 相关 ==========
        if "httptools" in self.dependencies:
            hidden.extend(
                [
                    "httptools",
                    "httptools.parser",
                ]
            )

        # ========== uvloop 相关 ==========
        if "uvloop" in self.dependencies:
            hidden.extend(
                [
                    "uvloop",
                ]
            )

        # ========== gunicorn 相关 ==========
        if "gunicorn" in self.dependencies:
            hidden.extend(
                [
                    "gunicorn",
                    "gunicorn.app",
                    "gunicorn.workers",
                    "gunicorn.config",
                ]
            )

        # ========== pytz 相关 ==========
        if "pytz" in self.dependencies:
            hidden.extend(
                [
                    "pytz",
                ]
            )

        # ========== dateutil 相关 ==========
        if "dateutil" in self.dependencies or "python-dateutil" in self.dependencies:
            hidden.extend(
                [
                    "dateutil",
                    "dateutil.parser",
                    "dateutil.tz",
                    "dateutil.relativedelta",
                ]
            )

        # ========== faker 相关 ==========
        if "faker" in self.dependencies or "Faker" in self.dependencies:
            hidden.extend(
                [
                    "faker",
                    "faker.providers",
                ]
            )

        # ========== attrs 相关 ==========
        if "attrs" in self.dependencies or "attr" in self.dependencies:
            hidden.extend(
                [
                    "attr",
                    "attrs",
                ]
            )

        # ========== pydantic 相关 ==========
        if "pydantic" in self.dependencies:
            hidden.extend(
                [
                    "pydantic",
                    "pydantic.fields",
                    "pydantic.main",
                    "pydantic.types",
                    "pydantic.validators",
                    "pydantic.networks",
                    "pydantic.color",
                ]
            )

        # ========== marshmallow 相关 ==========
        if "marshmallow" in self.dependencies:
            hidden.extend(
                [
                    "marshmallow",
                    "marshmallow.fields",
                    "marshmallow.validate",
                    "marshmallow.decorators",
                ]
            )

        # ========== python-dotenv 相关 ==========
        if "dotenv" in self.dependencies or "python-dotenv" in self.dependencies:
            hidden.extend(
                [
                    "dotenv",
                    "dotenv.main",
                ]
            )

        # ========== tenacity 相关 ==========
        if "tenacity" in self.dependencies:
            hidden.extend(
                [
                    "tenacity",
                    "tenacity.retry",
                    "tenacity.stop",
                    "tenacity.wait",
                ]
            )

        # ========== retrying 相关 ==========
        if "retrying" in self.dependencies:
            hidden.extend(
                [
                    "retrying",
                ]
            )

        # ========== cachetools 相关 ==========
        if "cachetools" in self.dependencies:
            hidden.extend(
                [
                    "cachetools",
                    "cachetools.func",
                ]
            )

        # ========== diskcache 相关 ==========
        if "diskcache" in self.dependencies:
            hidden.extend(
                [
                    "diskcache",
                    "diskcache.core",
                ]
            )

        # ========== joblib 相关 ==========
        if "joblib" in self.dependencies:
            hidden.extend(
                [
                    "joblib",
                    "joblib.parallel",
                    "joblib.memory",
                ]
            )

        # ========== dill 相关 ==========
        if "dill" in self.dependencies:
            hidden.extend(
                [
                    "dill",
                    "dill._dill",
                ]
            )

        # ========== cloudpickle 相关 ==========
        if "cloudpickle" in self.dependencies:
            hidden.extend(
                [
                    "cloudpickle",
                    "cloudpickle.cloudpickle",
                ]
            )

        # ========== pygame 相关 ==========
        if "pygame" in self.dependencies:
            hidden.extend(
                [
                    "pygame",
                    "pygame.base",
                    "pygame.constants",
                    "pygame.rect",
                    "pygame.rwobject",
                    "pygame.surface",
                    "pygame.surflock",
                    "pygame.color",
                    "pygame.bufferproxy",
                    "pygame.math",
                    "pygame.mixer",
                    "pygame.mixer_music",
                    "pygame.font",
                    "pygame.image",
                    "pygame.joystick",
                    "pygame.key",
                    "pygame.mouse",
                    "pygame.cursors",
                    "pygame.display",
                    "pygame.draw",
                    "pygame.event",
                    "pygame.pixelcopy",
                    "pygame.transform",
                    "pygame.sprite",
                    "pygame.time",
                ]
            )

        # ========== pyglet 相关 ==========
        if "pyglet" in self.dependencies:
            hidden.extend(
                [
                    "pyglet",
                    "pyglet.window",
                    "pyglet.app",
                    "pyglet.graphics",
                    "pyglet.image",
                    "pyglet.text",
                    "pyglet.font",
                    "pyglet.media",
                    "pyglet.sprite",
                    "pyglet.shapes",
                    "pyglet.gl",
                ]
            )

        # ========== arcade 相关 ==========
        if "arcade" in self.dependencies:
            hidden.extend(
                [
                    "arcade",
                    "arcade.window_commands",
                    "arcade.draw_commands",
                    "arcade.sprite",
                    "arcade.sprite_list",
                    "arcade.physics_engines",
                    "arcade.tilemap",
                ]
            )

        # ========== panda3d 相关 ==========
        if "panda3d" in self.dependencies:
            hidden.extend(
                [
                    "panda3d",
                    "direct",
                    "direct.showbase",
                    "direct.task",
                    "direct.actor",
                    "direct.gui",
                ]
            )

        # ========== ursina 相关 ==========
        if "ursina" in self.dependencies:
            hidden.extend(
                [
                    "ursina",
                    "ursina.prefabs",
                    "ursina.shaders",
                ]
            )

        # ========== pythonnet 相关 ==========
        if "pythonnet" in self.dependencies or "clr" in self.dependencies:
            hidden.extend(
                [
                    "clr",
                    "Python.Runtime",
                ]
            )

        # ========== comtypes 相关 ==========
        if "comtypes" in self.dependencies:
            hidden.extend(
                [
                    "comtypes",
                    "comtypes.client",
                    "comtypes.automation",
                    "comtypes.server",
                ]
            )

        # ========== pynput 相关 ==========
        if "pynput" in self.dependencies:
            hidden.extend(
                [
                    "pynput",
                    "pynput.keyboard",
                    "pynput.mouse",
                ]
            )

        # ========== keyboard 相关 ==========
        if "keyboard" in self.dependencies:
            hidden.extend(
                [
                    "keyboard",
                    "keyboard._keyboard_event",
                ]
            )

        # ========== mouse 相关 ==========
        if "mouse" in self.dependencies:
            hidden.extend(
                [
                    "mouse",
                    "mouse._mouse_event",
                ]
            )

        # ========== sounddevice 相关 ==========
        if "sounddevice" in self.dependencies:
            hidden.extend(
                [
                    "sounddevice",
                    "_sounddevice",
                ]
            )

        # ========== soundfile 相关 ==========
        if "soundfile" in self.dependencies:
            hidden.extend(
                [
                    "soundfile",
                    "_soundfile",
                ]
            )

        # ========== pyaudio 相关 ==========
        if "pyaudio" in self.dependencies:
            hidden.extend(
                [
                    "pyaudio",
                    "_portaudio",
                ]
            )

        # ========== pydub 相关 ==========
        if "pydub" in self.dependencies:
            hidden.extend(
                [
                    "pydub",
                    "pydub.audio_segment",
                    "pydub.effects",
                    "pydub.playback",
                ]
            )

        # ========== pillow-simd 相关 ==========
        if "pillow-simd" in self.dependencies:
            hidden.extend(
                [
                    "PIL",
                    "PIL.Image",
                    "PIL._imaging",
                ]
            )

        # ========== numpy 扩展支持 ==========
        if "numpy" in self.dependencies:
            # 添加更多 numpy 子模块
            hidden.extend(
                [
                    "numpy.fft",
                    "numpy.polynomial",
                    "numpy.random.mtrand",
                    "numpy.random.bit_generator",
                    "numpy.random.generator",
                ]
            )

        # ========== 第一层：动态追踪到的导入 ==========
        if self._dynamic_imports:
            self.log(f"\n添加动态追踪到的 {len(self._dynamic_imports)} 个导入...")
            hidden.extend(list(self._dynamic_imports))

        # ========== 第二层：通用库自动支持 ==========
        # 处理未在已知配置列表中的库
        unconfigured = set()
        for dep in self.dependencies:
            # 跳过标准库
            if self._is_stdlib(dep):
                continue

            # 检查是否已配置（检查多种可能的名称形式）
            dep_lower = dep.lower()
            dep_normalized = dep.replace('-', '_').replace('.', '_')

            is_configured = (
                dep in self.CONFIGURED_LIBRARIES or
                dep_lower in {lib.lower() for lib in self.CONFIGURED_LIBRARIES} or
                dep_normalized in self.CONFIGURED_LIBRARIES
            )

            # 检查是否已经在hidden中有相关导入
            has_hidden = any(dep_lower in h.lower() for h in hidden)

            if not is_configured and not has_hidden:
                unconfigured.add(dep)

        # 对未配置的库使用通用策略
        if unconfigured:
            self.log(f"\n检测到 {len(unconfigured)} 个未配置的库，使用通用策略:")
            for dep in sorted(unconfigured):
                self._unconfigured_libraries.add(dep)

                # 添加库本身
                hidden.append(dep)

                # 检测是否是真正的包还是单文件模块
                is_package = self.is_real_package(dep)

                if is_package:
                    self.log(f"  ⚠️ {dep} (包)")
                    # 如果已经自动收集了子模块，使用它们
                    if dep in self._auto_collected_modules:
                        submodules = self._auto_collected_modules[dep]
                        hidden.extend(submodules)
                        self.log(f"     已使用自动收集的 {len(submodules)} 个子模块")
                    else:
                        # 添加常见子模块模式
                        common_patterns = [
                            f"{dep}.utils",
                            f"{dep}.core",
                            f"{dep}.base",
                            f"{dep}.main",
                            f"{dep}.api",
                            f"{dep}.models",
                            f"{dep}.config",
                            f"{dep}.exceptions",
                            f"{dep}.helpers",
                            f"{dep}.common",
                            f"{dep}._internal",
                        ]
                        hidden.extend(common_patterns)
                        self.log(f"     使用常见模式策略（11个常见子模块）")
                else:
                    # 单文件模块，不需要添加子模块
                    self.log(f"  ⚠️ {dep} (单文件模块)")

        # 去重
        return list(set(hidden))

    # ========== 动态模块导入追踪 ==========
    def _detect_gui_in_script(self, script_path: str) -> Tuple[bool, str]:
        """
        检测脚本是否是 GUI 程序（通过检测主循环调用）

        仅检测导入是不够的，因为很多非 GUI 程序也会导入 GUI 库用于其他目的。
        这里检测的是实际调用 GUI 主循环的代码。

        Args:
            script_path: 脚本路径

        Returns:
            (是否是GUI程序, GUI框架名称)
        """
        # GUI 主循环调用模式 - 只有真正运行 GUI 的程序才会调用这些
        gui_mainloop_patterns = {
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

        # 同时需要检测导入，确保主循环确实属于 GUI 框架
        gui_import_patterns = {
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

        try:
            with open(script_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            for framework, mainloop_patterns in gui_mainloop_patterns.items():
                # 首先检查是否导入了这个框架
                import_patterns = gui_import_patterns.get(framework, [])
                has_import = any(pattern in content for pattern in import_patterns)

                if has_import:
                    # 然后检查是否调用了主循环
                    for pattern in mainloop_patterns:
                        if pattern in content:
                            return True, framework
        except Exception:
            pass

        return False, ""

    def trace_dynamic_imports(
        self,
        script_path: str,
        python_path: str,
        project_dir: Optional[str] = None,
        timeout: int = 20
    ) -> Tuple[bool, Set[str]]:
        """
        动态追踪脚本运行时的所有导入

        Args:
            script_path: Python脚本路径
            python_path: Python解释器路径
            project_dir: 项目目录
            timeout: 超时时间（秒）

        Returns:
            (是否成功, 追踪到的模块集合)
        """
        self.log("\n" + "=" * 50)
        self.log("第一层防护：动态模块导入追踪")
        self.log("=" * 50)

        # 检测是否是 GUI 程序
        is_gui, gui_framework = self._detect_gui_in_script(script_path)
        if is_gui:
            self.log(f"检测到 GUI 框架: {gui_framework}")
            self.log("GUI 程序不适合动态追踪（会打开窗口），跳过此步骤")
            self.log("将使用静态分析 + 通用策略")
            return False, set()

        # 创建追踪脚本 - 只追踪导入阶段，不执行主逻辑
        tracer_code = '''
import sys
import importlib
import importlib.abc
import json
import threading

class ImportTracer(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.imports = set()

    def find_module(self, fullname, path=None):
        self.imports.add(fullname)
        return None

tracer = ImportTracer()
sys.meta_path.insert(0, tracer)

# 用于标记是否应该退出
_should_exit = False
_import_phase_done = False

def output_and_exit():
    """输出收集到的导入并退出"""
    print("__IMPORTS_START__")
    print(json.dumps(list(tracer.imports)))
    print("__IMPORTS_END__")
    sys.stdout.flush()
    import os
    os._exit(0)

# 设置超时保护
def timeout_handler():
    output_and_exit()

timer = threading.Timer({timeout}, timeout_handler)
timer.daemon = True
timer.start()

# 拦截常见的 GUI 主循环入口，防止进入事件循环
_original_modules = {{}}

class GUIBlocker:
    """阻止 GUI 事件循环启动"""

    @staticmethod
    def block_tkinter():
        try:
            import tkinter
            original_mainloop = tkinter.Tk.mainloop
            def blocked_mainloop(self, n=0):
                output_and_exit()
            tkinter.Tk.mainloop = blocked_mainloop

            # 也拦截 Misc.mainloop
            if hasattr(tkinter, 'Misc'):
                tkinter.Misc.mainloop = blocked_mainloop
        except:
            pass

    @staticmethod
    def block_pyqt():
        for qt_module in ['PyQt6.QtWidgets', 'PyQt5.QtWidgets', 'PySide6.QtWidgets', 'PySide2.QtWidgets']:
            try:
                QtWidgets = importlib.import_module(qt_module)
                original_exec = QtWidgets.QApplication.exec
                def blocked_exec(self=None):
                    output_and_exit()
                QtWidgets.QApplication.exec = blocked_exec
                QtWidgets.QApplication.exec_ = blocked_exec
            except:
                pass

    @staticmethod
    def block_wx():
        try:
            import wx
            original_mainloop = wx.App.MainLoop
            def blocked_mainloop(self):
                output_and_exit()
            wx.App.MainLoop = blocked_mainloop
        except:
            pass

    @staticmethod
    def block_pygame():
        try:
            import pygame
            # pygame 没有显式的主循环，但我们可以在 display.flip 时退出
            original_flip = pygame.display.flip
            _flip_count = [0]
            def blocked_flip():
                _flip_count[0] += 1
                if _flip_count[0] > 2:  # 允许几次初始化
                    output_and_exit()
                return original_flip()
            pygame.display.flip = blocked_flip
        except:
            pass

# 应用所有阻止器
GUIBlocker.block_tkinter()
GUIBlocker.block_pyqt()
GUIBlocker.block_wx()
GUIBlocker.block_pygame()

try:
    # 运行目标脚本
    import runpy
    runpy.run_path("{script_path}", run_name="__main__")
except SystemExit:
    pass
except Exception as e:
    pass
finally:
    timer.cancel()
    output_and_exit()
'''.format(
            timeout=timeout - 2,
            script_path=script_path.replace("\\", "\\\\")
        )

        # 写入临时文件
        tracer_script = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(tracer_code)
                tracer_script = f.name

            self.log(f"运行脚本进行动态追踪（超时: {timeout}秒）...")

            # 设置工作目录
            cwd = project_dir if project_dir else os.path.dirname(script_path)

            # 运行追踪脚本
            env = os.environ.copy()
            if project_dir:
                env['PYTHONPATH'] = project_dir

            result = subprocess.run(
                [python_path, tracer_script],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # 解析输出
            stdout = result.stdout
            if "__IMPORTS_START__" in stdout and "__IMPORTS_END__" in stdout:
                start = stdout.index("__IMPORTS_START__") + len("__IMPORTS_START__")
                end = stdout.index("__IMPORTS_END__")
                imports_json = stdout[start:end].strip()

                import json
                traced_imports = set(json.loads(imports_json))

                # 过滤标准库和内部模块
                filtered_imports = set()
                for imp in traced_imports:
                    root_module = imp.split('.')[0]
                    if not self._is_stdlib(root_module):
                        filtered_imports.add(imp)

                self._dynamic_imports = filtered_imports
                self.log(f"✓ 动态追踪成功！捕获到 {len(filtered_imports)} 个第三方模块导入")

                # 显示部分结果
                if filtered_imports:
                    sample = sorted(list(filtered_imports))[:10]
                    self.log(f"  示例: {', '.join(sample)}{'...' if len(filtered_imports) > 10 else ''}")

                return True, filtered_imports
            else:
                self.log("⚠️ 动态追踪未能获取导入信息")
                if result.stderr:
                    self.log(f"  错误: {result.stderr[:200]}")
                return False, set()

        except subprocess.TimeoutExpired:
            self.log(f"⚠️ 脚本运行超时（{timeout}秒）")
            self.log("  可能是 GUI 程序或长时间运行的脚本，切换到通用策略")
            # 尝试终止进程
            try:
                import psutil
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline', [])
                        if cmdline and tracer_script and tracer_script in ' '.join(cmdline):
                            proc.terminate()
                    except:
                        pass
            except:
                pass
            return False, set()
        except Exception as e:
            self.log(f"⚠️ 动态追踪失败: {str(e)}")
            self.log("  将使用通用库自动支持策略")
            return False, set()
        finally:
            # 清理临时文件
            try:
                if tracer_script and os.path.exists(tracer_script):
                    os.unlink(tracer_script)
            except:
                pass

    def check_script_runnable(
        self,
        script_path: str,
        python_path: str,
        project_dir: Optional[str] = None
    ) -> bool:
        """
        检查脚本是否可以运行（快速语法检查+导入检查）

        Returns:
            True 如果脚本可以运行
        """
        self.log("\n检查脚本是否可运行...")

        # 1. 语法检查
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                source = f.read()
            compile(source, script_path, 'exec')
            self.log("  ✓ 语法检查通过")
        except SyntaxError as e:
            self.log(f"  ✗ 语法错误: {e}")
            return False

        # 2. 快速导入检查（只检查顶层导入）
        check_code = f'''
import sys
sys.path.insert(0, r"{project_dir or os.path.dirname(script_path)}")
try:
    import ast
    with open(r"{script_path}", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])

    # 尝试导入
    failed = []
    for imp in set(imports):
        if imp in ["__future__"]:
            continue
        try:
            __import__(imp)
        except ImportError:
            failed.append(imp)

    if failed:
        print("IMPORT_FAILED:" + ",".join(failed))
        sys.exit(1)
    else:
        print("IMPORT_OK")
        sys.exit(0)
except Exception as e:
    print(f"CHECK_ERROR:{{e}}")
    sys.exit(1)
'''

        try:
            result = subprocess.run(
                [python_path, '-c', check_code],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if "IMPORT_OK" in result.stdout:
                self.log("  ✓ 导入检查通过")
                return True
            elif "IMPORT_FAILED" in result.stdout:
                failed = result.stdout.split("IMPORT_FAILED:")[1].strip()
                self.log(f"  ⚠️ 部分导入失败: {failed}")
                self.log("  脚本可能无法完整运行，将使用混合策略")
                return False
            else:
                self.log(f"  ⚠️ 检查结果未知")
                return False

        except subprocess.TimeoutExpired:
            self.log("  ⚠️ 检查超时")
            return False
        except Exception as e:
            self.log(f"  ⚠️ 检查失败: {e}")
            return False

    # ========== 通用库自动支持 ==========
    def auto_collect_submodules(
        self,
        package_name: str,
        python_path: str
    ) -> List[str]:
        """
        自动收集包的所有子模块

        Args:
            package_name: 包名
            python_path: Python解释器路径

        Returns:
            子模块列表
        """
        if package_name in self._auto_collected_modules:
            return self._auto_collected_modules[package_name]

        collect_code = f'''
import sys
import json
import pkgutil
import importlib

try:
    package = importlib.import_module("{package_name}")
    submodules = ["{package_name}"]

    if hasattr(package, "__path__"):
        for importer, modname, ispkg in pkgutil.walk_packages(
            package.__path__,
            prefix=package.__name__ + "."
        ):
            submodules.append(modname)
            # 限制数量，避免过多
            if len(submodules) > 100:
                break

    print("__SUBMODULES__:" + json.dumps(submodules))
except Exception as e:
    print("__ERROR__:" + str(e))
'''

        try:
            result = subprocess.run(
                [python_path, '-c', collect_code],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if "__SUBMODULES__:" in result.stdout:
                import json
                json_str = result.stdout.split("__SUBMODULES__:")[1].strip()
                submodules = json.loads(json_str)
                self._auto_collected_modules[package_name] = submodules
                return submodules
        except:
            pass

        # 失败时返回基本模块
        return [package_name]

    def collect_all_unconfigured_submodules(self, python_path: str) -> None:
        """
        收集所有未配置库的子模块

        Args:
            python_path: Python解释器路径
        """
        self.log("\n" + "=" * 50)
        self.log("第二层防护：自动收集子模块")
        self.log("=" * 50)

        unconfigured = []
        for dep in self.dependencies:
            if self._is_stdlib(dep):
                continue

            dep_lower = dep.lower()
            is_configured = (
                dep in self.CONFIGURED_LIBRARIES or
                dep_lower in {lib.lower() for lib in self.CONFIGURED_LIBRARIES}
            )

            if not is_configured:
                unconfigured.append(dep)

        if not unconfigured:
            self.log("所有依赖都已有配置，无需自动收集")
            return

        self.log(f"发现 {len(unconfigured)} 个未配置的库，开始自动收集子模块:")

        for dep in unconfigured:
            self.log(f"\n  收集 {dep} 的子模块...")
            submodules = self.auto_collect_submodules(dep, python_path)

            if len(submodules) > 1:
                self.log(f"    ✓ 收集到 {len(submodules)} 个子模块")
            else:
                self.log(f"    使用基础模块")

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
