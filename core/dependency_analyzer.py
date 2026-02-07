"""
依赖分析器模块

本模块负责分析 Python 项目的依赖包，包括：
- 检测项目导入的模块
- 分析 GUI 框架使用情况
- 提供打包优化建议
- 追踪动态导入

本模块已重构，核心功能委托给 analyzer 子包中的专门模块：
- package_detection: 包检测功能
- gui_detection: GUI 框架检测功能
- hidden_imports: 隐藏导入配置
- dynamic_tracing: 动态导入追踪
- optimization: 优化建议生成

常量定义位于 analyzer_constants.py 模块。
"""

import ast
import os
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

# 导入子模块
from core.analyzer.dynamic_tracing import DynamicImportTracer
from core.analyzer.gui_detection import GUIDetector
from core.analyzer.hidden_imports import HiddenImportsManager
from core.analyzer.optimization import OptimizationAdvisor
from core.analyzer.package_detection import PackageDetector

# 导入常量定义
from core.analyzer_constants import (
    CONFIGURED_LIBRARIES,
    DEV_PACKAGES,
    FRAMEWORKS_WITH_DATA_FILES,
    GUI_FRAMEWORK_MAPPING,
    KNOWN_SINGLE_FILE_MODULES,
    KNOWN_STDLIB_PACKAGES,
    LARGE_PACKAGES,
    PACKAGE_IMPORT_MAP,
    QT_BINDINGS,
    STDLIB_MODULES,
)


