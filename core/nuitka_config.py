"""
Nuitka 最佳实践配置模块

基于 Nuitka 官方文档 (https://nuitka.net/user-documentation/) 的最佳实践，
提供标准化的 Nuitka 打包配置和选项管理。

本模块涵盖以下最佳实践：
1. 编译模式选择 (standalone, onefile, app)
2. Anti-bloat 插件配置（减少依赖膨胀）
3. 部署模式配置 (--deployment)
4. 缓存控制和 ccache 支持
5. 用户自定义包配置文件支持
6. onefile 临时目录规范
7. Python 标志优化
8. 数据文件处理
9. 编译报告生成
10. 低内存模式支持
"""

import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Windows 子进程隐藏标志
if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


class CompilationMode(Enum):
    """Nuitka 编译模式"""
    ACCELERATED = "accelerated"  # 加速模式（默认，仍依赖 Python 安装）
    STANDALONE = "standalone"    # 独立模式（包含所有依赖）
    ONEFILE = "onefile"          # 单文件模式（打包成单个可执行文件）
    MODULE = "module"            # 模块模式（生成扩展模块）
    APP = "app"                  # 应用模式（macOS app bundle 或其他平台的 onefile）


class ConsoleMode(Enum):
    """Windows 控制台窗口模式"""
    FORCE = "force"      # 强制显示控制台
    DISABLE = "disable"  # 禁用控制台（GUI 程序）
    ATTACH = "attach"    # 附加到现有控制台
    HIDE = "hide"        # 隐藏控制台（会短暂闪烁）


class AntiBlockMode(Enum):
    """Anti-bloat 模式"""
    NOFOLLOW = "nofollow"  # 不跟随导入
    WARNING = "warning"    # 警告但继续
    ERROR = "error"        # 报错并停止
    IGNORE = "ignore"      # 忽略


@dataclass
class PythonFlags:
    """Python 编译标志配置"""
    no_docstrings: bool = True      # 移除文档字符串（减小体积）
    no_asserts: bool = True         # 禁用断言语句（提升性能）
    no_warnings: bool = False       # 禁用运行时警告
    no_site: bool = False           # 不导入 site 模块（standalone 默认）
    no_annotations: bool = False    # 移除类型注解
    isolated: bool = False          # 隔离执行环境
    static_hashes: bool = False     # 禁用哈希随机化
    unbuffered: bool = False        # 无缓冲输出

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []
        if self.no_docstrings:
            args.append("--python-flag=no_docstrings")
        if self.no_asserts:
            args.append("--python-flag=no_asserts")
        if self.no_warnings:
            args.append("--python-flag=no_warnings")
        if self.no_site:
            args.append("--python-flag=no_site")
        if self.no_annotations:
            args.append("--python-flag=no_annotations")
        if self.isolated:
            args.append("--python-flag=isolated")
        if self.static_hashes:
            args.append("--python-flag=static_hashes")
        if self.unbuffered:
            args.append("--python-flag=unbuffered")
        return args


