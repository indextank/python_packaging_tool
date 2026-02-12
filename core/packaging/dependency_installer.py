"""
依赖安装模块

本模块负责安装 Python 项目的依赖包，包括：
- 分析和过滤依赖
- 使用多镜像源安装依赖
- 安装打包工具（PyInstaller/Nuitka）

功能：
- 过滤内置模块和项目内部模块
- 导入名到 PyPI 包名的映射
- 支持多镜像源自动切换
"""

import os
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Set, Tuple

from core.packaging.base import CREATE_NO_WINDOW
from core.packaging.network_utils import NetworkUtils


class DependencyInstaller:
    """依赖安装器"""

    # Python 内置模块和特殊模块映射（不需要或需要特殊处理的模块）
    BUILTIN_MODULES: Set[str] = {
        'Tkinter', 'tkinter', 'tkFileDialog', 'tkMessageBox', 'tkSimpleDialog',
        'ScrolledText', 'tkFont', 'tkColorChooser', 'tkCommonDialog',
        '_tkinter', 'turtle', 'turtledemo',
        # 其他内置/特殊模块
        'antigravity', 'this', '__hello__', '__phello__',
    }

    # 导入名到 PyPI 包名的映射
    IMPORT_TO_PACKAGE_MAP: Dict[str, str] = {
        'PIL': 'Pillow',
        'chardet': 'charset-normalizer',
        'cv2': 'opencv-python',
        'skimage': 'scikit-image',
        'sklearn': 'scikit-learn',
        'win32api': 'pywin32',
        'win32com': 'pywin32',
        'win32con': 'pywin32',
        'win32file': 'pywin32',
        'win32gui': 'pywin32',
        'win32process': 'pywin32',
        'pywintypes': 'pywin32',
        'pythoncom': 'pywin32',
        'yaml': 'pyyaml',
        'dotenv': 'python-dotenv',
        # DNS 相关
        'dns': 'dnspython',
        # 其他常见映射
        'bs4': 'beautifulsoup4',
        'dateutil': 'python-dateutil',
        'Crypto': 'pycryptodome',
        'Cryptodome': 'pycryptodomex',
        'wx': 'wxPython',
        'serial': 'pyserial',
        'usb': 'pyusb',
        'git': 'GitPython',
        'magic': 'python-magic',
        'docx': 'python-docx',
        'pptx': 'python-pptx',
        'jwt': 'PyJWT',
        'jose': 'python-jose',
        'ldap': 'python-ldap',
        'ldap3': 'ldap3',
        'memcache': 'python-memcached',
        'socks': 'PySocks',
        'lxml': 'lxml',
        'attr': 'attrs',
        'ruamel': 'ruamel.yaml',
        'fitz': 'PyMuPDF',
        'telegram': 'python-telegram-bot',
        'discord': 'discord.py',
        'flask_cors': 'Flask-Cors',
        'flask_login': 'Flask-Login',
        'flask_wtf': 'Flask-WTF',
        'flask_sqlalchemy': 'Flask-SQLAlchemy',
        'werkzeug': 'Werkzeug',
        'jinja2': 'Jinja2',
        'markupsafe': 'MarkupSafe',
    }

    # 已知的不存在于 PyPI 的模块模式（通常是内部模块）
    # 这些模式用于快速过滤，避免尝试从 PyPI 安装
    INTERNAL_MODULE_SUFFIXES: Set[str] = {
        # 常见的内部模块后缀
        '_worker', '_handler', '_manager', '_helper', '_util', '_utils',
        '_config', '_settings', '_constants', '_model', '_view', '_controller',
        '_service', '_client', '_server', '_resolver', '_processor',
        '_parser', '_builder', '_factory', '_adapter', '_interface',
        '_log', '_logger', '_cache', '_db', '_database', '_api', '_task',
        '_window', '_dialog', '_widget', '_panel', '_frame', '_form',
        '_page', '_screen', '_canvas', '_toolbar', '_menu', '_button',
        '_loader', '_reader', '_writer', '_exporter', '_importer',
        '_converter', '_transformer', '_formatter', '_validator',
        '_connector', '_connection', '_channel', '_socket', '_stream',
        '_entity', '_domain', '_repository', '_gateway', '_command',
        '_query', '_event', '_listener', '_subscriber', '_publisher',
        '_dispatcher', '_router', '_middleware', '_protocol', '_message',
    }

    # 内部模块命名关键字
    INTERNAL_MODULE_KEYWORDS: Set[str] = {
        # 通用
        'worker', 'handler', 'manager', 'helper', 'util', 'utils',
        'config', 'settings', 'constants', 'model', 'view', 'controller',
        'service', 'client', 'server', 'resolver', 'processor',
        'parser', 'builder', 'factory', 'adapter', 'interface',
        'log', 'logger', 'cache', 'db', 'database', 'api', 'task',
        # GUI 相关
        'window', 'dialog', 'widget', 'panel', 'frame', 'form',
        'page', 'screen', 'canvas', 'toolbar', 'menu', 'button',
        'tab', 'table', 'tree', 'list', 'layout', 'ui',
        # 项目结构
        'core', 'lib', 'src', 'app', 'main', 'run', 'start',
        'test', 'tests', 'spec', 'specs', 'fixture', 'fixtures',
        'mock', 'mocks', 'stub', 'stubs', 'fake', 'fakes',
        # 数据处理
        'loader', 'reader', 'writer', 'exporter', 'importer',
        'converter', 'transformer', 'formatter', 'validator',
        'serializer', 'deserializer', 'encoder', 'decoder',
        # 网络/通信
        'connector', 'connection', 'channel', 'socket', 'stream',
        'protocol', 'message', 'packet', 'request', 'response',
        # 业务逻辑
        'entity', 'domain', 'aggregate', 'repository', 'gateway',
        'command', 'query', 'event', 'listener', 'subscriber',
        'publisher', 'dispatcher', 'router', 'middleware',
    }

    # 常见的本地模块名（项目内部模块）
    LOCAL_MODULE_NAMES: Set[str] = {
        'ui', 'core', 'config', 'utils', 'lib', 'src', 'gui',
        'packager', 'dependency_analyzer', 'python_finder',
        'dependency_manager', 'main_window', 'main', 'app',
        'models', 'views', 'controllers', 'services', 'helpers',
        'tests', 'test', 'scripts', 'tools', 'common', 'shared',
        # 更多常见的内部模块名
        'worker', 'workers', 'handler', 'handlers', 'resolver', 'resolvers',
        'processor', 'processors', 'manager', 'managers', 'client', 'clients',
        'server', 'servers', 'api', 'apis', 'routes', 'middleware',
        'database', 'db', 'cache', 'task', 'tasks', 'job', 'jobs',
        'entity', 'entities', 'dto', 'schema', 'schemas', 'interface',
        'interfaces', 'abstract', 'base', 'bases', 'mixin', 'mixins',
        'plugin', 'plugins', 'extension', 'extensions', 'module', 'modules',
        'component', 'components', 'widget', 'widgets', 'dialog', 'dialogs',
        'panel', 'panels', 'page', 'pages', 'form', 'forms', 'table', 'tables',
        'resource', 'resources', 'asset', 'assets', 'static', 'template',
        'templates', 'layout', 'layouts', 'style', 'styles', 'theme', 'themes',
        # 网络/通信
        'connector', 'connectors', 'channel', 'channels', 'protocol', 'protocols',
        'message', 'messages', 'packet', 'packets', 'stream', 'streams',
        # 业务逻辑
        'domain', 'domains', 'aggregate', 'aggregates', 'repository', 'repositories',
        'gateway', 'gateways', 'command', 'commands', 'query', 'queries',
        'event', 'events', 'listener', 'listeners', 'subscriber', 'subscribers',
        'publisher', 'publishers', 'dispatcher', 'dispatchers', 'router', 'routers',
        # 数据处理
        'loader', 'loaders', 'reader', 'readers', 'writer', 'writers',
        'exporter', 'exporters', 'importer', 'importers', 'converter', 'converters',
        'transformer', 'transformers', 'formatter', 'formatters', 'validator', 'validators',
        'serializer', 'serializers', 'encoder', 'encoders', 'decoder', 'decoders',
    }

    # 需要跳过的目录
    SKIP_DIRS: Set[str] = {
        '.venv', 'venv', 'build', 'dist', '__pycache__', '.git',
        'node_modules', 'site-packages', '.tox', '.pytest_cache',
        'egg-info', '.eggs', '.mypy_cache', '.ruff_cache',
        '.idea', '.vscode', '.vs', 'htmlcov', 'coverage',
    }

    # PyPI 包验证缓存
    _pypi_validation_cache: Dict[str, bool] = {}

    def __init__(self):
        """初始化依赖安装器"""
        self.log: Callable = print
        self.cancel_flag: Optional[Callable] = None
        self.network_utils = NetworkUtils()

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback
        self.network_utils.set_log_callback(callback)

    def set_cancel_flag(self, cancel_flag: Callable) -> None:
        """设置取消标志回调函数"""
        self.cancel_flag = cancel_flag

    def is_likely_internal_module(self, name: str) -> bool:
        """
        检测模块名是否可能是项目内部模块（而非 PyPI 包）

        判断依据：
        1. 使用 PascalCase/CamelCase 命名（如 AsyncgenCodes, AttributeNodes）
           - PyPI 包通常使用小写加下划线或连字符
        2. 以常见的内部模块后缀结尾（如 Nodes, Codes, Helpers, Generated 等）
        3. 名称过长且无分隔符（真正的 PyPI 包很少这样命名）
        4. 包含多个驼峰单词模式
        5. 包含常见的内部模块模式（如 _worker, _handler 等）

        Args:
            name: 模块名

        Returns:
            是否可能是内部模块
        """
        if not name:
            return False

        # 检查是否包含内部模块模式后缀
        name_lower = name.lower()
        for suffix in self.INTERNAL_MODULE_SUFFIXES:
            if name_lower.endswith(suffix):
                return True

        # 检查是否包含下划线且看起来像内部模块
        if '_' in name:
            parts = name.split('_')
            # 如果包含多个部分且看起来像描述性命名，可能是内部模块
            if any(part.lower() in self.INTERNAL_MODULE_KEYWORDS for part in parts):
                return True

        # 检查是否是 PascalCase（多个大写字母开头的单词连接）
        # 排除全大写（如 PIL）和正常的包名（如 numpy）
        if name[0].isupper():
            # 统计大写字母数量
            upper_count = sum(1 for c in name if c.isupper())
            # 如果有多个大写字母且没有下划线/连字符，可能是内部模块
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
                    'Client', 'Server', 'Provider', 'Consumer', 'Adapter',
                )
                if any(name.endswith(suffix) for suffix in internal_suffixes):
                    return True

                # 名称很长（超过20字符）且全是字母，很可能是内部模块
                if len(name) > 20 and name.isalpha():
                    return True

                # 包含多个连续的驼峰单词模式（如 AttributeLookupNodes）
                camel_pattern_count = 0
                for i in range(len(name) - 1):
                    if name[i].isupper() and name[i + 1].islower():
                        camel_pattern_count += 1
                if camel_pattern_count >= 3:
                    return True

        return False

    def is_valid_pypi_package(self, package_name: str, python_path: str) -> bool:
        """
        验证包是否存在于 PyPI（通过 pip index versions 或 pip show 命令）

        Args:
            package_name: PyPI 包名
            python_path: Python 解释器路径

        Returns:
            包是否存在于 PyPI
        """
        # 检查缓存
        if package_name in self._pypi_validation_cache:
            return self._pypi_validation_cache[package_name]

        try:
            # 使用 pip index versions 检查包是否存在（pip 21.2+）
            result = subprocess.run(
                [python_path, '-m', 'pip', 'index', 'versions', package_name],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW
            )

            # 如果命令成功执行且有输出，说明包存在
            exists = result.returncode == 0 and package_name.lower() in result.stdout.lower()

            # 如果 pip index 不可用，尝试使用 pip show（检查本地安装）
            # 或者 pip download --no-deps --no-cache-dir -d tempdir（不推荐，太慢）
            if not exists and 'no such command' in result.stderr.lower():
                # 回退到检查本地是否已安装
                result = subprocess.run(
                    [python_path, '-m', 'pip', 'show', package_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=CREATE_NO_WINDOW
                )
                exists = result.returncode == 0

            self._pypi_validation_cache[package_name] = exists
            return exists

        except subprocess.TimeoutExpired:
            # 超时时假设包可能存在，让后续安装决定
            return True
        except Exception:
            # 出错时假设包可能存在
            return True

    def _collect_project_modules_recursive(
        self, project_dir: str, collected: Optional[Set[str]] = None,
        module_paths: Optional[Set[str]] = None
    ) -> Tuple[Set[str], Set[str]]:
        """
        递归收集项目目录下的所有 Python 模块名

        Args:
            project_dir: 项目目录
            collected: 已收集的模块名集合
            module_paths: 已收集的模块完整路径集合

        Returns:
            (模块名集合, 模块完整路径集合)
        """
        if collected is None:
            collected = set()
        if module_paths is None:
            module_paths = set()

        try:
            for item in os.listdir(project_dir):
                if item.startswith('.') or item in self.SKIP_DIRS:
                    continue
                # 跳过包含 egg-info 的目录
                if 'egg-info' in item or item.endswith('.egg'):
                    continue

                item_path = os.path.join(project_dir, item)

                if os.path.isdir(item_path):
                    # 检查是否为 Python 包（包含 __init__.py）
                    is_package = os.path.exists(os.path.join(item_path, "__init__.py"))
                    # 检查目录内是否有 .py 文件（隐式命名空间包）
                    has_py_files = self._dir_has_python_files(item_path)

                    if is_package or has_py_files:
                        collected.add(item)
                        module_paths.add(item)
                        # 递归收集子模块
                        self._collect_submodules_recursive(item_path, item, collected, module_paths)
                    # 或者是常见的项目目录名
                    elif item in self.LOCAL_MODULE_NAMES:
                        collected.add(item)

                elif item.endswith('.py') and item != '__init__.py':
                    # 单个 Python 文件也是模块
                    module_name = item[:-3]
                    collected.add(module_name)
                    module_paths.add(module_name)

        except Exception:
            pass

        return collected, module_paths

    def _dir_has_python_files(self, dir_path: str) -> bool:
        """检查目录是否包含 Python 文件"""
        try:
            for item in os.listdir(dir_path):
                if item.endswith('.py') and os.path.isfile(os.path.join(dir_path, item)):
                    return True
        except Exception:
            pass
        return False

    def _collect_submodules_recursive(
        self, dir_path: str, parent_module: str, collected: Set[str],
        module_paths: Set[str]
    ) -> None:
        """
        递归收集子模块

        Args:
            dir_path: 目录路径
            parent_module: 父模块路径
            collected: 已收集的模块名集合
            module_paths: 已收集的模块完整路径集合
        """
        try:
            for item in os.listdir(dir_path):
                if item.startswith('.') or item in self.SKIP_DIRS:
                    continue
                if 'egg-info' in item or item.endswith('.egg'):
                    continue

                item_path = os.path.join(dir_path, item)

                if os.path.isdir(item_path):
                    # 检查是否为 Python 包
                    is_package = os.path.exists(os.path.join(item_path, "__init__.py"))
                    has_py_files = self._dir_has_python_files(item_path)

                    if is_package or has_py_files:
                        # 添加子模块名（不带父模块前缀的名称也要添加）
                        collected.add(item)
                        # 添加完整路径
                        full_path = f"{parent_module}.{item}"
                        module_paths.add(full_path)
                        # 递归
                        self._collect_submodules_recursive(item_path, full_path, collected, module_paths)

                elif item.endswith('.py') and item != '__init__.py':
                    module_name = item[:-3]
                    collected.add(module_name)
                    module_paths.add(f"{parent_module}.{module_name}")

        except Exception:
            pass

    def _can_resolve_locally(self, module_name: str, project_dir: str) -> bool:
        """
        检查模块是否可以解析为项目本地文件

        Args:
            module_name: 模块名
            project_dir: 项目目录

        Returns:
            是否可以解析为本地文件
        """
        if not project_dir:
            return False

        # 将模块名转换为可能的路径
        module_parts = module_name.split('.')
        base_name = module_parts[0]

        # 检查各种可能的路径
        possible_paths = [
            # 作为目录（包）
            os.path.join(project_dir, base_name),
            # 作为 .py 文件
            os.path.join(project_dir, base_name + '.py'),
            # 作为包的 __init__.py
            os.path.join(project_dir, base_name, '__init__.py'),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return True

        # 如果有子模块路径，检查完整路径
        if len(module_parts) > 1:
            full_path = os.path.join(project_dir, *module_parts)
            if os.path.exists(full_path) or os.path.exists(full_path + '.py'):
                return True
            if os.path.exists(os.path.join(full_path, '__init__.py')):
                return True

        return False

    def filter_dependencies(
        self,
        dependencies: Set[str],
        project_dir: Optional[str],
        project_internal_modules: Set[str],
        is_stdlib_func: Callable[[str], bool],
        is_internal_module_func: Optional[Callable[[str], bool]] = None,
    ) -> Set[str]:
        """
        过滤依赖，移除不需要安装的模块

        Args:
            dependencies: 原始依赖集合
            project_dir: 项目目录
            project_internal_modules: 项目内部模块集合
            is_stdlib_func: 检测模块是否是标准库的函数
            is_internal_module_func: 检测模块是否是内部模块的函数

        Returns:
            过滤后的依赖集合
        """
        # 获取依赖分析器已收集的项目内部模块
        local_modules = set(project_internal_modules)
        module_paths: Set[str] = set()

        # 递归收集项目目录中的所有本地模块
        if project_dir:
            collected_modules, collected_paths = self._collect_project_modules_recursive(project_dir)
            local_modules.update(collected_modules)
            module_paths.update(collected_paths)

        # 过滤依赖
        filtered_dependencies = set()
        skipped_stdlib = 0
        skipped_builtin = 0
        skipped_local = 0
        skipped_internal = 0

        for dep in dependencies:
            # 跳过标准库
            if is_stdlib_func(dep):
                skipped_stdlib += 1
                continue

            # 跳过 Python 内置模块
            if dep in self.BUILTIN_MODULES:
                skipped_builtin += 1
                continue

            # 跳过已知的本地模块名
            if dep in self.LOCAL_MODULE_NAMES:
                skipped_local += 1
                continue

            # 跳过项目目录中的模块
            if dep in local_modules:
                skipped_internal += 1
                continue

            # 跳过内部模块（使用传入的检查函数）
            if is_internal_module_func and is_internal_module_func(dep):
                skipped_internal += 1
                continue

            # 检查是否是某个模块路径的一部分
            is_path_match = False
            for path in module_paths:
                if path.startswith(dep + '.') or path.endswith('.' + dep):
                    is_path_match = True
                    break
            if is_path_match:
                self.log(f"跳过项目内部模块: {dep}")
                continue

            # 如果知道项目目录，检查模块是否可以解析为本地文件
            if project_dir and self._can_resolve_locally(dep, project_dir):
                self.log(f"跳过项目内部模块: {dep} (可解析为本地文件)")
                continue

            # 检查是否是可能的内部模块（基于命名模式）
            if self.is_likely_internal_module(dep):
                self.log(f"跳过疑似内部模块: {dep} (命名模式不符合PyPI规范)")
                continue

            # 检查依赖分析器是否已标记为内部模块
            if is_internal_module_func and is_internal_module_func(dep):
                self.log(f"跳过内部模块: {dep}")
                continue

            filtered_dependencies.add(dep)

        return filtered_dependencies

    def install_dependencies(
        self,
        python_path: str,
        dependencies: Set[str],
        project_dir: Optional[str],
        project_internal_modules: Set[str],
        is_stdlib_func: Callable[[str], bool],
        is_internal_module_func: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """
        安装依赖

        Args:
            python_path: Python 解释器路径
            dependencies: 依赖包集合
            project_dir: 项目目录
            project_internal_modules: 项目内部模块集合
            is_stdlib_func: 检测模块是否是标准库的函数
            is_internal_module_func: 检测模块是否是内部模块的函数
        """
        self.log("\n安装项目依赖...")

        # 验证 Python 解释器路径
        import os
        if not os.path.exists(python_path):
            self.log(f"错误: Python 解释器不存在，无法安装依赖")
            self.log(f"  路径: {python_path}")
            # 尝试提供诊断信息
            parent_dir = os.path.dirname(python_path)
            if os.path.exists(parent_dir):
                try:
                    contents = os.listdir(parent_dir)
                    self.log(f"  父目录存在，内容: {contents}")
                except Exception as e:
                    self.log(f"  无法列出父目录内容: {e}")
            else:
                self.log(f"  父目录也不存在: {parent_dir}")
            return

        if not dependencies:
            self.log("未发现需要安装的依赖包")
            return

        # 过滤依赖
        filtered_dependencies = self.filter_dependencies(
            dependencies,
            project_dir,
            project_internal_modules,
            is_stdlib_func,
            is_internal_module_func,
        )

        if not filtered_dependencies:
            self.log("未发现需要安装的第三方依赖包")
            return

        # 检查是否取消
        if self.cancel_flag and self.cancel_flag():
            self.log("安装依赖已取消")
            return

        # 收集需要安装的包（合并相同的包）
        packages_to_install: Dict[str, List[str]] = {}
        for dep in sorted(filtered_dependencies):
            # 使用映射表获取真实的包名
            install_name = self.IMPORT_TO_PACKAGE_MAP.get(dep, dep)
            if install_name not in packages_to_install:
                packages_to_install[install_name] = []
            packages_to_install[install_name].append(dep)

        # 检查已安装的包
        already_installed = []
        packages_need_install = {}

        for install_name, import_names in packages_to_install.items():
            if self._check_package_installed(python_path, install_name):
                already_installed.append((install_name, import_names))
            else:
                packages_need_install[install_name] = import_names

        # 显示检查结果
        total_count = len(packages_to_install)
        installed_count = len(already_installed)
        need_install_count = len(packages_need_install)

        if installed_count > 0 and need_install_count > 0:
            self.log(f"依赖检查: {total_count} 个依赖包，{installed_count} 个已安装，{need_install_count} 个需要安装")
        elif installed_count > 0:
            self.log(f"✓ 所有 {total_count} 个依赖包均已安装")
            return
        else:
            self.log(f"需要安装 {need_install_count} 个依赖包")

        # 静默升级 pip（仅在需要时）
        try:
            subprocess.run(
                [python_path, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
                capture_output=True,
                timeout=30,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
        except FileNotFoundError as e:
            self.log(f"警告: 升级 pip 失败 - Python 解释器不存在")
            self.log(f"  路径: {python_path}")
            self.log(f"  错误: {str(e)}")
        except Exception:
            pass  # 升级失败不影响后续安装

        self.log("")

        # 逐个安装依赖
        for install_name, import_names in packages_need_install.items():
            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                self.log("安装依赖已取消")
                return

            import_display = ', '.join(import_names)

            # 构建显示名称
            if install_name != import_display and len(import_names) == 1:
                display_name = f"{import_display} ({install_name})"
            else:
                display_name = import_display

            self.log(f"安装 {display_name}...")

            try:
                # 特殊处理：PyQt5 需要同时安装 PyQt5-Qt5 以获取完整的插件
                packages = [install_name]
                if install_name == 'PyQt5':
                    packages.append('PyQt5-Qt5')

                all_success = True
                for pkg in packages:
                    success = self.network_utils.pip_install_with_mirrors(
                        python_path, [pkg], cancel_flag=self.cancel_flag
                    )

                    if not success:
                        all_success = False

                # 显示安装结果
                if all_success:
                    self.log(f"✓ {display_name} 安装成功")
                else:
                    self.log(f"✗ {display_name} 安装失败")

            except Exception as e:
                self.log(f"✗ {display_name} 安装出错: {e}")

        self.log("依赖安装完成")

    def install_packaging_tool(
        self,
        python_path: str,
        tool: str,
    ) -> bool:
        """
        安装打包工具（PyInstaller 或 Nuitka）

        Args:
            python_path: Python 解释器路径
            tool: 打包工具名称 ("pyinstaller" 或 "nuitka")

        Returns:
            是否安装成功
        """
        # 检查是否已安装
        is_installed = self._check_tool_installed(python_path, tool)

        if is_installed:
            self.log(f"✓ {tool} 已安装")
            return True

        # 安装
        success = self.network_utils.pip_install_with_mirrors(
            python_path, [tool], cancel_flag=self.cancel_flag
        )

        if success:
            self.log(f"✓ {tool} 安装成功")
            # 验证安装
            is_installed = self._check_tool_installed(python_path, tool)
            if is_installed:
                return True
            else:
                self.log(f"⚠️ {tool} 安装完成但验证失败")
                return False
        else:
            self.log(f"✗ {tool} 安装失败")
            return False

    def _check_tool_installed(self, python_path: str, tool: str) -> bool:
        """检查打包工具是否已安装"""
        try:
            if tool.lower() == "nuitka":
                result = subprocess.run(
                    [python_path, "-m", "nuitka", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
            else:
                result = subprocess.run(
                    [python_path, "-c", f"import {tool}; print({tool}.__version__)"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )

            return result.returncode == 0

        except Exception:
            return False

    def _check_package_installed(
        self,
        python_path: str,
        package_name: str,
    ) -> bool:
        """
        检查包是否已安装

        Args:
            python_path: Python 解释器路径
            package_name: 包名（PyPI包名，不是导入名）

        Returns:
            是否已安装
        """
        try:
            # 使用 pip show 检查包是否已安装（更可靠）
            result = subprocess.run(
                [python_path, "-m", "pip", "show", package_name],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return result.returncode == 0
        except Exception:
            return False

    def ensure_critical_dependencies(
        self,
        python_path: str,
        packages: List[str],
    ) -> bool:
        """
        确保关键依赖已安装

        Args:
            python_path: Python 解释器路径
            packages: 需要确保安装的包列表

        Returns:
            是否全部安装成功
        """
        all_success = True

        for package in packages:
            # 检查是否已安装
            try:
                result = subprocess.run(
                    [python_path, "-c", f"import {package}"],
                    capture_output=True,
                    timeout=10,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                if result.returncode == 0:
                    continue
            except Exception:
                pass

            # 未安装，尝试安装
            self.log(f"安装关键依赖: {package}")
            success = self.network_utils.pip_install_with_mirrors(
                python_path, [package], cancel_flag=self.cancel_flag
            )

            if not success:
                self.log(f"⚠️ 关键依赖 {package} 安装失败")
                all_success = False

        return all_success

    def get_package_name(self, import_name: str) -> str:
        """
        获取导入名对应的 PyPI 包名

        Args:
            import_name: 导入名

        Returns:
            PyPI 包名
        """
        return self.IMPORT_TO_PACKAGE_MAP.get(import_name, import_name)