class DependencyAnalyzer:
    """依赖分析器，用于分析 Python 项目的依赖包"""

    # 引用常量模块中的定义（保持向后兼容）
    STDLIB_MODULES = STDLIB_MODULES
    LARGE_PACKAGES = LARGE_PACKAGES
    DEV_PACKAGES = DEV_PACKAGES
    GUI_FRAMEWORK_MAPPING = GUI_FRAMEWORK_MAPPING
    FRAMEWORKS_WITH_DATA_FILES = FRAMEWORKS_WITH_DATA_FILES
    QT_BINDINGS = QT_BINDINGS
    CONFIGURED_LIBRARIES = CONFIGURED_LIBRARIES

    # 以下常量保留在类中（供内部方法使用）
    _PACKAGE_IMPORT_MAP = PACKAGE_IMPORT_MAP
    _KNOWN_SINGLE_FILE_MODULES = KNOWN_SINGLE_FILE_MODULES
    _KNOWN_STDLIB_PACKAGES = KNOWN_STDLIB_PACKAGES

    # PyPI 包名到实际模块名的映射表
    PACKAGE_TO_MODULE_MAPPING: Dict[str, str] = {
        'dnspython': 'dns',
        'charset-normalizer': 'charset_normalizer',
        'wxPython': 'wx',
        'Pillow': 'PIL',
        'opencv-python': 'cv2',
        'opencv-python-headless': 'cv2',
        'python-dateutil': 'dateutil',
        'beautifulsoup4': 'bs4',
        'scikit-learn': 'sklearn',
        'scikit-image': 'skimage',
        'PyYAML': 'yaml',
        'msgpack-python': 'msgpack',
        'pywin32': 'win32api',
        'pyobjc': 'objc',
        'pycryptodome': 'Crypto',
        'pycryptodomex': 'Cryptodome',
        'python-dotenv': 'dotenv',
        'typing-extensions': 'typing_extensions',
        'importlib-metadata': 'importlib_metadata',
        'importlib-resources': 'importlib_resources',
        'zipp': 'zipp',
    }

    # 常见的内部模块命名模式关键字
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

    def __init__(self):
        """初始化依赖分析器"""
        self.dependencies: Set[str] = set()
        self.all_imports: Set[str] = set()
        self.excluded_modules: Set[str] = set()
        self.detected_gui_frameworks: Set[str] = set()
        self.primary_qt_framework: Optional[str] = None
        self.log: Callable = print
        self._project_internal_modules: Set[str] = set()
        # 存储完整的模块路径映射（如 "workers.clash_log_worker" -> True）
        self._project_module_paths: Set[str] = set()
        # 存储项目目录路径
        self._project_dir: Optional[str] = None

        # 新增属性
        self._dynamic_imports: Set[str] = set()
        self._auto_collected_modules: Dict[str, List[str]] = {}
        self._unconfigured_libraries: Set[str] = set()
        self._module_type_cache: Dict[str, bool] = {}

        # 初始化子模块
        self._package_detector = PackageDetector()
        self._gui_detector = GUIDetector()
        self._hidden_imports_manager = HiddenImportsManager()
        self._dynamic_tracer = DynamicImportTracer()
        self._optimization_advisor = OptimizationAdvisor()

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback
        # 同步到子模块
        self._hidden_imports_manager.set_log_callback(callback)
        self._dynamic_tracer.set_log_callback(callback)
        self._optimization_advisor.set_log_callback(callback)

    def is_real_package(
        self, module_name: str, python_path: Optional[str] = None
    ) -> bool:
        """
        检测一个模块是否是真正的包（有 __path__ 属性）。
        委托给 PackageDetector。
        """
        return self._package_detector.is_real_package(module_name, python_path)

    def detect_primary_qt_framework(
        self, script_path: str, project_dir: Optional[str] = None
    ) -> Optional[str]:
        """
        从源代码中检测主要使用的 Qt 框架。
        委托给 GUIDetector。
        """
        self.primary_qt_framework = self._gui_detector.detect_primary_qt_framework(
            script_path, project_dir
        )
        return self.primary_qt_framework

    def get_qt_exclusion_list(self) -> List[str]:
        """
        获取需要排除的 Qt 绑定包列表。
        委托给 GUIDetector。
        """
        # 确保 GUIDetector 使用相同的主要 Qt 框架
        self._gui_detector.primary_qt_framework = self.primary_qt_framework
        return self._gui_detector.get_qt_exclusion_list()

    def get_detected_gui_frameworks(self) -> Set[str]:
        """
        获取检测到的 GUI 框架列表。
        委托给 GUIDetector。
        """
        self._gui_detector.primary_qt_framework = self.primary_qt_framework
        self.detected_gui_frameworks = self._gui_detector.detect_gui_frameworks(
            self.dependencies, self.all_imports
        )
        return self.detected_gui_frameworks

    def get_framework_data_files(self) -> List[Tuple[str, str]]:
        """
        获取需要包含的框架数据文件。
        委托给 GUIDetector。
        """
        # 先确保检测了 GUI 框架
        if not self._gui_detector.detected_gui_frameworks:
            self.get_detected_gui_frameworks()
        return self._gui_detector.get_framework_data_files()

    def analyze(
        self, script_path: str, project_dir: Optional[str] = None
    ) -> Set[str]:
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
        self._project_module_paths = set()

        # 确定项目目录
        if project_dir:
            self._project_dir = project_dir
        else:
            self._project_dir = os.path.dirname(script_path)

        # 先收集项目内部模块名（必须在分析文件之前执行）
        if self._project_dir:
            self._collect_internal_modules(self._project_dir)
            self.log(f"检测到 {len(self._project_internal_modules)} 个项目内部模块")

        # 从代码中提取依赖
        if project_dir:
            self._analyze_project(project_dir)
        else:
            self._analyze_file(script_path)

        # 读取 requirements.txt（如果存在）
        requirements = self._read_requirements(script_path, project_dir)
        self.dependencies.update(requirements)

        # 过滤掉标准库和项目内部模块
        self.dependencies = {
            dep for dep in self.dependencies
            if not self._is_stdlib(dep) and not self._is_internal_module(dep)
        }

        return self.dependencies

    def _collect_internal_modules(self, project_dir: str) -> None:
        """
        收集项目内部的模块名（递归收集所有子目录）

        这个方法会：
        1. 收集所有顶级模块名（目录名和 .py 文件名）
        2. 递归收集所有子模块名
        3. 收集完整的模块路径（如 "workers.clash_log_worker"）
        """
        skip_dirs = {
            ".venv", "venv", "build", "dist", "__pycache__", ".git",
            "node_modules", "site-packages", ".tox", ".pytest_cache",
            "egg-info", ".eggs", ".mypy_cache", ".ruff_cache",
            ".idea", ".vscode", ".vs", "htmlcov", "coverage",
        }

        try:
            for item in os.listdir(project_dir):
                if item.startswith('.') or item in skip_dirs:
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
                        self._project_internal_modules.add(item)
                        self._project_module_paths.add(item)
                        # 递归收集子模块
                        self._collect_submodules_internal(item_path, item, skip_dirs)

                elif item.endswith('.py') and item != '__init__.py':
                    module_name = item[:-3]
                    self._project_internal_modules.add(module_name)
                    self._project_module_paths.add(module_name)
        except Exception:
            pass

    def _dir_has_python_files(self, dir_path: str) -> bool:
        """检查目录是否包含 Python 文件"""
        try:
            for item in os.listdir(dir_path):
                if item.endswith('.py') and os.path.isfile(os.path.join(dir_path, item)):
                    return True
        except Exception:
            pass
        return False

    def _collect_submodules_internal(
        self, dir_path: str, parent_module: str, skip_dirs: set
    ) -> None:
        """
        递归收集子目录中的模块名

        Args:
            dir_path: 目录路径
            parent_module: 父模块路径（如 "workers" 或 "workers.sub"）
            skip_dirs: 需要跳过的目录集合
        """
        try:
            for item in os.listdir(dir_path):
                if item.startswith('.') or item in skip_dirs:
                    continue
                if 'egg-info' in item or item.endswith('.egg'):
                    continue

                item_path = os.path.join(dir_path, item)

                if os.path.isdir(item_path):
                    # 检查是否为 Python 包
                    is_package = os.path.exists(os.path.join(item_path, "__init__.py"))
                    has_py_files = self._dir_has_python_files(item_path)

                    if is_package or has_py_files:
                        # 添加子模块名（只添加目录名，不带父模块前缀）
                        # 这样可以匹配 "from clash_log_worker import xxx" 这种导入
                        self._project_internal_modules.add(item)
                        # 也添加完整路径
                        full_path = f"{parent_module}.{item}"
                        self._project_module_paths.add(full_path)
                        # 递归
                        self._collect_submodules_internal(item_path, full_path, skip_dirs)

                elif item.endswith('.py') and item != '__init__.py':
                    module_name = item[:-3]
                    self._project_internal_modules.add(module_name)
                    self._project_module_paths.add(f"{parent_module}.{module_name}")
        except Exception:
            pass

    def _collect_submodules(
        self, package_name: str, max_depth: int = 2
    ) -> List[str]:
        """收集包的子模块"""
        submodules = [package_name]

        try:
            import importlib
            import pkgutil

            pkg = importlib.import_module(package_name)
            if not hasattr(pkg, '__path__'):
                return submodules

            for importer, modname, ispkg in pkgutil.walk_packages(
                pkg.__path__, prefix=package_name + '.', onerror=lambda x: None
            ):
                depth = modname.count('.')
                if depth <= max_depth:
                    submodules.append(modname)
                    if len(submodules) > 100:
                        break
        except Exception:
            pass

        return submodules

    def _is_internal_module(self, module_name: str) -> bool:
        """检测模块是否是项目内部模块"""
        # 直接匹配模块名
        if module_name in self._project_internal_modules:
            return True

        # 检查完整路径匹配
        if module_name in self._project_module_paths:
            return True

        # 检查是否是某个完整路径的一部分
        for path in self._project_module_paths:
            if path.startswith(module_name + '.') or path.endswith('.' + module_name):
                return True

        # 检查模块是否可以解析为本地文件
        if self._project_dir and self._can_resolve_locally(module_name):
            return True

        # 检查是否可能是内部模块（基于命名模式）
        return self._is_likely_internal_by_naming(module_name)

    def _can_resolve_locally(self, module_name: str) -> bool:
        """
        检查模块是否可以解析为项目本地文件

        Args:
            module_name: 模块名

        Returns:
            是否可以解析为本地文件
        """
        if not self._project_dir:
            return False

        # 将模块名转换为可能的路径
        module_parts = module_name.split('.')
        base_name = module_parts[0]

        # 检查各种可能的路径
        possible_paths = [
            # 作为目录（包）
            os.path.join(self._project_dir, base_name),
            # 作为 .py 文件
            os.path.join(self._project_dir, base_name + '.py'),
            # 作为包的 __init__.py
            os.path.join(self._project_dir, base_name, '__init__.py'),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return True

        return False

    def _is_likely_internal_by_naming(self, name: str) -> bool:
        """基于命名模式判断是否可能是内部模块"""
        if not name:
            return False

        name_lower = name.lower()

        # 检查是否包含下划线且看起来像内部模块
        if '_' in name:
            parts = name.split('_')
            # 如果包含多个部分且看起来像描述性命名，可能是内部模块
            if any(part.lower() in self.INTERNAL_MODULE_KEYWORDS for part in parts):
                return True

            # 检查常见的内部模块后缀模式
            internal_suffixes = (
                '_worker', '_handler', '_manager', '_helper', '_util', '_utils',
                '_config', '_settings', '_constants', '_model', '_view', '_controller',
                '_service', '_client', '_server', '_resolver', '_processor',
                '_parser', '_builder', '_factory', '_adapter', '_interface',
                '_log', '_logger', '_cache', '_db', '_database', '_api', '_task',
                '_window', '_dialog', '_widget', '_panel', '_frame', '_form',
            )
            if any(name_lower.endswith(suffix) for suffix in internal_suffixes):
                return True

        # 检查是否是 PascalCase
        if name[0].isupper():
            upper_count = sum(1 for c in name if c.isupper())
            if upper_count >= 2 and '_' not in name and '-' not in name:
                internal_suffixes = (
                    'Nodes', 'Codes', 'Helpers', 'Generated', 'Specs',
                    'Definitions', 'Bases', 'Utils', 'Mixin', 'Base',
                    'Handler', 'Manager', 'Factory', 'Builder', 'Visitor',
                    'Parser', 'Lexer', 'Analyzer', 'Optimizer', 'Generator',
                    'Transformer', 'Processor', 'Worker', 'Runner', 'Loader',
                    'Service', 'Controller', 'Model', 'View', 'Schema',
                    'Serializer', 'Validator', 'Exception', 'Error', 'Config',
                    'Client', 'Server', 'Provider', 'Consumer', 'Adapter',
                    'Window', 'Dialog', 'Widget', 'Panel', 'Frame', 'Form',
                    'Resolver', 'Connector', 'Provider', 'Gateway', 'Repository',
                )
                if any(name.endswith(suffix) for suffix in internal_suffixes):
                    return True

                if len(name) > 20 and name.isalpha():
                    return True

                camel_pattern_count = 0
                for i in range(len(name) - 1):
                    if name[i].isupper() and name[i + 1].islower():
                        camel_pattern_count += 1
                if camel_pattern_count >= 3:
                    return True

        return False

    def get_exclude_modules(self) -> List[str]:
        """获取建议排除的模块列表"""
        return self._optimization_advisor.get_exclude_modules(self.dependencies)

    def get_hidden_imports(self) -> List[str]:
        """获取可能需要的隐藏导入"""
        # 同步状态到隐藏导入管理器
        self._hidden_imports_manager.set_dynamic_imports(self._dynamic_imports)
        self._hidden_imports_manager.set_auto_collected_modules(
            self._auto_collected_modules
        )

        return self._hidden_imports_manager.get_hidden_imports(
            self.dependencies,
            self.primary_qt_framework,
            is_real_package_func=self.is_real_package,
            is_stdlib_func=self._is_stdlib,
        )

    def _detect_gui_in_script(self, script_path: str) -> Tuple[bool, str]:
        """检测脚本是否是 GUI 程序"""
        return self._gui_detector.detect_gui_in_script(script_path)

    def trace_dynamic_imports(
        self,
        script_path: str,
        python_path: str,
        project_dir: Optional[str] = None,
        timeout: int = 20
    ) -> Tuple[bool, Set[str]]:
        """动态追踪脚本运行时的所有导入"""
        success, imports = self._dynamic_tracer.trace_dynamic_imports(
            script_path,
            python_path,
            project_dir,
            timeout,
            is_stdlib_func=self._is_stdlib,
        )

        if success:
            self._dynamic_imports = imports

        return success, imports

    def check_script_runnable(
        self,
        script_path: str,
        python_path: str,
        project_dir: Optional[str] = None
    ) -> bool:
        """检查脚本是否可以运行"""
        return self._dynamic_tracer.check_script_runnable(
            script_path, python_path, project_dir
        )

    def auto_collect_submodules(
        self, package_name: str, python_path: str
    ) -> List[str]:
        """自动收集包的子模块"""
        submodules = self._optimization_advisor.auto_collect_submodules(
            package_name, python_path
        )
        self._auto_collected_modules[package_name] = submodules
        return submodules

    def collect_all_unconfigured_submodules(self, python_path: str) -> None:
        """收集所有未配置库的子模块"""
        auto_collected = self._optimization_advisor.collect_all_unconfigured_submodules(
            self.dependencies,
            python_path,
            self.CONFIGURED_LIBRARIES,
            self._is_stdlib,
        )
        self._auto_collected_modules.update(auto_collected)

    def get_package_size_info(
        self, python_path: str
    ) -> Dict[str, Dict[str, float]]:
        """获取已安装包的大小信息"""
        return self._optimization_advisor.get_package_size_info(
            self.dependencies, python_path
        )

    def get_optimization_suggestions(
        self, python_path: str
    ) -> Tuple[List[str], List[str], Dict[str, Dict[str, float]]]:
        """获取打包优化建议"""
        exclude_modules = self.get_exclude_modules()
        hidden_imports = self.get_hidden_imports()
        size_info = self.get_package_size_info(python_path)

        return exclude_modules, hidden_imports, size_info

    def generate_optimization_report(self, python_path: str) -> str:
        """生成优化报告"""
        hidden_imports = self.get_hidden_imports()
        return self._optimization_advisor.generate_optimization_report(
            self.dependencies, hidden_imports, python_path
        )

    def _analyze_project(self, project_dir: str) -> None:
        """分析整个项目目录"""
        project_path = Path(project_dir)

        skip_dirs = {
            ".venv", "venv", "build", "dist", "__pycache__", ".git",
            "node_modules", "site-packages", ".tox", ".pytest_cache",
            "egg-info", ".eggs"
        }

        for py_file in project_path.rglob("*.py"):
            if any(part in skip_dirs for part in py_file.parts):
                continue

            if any(
                part.startswith('.') and part not in {'.', '..'}
                for part in py_file.parts
            ):
                continue

            try:
                self._analyze_file(str(py_file))
            except Exception as e:
                print(f"警告: 分析文件 {py_file} 时出错: {e}")

    def _analyze_file(self, file_path: str) -> None:
        """分析单个 Python 文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module_name = alias.name.split(".")[0]
                        # 在添加之前先检查是否是内部模块
                        if not self._is_internal_module(module_name):
                            self.dependencies.add(module_name)
                        self.all_imports.add(module_name)

                elif isinstance(node, ast.ImportFrom):
                    # 跳过相对导入（level > 0 表示相对导入）
                    if node.level > 0:
                        continue
                    if node.module:
                        module_name = node.module.split(".")[0]
                        # 在添加之前先检查是否是内部模块
                        if not self._is_internal_module(module_name):
                            self.dependencies.add(module_name)
                        self.all_imports.add(module_name)

        except SyntaxError as e:
            print(f"警告: 文件 {file_path} 语法错误: {e}")
        except Exception as e:
            print(f"警告: 分析文件 {file_path} 时出错: {e}")

    def get_project_internal_modules(self) -> Set[str]:
        """获取已收集的项目内部模块集合"""
        return self._project_internal_modules.copy()

    def get_project_module_paths(self) -> Set[str]:
        """获取已收集的项目模块完整路径集合"""
        return self._project_module_paths.copy()

    def _read_requirements(
        self, script_path: str, project_dir: Optional[str]
    ) -> Set[str]:
        """读取 requirements.txt 文件"""
        requirements = set()

        search_paths = []

        if project_dir:
            search_paths.append(Path(project_dir) / "requirements.txt")

        script_dir = Path(script_path).parent
        search_paths.append(script_dir / "requirements.txt")

        for req_path in search_paths:
            if req_path.exists():
                try:
                    with open(req_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()

                            if not line or line.startswith("#"):
                                continue

                            match = re.match(r"^([a-zA-Z0-9_\-]+)", line)
                            if match:
                                package_name = match.group(1)
                                requirements.add(package_name)

                except Exception as e:
                    print(f"警告: 读取 {req_path} 时出错: {e}")

                break

        return requirements

    def _is_stdlib(self, module_name: str) -> bool:
        """判断是否为 Python 标准库"""
        return module_name in self.STDLIB_MODULES

    def get_requirements_content(self) -> str:
        """获取 requirements.txt 格式的内容"""
        return "\n".join(sorted(self.dependencies))

    def save_requirements(self, output_path: str) -> None:
        """保存依赖到 requirements.txt 文件"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.get_requirements_content())