@dataclass
class AntiBloatConfig:
    """Anti-bloat 插件配置（减少依赖膨胀）"""
    # 常见的可以安全排除的包
    noinclude_pytest: AntiBlockMode = AntiBlockMode.NOFOLLOW
    noinclude_setuptools: AntiBlockMode = AntiBlockMode.NOFOLLOW
    noinclude_unittest: AntiBlockMode = AntiBlockMode.NOFOLLOW
    noinclude_ipython: AntiBlockMode = AntiBlockMode.NOFOLLOW
    noinclude_dask: AntiBlockMode = AntiBlockMode.NOFOLLOW

    # 自定义排除模块
    custom_nofollow: List[str] = field(default_factory=list)
    custom_error: List[str] = field(default_factory=list)
    custom_warning: List[str] = field(default_factory=list)

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []

        # 预定义包的排除配置
        if self.noinclude_pytest != AntiBlockMode.IGNORE:
            args.append(f"--noinclude-pytest-mode={self.noinclude_pytest.value}")
        if self.noinclude_setuptools != AntiBlockMode.IGNORE:
            args.append(f"--noinclude-setuptools-mode={self.noinclude_setuptools.value}")
        if self.noinclude_unittest != AntiBlockMode.IGNORE:
            args.append(f"--noinclude-unittest-mode={self.noinclude_unittest.value}")
        if self.noinclude_ipython != AntiBlockMode.IGNORE:
            args.append(f"--noinclude-IPython-mode={self.noinclude_ipython.value}")
        if self.noinclude_dask != AntiBlockMode.IGNORE:
            args.append(f"--noinclude-dask-mode={self.noinclude_dask.value}")

        # 自定义排除
        for module in self.custom_nofollow:
            args.append(f"--nofollow-import-to={module}")
        for module in self.custom_error:
            args.append(f"--noinclude-custom-mode={module}:error")
        for module in self.custom_warning:
            args.append(f"--noinclude-custom-mode={module}:warning")

        return args


@dataclass
class OnefileConfig:
    """Onefile 模式配置"""
    # 临时目录规范
    # 可用变量：{TEMP}, {PID}, {TIME}, {PROGRAM}, {PROGRAM_BASE},
    #          {CACHE_DIR}, {COMPANY}, {PRODUCT}, {VERSION}, {HOME}
    tempdir_spec: Optional[str] = None

    # 外部数据文件模式（这些文件不会打包到 onefile 内部）
    external_data_patterns: List[str] = field(default_factory=list)

    # Windows 启动画面
    splash_screen_image: Optional[str] = None

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []

        if self.tempdir_spec:
            args.append(f"--onefile-tempdir-spec={self.tempdir_spec}")

        for pattern in self.external_data_patterns:
            args.append(f"--include-onefile-external-data={pattern}")

        if self.splash_screen_image and os.path.exists(self.splash_screen_image):
            args.append(f"--onefile-windows-splash-screen-image={self.splash_screen_image}")

        return args


@dataclass
class WindowsConfig:
    """Windows 特定配置"""
    console_mode: ConsoleMode = ConsoleMode.DISABLE
    icon_path: Optional[str] = None
    uac_admin: bool = False        # 请求管理员权限
    uac_uiaccess: bool = False     # 远程桌面 UAC 访问

    # 版本信息
    product_name: Optional[str] = None
    company_name: Optional[str] = None
    file_description: Optional[str] = None
    product_version: Optional[str] = None
    file_version: Optional[str] = None
    copyright: Optional[str] = None
    trademark: Optional[str] = None

    # 资源文件（Nuitka 2.9+ 支持）
    force_rc_file: Optional[str] = None

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []

        # 控制台模式
        args.append(f"--windows-console-mode={self.console_mode.value}")

        # 图标
        if self.icon_path and os.path.exists(self.icon_path):
            args.append(f"--windows-icon-from-ico={self.icon_path}")

        # UAC
        if self.uac_admin:
            args.append("--windows-uac-admin")
        if self.uac_uiaccess:
            args.append("--windows-uac-uiaccess")

        # 版本信息
        if self.product_name:
            args.append(f"--product-name={self.product_name}")
        if self.company_name:
            args.append(f"--company-name={self.company_name}")
        if self.file_description:
            args.append(f"--file-description={self.file_description}")
        if self.product_version:
            args.append(f"--product-version={self.product_version}")
        if self.file_version:
            args.append(f"--file-version={self.file_version}")
        if self.copyright:
            args.append(f"--copyright={self.copyright}")
        if self.trademark:
            args.append(f"--trademark={self.trademark}")

        # 资源文件
        if self.force_rc_file and os.path.exists(self.force_rc_file):
            args.append(f"--windows-force-rc-file={self.force_rc_file}")

        return args


