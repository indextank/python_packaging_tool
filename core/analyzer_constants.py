"""
依赖分析器常量定义模块

本模块包含 DependencyAnalyzer 使用的所有常量定义，包括：
- Python 标准库模块列表
- 大型包及其子模块
- 开发/测试相关的包
- GUI 框架映射
- Qt 绑定包列表
- 已配置库列表
"""

from typing import Dict, List, Set, Tuple

# Python标准库列表（部分常用的）
STDLIB_MODULES: Set[str] = {
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
LARGE_PACKAGES: Dict[str, List[str]] = {
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
DEV_PACKAGES: Set[str] = {
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
GUI_FRAMEWORK_MAPPING: Dict[str, str] = {
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
FRAMEWORKS_WITH_DATA_FILES: Dict[str, List[Tuple[str, str]]] = {
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
QT_BINDINGS: Set[str] = {"PyQt6", "PyQt5", "PySide6", "PySide2"}

# 已配置的库列表（用于判断是否使用通用策略）
CONFIGURED_LIBRARIES: Set[str] = {
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
    "websocket", "websocket-client", "paramiko", "sshtunnel",
    "httptools", "uvloop",
    "gunicorn", "urllib3", "dns", "dnspython", "httplib2", "aiohttp",
    "certifi", "chardet", "charset_normalizer", "idna",
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

# 包名到导入名的映射（处理安装名和导入名不一致的情况）
PACKAGE_IMPORT_MAP: Dict[str, str] = {
    'dnspython': 'dns',
    'pillow': 'PIL',
    'beautifulsoup4': 'bs4',
    'pyyaml': 'yaml',
    'python-dateutil': 'dateutil',
    'opencv-python': 'cv2',
    'opencv-contrib-python': 'cv2',
    'pymysql': 'pymysql',
    'mysql-connector-python': 'mysql.connector',
    'requests': 'requests',
    'urllib3': 'urllib3',
    'certifi': 'certifi',
    'charset-normalizer': 'charset_normalizer',
    'idna': 'idna',
}

# 已知的单文件模块（明确不是包）
KNOWN_SINGLE_FILE_MODULES: Set[str] = {
    'img2pdf', 'pyperclip', 'keyboard', 'mouse', 'pynput',
    'colorama', 'tqdm', 'click',
}

# 已知的标准库包（明确是包）
KNOWN_STDLIB_PACKAGES: Set[str] = {
    'email', 'http', 'urllib', 'xml', 'json', 'logging',
    'multiprocessing', 'concurrent', 'asyncio', 'collections',
    'distutils', 'unittest', 'doctest', 'pdb', 'pydoc',
}
