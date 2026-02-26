"""
打包器协调模块

本模块作为打包流程的顶层协调器，负责：
- 协调各个子模块完成打包任务
- 管理打包流程的整体逻辑
- 提供统一的打包接口

子模块：
- analyzer: 依赖分析
- packaging: 打包相关工具（虚拟环境、依赖安装、图标处理、打包器等）
"""

import os
import shutil
import sys
from typing import Callable, Dict, List, Optional, Tuple

from core.dependency_analyzer import DependencyAnalyzer
from core.packaging.dependency_installer import DependencyInstaller
from core.packaging.icon_processor import IconProcessor
from core.packaging.network_utils import NetworkUtils
from core.packaging.nuitka_packager import NuitkaPackager
from core.packaging.pyinstaller_packager import PyInstallerPackager
from core.packaging.venv_manager import VenvManager
from core.version_info import RceditHandler, VersionInfoHandler, WindowsResourceHandler
from utils.dependency_manager import DependencyManager
from utils.python_finder import PythonFinder


class Packager:
    """
    打包器协调类

    作为高层协调器，将具体任务委托给各个子模块处理。
    保持与原有接口兼容。
    """

    def __init__(self):
        """初始化打包器及所有子模块"""
        # 工具类
        self.python_finder = PythonFinder()
        self.dependency_manager = DependencyManager()

        # 分析器
        self.dependency_analyzer = DependencyAnalyzer()

        # 打包子模块
        self.venv_manager = VenvManager()
        self.dependency_installer = DependencyInstaller()
        self.icon_processor = IconProcessor()
        self.network_utils = NetworkUtils()
        self.version_info_handler = VersionInfoHandler()
        self.windows_resource_handler = WindowsResourceHandler()
        self.rcedit_handler = RceditHandler()
        self.pyinstaller_packager = PyInstallerPackager()
        self.nuitka_packager = NuitkaPackager()

        # 回调函数
        self.log: Callable = print
        self.cancel_flag: Optional[Callable] = None
        self.process_callback: Optional[Callable] = None

        # 状态
        self._last_exe_path: Optional[str] = None

    def _set_log_callback(self, callback: Callable) -> None:
        """设置日志回调到所有子模块"""
        self.log = callback
        self.dependency_analyzer.log = callback
        self.dependency_manager.log = callback
        self.venv_manager.set_log_callback(callback)
        self.dependency_installer.set_log_callback(callback)
        self.icon_processor.set_log_callback(callback)
        self.network_utils.set_log_callback(callback)
        self.version_info_handler.log = callback
        self.windows_resource_handler.log = callback
        self.rcedit_handler.log = callback
        self.pyinstaller_packager.set_log_callback(callback)
        self.nuitka_packager.set_log_callback(callback)

    def _set_cancel_flag(self, cancel_flag: Callable) -> None:
        """设置取消标志到所有子模块"""
        self.cancel_flag = cancel_flag
        self.dependency_installer.set_cancel_flag(cancel_flag)
        self.pyinstaller_packager.set_cancel_flag(cancel_flag)
        self.nuitka_packager.set_cancel_flag(cancel_flag)

    def _set_process_callback(self, callback: Callable) -> None:
        """设置进程回调到所有子模块"""
        self.process_callback = callback
        self.pyinstaller_packager.set_process_callback(callback)
        self.nuitka_packager.set_process_callback(callback)

    def _get_python_path(self, config: Dict) -> Tuple[Optional[str], str]:
        """
        获取 Python 解释器路径（不处理虚拟环境，仅获取基础解释器）

        优先级：
        1. 用户在配置中手动指定的路径（经过有效性校验）
        2. 当前运行的解释器（仅在非打包环境下）
        3. 通过 PythonFinder 在系统中搜索

        Returns:
            (python_path, error_message) 元组。
            成功时 python_path 为有效路径、error_message 为空字符串；
            失败时 python_path 为 None、error_message 为描述性错误信息。
        """
        # 1. 优先使用配置指定的解释器
        python_path = config.get("python_path") or config.get("python")
        if python_path and os.path.exists(python_path):
            # 即使用户手动指定，也要验证它不是打包环境中的临时文件
            if PythonFinder.is_valid_python_interpreter(python_path):
                return python_path, ""
            else:
                self.log(f"警告: 指定的 Python 路径不是有效的解释器: {python_path}")

        # 2. 检测是否处于 PyInstaller/Nuitka 打包后的环境中
        if PythonFinder.is_bundled_environment():
            self.log(
                "检测到当前运行在打包环境中，sys.executable 不可用于创建虚拟环境"
            )
            self.log(f"  sys.executable = {sys.executable}")
            self.log("正在搜索系统中安装的 Python 解释器...")

            finder = PythonFinder()
            system_python = finder.find_python()
            if system_python:
                self.log(f"✓ 找到系统 Python: {system_python}")
                return system_python, ""
            else:
                error_msg = (
                    "未在系统中找到可用的 Python 解释器。\n\n"
                    "请在工具界面的「Python路径」中手动指定系统安装的 Python 解释器路径\n"
                    "（例如 C:\\Python311\\python.exe）。\n\n"
                    "如果尚未安装 Python，请先从 https://www.python.org 下载安装，\n"
                    "安装时请勾选「Add Python to PATH」。"
                )
                self.log("错误: 未在系统中找到可用的 Python 解释器")
                self.log("请在工具界面中手动指定 Python 路径")
                return None, error_msg

        # 3. 非打包环境，使用当前解释器
        return sys.executable, ""

    def _setup_venv_if_needed(
        self,
        config: Dict,
        base_python_path: str,
    ) -> str:
        """
        根据配置设置虚拟环境

        如果 use_venv 为 True：
        1. 检查项目目录下是否存在虚拟环境（.venv/venv）
        2. 如果不存在则创建
        3. 安装依赖（从 requirements.txt 或分析项目）

        Args:
            config: 打包配置
            base_python_path: 基础 Python 解释器路径

        Returns:
            最终使用的 Python 解释器路径
        """
        use_venv = config.get("use_venv", False)

        if not use_venv:
            self.log("未启用虚拟环境，使用指定的 Python 解释器")
            # 验证基础 Python 解释器是否存在
            if not os.path.exists(base_python_path):
                self.log(f"错误: 指定的 Python 解释器不存在: {base_python_path}")
                raise FileNotFoundError(f"Python 解释器不存在: {base_python_path}")
            return base_python_path

        project_dir = config.get("project_dir")
        if not project_dir:
            script_path = config.get("script_path", "")
            project_dir = os.path.dirname(script_path) if script_path else None

        if not project_dir or not os.path.isdir(project_dir):
            self.log("警告: 无法确定项目目录，跳过虚拟环境设置")
            return base_python_path

        self.log("\n" + "=" * 50)
        self.log("虚拟环境设置")
        self.log("=" * 50)

        # 验证基础 Python 解释器路径
        if not os.path.exists(base_python_path):
            self.log(f"错误: 基础 Python 解释器不存在: {base_python_path}")
            self.log("将无法创建虚拟环境，请检查 Python 安装")
            raise FileNotFoundError(f"Python 解释器不存在: {base_python_path}")

        self.log(f"基础 Python 解释器: {base_python_path}")

        # 1. 检查是否存在虚拟环境
        existing_venv = self.venv_manager.check_existing_venv(project_dir)
        venv_python: Optional[str] = None
        active_venv_path: Optional[str] = None

        if existing_venv:
            self.log(f"✓ 检测到现有虚拟环境: {existing_venv}")
            venv_python = self.venv_manager.get_venv_python(existing_venv)
            active_venv_path = existing_venv

            # 验证现有虚拟环境的有效性
            if not os.path.exists(venv_python):
                self.log(f"警告: 现有虚拟环境的 Python 解释器不存在: {venv_python}")
                self.log("尝试验证虚拟环境...")
                if not self.venv_manager.validate_venv(existing_venv, verbose=True):
                    self.log("现有虚拟环境无效，将创建新的虚拟环境")
                    existing_venv = None
                    venv_python = None
                    active_venv_path = None

        if not existing_venv:
            # 创建新的虚拟环境
            self.log("未检测到有效的虚拟环境，正在创建...")
            venv_path = self.venv_manager.setup_venv(
                project_dir,
                base_python_path,
                venv_name=".venv"
            )

            if not venv_path:
                self.log("警告: 虚拟环境创建失败，使用原始 Python 解释器")
                return base_python_path

            self.log(f"✓ 虚拟环境创建成功: {venv_path}")
            venv_python = self.venv_manager.get_venv_python(venv_path)
            active_venv_path = venv_path

            # 再次验证虚拟环境是否真的可用
            if not os.path.exists(venv_python):
                self.log(f"错误: 虚拟环境创建后 Python 解释器仍不存在: {venv_python}")
                self.log("虚拟环境创建失败，使用原始 Python 解释器")
                return base_python_path

            # 升级 pip
            if not self.venv_manager.upgrade_pip(venv_path):
                self.log("警告: pip 升级失败，但将继续使用虚拟环境")

        # 最终验证
        if not venv_python or not os.path.exists(venv_python):
            self.log(f"错误: 虚拟环境 Python 解释器不存在: {venv_python}")
            self.log("详细诊断信息:")
            if active_venv_path:
                self.venv_manager.get_venv_python(active_venv_path, verify=True)
            self.log("回退到使用原始 Python 解释器")
            return base_python_path

        self.log(f"✓ 将使用虚拟环境 Python: {venv_python}")

        # 2. 安装依赖
        self._install_venv_dependencies(project_dir, venv_python, config)

        return venv_python

    def _install_venv_dependencies(
        self,
        project_dir: str,
        venv_python: str,
        config: Dict,
    ) -> None:
        """
        在虚拟环境中安装依赖

        优先使用 requirements.txt，否则从项目中分析提取依赖

        Args:
            project_dir: 项目目录
            venv_python: 虚拟环境 Python 解释器路径
            config: 打包配置
        """
        requirements_file = os.path.join(project_dir, "requirements.txt")

        if os.path.exists(requirements_file):
            # 使用 requirements.txt 安装依赖
            self.log("检测到 requirements.txt，正在安装依赖...")
            self._install_from_requirements(venv_python, requirements_file)
        else:
            # 从项目中分析依赖
            self.log("未检测到 requirements.txt，正在分析项目依赖...")
            script_path = config.get("script_path", "")
            if script_path:
                deps = self.dependency_analyzer.analyze(script_path, project_dir)
                if deps:
                    self.log(f"检测到 {len(deps)} 个第三方依赖，正在安装...")
                    self._install_analyzed_dependencies(venv_python, deps, project_dir)
                else:
                    self.log("未检测到需要安装的第三方依赖")

    def _install_from_requirements(
        self,
        python_path: str,
        requirements_file: str,
    ) -> bool:
        """
        从 requirements.txt 安装依赖

        Args:
            python_path: Python 解释器路径
            requirements_file: requirements.txt 文件路径

        Returns:
            是否成功
        """
        import subprocess

        from utils.constants import CREATE_NO_WINDOW

        try:
            # 使用镜像源安装
            mirrors = [
                ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
                ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
                ("默认源", None),
            ]

            for mirror_name, mirror_url in mirrors:
                self.log(f"  尝试使用 {mirror_name} 安装依赖...")

                cmd = [
                    python_path, "-m", "pip", "install",
                    "-r", requirements_file,
                    "--quiet",
                ]

                if mirror_url:
                    cmd.extend(["-i", mirror_url, "--trusted-host",
                               mirror_url.split("//")[1].split("/")[0]])

                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=300,
                        creationflags=CREATE_NO_WINDOW,
                    )

                    if result.returncode == 0:
                        self.log(f"✓ 依赖安装成功（使用 {mirror_name}）")
                        return True
                    else:
                        self.log(f"  {mirror_name} 安装失败，尝试下一个镜像源...")

                except subprocess.TimeoutExpired:
                    self.log(f"  {mirror_name} 安装超时，尝试下一个镜像源...")

            self.log("警告: 所有镜像源均安装失败")
            return False

        except Exception as e:
            self.log(f"安装依赖时出错: {e}")
            return False

    def _install_analyzed_dependencies(
        self,
        python_path: str,
        deps: set,
        project_dir: str,
    ) -> bool:
        """
        安装分析到的依赖

        Args:
            python_path: Python 解释器路径
            deps: 依赖集合
            project_dir: 项目目录

        Returns:
            是否成功
        """
        # 获取内部模块信息
        internal_modules = getattr(self.dependency_analyzer, '_project_internal_modules', set())
        is_stdlib = self.dependency_analyzer._is_stdlib
        is_internal = getattr(self.dependency_analyzer, '_is_internal_module', None)

        result = self.dependency_installer.install_dependencies(
            python_path,
            deps,
            project_dir,
            internal_modules,
            is_stdlib,
            is_internal,
        )
        return result if result is not None else True

    def _is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self.cancel_flag is not None and self.cancel_flag()

    def _has_chinese(self, text: str) -> bool:
        """检查字符串中是否包含中文字符"""
        if not text:
            return False
        return any('\u4e00' <= char <= '\u9fff' for char in text)

    def _check_chinese_paths(self, config: Dict) -> None:
        """检查路径中是否包含中文字符并发出警告"""
        script_path = config.get("script_path")
        project_dir = config.get("project_dir")

        paths_to_check = {
            "脚本路径": script_path,
            "项目目录": project_dir,
        }

        chinese_paths = []
        for path_name, path_value in paths_to_check.items():
            if path_value and self._has_chinese(path_value):
                chinese_paths.append(f"{path_name}: {path_value}")

        if chinese_paths:
            self.log("\n" + "!" * 50)
            self.log("警告: 检测到路径中包含中文字符")
            self.log("!" * 50)
            for path_info in chinese_paths:
                self.log(f"  {path_info}")
            self.log("")
            self.log("中文路径可能导致以下问题：")
            self.log("  1. PyInstaller/Nuitka 在处理某些依赖时可能出现编码错误")
            self.log("  2. 虚拟环境创建可能失败")
            self.log("  3. Qt 插件目录识别可能出现问题")
            self.log("")
            self.log("建议:")
            self.log("  - 将项目移动到纯英文路径下（如 C:/Projects/myapp）")
            self.log("")
            self.log("打包将继续尝试，但可能会遇到问题...")
            self.log("!" * 50 + "\n")

    def _prepare_output_dir(self, config: Dict) -> str:
        """准备输出目录"""
        script_path = config["script_path"]
        project_dir = config.get("project_dir")
        output_dir = config.get("output_dir")

        if not output_dir:
            if project_dir:
                output_dir = os.path.join(project_dir, "build")
            else:
                output_dir = os.path.join(os.path.dirname(script_path), "build")

        # 清空已存在的 build 目录
        if os.path.exists(output_dir):
            self.log(f"\n检测到已存在的输出目录: {output_dir}")
            try:
                items = os.listdir(output_dir)
                if items:
                    self.log(f"发现 {len(items)} 个文件/目录需要清理")
                    for item in items:
                        item_path = os.path.join(output_dir, item)
                        try:
                            if os.path.isfile(item_path) or os.path.islink(item_path):
                                os.unlink(item_path)
                            elif os.path.isdir(item_path):
                                shutil.rmtree(item_path)
                        except Exception as e:
                            self.log(f"  警告：无法删除 {item}: {str(e)}")
                self.log("✓ 旧构建文件已清理")
            except Exception as e:
                self.log(f"警告：清理输出目录时出错: {str(e)}")

        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def _analyze_dependencies(
        self,
        script_path: str,
        project_dir: Optional[str],
        python_path: str,
        config: Dict,
    ) -> Tuple[set, List[str], List[str]]:
        """
        分析项目依赖

        Returns:
            (dependencies, hidden_imports, exclude_modules)
        """
        self.log("\n" + "=" * 50)
        self.log("第一阶段：依赖分析")
        self.log("=" * 50)

        # 静态分析
        self.log("执行静态依赖分析...")
        deps = self.dependency_analyzer.analyze(script_path, project_dir)
        self.log(f"静态分析检测到 {len(deps)} 个第三方依赖")
        if deps:
            # 显示具体的依赖名称
            deps_list = sorted(deps)
            self.log(f"  依赖列表: {', '.join(deps_list)}")

        # 动态追踪（非 GUI 项目）
        self.log("执行动态导入追踪...")
        success_trace, traced = self.dependency_analyzer.trace_dynamic_imports(
            script_path, python_path, project_dir
        )
        if success_trace:
            self.log(f"动态追踪捕获到 {len(traced)} 个导入")

        # 自动收集未配置库的子模块
        self.dependency_analyzer.collect_all_unconfigured_submodules(python_path)

        # 获取优化建议并自动应用到配置
        exclude_modules, hidden_imports, _ = self.dependency_analyzer.get_optimization_suggestions(python_path)

        # 自动合并到配置中的 hidden_imports / exclude_modules（去重保序）
        config_hidden = config.get("hidden_imports", []) or []
        config_exclude = config.get("exclude_modules", []) or []

        merged_hidden = list(dict.fromkeys(config_hidden + hidden_imports))
        merged_exclude = list(dict.fromkeys(config_exclude + exclude_modules))

        config["hidden_imports"] = merged_hidden
        config["exclude_modules"] = merged_exclude

        applied_hidden_count = max(0, len(merged_hidden) - len(config_hidden))
        applied_exclude_count = max(0, len(merged_exclude) - len(config_exclude))

        self.log(f"已自动应用隐藏导入: +{applied_hidden_count} 个（当前共 {len(merged_hidden)} 个）")
        self.log(f"已自动应用排除模块: +{applied_exclude_count} 个（当前共 {len(merged_exclude)} 个）")

        return deps, merged_hidden, merged_exclude

    def _install_dependencies(
        self,
        python_path: str,
        deps: set,
        project_dir: Optional[str],
    ) -> bool:
        """安装项目依赖"""
        self.log("\n" + "=" * 50)
        self.log("第二阶段：依赖安装")
        self.log("=" * 50)

        # 获取内部模块信息
        internal_modules = getattr(self.dependency_analyzer, '_project_internal_modules', set())
        is_stdlib = self.dependency_analyzer._is_stdlib
        is_internal = getattr(self.dependency_analyzer, '_is_internal_module', None)

        self.dependency_installer.install_dependencies(
            python_path,
            deps,
            project_dir,
            internal_modules,
            is_stdlib,
            is_internal,
        )
        return True

    def _process_icon(
        self,
        config: Dict,
        output_dir: str,
        python_path: str,
    ) -> Optional[str]:
        """处理图标文件"""
        # 同时支持 "icon" 和 "icon_path" 两个键名（兼容GUI和其他调用方式）
        icon_path = config.get("icon") or config.get("icon_path")
        if not icon_path:
            self.log("\n未指定程序图标，将使用默认图标")
            return None

        self.log("\n处理图标文件...")
        self.log(f"  用户指定的图标路径: {icon_path}")

        # 验证图标文件是否存在
        if not os.path.exists(icon_path):
            self.log(f"  ⚠️ 警告: 图标文件不存在: {icon_path}")
            return None

        # 输出图标文件信息
        try:
            icon_size = os.path.getsize(icon_path)
            icon_ext = os.path.splitext(icon_path)[1].lower()
            self.log(f"  图标文件大小: {icon_size} 字节, 格式: {icon_ext}")
        except Exception as e:
            self.log(f"  无法获取图标文件信息: {e}")

        processed_icon, warnings = self.icon_processor.process_icon_file(
            icon_path, output_dir, python_path
        )

        for warning in warnings:
            self.log(f"  图标: {warning}")

        if processed_icon:
            self.log(f"  最终使用的图标文件: {processed_icon}")
        else:
            self.log("  ⚠️ 图标处理失败，将使用默认图标")

        return processed_icon

    def _prepare_version_info(self, config: Dict, output_dir: str) -> Optional[str]:
        """准备版本信息"""
        # 检查是否有版本信息配置
        # GUI 将版本信息存储在 config["version_info"] 嵌套字典中
        version_info = config.get("version_info")
        if version_info:
            self.log(f"\n检测到版本信息配置: {list(version_info.keys())}")
            has_version_info = any([
                version_info.get("version"),
                version_info.get("company_name"),
                version_info.get("file_description"),
                version_info.get("copyright"),
                version_info.get("product_name"),
            ])
        else:
            self.log("\n未检测到 config['version_info'] 嵌套字典，尝试检查顶层键...")
            # 兼容：也检查顶层键（以防其他调用方式）
            has_version_info = any([
                config.get("version"),
                config.get("company_name"),
                config.get("file_description"),
                config.get("copyright"),
            ])

        if not has_version_info:
            self.log("未找到任何版本信息字段，跳过版本信息处理")
            return None

        self.log("\n准备版本信息...")
        version_file = self._create_version_info_file(config, output_dir)
        if version_file:
            self.log(f"  版本信息文件已创建: {version_file}")
            pending = self.version_info_handler.get_pending_version_info()
            if pending:
                self.log(f"  已注册待处理版本信息 (rcedit 后处理): {list(pending.keys())}")
            else:
                self.log("  ⚠️ 待处理版本信息未注册，rcedit 后处理将不会执行")
        else:
            self.log("  ⚠️ 版本信息文件创建失败")
        return version_file

    def _create_version_info_file(self, config: Dict, output_dir: str) -> Optional[str]:
        """创建 PyInstaller 版本信息文件"""
        version_info = config.get("version_info")
        if not version_info:
            return None

        version_str = version_info.get("version", "1.0.0")
        product_name = config.get("program_name", "Application")
        company_name = version_info.get("company_name", "")
        file_description = version_info.get("file_description", product_name)
        copyright_text = version_info.get("copyright", "")

        # 设置待处理版本信息，以便后续使用 rcedit 进行修复
        # PyInstaller 生成的版本信息有时会有乱码或不显示，特别是中文
        pending_info = {
            "version": version_str,
            "product_name": product_name,
            "company_name": company_name,
            "file_description": file_description,
            "copyright": copyright_text
        }
        self.version_info_handler.set_pending_version_info(pending_info)

        windows_version = self.version_info_handler.convert_version_to_windows_format(version_str)
        version_parts = windows_version.split(".")

        version_file_content = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({version_parts[0]}, {version_parts[1]}, {version_parts[2]}, {version_parts[3]}),
    prodvers=({version_parts[0]}, {version_parts[1]}, {version_parts[2]}, {version_parts[3]}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'080404B0',
          [
            StringStruct(u'CompanyName', u'{company_name}'),
            StringStruct(u'FileDescription', u'{file_description}'),
            StringStruct(u'FileVersion', u'{windows_version}'),
            StringStruct(u'InternalName', u'{product_name}'),
            StringStruct(u'LegalCopyright', u'{copyright_text}'),
            StringStruct(u'OriginalFilename', u'{product_name}.exe'),
            StringStruct(u'ProductName', u'{product_name}'),
            StringStruct(u'ProductVersion', u'{windows_version}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
'''
        try:
            version_file_path = os.path.join(output_dir, "version_info.txt")
            with open(version_file_path, "w", encoding="utf-8") as f:
                f.write(version_file_content)
            self.log(f"  已创建版本信息文件: {version_file_path}")
            return version_file_path
        except Exception as e:
            self.log(f"  创建版本信息文件失败: {str(e)}")
            return None

    def _do_package(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str],
        version_file: Optional[str],
    ) -> Tuple[bool, str]:
        """执行实际打包"""
        self.log("\n" + "=" * 50)
        self.log("第三阶段：打包")
        self.log("=" * 50)

        tool = config.get("tool", "pyinstaller").lower()
        self.log(f"使用打包工具: {tool.upper()}")

        # 获取 Qt 框架信息
        qt_framework = self.dependency_analyzer.primary_qt_framework
        pack_config = config.copy()
        pack_config["qt_framework"] = qt_framework

        # 添加版本文件到配置
        if version_file:
            pack_config["version_file"] = version_file

        # 选择打包器
        if tool == "nuitka":
            packager = self.nuitka_packager
            gcc_path = config.get("gcc_path")
            success, message = packager.package(
                python_path,
                pack_config,
                output_dir,
                hidden_imports,
                exclude_modules,
                icon_path=icon_path,
                gcc_path=gcc_path,
            )
        else:
            packager = self.pyinstaller_packager
            success, message = packager.package(
                python_path,
                pack_config,
                output_dir,
                hidden_imports,
                exclude_modules,
                icon_path=icon_path,
            )

        if success:
            self._last_exe_path = packager.get_last_exe_path()
            self.log(f"\n打包成功，exe 路径: {self._last_exe_path}")

            # rcedit 后处理仅用于 Nuitka 构建
            # PyInstaller 的 onefile 模式在 exe 末尾附加 PKG 归档，
            # rcedit 修改 PE 资源段会使 PKG 偏移失效，导致
            # "Could not load PyInstaller's embedded PKG archive" 错误。
            # PyInstaller 已通过 --version-file 和 --icon 在构建时嵌入信息，无需再用 rcedit。
            if tool == "nuitka":
                # 检查是否需要后处理添加中文版本信息
                pending_info = self.nuitka_packager.get_pending_version_info()
                self.log(f"从 Nuitka 打包器获取待处理版本信息: {pending_info is not None}")

                # 如果打包器没有，再从 version_info_handler 获取
                if not pending_info:
                    pending_info = self.version_info_handler.get_pending_version_info()
                    self.log(f"从 version_info_handler 获取待处理版本信息: {pending_info is not None}")

                if pending_info:
                    self.log(f"待处理版本信息内容: {list(pending_info.keys())}")

                if pending_info and self._last_exe_path:
                    self.log("\n后处理: 添加中文版本信息...")
                    post_success = self.rcedit_handler.post_process_add_version_info(
                        self._last_exe_path, pending_info
                    )
                    if post_success:
                        self.log("✓ 中文版本信息添加成功")
                    else:
                        self.log("⚠️ 中文版本信息添加失败，exe 仍可正常运行")

                    self.nuitka_packager.clear_pending_version_info()
                    self.version_info_handler.clear_pending_version_info()

                # 额外保障：使用 rcedit 强制设置图标（仅 Nuitka）
                if self._last_exe_path and icon_path and os.path.exists(icon_path):
                    if icon_path.lower().endswith('.ico'):
                        self.log("\n后处理: 验证并强制设置 exe 图标...")
                        try:
                            # 检查图标文件是否存在（可能已被清理）
                            if not os.path.exists(icon_path):
                                self.log(f"  ⚠️ 图标文件已被清理，跳过 rcedit 设置: {icon_path}")
                            else:
                                rcedit_exe = self.rcedit_handler.find_or_download_rcedit()
                                if rcedit_exe and os.path.exists(rcedit_exe):
                                    import subprocess
                                    import sys
                                    creationflags = 0
                                    if sys.platform == "win32":
                                        creationflags = 0x08000000  # CREATE_NO_WINDOW

                                    cmd = [rcedit_exe, self._last_exe_path, "--set-icon", icon_path]
                                    result = subprocess.run(
                                        cmd,
                                        capture_output=True,
                                        text=True,
                                        encoding="utf-8",
                                        errors="replace",
                                        creationflags=creationflags
                                    )
                                    if result.returncode == 0:
                                        self.log("  ✓ 图标已通过 rcedit 确认设置")
                                    else:
                                        self.log(f"  ⚠️ 设置图标警告: {result.stderr}")
                        except Exception as e:
                            self.log(f"  设置图标时出错: {e}")
            else:
                # PyInstaller: 版本信息已通过 --version-file 嵌入，图标已通过 --icon 嵌入
                # 不使用 rcedit，避免破坏 PKG 归档
                self.log("PyInstaller 构建: 跳过 rcedit 后处理（已通过 --version-file 和 --icon 嵌入）")
                self.version_info_handler.clear_pending_version_info()

        # 所有后处理完成后，统一清理临时文件
        # 清理临时版本信息文件
        if version_file and os.path.exists(version_file):
            try:
                os.remove(version_file)
                self.log(f"已清理临时版本信息文件: {version_file}")
            except Exception:
                pass

        # 清理临时转换的图标文件（icon_converted.ico）
        # 注意：只清理自动生成的 icon_converted.ico，不清理用户原始图标
        if icon_path and "icon_converted.ico" in icon_path and os.path.exists(icon_path):
            try:
                os.remove(icon_path)
                self.log(f"已清理临时图标文件: {icon_path}")
            except Exception:
                pass

        return success, message

    def package(
        self,
        config: Dict,
        log_callback: Optional[Callable] = None,
        cancel_flag: Optional[Callable] = None,
        process_callback: Optional[Callable] = None,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        执行打包操作

        Args:
            config: 打包配置字典
            log_callback: 日志回调函数
            cancel_flag: 取消标志回调函数
            process_callback: 进程回调函数

        Returns:
            (success, message, exe_path) 元组
        """
        # 设置回调
        if log_callback:
            self._set_log_callback(log_callback)
        if cancel_flag:
            self._set_cancel_flag(cancel_flag)
        if process_callback:
            self._set_process_callback(process_callback)

        try:
            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 1. 获取基础 Python 路径
            base_python_path, python_error = self._get_python_path(config)
            if not base_python_path:
                return False, python_error or "未找到 Python 环境", None

            self.log(f"基础 Python: {base_python_path}")

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 2. 设置虚拟环境（如果启用）
            python_path = self._setup_venv_if_needed(config, base_python_path)
            if python_path != base_python_path:
                self.log(f"使用虚拟环境 Python: {python_path}")

            # 3. 检查中文路径警告
            self._check_chinese_paths(config)

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 4. 准备输出目录
            script_path = config["script_path"]
            project_dir = config.get("project_dir")
            output_dir = self._prepare_output_dir(config)
            self.log(f"输出目录: {output_dir}")

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 5. 检测 Qt 框架
            primary_qt = self.dependency_analyzer.detect_primary_qt_framework(
                script_path, project_dir
            )
            if primary_qt:
                self.log(f"检测到GUI主要 Qt 框架: {primary_qt}")

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 6. 分析依赖
            deps, hidden_imports, exclude_modules = self._analyze_dependencies(
                script_path, project_dir, python_path, config
            )

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 7. 安装依赖（补充安装分析到的额外依赖）
            self._install_dependencies(python_path, deps, project_dir)

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 8. 安装打包工具
            tool = config.get("tool", "pyinstaller")
            self.log(f"\n检查打包工具 {tool}...")
            self.dependency_installer.install_packaging_tool(python_path, tool)

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 9. 处理图标
            icon_path = self._process_icon(config, output_dir, python_path)

            # 10. 准备版本信息
            version_file = self._prepare_version_info(config, output_dir)

            # 检查取消
            if self._is_cancelled():
                return False, "打包已取消", None

            # 11. 执行打包
            success, message = self._do_package(
                python_path,
                config,
                output_dir,
                hidden_imports,
                exclude_modules,
                icon_path,
                version_file,
            )

            return success, message, self._last_exe_path

        except Exception as e:
            self.log(f"打包异常: {e}")
            import traceback
            self.log(traceback.format_exc())
            return False, f"打包过程出错: {str(e)}", None

    # ========== 兼容性方法（保持原有接口）==========

    def check_windows_sdk_support(self) -> Tuple[bool, str]:
        """检查 Windows SDK 支持（委托给 windows_resource_handler）"""
        return self.windows_resource_handler.check_windows_sdk_support()