@dataclass
class MacOSConfig:
    """macOS 特定配置"""
    create_app_bundle: bool = True
    app_icon: Optional[str] = None
    app_name: Optional[str] = None
    signed_app_name: Optional[str] = None

    # 权限配置
    protected_resources: List[Tuple[str, str]] = field(default_factory=list)

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []

        if self.create_app_bundle:
            args.append("--macos-create-app-bundle")

        if self.app_icon and os.path.exists(self.app_icon):
            args.append(f"--macos-app-icon={self.app_icon}")

        if self.app_name:
            args.append(f"--macos-app-name={self.app_name}")

        if self.signed_app_name:
            args.append(f"--macos-signed-app-name={self.signed_app_name}")

        for identifier, description in self.protected_resources:
            args.append(f"--macos-app-protected-resource={identifier}:{description}")

        return args


@dataclass
class ReportConfig:
    """编译报告配置"""
    # XML 报告
    xml_report_path: Optional[str] = None

    # 自定义模板报告
    template_reports: List[Tuple[str, str]] = field(default_factory=list)  # (template, output)

    # 内置报告
    license_report: bool = False

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []

        if self.xml_report_path:
            args.append(f"--report={self.xml_report_path}")

        for template, output in self.template_reports:
            args.append(f"--report-template={template}:{output}")

        if self.license_report:
            args.append("--report-template=LicenseReport:license-report.txt")

        return args


@dataclass
class CacheConfig:
    """缓存配置"""
    # 缓存目录（覆盖默认位置）
    cache_dir: Optional[str] = None

    # 各类缓存的独立控制
    downloads_dir: Optional[str] = None
    ccache_dir: Optional[str] = None
    clcache_dir: Optional[str] = None
    bytecode_dir: Optional[str] = None
    dll_dependencies_dir: Optional[str] = None

    def get_env_vars(self) -> Dict[str, str]:
        """获取缓存相关的环境变量"""
        env = {}

        if self.cache_dir:
            env["NUITKA_CACHE_DIR"] = self.cache_dir
        if self.downloads_dir:
            env["NUITKA_CACHE_DIR_DOWNLOADS"] = self.downloads_dir
        if self.ccache_dir:
            env["NUITKA_CACHE_DIR_CCACHE"] = self.ccache_dir
        if self.clcache_dir:
            env["NUITKA_CACHE_DIR_CLCACHE"] = self.clcache_dir
        if self.bytecode_dir:
            env["NUITKA_CACHE_DIR_BYTECODE"] = self.bytecode_dir
        if self.dll_dependencies_dir:
            env["NUITKA_CACHE_DIR_DLL_DEPENDENCIES"] = self.dll_dependencies_dir

        return env


@dataclass
class PluginConfig:
    """插件配置"""
    # Qt 插件
    enable_pyqt6: bool = False
    enable_pyqt5: bool = False
    enable_pyside6: bool = False
    enable_pyside2: bool = False

    # 其他插件
    enable_tk_inter: bool = False
    enable_multiprocessing: bool = False
    enable_pylint_warnings: bool = False
    enable_upx: bool = False

    # Qt 插件选项
    qt_plugins: List[str] = field(default_factory=lambda: [
        "sensible", "platforms", "styles", "iconengines", "imageformats"
    ])

    # 自定义插件
    custom_plugins: List[str] = field(default_factory=list)
    disabled_plugins: List[str] = field(default_factory=list)

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []

        # Qt 插件（互斥，只能启用一个）
        if self.enable_pyqt6:
            args.append("--enable-plugin=pyqt6")
        elif self.enable_pyqt5:
            args.append("--enable-plugin=pyqt5")
        elif self.enable_pyside6:
            args.append("--enable-plugin=pyside6")
        elif self.enable_pyside2:
            args.append("--enable-plugin=pyside2")

        # 其他插件
        if self.enable_tk_inter:
            args.append("--enable-plugin=tk-inter")
        if self.enable_multiprocessing:
            args.append("--enable-plugin=multiprocessing")
        if self.enable_pylint_warnings:
            args.append("--enable-plugin=pylint-warnings")
        if self.enable_upx:
            args.append("--enable-plugin=upx")

        # Qt 插件选项
        if (self.enable_pyqt6 or self.enable_pyqt5 or
            self.enable_pyside6 or self.enable_pyside2) and self.qt_plugins:
            args.append(f"--include-qt-plugins={','.join(self.qt_plugins)}")

        # 自定义插件
        for plugin in self.custom_plugins:
            args.append(f"--enable-plugin={plugin}")

        # 禁用的插件
        for plugin in self.disabled_plugins:
            args.append(f"--disable-plugin={plugin}")

        return args


