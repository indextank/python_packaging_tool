"""
Nuitka 打包器模块

本模块负责使用 Nuitka 进行打包，包括：
- 构建 Nuitka 命令行参数
- 处理隐藏导入和排除模块
- 处理 GCC 编译器配置
- 执行打包过程

功能：
- 支持单文件和目录模式
- 支持 GUI 和控制台模式
- 支持图标和版本信息
- 支持 GCC/MinGW 编译器
- 支持中文路径和中文版本信息处理
"""

import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.packaging.base import CREATE_NO_WINDOW, BasePackager, verify_tool


class NuitkaPackager(BasePackager):
    """Nuitka 打包器"""

    def __init__(self):
        """初始化 Nuitka 打包器"""
        super().__init__()
        self._pending_version_info: Optional[Dict] = None

    # region 版本信息管理

    def get_pending_version_info(self) -> Optional[Dict]:
        """获取待处理的版本信息"""
        return self._pending_version_info

    def set_pending_version_info(self, version_info: Dict) -> None:
        """设置待处理的版本信息"""
        self._pending_version_info = version_info

    def clear_pending_version_info(self) -> None:
        """清除待处理的版本信息"""
        self._pending_version_info = None

    # endregion

    def verify_nuitka(self, python_path: str) -> Tuple[bool, str]:
        """验证 Nuitka 是否可用"""
        return verify_tool(python_path, "nuitka")

    def build_command(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        script_name: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str] = None,
        gcc_path: Optional[str] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        构建 Nuitka 命令行参数

        Args:
            python_path: Python 解释器路径
            config: 打包配置
            output_dir: 输出目录
            script_name: 脚本名称
            hidden_imports: 隐藏导入列表
            exclude_modules: 排除模块列表
            icon_path: 图标路径
            gcc_path: GCC 编译器路径

        Returns:
            (命令行参数列表, 环境变量字典)
        """
        script_path = config["script_path"]

        cmd = [
            python_path,
            "-m", "nuitka",
            "--standalone",
            f"--output-dir={output_dir}",
            f"--output-filename={script_name}.exe",
        ]

        # 单文件模式
        if config.get("onefile", True):
            cmd.append("--onefile")

        # 控制台模式
        if not config.get("console", False):
            cmd.append("--windows-console-mode=disable")

        # 图标
        if icon_path and os.path.exists(icon_path):
            cmd.append(f"--windows-icon-from-ico={icon_path}")

        # 自动包含原始图标文件，确保运行时可用
        original_icon = config.get("icon_path") or config.get("icon")
        if original_icon and os.path.exists(original_icon):
            # 1. 以原始文件名包含
            basename = os.path.basename(original_icon)
            cmd.append(f"--include-data-file={original_icon}={basename}")

            # 2. 以标准名称 icon<ext> 包含
            ext = os.path.splitext(original_icon)[1]
            std_name = f"icon{ext}"
            if basename.lower() != std_name.lower():
                cmd.append(f"--include-data-file={original_icon}={std_name}")

            self.log(f"  已自动包含图标资源: {basename}")

            # 如果生成了转换后的 ICO (icon_converted.ico)，也将其包含为 icon.ico
            # 这样用户代码如果引用 icon.ico 也能正常工作
            if icon_path and icon_path != original_icon and icon_path.endswith(".ico"):
                if "icon_converted.ico" in os.path.basename(icon_path):
                    cmd.append(f"--include-data-file={icon_path}=icon.ico")
                    self.log("  已自动包含转换后的图标: icon.ico")

        # 隐藏导入（使用 --include-module）
        for hidden in hidden_imports:
            # 检查是否是包还是模块
            if '.' in hidden:
                cmd.append(f"--include-module={hidden}")
            else:
                cmd.append(f"--include-package={hidden}")

        # 排除模块
        for exclude in exclude_modules:
            cmd.append(f"--nofollow-import-to={exclude}")

        # 启用插件（根据检测到的框架）
        if config.get("qt_framework"):
            qt_framework = config["qt_framework"]
            if qt_framework == "PyQt6":
                cmd.append("--enable-plugin=pyqt6")
            elif qt_framework == "PyQt5":
                cmd.append("--enable-plugin=pyqt5")
            elif qt_framework == "PySide6":
                cmd.append("--enable-plugin=pyside6")
            elif qt_framework == "PySide2":
                cmd.append("--enable-plugin=pyside2")

        if config.get("uses_tkinter"):
            cmd.append("--enable-plugin=tk-inter")

        if config.get("uses_numpy"):
            cmd.append("--enable-plugin=numpy")

        if config.get("uses_matplotlib"):
            cmd.append("--enable-plugin=matplotlib")

        # 版本信息
        version_info = config.get("version_info", {})
        if version_info:
            self.log(f"检测到版本信息配置: {list(version_info.keys())}")
            self._add_version_info_to_cmd(cmd, version_info, config)
        else:
            self.log("未检测到版本信息配置")

        # 额外数据文件
        extra_data = config.get("extra_data", [])
        for data in extra_data:
            if os.path.isdir(data):
                cmd.append(f"--include-data-dir={data}={os.path.basename(data)}")
            elif os.path.isfile(data):
                cmd.append(f"--include-data-file={data}={os.path.basename(data)}")

        # 添加脚本路径
        cmd.append(script_path)

        # 环境变量
        env = os.environ.copy()

        # 设置 GCC 编译器
        if gcc_path:
            # 确保 gcc_path 指向 gcc.exe 文件而不是目录
            actual_gcc_path = self._resolve_gcc_executable(gcc_path)
            if actual_gcc_path:
                gcc_dir = os.path.dirname(actual_gcc_path)
                env["CC"] = actual_gcc_path
                # 添加到 PATH
                if gcc_dir not in env.get("PATH", ""):
                    env["PATH"] = gcc_dir + os.pathsep + env.get("PATH", "")

        return cmd, env

    def _resolve_gcc_executable(self, gcc_path: str) -> Optional[str]:
        """
        解析 GCC 可执行文件路径

        如果传入的是目录路径，则尝试在其中找到 gcc.exe
        如果传入的已经是 gcc.exe 文件路径，则直接返回

        Args:
            gcc_path: GCC 路径（可能是目录或文件）

        Returns:
            gcc.exe 的完整路径，如果未找到则返回 None
        """
        if not gcc_path:
            return None

        # 如果已经是文件路径且存在
        if os.path.isfile(gcc_path):
            return gcc_path

        # 如果是目录，尝试在其中找到 gcc.exe
        if os.path.isdir(gcc_path):
            # 常见的 GCC 可执行文件位置
            possible_paths = [
                os.path.join(gcc_path, "bin", "gcc.exe"),
                os.path.join(gcc_path, "gcc.exe"),
                os.path.join(gcc_path, "mingw64", "bin", "gcc.exe"),
                os.path.join(gcc_path, "mingw32", "bin", "gcc.exe"),
            ]

            for path in possible_paths:
                if os.path.isfile(path):
                    self.log(f"找到 GCC: {path}")
                    return path

            # 尝试递归查找 bin/gcc.exe
            for root, dirs, files in os.walk(gcc_path):
                if "gcc.exe" in files:
                    gcc_exe = os.path.join(root, "gcc.exe")
                    self.log(f"找到 GCC: {gcc_exe}")
                    return gcc_exe
                # 限制搜索深度
                depth = root[len(gcc_path):].count(os.sep)
                if depth >= 3:
                    dirs[:] = []  # 不再深入搜索

            self.log(f"警告: 在 {gcc_path} 中未找到 gcc.exe")
            return None

        return None

    def _add_version_info_to_cmd(
        self,
        cmd: List[str],
        version_info: Dict,
        config: Dict,
    ) -> None:
        """
        添加版本信息到命令行

        Args:
            cmd: 命令行参数列表
            version_info: 版本信息字典
            config: 打包配置
        """
        # 检查是否包含中文字符
        def has_chinese(text: str) -> bool:
            if not text:
                return False
            return any('\u4e00' <= char <= '\u9fff' for char in text)

        # 检查版本信息中是否有中文
        has_chinese_info = any(
            has_chinese(str(v)) for v in version_info.values()
        )

        if has_chinese_info:
            # 中文版本信息需要后处理
            self._pending_version_info = version_info.copy()  # 使用副本避免引用问题
            self.log("检测到中文版本信息，将在打包后通过后处理添加")
            self.log(f"  待处理版本信息: product_name={version_info.get('product_name', '')}, "
                     f"company_name={version_info.get('company_name', '')}, "
                     f"file_description={version_info.get('file_description', '')}, "
                     f"copyright={version_info.get('copyright', '')}, "
                     f"version={version_info.get('version', '')}")
        else:
            # 非中文版本信息可以直接添加
            if version_info.get("product_name"):
                cmd.append(f"--product-name={version_info['product_name']}")

            if version_info.get("file_version"):
                cmd.append(f"--file-version={version_info['file_version']}")

            if version_info.get("product_version"):
                cmd.append(f"--product-version={version_info['product_version']}")

            if version_info.get("company_name"):
                cmd.append(f"--company-name={version_info['company_name']}")

            if version_info.get("file_description"):
                cmd.append(f"--file-description={version_info['file_description']}")

            if version_info.get("copyright"):
                cmd.append(f"--copyright={version_info['copyright']}")

    def package(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str] = None,
        gcc_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        执行 Nuitka 打包

        Args:
            python_path: Python 解释器路径
            config: 打包配置
            output_dir: 输出目录
            hidden_imports: 隐藏导入列表
            exclude_modules: 排除模块列表
            icon_path: 图标路径
            gcc_path: GCC 编译器路径

        Returns:
            (是否成功, 消息)
        """
        # 验证 Nuitka
        is_available, version_info = self.verify_nuitka(python_path)
        if not is_available:
            return False, f"Nuitka 不可用: {version_info}"

        self.log(f"✓ Nuitka 版本: {version_info}")

        script_path = config["script_path"]
        project_dir = config.get("project_dir")

        # 确定输出文件名
        if config.get("program_name"):
            script_name = config["program_name"]
        elif project_dir and os.path.basename(project_dir):
            script_name = os.path.basename(project_dir)
        else:
            script_name = Path(script_path).stem

        # 检测中文字符，使用临时英文名
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in script_name)
        temp_name = None
        if has_chinese:
            import uuid
            temp_name = f"temp_{uuid.uuid4().hex[:8]}"
            self.log(f"检测到中文名称，使用临时名称打包: {temp_name}")
            build_name = temp_name
        else:
            build_name = script_name

        self.log(f"输出文件名: {script_name}")

        # 构建命令
        cmd, env = self.build_command(
            python_path,
            config,
            output_dir,
            build_name,
            hidden_imports,
            exclude_modules,
            icon_path,
            gcc_path,
        )

        self.log(f"\n执行命令: {' '.join(cmd[:5])}...")

        try:
            # 执行打包
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if self.process_callback:
                self.process_callback(process)

            # 实时输出日志
            cancelled, msg = self._read_process_output(process)
            if cancelled:
                return False, msg

            # 检查结果
            if process.returncode == 0:
                # 查找输出文件
                exe_path = self._find_output_exe(output_dir, build_name, config)

                if exe_path and os.path.exists(exe_path):
                    # 如果使用了临时名称，重命名
                    if temp_name:
                        final_exe_path = os.path.join(
                            os.path.dirname(exe_path),
                            f"{script_name}.exe"
                        )
                        try:
                            os.rename(exe_path, final_exe_path)
                            exe_path = final_exe_path
                            self.log(f"已重命名为: {script_name}.exe")
                        except Exception as e:
                            self.log(f"⚠️ 重命名失败: {e}")

                    self._last_exe_path = exe_path

                    # 清理构建缓存
                    self._clean_build_cache(output_dir, build_name, config)

                    return True, f"打包成功！\n\n输出文件: {exe_path}"
                else:
                    return False, "打包完成，但未找到输出文件"
            else:
                return False, f"Nuitka 执行失败，返回码: {process.returncode}"

        except Exception as e:
            return False, f"执行 Nuitka 时出错: {str(e)}"

    def _find_output_exe(
        self,
        output_dir: str,
        script_name: str,
        config: Dict,
    ) -> Optional[str]:
        """
        查找输出的 exe 文件

        Args:
            output_dir: 输出目录
            script_name: 脚本名称
            config: 打包配置

        Returns:
            exe 文件路径
        """
        # Nuitka 输出路径模式
        patterns = [
            # onefile 模式
            os.path.join(output_dir, f"{script_name}.exe"),
            # standalone 模式（目录）
            os.path.join(output_dir, f"{script_name}.dist", f"{script_name}.exe"),
            # 其他可能的位置
            os.path.join(output_dir, script_name, f"{script_name}.exe"),
        ]

        for pattern in patterns:
            if os.path.exists(pattern):
                return pattern

        # 搜索输出目录
        for root, dirs, files in os.walk(output_dir):
            for file in files:
                if file == f"{script_name}.exe":
                    return os.path.join(root, file)

        return None

    def _clean_build_cache(self, output_dir: str, script_name: str, config: Optional[Dict] = None) -> None:
        """
        清理 Nuitka 构建缓存

        Args:
            output_dir: 输出目录
            script_name: 程序名称（输出文件名）
            config: 打包配置（用于获取入口脚本名）
        """
        import shutil

        # 收集需要清理的目录名前缀
        # Nuitka 使用入口脚本名（不含扩展名）作为临时目录名，而不是输出文件名
        names_to_clean = {script_name}

        if config and config.get("script_path"):
            # 获取入口脚本的基本名称（不含扩展名）
            entry_script_name = Path(config["script_path"]).stem
            names_to_clean.add(entry_script_name)

        # 同时扫描输出目录，查找所有 .build, .dist, .onefile-build 目录
        try:
            for item in os.listdir(output_dir):
                item_path = os.path.join(output_dir, item)
                if os.path.isdir(item_path):
                    # 检查是否是 Nuitka 生成的临时目录
                    if item.endswith('.build') or item.endswith('.dist') or item.endswith('.onefile-build'):
                        names_to_clean.add(item.rsplit('.', 1)[0])
        except Exception:
            pass

        # 清理所有匹配的目录
        for name in names_to_clean:
            # 清理 .build 目录
            build_dir = os.path.join(output_dir, f"{name}.build")
            if os.path.exists(build_dir):
                try:
                    shutil.rmtree(build_dir)
                    self.log(f"已清理构建缓存: {build_dir}")
                except Exception as e:
                    self.log(f"⚠️ 清理构建缓存失败: {e}")

            # 清理 .dist 目录（standalone 模式下的输出目录）
            dist_dir = os.path.join(output_dir, f"{name}.dist")
            if os.path.exists(dist_dir):
                try:
                    shutil.rmtree(dist_dir)
                    self.log(f"已清理 dist 目录: {dist_dir}")
                except Exception as e:
                    self.log(f"⚠️ 清理 dist 目录失败: {e}")

            # 清理 .onefile-build 目录
            onefile_build_dir = os.path.join(output_dir, f"{name}.onefile-build")
            if os.path.exists(onefile_build_dir):
                try:
                    shutil.rmtree(onefile_build_dir)
                    self.log(f"已清理构建缓存: {onefile_build_dir}")
                except Exception as e:
                    self.log(f"⚠️ 清理构建缓存失败: {e}")

        # 清理 Nuitka 全局编译缓存（clcache、ccache 等）
        nuitka_options = config.get("nuitka_advanced_options", {}) if config else {}
        if nuitka_options.get("clean_cache_after_build", False):
            self._clean_nuitka_global_cache(nuitka_options.get("custom_cache_dir", ""))

        # 注意：不再此处清理 icon_converted.ico，保留给后处理使用
        # 由 packager.py 在完成所有操作后统一清理

    @staticmethod
    def _get_default_nuitka_cache_dir() -> str:
        """
        获取 Nuitka 默认全局缓存根目录

        Returns:
            缓存根目录路径，如 C:\\Users\\<用户名>\\AppData\\Local\\Nuitka\\Nuitka\\Cache
        """
        if sys.platform == "win32":
            local_app_data = os.environ.get(
                "LOCALAPPDATA",
                os.path.join(os.path.expanduser("~"), "AppData", "Local"),
            )
            return os.path.join(local_app_data, "Nuitka", "Nuitka", "Cache")
        else:
            # Linux / macOS: ~/.cache/Nuitka
            xdg_cache = os.environ.get(
                "XDG_CACHE_HOME",
                os.path.join(os.path.expanduser("~"), ".cache"),
            )
            return os.path.join(xdg_cache, "Nuitka")

    def _clean_nuitka_global_cache(self, custom_cache_dir: str = "") -> None:
        """
        清理 Nuitka 全局编译缓存目录

        清理的子目录包括：
        - clcache   (Windows MSVC 编译缓存)
        - ccache    (GCC/Clang 编译缓存)
        - bytecode  (字节码缓存)
        - dll_dependencies (DLL 依赖分析缓存)

        不清理的子目录：
        - downloads (已下载的工具链，如 MinGW GCC，清理后需重新下载)

        Args:
            custom_cache_dir: 用户自定义的缓存根目录，为空则使用默认位置
        """
        import shutil

        # 确定缓存根目录
        if custom_cache_dir and os.path.isdir(custom_cache_dir):
            cache_root = custom_cache_dir
        else:
            cache_root = self._get_default_nuitka_cache_dir()

        if not os.path.isdir(cache_root):
            self.log(f"Nuitka 全局缓存目录不存在，跳过清理: {cache_root}")
            return

        self.log(f"\n开始清理 Nuitka 全局编译缓存: {cache_root}")

        # 需要清理的编译缓存子目录
        # 注意：保留 downloads 目录，该目录包含已下载的工具链（如 MinGW GCC），
        # 清理后需要重新下载，耗时且浪费带宽
        cache_subdirs = [
            "clcache",
            "ccache",
            "bytecode",
            "dll_dependencies",
        ]

        total_cleaned_size = 0

        for subdir_name in cache_subdirs:
            subdir_path = os.path.join(cache_root, subdir_name)
            if not os.path.isdir(subdir_path):
                continue

            # 计算目录大小
            dir_size = 0
            try:
                for dirpath, _dirnames, filenames in os.walk(subdir_path):
                    for f in filenames:
                        fp = os.path.join(dirpath, f)
                        try:
                            dir_size += os.path.getsize(fp)
                        except OSError:
                            pass
            except Exception:
                pass

            # 执行清理
            try:
                shutil.rmtree(subdir_path)
                size_mb = dir_size / (1024 * 1024)
                total_cleaned_size += dir_size
                self.log(f"  ✓ 已清理 {subdir_name} ({size_mb:.1f} MB)")
            except Exception as e:
                self.log(f"  ⚠️ 清理 {subdir_name} 失败: {e}")

        if total_cleaned_size > 0:
            total_mb = total_cleaned_size / (1024 * 1024)
            self.log(f"  共释放空间: {total_mb:.1f} MB")
        else:
            self.log("  未发现需要清理的编译缓存")

    def extract_gcc(
        self,
        gcc_zip_path: str,
        extract_base_dir: str,
    ) -> Optional[str]:
        """
        解压 GCC 工具链

        Args:
            gcc_zip_path: GCC zip 文件路径
            extract_base_dir: 解压基础目录

        Returns:
            解压后的 mingw64 目录路径，失败返回 None
        """
        try:
            self.log(f"解压 GCC 工具链: {gcc_zip_path}")

            with zipfile.ZipFile(gcc_zip_path, 'r') as zip_ref:
                # 获取顶层目录名
                top_dirs = set()
                for name in zip_ref.namelist():
                    parts = name.split('/')
                    if parts[0]:
                        top_dirs.add(parts[0])

                # 解压
                zip_ref.extractall(extract_base_dir)

            # 查找 mingw64 目录
            for top_dir in top_dirs:
                mingw_path = os.path.join(extract_base_dir, top_dir)
                if os.path.isdir(mingw_path):
                    bin_path = os.path.join(mingw_path, "bin")
                    if os.path.isdir(bin_path):
                        gcc_exe = os.path.join(bin_path, "gcc.exe")
                        if os.path.exists(gcc_exe):
                            self.log(f"✓ GCC 工具链解压成功: {mingw_path}")
                            return mingw_path

            # 直接查找 bin 目录
            bin_path = os.path.join(extract_base_dir, "bin")
            if os.path.isdir(bin_path):
                gcc_exe = os.path.join(bin_path, "gcc.exe")
                if os.path.exists(gcc_exe):
                    return extract_base_dir

            self.log("⚠️ 未找到 GCC 可执行文件")
            return None

        except Exception as e:
            self.log(f"⚠️ 解压 GCC 失败: {e}")
            return None

    def find_gcc(self) -> Optional[str]:
        """
        查找系统中的 GCC 编译器

        Returns:
            GCC 可执行文件路径，未找到返回 None
        """
        import shutil

        # 尝试在 PATH 中查找
        gcc_path = shutil.which("gcc")
        if gcc_path:
            self.log(f"找到系统 GCC: {gcc_path}")
            return gcc_path

        # 常见的 MinGW 安装位置
        common_paths = [
            r"C:\mingw64\bin\gcc.exe",
            r"C:\mingw-w64\mingw64\bin\gcc.exe",
            r"C:\msys64\mingw64\bin\gcc.exe",
            r"C:\msys64\ucrt64\bin\gcc.exe",
            r"C:\TDM-GCC-64\bin\gcc.exe",
            r"C:\Program Files\mingw-w64\x86_64-posix-seh\mingw64\bin\gcc.exe",
        ]

        for path in common_paths:
            if os.path.exists(path):
                self.log(f"找到 GCC: {path}")
                return path

        return None

    def verify_gcc(self, gcc_path: str) -> Tuple[bool, str]:
        """
        验证 GCC 是否可用

        Args:
            gcc_path: GCC 可执行文件路径

        Returns:
            (是否可用, 版本信息或错误信息)
        """
        try:
            result = subprocess.run(
                [gcc_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                return True, version
            else:
                return False, result.stderr

        except Exception as e:
            return False, str(e)

    def get_nuitka_version_info(
        self,
        python_path: str,
    ) -> Dict[str, Any]:
        """
        获取 Nuitka 版本信息

        Args:
            python_path: Python 解释器路径

        Returns:
            版本信息字典
        """
        info = {
            "version": None,
            "supports_onefile": False,
            "supports_plugins": False,
        }

        try:
            result = subprocess.run(
                [python_path, "-m", "nuitka", "--version"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if result.returncode == 0:
                version_str = result.stdout.strip().split('\n')[0]
                info["version"] = version_str

                # 解析版本号
                import re
                match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_str)
                if match:
                    major = int(match.group(1))
                    minor = int(match.group(2))
                    patch = int(match.group(3))

                    # Nuitka 0.6.8+ 支持 onefile
                    if (major, minor, patch) >= (0, 6, 8):
                        info["supports_onefile"] = True

                    # Nuitka 0.6.0+ 支持插件
                    if (major, minor) >= (0, 6):
                        info["supports_plugins"] = True

        except Exception:
            pass

        return info