@dataclass
class DataFileConfig:
    """数据文件配置"""
    # 包数据
    include_package_data: List[str] = field(default_factory=list)

    # 数据目录
    include_data_dirs: List[Tuple[str, str]] = field(default_factory=list)  # (source, dest)

    # 数据文件
    include_data_files: List[Tuple[str, str]] = field(default_factory=list)  # (source, dest)

    # 排除的数据文件
    noinclude_data_files: List[str] = field(default_factory=list)

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []

        for package in self.include_package_data:
            args.append(f"--include-package-data={package}")

        for source, dest in self.include_data_dirs:
            args.append(f"--include-data-dir={source}={dest}")

        for source, dest in self.include_data_files:
            args.append(f"--include-data-files={source}={dest}")

        for pattern in self.noinclude_data_files:
            args.append(f"--noinclude-data-files={pattern}")

        return args


@dataclass
class ModuleConfig:
    """模块包含/排除配置"""
    # 包含的模块
    include_modules: List[str] = field(default_factory=list)
    include_packages: List[str] = field(default_factory=list)

    # 排除的模块
    nofollow_imports: List[str] = field(default_factory=list)

    # 插件目录（动态加载的模块）
    plugin_directories: List[str] = field(default_factory=list)

    def to_args(self) -> List[str]:
        """转换为命令行参数"""
        args = []

        for module in self.include_modules:
            args.append(f"--include-module={module}")

        for package in self.include_packages:
            args.append(f"--include-package={package}")

        for module in self.nofollow_imports:
            args.append(f"--nofollow-import-to={module}")

        for directory in self.plugin_directories:
            args.append(f"--include-plugin-directory={directory}")

        return args


@dataclass
class NuitkaConfig:
    """Nuitka 完整配置"""
    # 基本配置
    mode: CompilationMode = CompilationMode.ONEFILE
    output_filename: Optional[str] = None
    output_dir: Optional[str] = None

    # 部署模式（移除所有调试助手）
    deployment: bool = False

    # 显示选项
    show_progress: bool = True
    show_memory: bool = True
    show_scons: bool = False

    # 编译优化
    lto: bool = True                    # 链接时优化
    clang: bool = False                 # 使用 Clang 编译器
    mingw64: bool = False               # 使用 MinGW64
    jobs: Optional[int] = None          # 并行编译任务数
    low_memory: bool = False            # 低内存模式

    # 自动下载
    assume_yes_for_downloads: bool = True

    # 用户包配置文件
    user_package_config_file: Optional[str] = None

    # 多入口点（Multidist）
    main_scripts: List[str] = field(default_factory=list)

    # 子配置
    python_flags: PythonFlags = field(default_factory=PythonFlags)
    anti_bloat: AntiBloatConfig = field(default_factory=AntiBloatConfig)
    onefile: OnefileConfig = field(default_factory=OnefileConfig)
    windows: WindowsConfig = field(default_factory=WindowsConfig)
    macos: MacOSConfig = field(default_factory=MacOSConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    plugins: PluginConfig = field(default_factory=PluginConfig)
    data_files: DataFileConfig = field(default_factory=DataFileConfig)
    modules: ModuleConfig = field(default_factory=ModuleConfig)

    def to_command(self, python_path: str, script_path: str) -> List[str]:
        """
        生成完整的 Nuitka 命令行

        Args:
            python_path: Python 解释器路径
            script_path: 主脚本路径

        Returns:
            完整的命令行参数列表
        """
        cmd = [python_path, "-m", "nuitka"]

        # 编译模式
        if self.mode != CompilationMode.ACCELERATED:
            cmd.append(f"--mode={self.mode.value}")

        # 输出配置
        if self.output_filename:
            cmd.append(f"--output-filename={self.output_filename}")
        if self.output_dir:
            cmd.append(f"--output-dir={self.output_dir}")

        # 部署模式
        if self.deployment:
            cmd.append("--deployment")

        # 显示选项
        if self.show_progress:
            cmd.append("--show-progress")
        if self.show_memory:
            cmd.append("--show-memory")
        if self.show_scons:
            cmd.append("--show-scons")

        # 编译优化
        if self.lto:
            cmd.append("--lto=yes")
        else:
            cmd.append("--lto=no")

        if self.clang:
            cmd.append("--clang")
        if self.mingw64:
            cmd.append("--mingw64")
        if self.jobs is not None:
            cmd.append(f"--jobs={self.jobs}")
        if self.low_memory:
            cmd.append("--low-memory")

        # 自动下载
        if self.assume_yes_for_downloads:
            cmd.append("--assume-yes-for-downloads")

        # 用户包配置
        if self.user_package_config_file and os.path.exists(self.user_package_config_file):
            cmd.append(f"--user-package-configuration-file={self.user_package_config_file}")

        # 源代码优化
        cmd.append("--no-prefer-source-code")

        # 子配置
        cmd.extend(self.python_flags.to_args())
        cmd.extend(self.anti_bloat.to_args())

        # 平台特定配置
        if sys.platform == "win32":
            cmd.extend(self.windows.to_args())
            if self.mode == CompilationMode.ONEFILE:
                cmd.extend(self.onefile.to_args())
        elif sys.platform == "darwin":
            cmd.extend(self.macos.to_args())

        # 其他配置
        cmd.extend(self.report.to_args())
        cmd.extend(self.plugins.to_args())
        cmd.extend(self.data_files.to_args())
        cmd.extend(self.modules.to_args())

        # 多入口点
        for main_script in self.main_scripts:
            cmd.append(f"--main={main_script}")

        # 主脚本
        cmd.append(script_path)

        return cmd

    def get_env(self) -> Dict[str, str]:
        """获取需要设置的环境变量"""
        env = os.environ.copy()
        env.update(self.cache.get_env_vars())
        return env


class NuitkaVersionInfo:
    """Nuitka 版本信息管理"""

    def __init__(self, python_path: str):
        self.python_path = python_path
        self._version: Optional[Tuple[int, int, int]] = None
        self._version_str: Optional[str] = None

    @property
    def version(self) -> Optional[Tuple[int, int, int]]:
        """获取 Nuitka 版本号元组"""
        if self._version is None:
            self._detect_version()
        return self._version

    @property
    def version_str(self) -> Optional[str]:
        """获取 Nuitka 版本号字符串"""
        if self._version_str is None:
            self._detect_version()
        return self._version_str

    def _detect_version(self) -> None:
        """检测 Nuitka 版本"""
        try:
            result = subprocess.run(
                [self.python_path, "-m", "nuitka", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                import re
                version_match = re.search(r'(\d+)\.(\d+)\.(\d+)', result.stdout)
                if version_match:
                    major = int(version_match.group(1))
                    minor = int(version_match.group(2))
                    patch = int(version_match.group(3))
                    self._version = (major, minor, patch)
                    self._version_str = f"{major}.{minor}.{patch}"
        except Exception:
            pass

    def supports_feature(self, feature: str) -> bool:
        """检查是否支持特定功能"""
        version = self.version
        if version is None:
            return False

        # 功能版本要求映射
        feature_requirements = {
            "windows_force_rc_file": (2, 9, 0),  # --windows-force-rc-file
            "mode_option": (2, 0, 0),            # --mode= 参数
            "deployment": (2, 0, 0),             # --deployment
            "low_memory": (1, 8, 0),             # --low-memory
            "report_template": (1, 9, 0),        # --report-template
        }

        required = feature_requirements.get(feature, (0, 0, 0))
        return version >= required


class NuitkaBestPractices:
    """Nuitka 最佳实践建议"""

    # 建议排除的开发/测试模块
    RECOMMENDED_EXCLUSIONS = [
        # 测试框架
        "pytest", "unittest", "doctest", "nose", "mock", "tox",
        "coverage", "hypothesis",
        # 开发工具
        "sphinx", "docutils", "IPython", "jupyter", "notebook",
        "ipython", "ipykernel", "ipywidgets",
        # 代码质量工具
        "pylint", "flake8", "mypy", "black", "isort", "yapf",
        "autopep8", "bandit",
        # 打包工具
        "setuptools", "pip", "wheel", "twine", "distutils",
        "pkg_resources",
        # 调试工具
        "pdb", "bdb", "trace", "profile", "cProfile",
    ]

    # Qt 绑定冲突列表
    QT_BINDINGS = ["PyQt6", "PyQt5", "PySide6", "PySide2"]

    @staticmethod
    def get_recommended_config(
        script_path: str,
        output_dir: str,
        is_gui: bool = True,
        qt_framework: Optional[str] = None,
        is_production: bool = False,
    ) -> NuitkaConfig:
        """
        获取推荐的 Nuitka 配置

        Args:
            script_path: 主脚本路径
            output_dir: 输出目录
            is_gui: 是否是 GUI 程序
            qt_framework: 使用的 Qt 框架（PyQt6, PyQt5, PySide6, PySide2）
            is_production: 是否是生产构建

        Returns:
            推荐的 NuitkaConfig 配置
        """
        config = NuitkaConfig()

        # 基本配置
        config.mode = CompilationMode.ONEFILE
        config.output_dir = output_dir
        config.show_progress = True
        config.show_memory = True

        # 生产构建启用部署模式
        if is_production:
            config.deployment = True
            config.show_scons = False
        else:
            # 开发构建生成编译报告
            config.report.xml_report_path = os.path.join(output_dir, "compilation-report.xml")

        # 编译优化
        config.lto = True
        config.assume_yes_for_downloads = True

        # Python 标志优化
        config.python_flags.no_docstrings = True
        config.python_flags.no_asserts = is_production

        # Anti-bloat 配置
        config.anti_bloat.noinclude_pytest = AntiBlockMode.NOFOLLOW
        config.anti_bloat.noinclude_setuptools = AntiBlockMode.NOFOLLOW
        config.anti_bloat.noinclude_unittest = AntiBlockMode.NOFOLLOW
        config.anti_bloat.noinclude_ipython = AntiBlockMode.NOFOLLOW

        # 添加推荐排除
        for module in NuitkaBestPractices.RECOMMENDED_EXCLUSIONS:
            if module not in config.anti_bloat.custom_nofollow:
                config.anti_bloat.custom_nofollow.append(module)

        # Windows 配置
        if sys.platform == "win32":
            config.windows.console_mode = (
                ConsoleMode.DISABLE if is_gui else ConsoleMode.FORCE
            )

            # onefile 临时目录使用缓存路径（避免 Windows 防火墙问题）
            if is_production:
                config.onefile.tempdir_spec = "{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}"
            else:
                config.onefile.tempdir_spec = "{TEMP}/onefile_{PID}_{TIME}"

        # Qt 框架配置
        if qt_framework:
            qt_lower = qt_framework.lower()
            if "pyqt6" in qt_lower:
                config.plugins.enable_pyqt6 = True
            elif "pyqt5" in qt_lower:
                config.plugins.enable_pyqt5 = True
            elif "pyside6" in qt_lower:
                config.plugins.enable_pyside6 = True
            elif "pyside2" in qt_lower:
                config.plugins.enable_pyside2 = True

            # 排除其他 Qt 绑定
            for binding in NuitkaBestPractices.QT_BINDINGS:
                if binding.lower() != qt_framework.lower():
                    config.anti_bloat.custom_nofollow.append(binding)

            # 包含 Qt 数据
            config.data_files.include_package_data.append(qt_framework)

        return config

    @staticmethod
    def get_troubleshooting_tips() -> List[str]:
        """获取常见问题解决提示"""
        return [
            "1. 如果遇到内存不足错误，使用 --low-memory 选项或减少 --jobs 数量",
            "2. 如果程序无法启动，先用 --mode=standalone 测试，再切换到 onefile",
            "3. 如果缺少数据文件，使用 --include-package-data 或 --include-data-files",
            "4. 如果缺少 DLL，检查是否需要添加包配置或使用 --include-module",
            "5. 对于 Qt 程序，确保启用正确的 Qt 插件并排除其他 Qt 绑定",
            "6. Windows 防火墙问题：使用缓存的 tempdir-spec 避免每次都生成新路径",
            "7. 使用 --report 生成编译报告以诊断问题",
            "8. fork bomb 问题：检查程序是否正确处理 sys.argv",
            "9. 中文路径/文件名问题：使用临时英文名编译后再重命名",
            "10. 依赖膨胀：使用 anti-bloat 选项排除不必要的包",
        ]

    @staticmethod
    def parse_nuitka_project_options(script_path: str) -> Dict[str, Any]:
        """
        解析脚本中的 Nuitka 项目选项（# nuitka-project: 注释）

        Args:
            script_path: 脚本路径

        Returns:
            解析出的选项字典
        """
        options = {}

        try:
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()

            import re
            # 匹配 # nuitka-project: --option 或 # nuitka-project: --option=value
            pattern = r'#\s*nuitka-project:\s*(--[\w-]+=?[^\n]*)'
            matches = re.findall(pattern, content)

            for match in matches:
                match = match.strip()
                if "=" in match:
                    key, value = match.split("=", 1)
                    options[key.strip("-")] = value.strip()
                else:
                    options[match.strip("-")] = True

        except Exception:
            pass

        return options


def create_user_package_config(
    output_path: str,
    package_name: str,
    data_files: Optional[List[str]] = None,
    data_dirs: Optional[List[str]] = None,
    implicit_imports: Optional[List[str]] = None,
    dlls: Optional[List[str]] = None,
) -> bool:
    """
    创建用户自定义包配置文件（YAML 格式）

    这是 Nuitka 推荐的处理特殊包需求的方式。

    Args:
        output_path: 输出文件路径
        package_name: 包名
        data_files: 需要包含的数据文件模式列表
        data_dirs: 需要包含的数据目录列表
        implicit_imports: 隐式导入列表
        dlls: DLL 前缀列表

    Returns:
        是否成功创建
    """
    try:
        lines = [
            "# yamllint disable rule:line-length",
            "# yamllint disable rule:indentation",
            "---",
            "",
            f"- module-name: '{package_name}'",
        ]

        # 数据文件
        if data_files or data_dirs:
            lines.append("  data-files:")
            if data_dirs:
                lines.append("    dirs:")
                for d in data_dirs:
                    lines.append(f"      - '{d}'")
            if data_files:
                lines.append("    patterns:")
                for f in data_files:
                    lines.append(f"      - '{f}'")

        # 隐式导入
        if implicit_imports:
            lines.append("  implicit-imports:")
            lines.append("    - depends:")
            for imp in implicit_imports:
                lines.append(f"        - '{imp}'")

        # DLLs
        if dlls:
            lines.append("  dlls:")
            lines.append("    - from_filenames:")
            lines.append("        prefixes:")
            for dll in dlls:
                lines.append(f"          - '{dll}'")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return True

    except Exception:
        return False
