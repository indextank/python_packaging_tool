import ast
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple, cast

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from core.dependency_analyzer import DependencyAnalyzer
from utils.dependency_manager import DependencyManager
from utils.python_finder import PythonFinder

# Windows 子进程隐藏标志
if sys.platform == "win32":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0


class Packager:
    """打包器，负责将Python脚本打包成exe"""

    # 国内镜像源列表（国内网络环境优先使用）
    PIP_MIRRORS_DOMESTIC = [
        ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
        ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
        ("腾讯云", "https://mirrors.cloud.tencent.com/pypi/simple"),
        ("华为云", "https://repo.huaweicloud.com/repository/pypi/simple"),
        ("中科大", "https://pypi.mirrors.ustc.edu.cn/simple"),
        ("豆瓣", "https://pypi.douban.com/simple"),
        ("默认源", None),  # 默认 PyPI 放在最后
    ]

    # 国外镜像源列表（国外网络环境优先使用）
    PIP_MIRRORS_INTERNATIONAL = [
        ("默认源", None),  # 默认 PyPI 优先
        ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
        ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
        ("腾讯云", "https://mirrors.cloud.tencent.com/pypi/simple"),
        ("华为云", "https://repo.huaweicloud.com/repository/pypi/simple"),
        ("中科大", "https://pypi.mirrors.ustc.edu.cn/simple"),
        ("豆瓣", "https://pypi.douban.com/simple"),
    ]

    def __init__(self):
        self.python_finder = PythonFinder()
        self.dependency_analyzer = DependencyAnalyzer()
        self.dependency_manager = DependencyManager()
        self.cancel_flag: Optional[Callable] = None
        self.process_callback: Optional[Callable] = None
        self._last_exe_path: Optional[str] = None  # 记录最后生成的 exe 路径
        self._current_mirror_index = 0  # 当前使用的镜像源索引
        self._is_domestic_network: Optional[bool] = None  # 缓存网络环境检测结果
        self._pip_mirrors: Optional[List[Tuple[str, Optional[str]]]] = None  # 当前使用的镜像源列表

    def _add_version_info_cmdline(self, cmd: List[str], product_name: str, company_name: str,
                                   file_description: str, copyright_text: str, version_str: str) -> None:
        """通过命令行参数添加 Windows 版本信息"""
        if product_name:
            cmd.append(f"--windows-product-name={product_name}")
            self.log(f"  ✓ 产品名称: {product_name}")
        if company_name:
            cmd.append(f"--windows-company-name={company_name}")
            self.log(f"  ✓ 公司名称: {company_name}")
        if file_description:
            cmd.append(f"--windows-file-description={file_description}")
            self.log(f"  ✓ 文件描述: {file_description}")
        if copyright_text:
            cmd.append(f"--copyright={copyright_text}")
            self.log(f"  ✓ 版权信息: {copyright_text}")
        if version_str:
            cmd.append(f"--windows-product-version={version_str}")
            cmd.append(f"--windows-file-version={version_str}")
            self.log(f"  ✓ 版本号: {version_str}")

    def _create_version_resource_file(self, output_dir: str, script_name: str,
                                       product_name: str, company_name: str,
                                       file_description: str, copyright_text: str,
                                       version_str: str, icon_path: Optional[str] = None) -> Optional[str]:
        """
        创建 Windows 资源文件(.rc)并编译为 .res 文件，用于支持中文版本信息

        Args:
            output_dir: 输出目录
            script_name: 脚本名称（用于内部名称）
            product_name: 产品名称
            company_name: 公司名称
            file_description: 文件描述
            copyright_text: 版权信息
            version_str: 版本号
            icon_path: 图标路径（可选）

        Returns:
            编译后的 .res 文件路径，失败返回 None
        """
        try:
            # 解析版本号为四段式
            version_parts = version_str.split(".")
            while len(version_parts) < 4:
                version_parts.append("0")
            version_parts = [p if p.isdigit() else "0" for p in version_parts[:4]]
            version_tuple = ",".join(version_parts)
            version_dot = ".".join(version_parts)

            # 转义特殊字符
            def escape_rc_string(s: str) -> str:
                if not s:
                    return ""
                return s.replace("\\", "\\\\").replace('"', '\\"')

            product_name_escaped = escape_rc_string(product_name)
            company_name_escaped = escape_rc_string(company_name)
            file_description_escaped = escape_rc_string(file_description)
            copyright_text_escaped = escape_rc_string(copyright_text)

            # 构建 .rc 文件内容
            # 不包含 windows.h - 手动定义所需常量以避免依赖
            rc_content = f'''// 版本信息资源 - 由 Python打包工具 自动生成
// 支持中文字符
// 自包含 - 不需要 windows.h

// 手动定义常量 (来自 winver.h)
#ifndef VS_VERSION_INFO
#define VS_VERSION_INFO 1
#endif
#define VOS_NT_WINDOWS32 0x00040004L
#define VFT_APP 0x00000001L

'''
            # 如果有图标，添加图标资源
            if icon_path:
                # 转换路径分隔符
                icon_path_escaped = icon_path.replace("\\", "\\\\").replace("/", "\\\\")
                rc_content += f'IDI_ICON1 ICON "{icon_path_escaped}"\n\n'

            rc_content += f'''VS_VERSION_INFO VERSIONINFO
 FILEVERSION {version_tuple}
 PRODUCTVERSION {version_tuple}
 FILEFLAGSMASK 0x3fL
#ifdef _DEBUG
 FILEFLAGS 0x1L
#else
 FILEFLAGS 0x0L
#endif
 FILEOS VOS_NT_WINDOWS32
 FILETYPE VFT_APP
 FILESUBTYPE 0x0L
BEGIN
    BLOCK "StringFileInfo"
    BEGIN
        BLOCK "080404b0"
        BEGIN
            VALUE "CompanyName", "{company_name_escaped}"
            VALUE "FileDescription", "{file_description_escaped}"
            VALUE "FileVersion", "{version_dot}"
            VALUE "InternalName", "{escape_rc_string(script_name)}"
            VALUE "LegalCopyright", "{copyright_text_escaped}"
            VALUE "ProductName", "{product_name_escaped}"
            VALUE "ProductVersion", "{version_dot}"
        END
    END
    BLOCK "VarFileInfo"
    BEGIN
        VALUE "Translation", 0x804, 1200
    END
END
'''

            # 写入 .rc 文件（使用 UTF-8 with BOM，Windows rc.exe 支持）
            rc_file_path = os.path.join(output_dir, "version_info.rc")
            with open(rc_file_path, "w", encoding="utf-8-sig") as f:
                f.write(rc_content)

            self.log(f"  已创建资源文件: {rc_file_path}")

            # 查找 Windows SDK 的 rc.exe
            rc_exe = self._find_rc_exe()

            if not rc_exe:
                self.log("  ⚠️  未找到 Windows SDK 资源编译器 (rc.exe)")
                self.log("  提示: 请安装 Windows SDK 或 Visual Studio Build Tools")
                return None

            self.log(f"  使用资源编译器: {rc_exe}")

            # 编译 .rc 为 .res
            res_file_path = os.path.join(output_dir, "version_info.res")

            include_dirs = self._get_windows_sdk_include_dirs()
            include_args: List[str] = []
            for include_dir in include_dirs:
                include_args.extend(["/I", include_dir])

            if not include_dirs:
                self.log("  ⚠️  未找到 Windows SDK Include 目录，可能无法编译包含 windows.h 的资源文件")

            # 执行编译命令
            compile_cmd = [rc_exe, "/fo", res_file_path, "/nologo"] + include_args + [rc_file_path]

            result = subprocess.run(
                compile_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                cwd=output_dir
            )

            if result.returncode == 0 and os.path.exists(res_file_path):
                self.log(f"  已编译资源文件: {res_file_path}")
                return res_file_path
            else:
                self.log(f"  ⚠️  资源编译失败，返回码: {result.returncode}")
                if result.stdout:
                    self.log(f"  stdout: {result.stdout.strip()}")
                if result.stderr:
                    self.log(f"  stderr: {result.stderr.strip()}")
                return None

        except Exception as e:
            self.log(f"  ⚠️  创建资源文件时出错: {str(e)}")
            return None

    def check_windows_sdk_support(self) -> Tuple[bool, str]:
        """
        检查系统是否支持中文版本信息（Windows SDK/Visual Studio）

        Returns:
            (是否支持, 描述信息)
        """
        rc_exe = self._find_rc_exe()
        if rc_exe:
            include_dirs = self._get_windows_sdk_include_dirs()
            if not include_dirs:
                return False, "检测到 rc.exe，但未找到 Windows SDK Include 目录（windows.h），请安装 Windows SDK C++ 组件"

            if "Windows Kits" in rc_exe:
                return True, f"检测到 Windows SDK (rc.exe: {rc_exe})"
            elif "Visual Studio" in rc_exe:
                return True, f"检测到 Visual Studio (rc.exe: {rc_exe})"
            else:
                return True, f"检测到资源编译器 (rc.exe: {rc_exe})"

        # 检查是否存在 Windows SDK 或 Visual Studio 目录（即使没找到 rc.exe）
        sdk_paths = [
            r"C:\Program Files (x86)\Windows Kits\10",
            r"C:\Program Files\Windows Kits\10",
        ]
        vs_paths = [
            r"C:\Program Files\Microsoft Visual Studio",
            r"C:\Program Files (x86)\Microsoft Visual Studio",
        ]

        for path in sdk_paths:
            if os.path.exists(path):
                return False, "检测到 Windows SDK 目录，但未找到 rc.exe，可能需要安装 Windows SDK 开发工具"

        for path in vs_paths:
            if os.path.exists(path):
                return False, "检测到 Visual Studio 目录，但未找到 rc.exe，可能需要安装 C++ 桌面开发工具"

        return False, "未检测到 Windows SDK 或 Visual Studio，中文版本信息可能无法正常显示"

    def _get_windows_sdk_include_dirs(self) -> List[str]:
        """
        获取 Windows SDK Include 目录（用于 rc.exe 编译 resources）

        Returns:
            Include 目录列表（um/shared/ucrt 等），未找到返回空列表
        """
        include_roots = [
            r"C:\Program Files (x86)\Windows Kits\10\Include",
            r"C:\Program Files\Windows Kits\10\Include",
        ]

        for root in include_roots:
            if not os.path.exists(root):
                continue

            try:
                versions = [v for v in os.listdir(root) if v.startswith("10.")]
                versions.sort(reverse=True)
                for version in versions:
                    version_dir = os.path.join(root, version)
                    if not os.path.isdir(version_dir):
                        continue
                    candidates = [
                        os.path.join(version_dir, "um"),
                        os.path.join(version_dir, "shared"),
                        os.path.join(version_dir, "ucrt"),
                        os.path.join(version_dir, "winrt"),
                    ]
                    include_dirs = [p for p in candidates if os.path.isdir(p)]
                    if include_dirs:
                        return include_dirs
            except Exception:
                continue

        return []

    def _find_rc_exe(self) -> Optional[str]:
        """
        查找 Windows SDK 的资源编译器 rc.exe

        Returns:
            rc.exe 的完整路径，未找到返回 None
        """
        # 首先检查 PATH 中是否有 rc.exe
        rc_in_path = shutil.which("rc.exe")
        if rc_in_path:
            return rc_in_path

        # 搜索 Windows SDK 安装目录
        sdk_roots = [
            r"C:\Program Files (x86)\Windows Kits\10\bin",
            r"C:\Program Files\Windows Kits\10\bin",
        ]

        # 按版本号降序排列，优先使用新版本
        for sdk_root in sdk_roots:
            if not os.path.exists(sdk_root):
                continue

            try:
                # 获取所有版本目录
                versions = []
                for item in os.listdir(sdk_root):
                    item_path = os.path.join(sdk_root, item)
                    if os.path.isdir(item_path) and item.startswith("10."):
                        versions.append(item)

                # 按版本号降序排列
                versions.sort(reverse=True)

                for version in versions:
                    # 优先使用 x64 版本
                    for arch in ["x64", "x86"]:
                        rc_path = os.path.join(sdk_root, version, arch, "rc.exe")
                        if os.path.exists(rc_path):
                            return rc_path
            except Exception:
                continue

        # 搜索 Visual Studio 安装目录
        vs_roots = [
            r"C:\Program Files\Microsoft Visual Studio",
            r"C:\Program Files (x86)\Microsoft Visual Studio",
        ]

        for vs_root in vs_roots:
            if not os.path.exists(vs_root):
                continue

            try:
                # 遍历 VS 版本 (2022, 2019, 2017...)
                for vs_year in sorted(os.listdir(vs_root), reverse=True):
                    vs_year_path = os.path.join(vs_root, vs_year)
                    if not os.path.isdir(vs_year_path):
                        continue

                    # 遍历 VS 版本类型 (Enterprise, Professional, Community, BuildTools)
                    for edition in os.listdir(vs_year_path):
                        sdk_bin = os.path.join(vs_year_path, edition, "VC", "Tools", "MSVC")
                        if not os.path.exists(sdk_bin):
                            continue

                        # 遍历 MSVC 版本
                        for msvc_ver in sorted(os.listdir(sdk_bin), reverse=True):
                            for arch in ["x64", "x86"]:
                                rc_path = os.path.join(sdk_bin, msvc_ver, "bin", f"Host{arch}", arch, "rc.exe")
                                if os.path.exists(rc_path):
                                    return rc_path
            except Exception:
                continue

        return None

    def _create_version_info_file(self, config: Dict, output_dir: str) -> Optional[str]:
        """
        创建 PyInstaller 版本信息文件

        Args:
            config: 打包配置，包含 version_info 字段
            output_dir: 输出目录

        Returns:
            版本信息文件路径，如果没有配置则返回 None
        """
        version_info = config.get("version_info")
        if not version_info:
            return None

        # 解析版本号
        version_str = version_info.get("version", "1.0.0")
        version_parts = version_str.split(".")
        while len(version_parts) < 4:
            version_parts.append("0")
        version_tuple = tuple(int(p) if p.isdigit() else 0 for p in version_parts[:4])

        # 获取程序名称
        program_name = config.get("program_name") or Path(config.get("script_path", "app")).stem

        # 创建版本信息文件内容
        version_info_content = f'''# UTF-8
#
# 版本信息文件 - 由 Python打包工具 自动生成
#

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
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
          u'080404b0',
          [
            StringStruct(u'CompanyName', u'{version_info.get("company_name", "")}'),
            StringStruct(u'FileDescription', u'{version_info.get("file_description", program_name)}'),
            StringStruct(u'FileVersion', u'{version_str}'),
            StringStruct(u'InternalName', u'{program_name}'),
            StringStruct(u'LegalCopyright', u'{version_info.get("copyright", "")}'),
            StringStruct(u'OriginalFilename', u'{program_name}.exe'),
            StringStruct(u'ProductName', u'{version_info.get("product_name", program_name)}'),
            StringStruct(u'ProductVersion', u'{version_str}'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [2052, 1200])])
  ]
)
'''

        # 写入文件
        version_file_path = os.path.join(output_dir, "version_info.txt")
        try:
            with open(version_file_path, "w", encoding="utf-8") as f:
                f.write(version_info_content)
            self.log(f"已创建版本信息文件: {version_file_path}")
            return version_file_path
        except Exception as e:
            self.log(f"警告: 创建版本信息文件失败: {str(e)}")
            return None

    def _detect_network_environment(self) -> bool:
        """
        检测当前网络环境是否为国内网络

        通过尝试连接国内和国外的服务器来判断网络环境。
        国内网络通常访问国内服务器更快，访问国外服务器较慢或被限制。

        Returns:
            True 表示国内网络环境，False 表示国外网络环境
        """
        import socket
        import time

        # 测试目标：国内服务器和国外服务器
        test_targets = [
            # (host, port, is_domestic)
            ("mirrors.aliyun.com", 443, True),      # 阿里云（国内）
            ("pypi.org", 443, False),               # PyPI（国外）
        ]

        domestic_time = float('inf')
        international_time = float('inf')

        for host, port, is_domestic in test_targets:
            try:
                start = time.time()
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)  # 3秒超时
                sock.connect((host, port))
                sock.close()
                elapsed = time.time() - start

                if is_domestic:
                    domestic_time = elapsed
                else:
                    international_time = elapsed

            except (socket.timeout, socket.error, OSError):
                # 连接失败，设置为超时值
                if is_domestic:
                    domestic_time = 10.0  # 假设超时
                else:
                    international_time = 10.0

        # 判断逻辑：
        # 1. 如果国内服务器响应明显更快（小于国外的一半），认为是国内网络
        # 2. 如果国外服务器连接失败或超时，认为是国内网络
        # 3. 否则认为是国外网络
        if international_time >= 10.0:  # 国外服务器连接失败/超时
            return True
        if domestic_time < international_time * 0.5:  # 国内明显更快
            return True
        if domestic_time < 1.0 and international_time > 2.0:  # 国内很快，国外较慢
            return True

        return False

    def _get_pip_mirrors(self) -> List[Tuple[str, Optional[str]]]:
        """
        获取当前网络环境对应的镜像源列表

        Returns:
            镜像源列表，格式为 [(名称, URL), ...]
        """
        if self._pip_mirrors is not None:
            return self._pip_mirrors

        # 检测网络环境（只检测一次并缓存）
        if self._is_domestic_network is None:
            try:
                self._is_domestic_network = self._detect_network_environment()
                env_name = "中国大陆" if self._is_domestic_network else "国外"
                self.log(f"检测到网络环境: {env_name}")
            except Exception:
                # 检测失败，默认使用国内配置（更保守的选择）
                self._is_domestic_network = True
                self.log("网络环境检测失败，默认使用国内镜像源配置")

        # 根据网络环境选择镜像源列表
        if self._is_domestic_network:
            self._pip_mirrors = self.PIP_MIRRORS_DOMESTIC
        else:
            self._pip_mirrors = self.PIP_MIRRORS_INTERNATIONAL

        return self._pip_mirrors

    def package(
        self,
        config: Dict,
        log_callback: Optional[Callable] = None,
        cancel_flag: Optional[Callable] = None,
        process_callback: Optional[Callable] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        执行打包操作

        Args:
            config: 打包配置字典
            log_callback: 日志回调函数
            cancel_flag: 取消标志回调函数，返回True表示取消
            process_callback: 进程回调函数，用于传递subprocess进程对象

        Returns:
            (success, message, exe_path) 元组，exe_path 为生成的可执行文件路径
        """
        self.log = log_callback if log_callback else print
        self.cancel_flag = cancel_flag
        self.process_callback = process_callback

        # 更新依赖管理器的日志回调
        self.dependency_manager.log = self.log

        try:
            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # 1. 获取Python环境
            python_path = self._get_python_path(config)
            if not python_path:
                return False, "未找到Python环境，请安装Python或指定Python路径", None

            self.log(f"使用Python: {python_path}")

            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # 2. 准备工作目录
            script_path = config["script_path"]
            project_dir = config.get("project_dir")
            output_dir = config.get("output_dir")

            # 检查路径中是否包含中文字符
            def has_chinese(text):
                """检查字符串中是否包含中文字符"""
                if not text:
                    return False
                return any('\u4e00' <= char <= '\u9fff' for char in text)

            # 检查关键路径
            paths_to_check = {
                "脚本路径": script_path,
                "项目目录": project_dir,
            }

            chinese_paths = []
            for path_name, path_value in paths_to_check.items():
                if path_value and has_chinese(path_value):
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
                self.log("  - 或者在命令行中使用短路径名")
                self.log("")
                self.log("打包将继续尝试，但可能会遇到问题...")
                self.log("!" * 50 + "\n")

            # 确定输出目录
            if not output_dir:
                if project_dir:
                    output_dir = os.path.join(project_dir, "build")
                else:
                    output_dir = os.path.join(os.path.dirname(script_path), "build")

            # 清空已存在的 build 目录
            if os.path.exists(output_dir):
                self.log(f"\n检测到已存在的输出目录: {output_dir}")
                self.log("正在清空旧的构建文件...")
                try:
                    # 列出要删除的内容
                    items = os.listdir(output_dir)
                    if items:
                        self.log(f"发现 {len(items)} 个文件/目录需要清理")
                        for item in items:
                            item_path = os.path.join(output_dir, item)
                            try:
                                if os.path.isfile(item_path) or os.path.islink(item_path):
                                    os.unlink(item_path)
                                    self.log(f"  已删除文件: {item}")
                                elif os.path.isdir(item_path):
                                    shutil.rmtree(item_path)
                                    self.log(f"  已删除目录: {item}")
                            except Exception as e:
                                self.log(f"  警告：无法删除 {item}: {str(e)}")
                        self.log("✓ 输出目录已清空")
                    else:
                        self.log("输出目录为空，无需清理")
                except Exception as e:
                    self.log(f"警告：清空目录时出错: {str(e)}")
                    self.log("将尝试继续打包...")

            os.makedirs(output_dir, exist_ok=True)
            self.log(f"输出目录: {output_dir}")

            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # 3. 处理虚拟环境
            venv_path = None
            venv_exists = False
            if project_dir:
                venv_path = self._check_existing_venv(project_dir)
                if venv_path:
                    venv_exists = True
                    python_path = self._get_venv_python(venv_path)
                    self.log(f"使用已存在的虚拟环境: {venv_path}")
                else:
                    # 只在没有虚拟环境时才创建
                    venv_path = self._setup_venv(project_dir, python_path)
                    if venv_path:
                        python_path = self._get_venv_python(venv_path)
                        self.log(f"使用新创建的虚拟环境: {venv_path}")

            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # 4. 检测主要使用的 Qt 框架（避免多 Qt 绑定冲突）
            self.log("\n" + "=" * 50)
            self.log("检测项目使用的 GUI 框架...")
            self.log("=" * 50)
            primary_qt = self.dependency_analyzer.detect_primary_qt_framework(script_path, project_dir)
            if primary_qt:
                self.log(f"检测到主要 Qt 框架: {primary_qt}")
                # 获取需要排除的其他 Qt 绑定
                qt_exclusions = self.dependency_analyzer.get_qt_exclusion_list()
                if qt_exclusions:
                    self.log(f"将排除冲突的 Qt 绑定: {', '.join(qt_exclusions)}")

            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # 5. 分析依赖并生成优化建议
            self.log("\n" + "=" * 50)
            self.log("分析项目依赖和优化建议...")
            self.log("=" * 50)
            # 保存项目目录，供后续依赖检查使用
            self._current_project_dir = project_dir
            dependencies = self.dependency_analyzer.analyze(script_path, project_dir)

            # 生成优化报告
            if dependencies:
                optimization_report = (
                    self.dependency_analyzer.generate_optimization_report(python_path)
                )
                self.log("\n" + optimization_report)

            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # ========== 三层防护机制 ==========
            # 第一层：动态模块导入追踪
            enable_dynamic_trace = config.get("enable_dynamic_trace", True)
            if enable_dynamic_trace:
                # 检查脚本是否可运行
                script_runnable = self.dependency_analyzer.check_script_runnable(
                    script_path, python_path, project_dir
                )

                if script_runnable:
                    # 脚本可运行，使用动态追踪（超时10秒，GUI程序会自动跳过）
                    trace_success, traced_imports = self.dependency_analyzer.trace_dynamic_imports(
                        script_path, python_path, project_dir, timeout=10
                    )
                    if trace_success:
                        self.log(f"✓ 动态追踪成功，捕获到 {len(traced_imports)} 个模块导入")
                    # 注意：失败时 trace_dynamic_imports 内部已经输出了日志
                else:
                    self.log("⚠️ 脚本无法完整运行，将使用通用策略")

            # 第二层：自动收集未配置库的子模块
            self.dependency_analyzer.collect_all_unconfigured_submodules(python_path)

            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # 6. 确保必要的依赖已安装
            if not venv_exists:
                self._install_dependencies(python_path, script_path, project_dir, venv_path)
            else:
                self.log("\n检测到已存在的虚拟环境")
                # 检查并安装缺失的关键依赖
                self._ensure_critical_dependencies(python_path)

            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # 7. 安装打包工具
            tool = config.get("tool", "pyinstaller")
            self._install_packaging_tool(python_path, tool, config)

            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已取消", None

            # 8. 执行打包（带优化和失败重试）
            max_retries = config.get("max_retries", 2)  # 最多重试次数
            retry_count = 0
            last_missing_modules = set()

            while retry_count <= max_retries:
                if retry_count > 0:
                    self.log("\n" + "=" * 50)
                    self.log(f"第三层防护：失败重试（第 {retry_count} 次重试）")
                    self.log("=" * 50)

                # 根据选择的工具打包
                if tool == "pyinstaller":
                    success, message = self._package_with_pyinstaller(
                        python_path, config, output_dir
                    )
                else:  # nuitka
                    success, message = self._package_with_nuitka(
                        python_path, config, output_dir
                    )

                # 如果打包成功，测试运行
                if success and self._last_exe_path:
                    # 测试运行exe，检测是否有缺失模块
                    test_success, missing_modules = self._test_exe_for_missing_modules(
                        self._last_exe_path
                    )

                    if test_success:
                        # 运行成功
                        return success, message, self._last_exe_path
                    elif missing_modules:
                        # 检测到缺失模块
                        if missing_modules == last_missing_modules:
                            # 和上次一样的模块缺失，说明无法自动修复
                            self.log(f"⚠️ 无法自动修复缺失的模块: {missing_modules}")
                            self.log("请手动添加这些模块到隐藏导入列表")
                            return success, message + f"\n\n⚠️ 警告：检测到可能缺失的模块: {', '.join(missing_modules)}", self._last_exe_path

                        if retry_count < max_retries:
                            self.log(f"\n检测到缺失模块: {', '.join(missing_modules)}")
                            self.log("自动添加到隐藏导入列表，准备重新打包...")

                            # 添加缺失模块到动态导入集合
                            self.dependency_analyzer._dynamic_imports.update(missing_modules)

                            # 记录本次缺失的模块
                            last_missing_modules = missing_modules

                            retry_count += 1
                            continue
                        else:
                            # 达到最大重试次数
                            return success, message + f"\n\n⚠️ 警告：检测到可能缺失的模块: {', '.join(missing_modules)}", self._last_exe_path
                    else:
                        # 测试失败但没有检测到具体缺失模块
                        return success, message, self._last_exe_path
                else:
                    # 打包失败
                    return success, message, None

                retry_count += 1

            # 如果打包成功，返回 exe 路径用于打开目录
            if success and self._last_exe_path:
                return success, message, self._last_exe_path
            return success, message, None

        except Exception as e:
            return False, f"打包过程出错: {str(e)}", None

    def _get_python_path(self, config: Dict) -> Optional[str]:
        """获取Python路径"""
        # 优先使用用户指定的路径
        if config.get("python_path"):
            python_path = config["python_path"]
            if os.path.exists(python_path):
                return python_path

        # 自动查找系统Python
        python_path = self.python_finder.find_python()
        return python_path

    def _check_existing_venv(self, project_dir: str) -> Optional[str]:
        """检查是否存在虚拟环境"""
        venv_names = [".venv", "venv"]
        for venv_name in venv_names:
            venv_path = os.path.join(project_dir, venv_name)
            venv_python = self._get_venv_python(venv_path)
            if os.path.exists(venv_python):
                return venv_path
        return None

    def _setup_venv(self, project_dir: str, python_path: str) -> Optional[str]:
        """创建新的虚拟环境"""
        # 创建新的虚拟环境
        venv_path = os.path.join(project_dir, ".venv")
        self.log(f"创建虚拟环境: {venv_path}")

        try:
            result = subprocess.run(
                [python_path, "-m", "venv", venv_path],
                capture_output=True,
                text=True,
                encoding="utf-8",
                creationflags=CREATE_NO_WINDOW,
            )

            if result.returncode != 0:
                self.log(f"警告: 创建虚拟环境失败: {result.stderr}")
                return None

            self.log("虚拟环境创建成功")
            return venv_path

        except Exception as e:
            self.log(f"警告: 创建虚拟环境时出错: {e}")
            return None

    def _process_icon_file(self, icon_path: str, output_dir: str) -> Tuple[str, List[str]]:
        """
        处理图标文件，支持 PNG/SVG/ICO 格式
        自动转换为包含多尺寸的 ICO 文件

        Args:
            icon_path: 原始图标文件路径
            output_dir: 输出目录

        Returns:
            (processed_icon_path, warnings): 处理后的图标路径和警告信息列表
        """
        warnings = []

        if not os.path.exists(icon_path):
            return icon_path, ["图标文件不存在"]

        # 获取文件扩展名
        ext = os.path.splitext(icon_path)[1].lower()

        # 如果已经是 ICO 格式，检查是否包含必要尺寸
        if ext == '.ico':
            if HAS_PIL:
                try:
                    from PIL import Image
                    img = Image.open(icon_path)

                    # 检查 ICO 文件的尺寸
                    if hasattr(img, 'sizes') and img.sizes:
                        sizes = img.sizes
                        required_sizes = [(16, 16), (32, 32), (48, 48)]
                        has_required = any(size in sizes for size in required_sizes)

                        if not has_required:
                            warnings.append(f"ICO 文件缺少小尺寸图标（16x16, 32x32, 48x48）")
                            warnings.append(f"当前包含尺寸: {', '.join([f'{w}x{h}' for w, h in sizes])}")
                            warnings.append("将尝试重新生成包含所有必要尺寸的 ICO 文件")
                            # 重新生成
                            return self._convert_to_ico(icon_path, output_dir, warnings)
                        else:
                            self.log(f"✓ ICO 文件包含必要尺寸: {', '.join([f'{w}x{h}' for w, h in sizes])}")
                            return icon_path, warnings
                    else:
                        # 单尺寸 ICO，需要重新生成
                        warnings.append("ICO 文件只包含单一尺寸，将重新生成多尺寸版本")
                        return self._convert_to_ico(icon_path, output_dir, warnings)

                except Exception as e:
                    warnings.append(f"检查 ICO 文件时出错: {str(e)}")
                    return icon_path, warnings
            else:
                # 没有 PIL，无法检查，直接使用
                warnings.append("未安装 Pillow，无法验证图标尺寸")
                return icon_path, warnings

        # PNG 或 SVG 格式，需要转换
        elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.svg']:
            if not HAS_PIL:
                self.log(f"\n" + "=" * 50)
                self.log("⚠️ 需要安装 Pillow 库才能转换图标格式")
                self.log("=" * 50)
                self.log(f"检测到 {ext.upper()} 格式图标，但无法自动转换为 ICO")
                self.log("解决方案：")
                self.log("  1. 安装 Pillow: pip install Pillow")
                self.log("  2. 或手动转换为 .ico 格式后重新选择")
                self.log("  3. 或使用在线工具转换: https://www.icoconverter.com/")
                warnings.append("需要安装 Pillow 才能转换图标格式")
                warnings.append("请运行: pip install Pillow")
                return icon_path, warnings

            self.log(f"检测到 {ext.upper()} 格式图标，将转换为多尺寸 ICO 文件...")
            return self._convert_to_ico(icon_path, output_dir, warnings)
        else:
            warnings.append(f"不支持的图标格式: {ext}")
            return icon_path, warnings

        return icon_path, warnings

    def _convert_to_ico(self, source_path: str, output_dir: str, warnings: List[str]) -> Tuple[str, List[str]]:
        """
        将图片转换为包含多尺寸的 ICO 文件

        Args:
            source_path: 源图片路径
            output_dir: 输出目录
            warnings: 警告信息列表

        Returns:
            (ico_path, warnings): ICO 文件路径和警告信息
        """
        if not HAS_PIL:
            self.log("✗ 无法转换图标：未安装 Pillow 库")
            warnings.append("需要安装 Pillow 才能转换图标")
            return source_path, warnings

        try:
            from PIL import Image

            # 打开源图片
            img = Image.open(source_path)
            self.log(f"源图片尺寸: {img.size[0]}x{img.size[1]}")

            # 如果是 RGBA 模式，保持；否则转换
            if img.mode != 'RGBA':
                self.log(f"转换图片模式: {img.mode} -> RGBA")
                img = img.convert('RGBA')

            # 生成 ICO 文件路径 - 使用统一的标准名称
            ico_filename = "app_icon.ico"
            ico_path = os.path.join(output_dir, ico_filename)

            # 定义需要的尺寸（重要：包含 16x16 和 32x32）
            sizes = [
                (16, 16),    # 窗口标题栏
                (32, 32),    # 任务栏
                (48, 48),    # 文件管理器
                (64, 64),    # 高分辨率显示
                (128, 128),  # 更大尺寸
                (256, 256),  # 大图标
            ]

            # 如果源图片小于最大尺寸，调整尺寸列表
            max_size = max(img.size)
            sizes = [(w, h) for w, h in sizes if w <= max_size and h <= max_size]

            if not sizes:
                # 源图片太小，至少包含原始尺寸
                sizes = [img.size]
                warnings.append(f"源图片尺寸较小 ({img.size[0]}x{img.size[1]})，建议使用至少 256x256 的图片")

            self.log(f"生成多尺寸 ICO 文件，包含尺寸: {', '.join([f'{w}x{h}' for w, h in sizes])}")

            # 保存为 ICO 文件
            img.save(ico_path, format='ICO', sizes=sizes)

            self.log(f"✓ 成功生成 ICO 文件: {ico_path}")

            # 验证生成的 ICO 文件
            try:
                test_img = Image.open(ico_path)
                if hasattr(test_img, 'sizes'):
                    actual_sizes = test_img.sizes
                    self.log(f"✓ ICO 文件包含 {len(actual_sizes)} 个尺寸")

                    # 检查关键尺寸
                    if (16, 16) in actual_sizes and (32, 32) in actual_sizes:
                        self.log("✓ 包含窗口标题栏和任务栏所需的小尺寸图标")
                    else:
                        warnings.append("警告: 生成的 ICO 文件可能缺少某些关键尺寸")
                test_img.close()
            except Exception as e:
                warnings.append(f"验证生成的 ICO 文件时出错: {str(e)}")

            return ico_path, warnings

        except Exception as e:
            error_msg = f"转换图标失败: {str(e)}"
            self.log(f"✗ {error_msg}")
            warnings.append(error_msg)
            return source_path, warnings

    def _get_venv_python(self, venv_path: str) -> str:
        """获取虚拟环境中的Python路径"""
        if sys.platform == "win32":
            return os.path.join(venv_path, "Scripts", "python.exe")
        else:
            return os.path.join(venv_path, "bin", "python")

    def _install_dependencies(
        self,
        python_path: str,
        script_path: str,
        project_dir: Optional[str],
        venv_path: Optional[str],
    ):
        """安装依赖"""
        self.log("\n安装项目依赖...")

        # 获取依赖（已经在前面分析过了）
        dependencies = self.dependency_analyzer.dependencies

        if not dependencies:
            self.log("未发现需要安装的依赖包")
            return

        # Python内置模块和特殊模块映射（不需要或需要特殊处理的模块）
        builtin_modules = {
            'Tkinter', 'tkinter', 'tkFileDialog', 'tkMessageBox', 'tkSimpleDialog',
            'ScrolledText', 'tkFont', 'tkColorChooser', 'tkCommonDialog',
            '_tkinter', 'turtle', 'turtledemo'
        }

        # 导入名到PyPI包名的映射
        import_to_package_map = {
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
        }

        # 过滤掉本地模块（不是真正的第三方包）
        # 常见的本地模块名（项目内部模块）
        local_module_names = {
            'ui', 'core', 'config', 'utils', 'lib', 'src', 'gui',
            'packager', 'dependency_analyzer', 'python_finder',
            'dependency_manager', 'main_window', 'main', 'app',
            'models', 'views', 'controllers', 'services', 'helpers',
            'tests', 'test', 'scripts', 'tools', 'common', 'shared',
        }

        def is_likely_internal_module(name: str) -> bool:
            """
            检测模块名是否可能是项目内部模块（而非 PyPI 包）

            判断依据：
            1. 使用 PascalCase/CamelCase 命名（如 AsyncgenCodes, AttributeNodes）
               - PyPI 包通常使用小写加下划线或连字符
            2. 以常见的内部模块后缀结尾（如 Nodes, Codes, Helpers, Generated 等）
            3. 名称过长且无分隔符（真正的 PyPI 包很少这样命名）
            4. 包含多个驼峰单词模式
            """
            if not name:
                return False

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

        # 获取依赖分析器已收集的项目内部模块
        analyzer_internal_modules = getattr(self.dependency_analyzer, '_project_internal_modules', set())

        # 检查项目目录中的本地模块
        local_modules = set(analyzer_internal_modules)  # 使用分析器已收集的
        if project_dir:
            skip_dirs = {'.venv', 'venv', 'build', 'dist', '__pycache__', '.git',
                         'node_modules', 'site-packages', '.tox', '.pytest_cache'}
            for item in os.listdir(project_dir):
                if item.startswith('.') or item in skip_dirs:
                    continue
                item_path = os.path.join(project_dir, item)
                if os.path.isdir(item_path):
                    # 检查是否为Python包（包含__init__.py）
                    if os.path.exists(os.path.join(item_path, "__init__.py")):
                        local_modules.add(item)
                    # 检查目录内是否有.py文件
                    elif any(f.endswith('.py') for f in os.listdir(item_path) if os.path.isfile(os.path.join(item_path, f))):
                        local_modules.add(item)
                    # 或者是常见的项目目录名
                    elif item in local_module_names:
                        local_modules.add(item)
                elif item.endswith('.py') and item != '__init__.py':
                    # 单个Python文件也是模块
                    module_name = item[:-3]
                    local_modules.add(module_name)

        # 过滤依赖
        filtered_dependencies = set()
        for dep in dependencies:
            # 跳过标准库
            if self.dependency_analyzer._is_stdlib(dep):
                continue

            # 跳过Python内置模块
            if dep in builtin_modules:
                self.log(f"跳过内置模块: {dep} (无需安装)")
                continue

            # 跳过已知的本地模块名
            if dep in local_module_names:
                self.log(f"跳过本地模块: {dep}")
                continue

            # 跳过项目目录中的模块
            if dep in local_modules:
                self.log(f"跳过项目内部模块: {dep}")
                continue

            # 如果知道项目目录，检查模块是否在项目目录中
            if project_dir:
                # 检查是否是项目内部模块（通过检查目录或文件是否存在）
                possible_paths = [
                    os.path.join(project_dir, dep),
                    os.path.join(project_dir, dep + '.py'),
                    os.path.join(project_dir, dep, '__init__.py'),
                ]
                if any(os.path.exists(p) for p in possible_paths):
                    self.log(f"跳过项目内部模块: {dep}")
                    continue

            # 检查是否是可能的内部模块（基于命名模式）
            if is_likely_internal_module(dep):
                self.log(f"跳过疑似内部模块: {dep} (命名模式不符合PyPI规范)")
                continue

            # 检查依赖分析器是否已标记为内部模块
            if self.dependency_analyzer._is_internal_module(dep) if hasattr(self.dependency_analyzer, '_is_internal_module') else False:
                self.log(f"跳过内部模块: {dep}")
                continue

            filtered_dependencies.add(dep)

        if not filtered_dependencies:
            self.log("未发现需要安装的第三方依赖包")
            return

        self.log(f"需要安装 {len(filtered_dependencies)} 个第三方依赖包")
        self.log("")

        # 安装依赖
        self.log("\n开始安装依赖...")

        # 检查是否取消
        if self.cancel_flag and self.cancel_flag():
            self.log("安装依赖已取消")
            return

        # 先升级pip
        self.log("升级pip...")
        self._pip_install_with_mirrors(python_path, ["pip"], upgrade=True)

        # 收集需要安装的包（合并相同的包）
        packages_to_install = {}  # {package_name: [import_names]}
        for dep in sorted(filtered_dependencies):
            # 使用映射表获取真实的包名
            install_name = import_to_package_map.get(dep, dep)
            if install_name not in packages_to_install:
                packages_to_install[install_name] = []
            packages_to_install[install_name].append(dep)

        # 逐个安装依赖（使用多镜像源支持）
        for install_name, import_names in packages_to_install.items():
            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                self.log("安装依赖已取消")
                return

            import_display = ', '.join(import_names)
            self.log(f"安装 {import_display}...")
            try:
                # 特殊处理：PyQt5 需要同时安装 PyQt5-Qt5 以获取完整的插件
                packages = [install_name]
                if install_name == 'PyQt5':
                    packages.append('PyQt5-Qt5')
                    self.log(f"  注意: 同时安装 PyQt5-Qt5 以获取完整的Qt插件支持")

                for pkg in packages:
                    success = self._pip_install_with_mirrors(python_path, [pkg])

                    if not success:
                        self.log(f"警告: 安装 {pkg} 失败（已尝试所有镜像源）")
                    else:
                        if pkg != install_name:
                            self.log(f"  ✓ {pkg} 安装成功")

                # 显示总体结果
                if install_name != import_display:
                    self.log(f"✓ {import_display} (安装为 {install_name}) 安装成功")
                else:
                    self.log(f"✓ {import_display} 安装成功")
            except Exception as e:
                self.log(f"警告: 安装 {import_display} 时出错: {e}")

        self.log("依赖安装完成")

    def _pip_install_with_mirrors(
        self,
        python_path: str,
        packages: List[str],
        upgrade: bool = False,
        timeout: int = 60
    ) -> bool:
        """
        使用多镜像源安装 pip 包，自动切换镜像源以应对网络问题

        Args:
            python_path: Python 解释器路径
            packages: 要安装的包列表
            upgrade: 是否使用 --upgrade 参数
            timeout: 每个镜像源的超时时间（秒）

        Returns:
            安装是否成功
        """
        import time

        # 获取当前网络环境对应的镜像源列表
        pip_mirrors = self._get_pip_mirrors()

        # 每次安装新包时，从第一个镜像源开始尝试（重置索引）
        self._current_mirror_index = 0
        tried_mirrors = 0
        total_mirrors = len(pip_mirrors)

        while tried_mirrors < total_mirrors:
            # 检查是否取消
            if self.cancel_flag and self.cancel_flag():
                return False

            mirror_name, mirror_url = pip_mirrors[self._current_mirror_index]

            # 构建 pip install 命令
            cmd = [python_path, "-m", "pip", "install"]
            if upgrade:
                cmd.append("--upgrade")

            # 添加镜像源参数
            if mirror_url:
                cmd.extend(["-i", mirror_url, "--trusted-host", mirror_url.split("//")[1].split("/")[0]])

            cmd.extend(packages)

            process = None
            try:
                # 使用 Popen 以便能够在取消时终止进程
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_NO_WINDOW,
                )

                # 等待进程完成，同时检查取消标志
                start_time = time.time()
                while process.poll() is None:
                    # 检查是否取消
                    if self.cancel_flag and self.cancel_flag():
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        return False

                    # 检查超时
                    if time.time() - start_time > timeout:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        raise subprocess.TimeoutExpired(cmd, timeout)

                    time.sleep(0.1)  # 短暂休眠避免CPU占用过高

                # 获取输出
                stdout, stderr = process.communicate()

                if process.returncode == 0:
                    # 安装成功，记住当前有效的镜像源
                    if mirror_url and tried_mirrors > 0:
                        self.log(f"  (使用镜像源: {mirror_name})")
                    return True
                else:
                    # 安装失败，检查错误类型
                    stderr_lower = stderr.lower() if stderr else ""

                    # 包不存在的错误 - 不需要切换镜像源，直接返回失败
                    is_package_not_found = any(keyword in stderr_lower for keyword in [
                        "no matching distribution found for",
                        "could not find a version that satisfies",
                        "no such package",
                        "package not found",
                    ])

                    if is_package_not_found:
                        # 包不存在，不是网络问题，直接返回失败（不显示错误，调用者会处理）
                        return False

                    # 网络相关错误 - 可以尝试切换镜像源
                    is_network_error = any(keyword in stderr_lower for keyword in [
                        "connection", "timeout", "network", "ssl", "certificate",
                        "retrying", "failed to establish", "connection reset",
                        "connection refused", "connection timed out",
                        "temporary failure in name resolution",
                    ])

                    if is_network_error and tried_mirrors < total_mirrors - 1:
                        # 网络问题，切换到下一个镜像源
                        self._current_mirror_index = (self._current_mirror_index + 1) % total_mirrors
                        next_mirror_name = pip_mirrors[self._current_mirror_index][0]
                        self.log(f"  镜像源 {mirror_name} 连接失败，切换到 {next_mirror_name}...")
                        tried_mirrors += 1
                        continue
                    else:
                        # 非网络问题或已尝试所有镜像源
                        if stderr:
                            # 只显示简短的错误信息
                            error_lines = stderr.strip().split('\n')
                            if error_lines:
                                self.log(f"  错误: {error_lines[-1][:100]}")
                        return False

            except subprocess.TimeoutExpired:
                # 超时，切换到下一个镜像源
                self.log(f"  镜像源 {mirror_name} 连接超时...")
                self._current_mirror_index = (self._current_mirror_index + 1) % total_mirrors
                tried_mirrors += 1
                continue

            except Exception as e:
                self.log(f"  安装时发生异常: {str(e)[:50]}")
                self._current_mirror_index = (self._current_mirror_index + 1) % total_mirrors
                tried_mirrors += 1
                continue

            finally:
                # 确保进程被清理
                if process and process.poll() is None:
                    try:
                        process.terminate()
                        process.wait(timeout=2)
                    except Exception:
                        try:
                            process.kill()
                        except Exception:
                            pass

        # 所有镜像源都失败
        self.log(f"  警告: 所有镜像源均安装失败")
        return False

    def _ensure_critical_dependencies(self, python_path: str):
        """确保关键依赖已安装（用于已有虚拟环境的情况）"""
        self.log("检查关键依赖包...")

        # 检查必要的依赖
        critical_packages = []

        # 获取项目目录（从依赖分析器的分析结果推断）
        # 如果之前分析过项目，project_dir应该已经设置
        project_dir = getattr(self, '_current_project_dir', None)

        # 常见的本地模块名（项目内部模块）
        local_module_names = {
            'ui', 'core', 'config', 'utils', 'lib', 'src', 'gui',
            'packager', 'dependency_analyzer', 'python_finder',
            'dependency_manager', 'main_window', 'main'
        }

        # 检查依赖分析中发现的包
        if self.dependency_analyzer.dependencies:
            for dep in self.dependency_analyzer.dependencies:
                # 跳过标准库
                if self.dependency_analyzer._is_stdlib(dep):
                    continue

                # 跳过已知的本地模块名
                if dep in local_module_names:
                    continue

                # 如果知道项目目录，检查模块是否在项目目录中
                if project_dir:
                    # 检查是否是项目内部模块（通过检查目录或文件是否存在）
                    possible_paths = [
                        os.path.join(project_dir, dep),
                        os.path.join(project_dir, dep + '.py'),
                        os.path.join(project_dir, dep, '__init__.py'),
                    ]
                    if any(os.path.exists(p) for p in possible_paths):
                        self.log(f"跳过项目内部模块: {dep}")
                        continue

                # 检查模块名是否包含下划线（通常本地模块会有下划线，但PyPI包也可能有）
                # 这里只作为辅助判断

                critical_packages.append(dep)

        if critical_packages:
            self.log(f"检查 {len(critical_packages)} 个依赖包...")
            for package in critical_packages:
                # 特殊处理：某些包的PyPI名称与导入名称不同
                if package == 'chardet':
                    package = 'charset-normalizer'
                elif package == 'PIL':
                    # PIL是Pillow的导入名，PyPI包名是Pillow
                    package = 'Pillow'

                self.dependency_manager.ensure_package_installed(python_path, package)
        else:
            self.log("没有需要检查的外部依赖包")

    def _install_packaging_tool(self, python_path: str, tool: str, config: Dict):
        """安装打包工具"""
        self.log(f"\n检查打包工具 {tool}...")

        # 先检查工具是否已安装
        result = subprocess.run(
            [python_path, "-m", "pip", "show", tool],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
        )

        if result.returncode == 0:
            self.log(f"✓ {tool} 已安装")
            # 验证能否导入
            self.log(f"验证 {tool} 可用性...")
            verify_result = subprocess.run(
                [python_path, "-c", f"import {tool}; print({tool}.__version__)"],
                capture_output=True,
                text=True,
                creationflags=CREATE_NO_WINDOW,
            )
            if verify_result.returncode == 0:
                version = verify_result.stdout.strip()
                self.log(f"✓ {tool} 版本: {version}")
            else:
                self.log(f"⚠️ 警告: {tool} 已安装但无法导入")
                self.log(f"错误信息: {verify_result.stderr}")
        else:
            # 未安装，使用多镜像源安装
            self.log(f"安装 {tool}...")
            success = self._pip_install_with_mirrors(python_path, [tool])
            if success:
                self.log(f"✓ {tool} 安装成功")
                # 再次验证
                verify_result = subprocess.run(
                    [python_path, "-c", f"import {tool}; print({tool}.__version__)"],
                    capture_output=True,
                    text=True,
                    creationflags=CREATE_NO_WINDOW,
                )
                if verify_result.returncode == 0:
                    version = verify_result.stdout.strip()
                    self.log(f"✓ {tool} 验证成功，版本: {version}")
                else:
                    self.log(f"⚠️ 警告: {tool} 安装后无法导入")
            else:
                self.log(f"警告: {tool} 安装失败，尝试使用依赖管理器...")
                try:
                    self.dependency_manager.ensure_package_installed(python_path, tool)
                except Exception as e:
                    self.log(f"依赖管理器安装也失败: {str(e)}")

        # 如果选择了UPX压缩，自动安装UPX
        if config.get("upx"):
            self.log("\n检查UPX...")
            self.dependency_manager.ensure_upx_installed()

    def _package_with_pyinstaller(
        self, python_path: str, config: Dict, output_dir: str
    ) -> Tuple[bool, str]:
        """使用PyInstaller打包"""
        self.log("\n" + "=" * 50)
        self.log("使用PyInstaller打包（已优化）...")
        self.log("=" * 50)

        # 显示详细的 Python 环境信息
        self.log("\n=== Python 环境信息 ===")
        self.log(f"Python 路径: {python_path}")

        # 检查 Python 是否存在
        if not os.path.exists(python_path):
            error_msg = f"错误：Python 路径不存在: {python_path}\n"
            self.log(error_msg)
            return False, error_msg

        # 显示 Python 版本
        py_version_result = subprocess.run(
            [python_path, "--version"],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        if py_version_result.returncode == 0:
            py_version = py_version_result.stdout.strip() or py_version_result.stderr.strip()
            self.log(f"Python 版本: {py_version}")

        # 显示 pip 列表（仅显示关键包）
        self.log("检查已安装的关键包...")
        pip_list_result = subprocess.run(
            [python_path, "-m", "pip", "list"],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        if pip_list_result.returncode == 0:
            pip_output = pip_list_result.stdout
            for line in pip_output.split('\n'):
                line_lower = line.lower()
                if 'pyinstaller' in line_lower or 'setuptools' in line_lower or 'pip' in line_lower:
                    self.log(f"  {line.strip()}")
        self.log("=" * 50 + "\n")

        # 最终验证 PyInstaller 是否可用
        self.log("最终验证 PyInstaller...")
        verify_cmd = [python_path, "-m", "PyInstaller", "--version"]
        verify_result = subprocess.run(
            verify_cmd,
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
        )

        if verify_result.returncode != 0:
            error_msg = f"PyInstaller 不可用！\n"
            error_msg += f"Python路径: {python_path}\n"
            error_msg += f"错误信息: {verify_result.stderr}\n"
            error_msg += f"\n可能的原因：\n"
            error_msg += f"1. PyInstaller 未正确安装到虚拟环境\n"
            error_msg += f"2. 虚拟环境损坏\n"
            error_msg += f"3. Python环境有问题\n"
            error_msg += f"\n建议：\n"
            error_msg += f"- 删除项目目录下的 .venv 或 venv 文件夹\n"
            error_msg += f"- 重新运行打包，让工具创建新的虚拟环境\n"
            self.log(error_msg)
            return False, error_msg
        else:
            pyinstaller_version = verify_result.stdout.strip()
            self.log(f"✓ PyInstaller 可用，版本: {pyinstaller_version}")

        script_path = config["script_path"]
        project_dir = config.get("project_dir")

        # 确定输出文件名：优先级：用户指定 > 项目名 > 脚本名
        if config.get("program_name"):
            script_name = config["program_name"]
            self.log(f"使用用户指定的程序名称: {script_name}")
        elif project_dir and os.path.basename(project_dir):
            script_name = os.path.basename(project_dir)
            self.log(f"使用项目名称: {script_name}")
        else:
            script_name = Path(script_path).stem
            self.log(f"使用脚本名称: {script_name}")

        # 检测项目使用的 GUI 框架
        # 使用依赖分析器已检测的主要 Qt 框架（避免多 Qt 绑定冲突）
        qt_framework = self.dependency_analyzer.primary_qt_framework
        if qt_framework:
            self.log(f"使用主要 Qt 框架: {qt_framework}")

        uses_wx = False
        uses_tkinter = False
        uses_kivy = False
        uses_flet = False
        uses_customtkinter = False
        uses_eel = False
        uses_dearpygui = False
        uses_toga = False
        uses_textual = False
        uses_pysimplegui = False
        uses_pygame = False
        uses_matplotlib = False
        uses_numpy = False
        uses_scipy = False
        uses_pandas = False
        uses_opencv = False
        uses_pillow = False
        uses_sqlalchemy = False
        uses_cryptography = False
        uses_requests = False
        uses_certifi = False

        # 使用 AST 精确检测项目中实际导入的模块
        actual_imports = self._detect_actual_imports(script_path, project_dir)
        self.log(f"AST 检测到的实际导入模块: {len(actual_imports)} 个")

        # 验证包是否实际安装的辅助函数
        def is_package_installed(package_name: str) -> bool:
            try:
                result = subprocess.run(
                    [python_path, "-c", f"import {package_name}"],
                    capture_output=True,
                    timeout=5,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                return result.returncode == 0
            except:
                return False

        # 检测模块是真正的包（目录）还是单文件模块
        def is_real_package(module_name: str) -> bool:
            """
            检测一个模块是否是真正的包（有 __path__ 属性）。
            单文件模块（如 img2pdf.py）不是包，不能使用 --collect-all。
            """
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
                return output == "package"
            except:
                # 默认假设是包，保守处理
                return True

        # 检测 wxPython（需要实际导入 wx 且包已安装）
        if 'wx' in actual_imports and is_package_installed('wx'):
            uses_wx = True
            self.log(f"检测到 wxPython 框架（已验证安装）")

        # 检测 Tkinter（标准库，不需要验证安装）
        tkinter_imports = {'tkinter', 'Tkinter', 'ttk', 'tkinter.ttk',
                          'tkinter.filedialog', 'tkinter.messagebox',
                          'tkinter.simpledialog', 'tkinter.colorchooser'}
        if any(imp in actual_imports or imp.startswith('tkinter.') for imp in actual_imports) or \
           actual_imports & tkinter_imports:
            uses_tkinter = True
            self.log(f"检测到 Tkinter 框架")

        # 检测 pygame
        if 'pygame' in actual_imports and is_package_installed('pygame'):
            uses_pygame = True
            self.log(f"检测到 Pygame 框架（已验证安装）")

        # 检测 matplotlib
        if 'matplotlib' in actual_imports and is_package_installed('matplotlib'):
            uses_matplotlib = True
            self.log(f"检测到 Matplotlib 库（已验证安装）")

        # 检测 numpy
        if 'numpy' in actual_imports and is_package_installed('numpy'):
            uses_numpy = True
            self.log(f"检测到 NumPy 库（已验证安装）")

        # 检测 scipy
        if 'scipy' in actual_imports and is_package_installed('scipy'):
            uses_scipy = True
            self.log(f"检测到 SciPy 库（已验证安装）")

        # 检测 pandas
        if 'pandas' in actual_imports and is_package_installed('pandas'):
            uses_pandas = True
            self.log(f"检测到 Pandas 库（已验证安装）")

        # 检测 opencv
        if 'cv2' in actual_imports and is_package_installed('cv2'):
            uses_opencv = True
            self.log(f"检测到 OpenCV 库（已验证安装）")

        # 检测 PIL/Pillow
        if ('PIL' in actual_imports or 'pillow' in actual_imports) and is_package_installed('PIL'):
            uses_pillow = True
            self.log(f"检测到 Pillow 库（已验证安装）")

        # 检测 sqlalchemy
        if 'sqlalchemy' in actual_imports and is_package_installed('sqlalchemy'):
            uses_sqlalchemy = True
            self.log(f"检测到 SQLAlchemy 库（已验证安装）")

        # 检测 cryptography
        if 'cryptography' in actual_imports and is_package_installed('cryptography'):
            uses_cryptography = True
            self.log(f"检测到 Cryptography 库（已验证安装）")

        # 检测 requests
        if 'requests' in actual_imports and is_package_installed('requests'):
            uses_requests = True
            self.log(f"检测到 Requests 库（已验证安装）")

        # 检测 certifi（SSL证书库，需要包含数据文件）
        if 'certifi' in actual_imports and is_package_installed('certifi'):
            uses_certifi = True
            self.log(f"检测到 Certifi 库（已验证安装）")

        # 检测其他 GUI 框架（需要实际导入且包已安装）
        if 'kivy' in actual_imports and is_package_installed('kivy'):
            uses_kivy = True
            self.log(f"检测到 Kivy 框架（已验证安装）")
        if 'flet' in actual_imports and is_package_installed('flet'):
            uses_flet = True
            self.log(f"检测到 Flet 框架（已验证安装）")
        if 'customtkinter' in actual_imports and is_package_installed('customtkinter'):
            uses_customtkinter = True
            self.log(f"检测到 CustomTkinter 框架（已验证安装）")
        if 'eel' in actual_imports and is_package_installed('eel'):
            uses_eel = True
            self.log(f"检测到 Eel 框架（已验证安装）")
        if 'dearpygui' in actual_imports and is_package_installed('dearpygui'):
            uses_dearpygui = True
            self.log(f"检测到 DearPyGui 框架（已验证安装）")
        if 'toga' in actual_imports and is_package_installed('toga'):
            uses_toga = True
            self.log(f"检测到 Toga 框架（已验证安装）")
        if 'textual' in actual_imports and is_package_installed('textual'):
            uses_textual = True
            self.log(f"检测到 Textual 框架（已验证安装）")
        if 'PySimpleGUI' in actual_imports and is_package_installed('PySimpleGUI'):
            uses_pysimplegui = True
            self.log(f"检测到 PySimpleGUI 框架（已验证安装）")

        # 检测中文字符，使用临时英文名避免编码问题
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in script_name)
        temp_name = None
        if has_chinese:
            import uuid
            temp_name = f"temp_{uuid.uuid4().hex[:8]}"
            self.log(f"检测到中文名称，使用临时名称打包: {temp_name}")
            build_name = temp_name
        else:
            build_name = script_name

        # 获取优化建议
        exclude_modules, hidden_imports, _ = (
            self.dependency_analyzer.get_optimization_suggestions(python_path)
        )

        # 确保排除打包工具本身及其子模块（防止PyInstaller编译失败）
        packaging_tools = {'pyinstaller', 'nuitka', 'PyInstaller'}
        exclude_modules = list(set(exclude_modules) | packaging_tools)

        # 获取需要排除的冲突 Qt 绑定（避免 PyInstaller 多 Qt 绑定错误）
        qt_exclusions = self.dependency_analyzer.get_qt_exclusion_list()
        if qt_exclusions:
            self.log(f"\n排除冲突的 Qt 绑定: {', '.join(qt_exclusions)}")
            exclude_modules = list(set(exclude_modules) | set(qt_exclusions))

        # 合并用户自定义的排除模块
        user_exclude_modules = config.get("exclude_modules", [])
        if user_exclude_modules:
            self.log(f"\n用户手动指定排除模块: {', '.join(user_exclude_modules)}")
            self.log(f"自动分析建议排除模块: {', '.join(sorted(exclude_modules))}")
            exclude_modules = list(set(exclude_modules) | set(user_exclude_modules))
            self.log(f"最终排除模块（合并去重后）: {', '.join(sorted(exclude_modules))}")
        else:
            self.log(f"\n使用自动分析的排除模块（共 {len(exclude_modules)} 个）")

        # 构建PyInstaller命令
        self.log("\n=== 开始构建 PyInstaller 命令 ===")
        cmd = [python_path, "-m", "PyInstaller"]

        # 单文件模式
        if config.get("onefile", True):
            cmd.append("--onefile")

        # 控制台窗口
        if not config.get("console", False):
            cmd.append("--noconsole")

        # 清理构建缓存
        if config.get("clean", True):
            cmd.append("--clean")

        # 图标 - 转换为绝对路径
        icon_path = config.get("icon_path")
        processed_icon_path = None
        if icon_path:
            # 如果是相对路径，转换为绝对路径
            if not os.path.isabs(icon_path):
                # 相对于项目目录或脚本目录
                if project_dir:
                    icon_path = os.path.join(project_dir, icon_path)
                else:
                    icon_path = os.path.join(os.path.dirname(script_path), icon_path)

            # 检查图标文件是否存在
            if os.path.exists(icon_path):
                self.log(f"\n" + "=" * 50)
                self.log("处理图标文件...")
                self.log("=" * 50)
                self.log(f"原始图标: {icon_path}")

                # 处理图标文件（自动转换格式和尺寸）
                processed_icon_path, warnings = self._process_icon_file(icon_path, output_dir)

                if warnings:
                    for warning in warnings:
                        self.log(f"⚠️ {warning}")

                # 使用处理后的图标
                self.log(f"最终使用图标: {processed_icon_path}")
                # PyInstaller使用--icon参数，会自动嵌入到exe资源中
                # 这是关键：确保图标正确嵌入到exe的资源段
                cmd.extend(["--icon", processed_icon_path])

                # 获取图标的基本文件名
                icon_basename = os.path.basename(processed_icon_path)

                # 将图标以标准名称添加为数据文件到根目录（运行时可访问）
                # 使用固定的标准名称，方便运行时钩子查找
                cmd.extend(["--add-data", f"{processed_icon_path}{os.pathsep}."])
                self.log(f"已添加图标数据文件到根目录: {icon_basename}")

                # 关键修复：同时将原始图标文件添加为数据文件，以便运行时加载
                # 许多GUI程序在运行时需要读取图标文件来设置窗口图标
                # 格式: 源路径;目标路径 (Windows用分号)

                # 尝试保持图标的相对目录结构
                base_dir = project_dir if project_dir else os.path.dirname(script_path)
                # 方法2：如果原始图标和处理后的图标不同，也添加原始图标
                # 这样应用程序可以在运行时使用相对路径访问图标
                if os.path.abspath(icon_path) != os.path.abspath(processed_icon_path):
                    try:
                        rel_path = os.path.relpath(icon_path, base_dir)
                        # 如果图标在项目目录下（不以..开头且不是绝对路径）
                        if not rel_path.startswith("..") and not os.path.isabs(rel_path):
                            target_dir = os.path.dirname(rel_path)
                            if not target_dir:
                                target_dir = "."
                            cmd.extend(["--add-data", f"{icon_path}{os.pathsep}{target_dir}"])
                            self.log(f"已添加原始图标: {rel_path} -> {target_dir} (保持目录结构)")
                        else:
                            # 图标在项目外，直接放在根目录
                            cmd.extend(["--add-data", f"{icon_path}{os.pathsep}."])
                            self.log(f"已添加原始图标: {os.path.basename(icon_path)} -> 根目录")
                    except Exception as e:
                        # 发生任何路径计算错误，回退到根目录
                        cmd.extend(["--add-data", f"{icon_path}{os.pathsep}."])
                        self.log(f"已添加原始图标到根目录 (回退方案): {os.path.basename(icon_path)}")
            else:
                self.log(f"警告: 图标文件不存在: {icon_path}")

        # UPX
        if config.get("upx"):
            cmd.append("--upx-dir=upx")

        # 添加排除模块（优化）
        if exclude_modules:
            self.log(f"\n应用优化: 排除 {len(exclude_modules)} 个不必要的模块")
            for module in exclude_modules:
                cmd.extend(["--exclude-module", module])

        # 添加隐藏导入
        if hidden_imports:
            # 过滤掉打包工具本身（pyinstaller 和 nuitka）及其所有子模块
            def should_include_module(module_name):
                # 精确匹配打包工具名
                if module_name in {'pyinstaller', 'nuitka', 'PyInstaller'}:
                    return False
                # 排除打包工具的所有子模块
                if module_name.startswith(('pyinstaller.', 'nuitka.', 'PyInstaller.')):
                    return False
                return True

            filtered_imports = [m for m in hidden_imports if should_include_module(m)]
            self.log(f"应用优化: 添加 {len(filtered_imports)} 个隐藏导入")
            for module in filtered_imports:
                cmd.extend(["--hidden-import", module])

        # 重要：添加原始脚本分析到的所有依赖作为隐藏导入
        # 这确保了即使使用 runtime-hook，所有依赖也能被正确包含
        if self.dependency_analyzer.dependencies:
            self.log(f"\n添加原始脚本依赖作为隐藏导入...")
            added_deps = []
            # 需要跳过的本地模块、打包工具和冲突的 Qt 绑定
            skip_modules = {'config', 'core', 'ui', 'nuitka', 'pyinstaller', 'PyInstaller'}
            # 添加冲突的 Qt 绑定到跳过列表
            skip_modules.update(set(qt_exclusions))
            # PyPI包名到Python导入名的映射（处理名称不一致的情况）
            package_to_import = {
                'wxPython': 'wx',
                'Pillow': 'PIL',
                'scikit-learn': 'sklearn',
                'python-dateutil': 'dateutil',
                'beautifulsoup4': 'bs4',
                'pyyaml': 'yaml',
                'opencv-python': 'cv2',
                'opencv-python-headless': 'cv2',
            }
            for dep in self.dependency_analyzer.dependencies:
                # 跳过标准库
                if self.dependency_analyzer._is_stdlib(dep):
                    continue
                # 跳过本地模块和打包工具自身
                if dep in skip_modules:
                    continue
                # 跳过已经在 hidden_imports 中的
                if dep in hidden_imports:
                    continue
                # 使用映射表或将包名中的连字符转换为下划线
                if dep in package_to_import:
                    module_name = package_to_import[dep]
                else:
                    module_name = dep.replace('-', '_')
                # 跳过重复的（转换后可能与已添加的相同）
                if module_name in hidden_imports or module_name in added_deps:
                    continue
                cmd.extend(["--hidden-import", module_name])
                added_deps.append(module_name)
            if added_deps:
                self.log(f"  已添加 {len(added_deps)} 个依赖: {', '.join(sorted(added_deps)[:10])}{'...' if len(added_deps) > 10 else ''}")

        # ========== 增强Analysis阶段：对未配置的库使用完整收集 ==========
        # 增强Analysis阶段：对未配置的库使用完整收集
        unconfigured_libs = self.dependency_analyzer._unconfigured_libraries
        if unconfigured_libs:
            # 过滤掉打包工具本身（排除 pyinstaller 和 nuitka）
            def should_collect_lib(lib_name):
                lib_lower = lib_name.lower()
                if lib_lower in {'pyinstaller', 'nuitka'}:
                    return False
                return True

            filtered_libs = [lib for lib in unconfigured_libs if should_collect_lib(lib)]
            if filtered_libs:
                self.log(f"\n增强Analysis阶段: 对 {len(filtered_libs)} 个未配置的库使用完整收集")
            else:
                self.log(f"\n增强Analysis阶段: 未发现需要收集的库（已过滤打包工具）")
        if unconfigured_libs:
            filtered_libs = [lib for lib in unconfigured_libs if lib.lower() not in {'pyinstaller', 'nuitka'}]
            for lib in sorted(filtered_libs):
                # 先检测是否是真正的包（目录）还是单文件模块
                if is_real_package(lib):
                    # 真正的包：使用 --collect-all 收集所有数据和子模块
                    # 注意：这可能会增加包体积，但能确保所有依赖都被包含
                    self.log(f"  收集 {lib} 的所有资源（包）...")
                    cmd.extend(["--collect-all", lib])
                else:
                    # 单文件模块：使用 --hidden-import
                    self.log(f"  收集 {lib}（单文件模块）...")
                    cmd.extend(["--hidden-import", lib])
            self.log(f"  ✓ 已为未配置的库启用完整收集模式")

        # 添加自动收集到的子模块
        auto_collected = self.dependency_analyzer._auto_collected_modules
        if auto_collected:
            self.log(f"\n添加自动收集的子模块...")
            added_count = 0
            for lib, submodules in auto_collected.items():
                # 跳过打包工具本身（所有变体）
                lib_lower = lib.lower()
                if lib_lower in {'pyinstaller', 'nuitka'}:
                    continue
                for submodule in submodules:
                    # 跳过打包工具的所有子模块（所有变体）
                    if (submodule.startswith(('pyinstaller.', 'nuitka.', 'PyInstaller.')) or
                        submodule.lower().startswith(('pyinstaller.', 'nuitka.'))):
                        continue
                    if submodule not in hidden_imports and submodule not in added_deps:
                        cmd.extend(["--hidden-import", submodule])
                        added_count += 1
            if added_count > 0:
                self.log(f"  已添加 {added_count} 个自动收集的子模块")

        # 添加动态追踪到的导入
        dynamic_imports = self.dependency_analyzer._dynamic_imports
        if dynamic_imports:
            self.log(f"\n添加动态追踪到的导入...")
            added_dynamic = 0
            for imp in dynamic_imports:
                # 跳过已添加的
                if imp in hidden_imports or imp in added_deps:
                    continue
                # 跳过标准库
                root_module = imp.split('.')[0]
                if self.dependency_analyzer._is_stdlib(root_module):
                    continue
                # 跳过打包工具本身（所有变体）
                root_lower = root_module.lower()
                if root_lower in {'pyinstaller', 'nuitka'}:
                    continue
                # 跳过打包工具的子模块
                if imp.lower().startswith(('pyinstaller.', 'nuitka.')):
                    continue
                cmd.extend(["--hidden-import", imp])
                added_dynamic += 1
            if added_dynamic > 0:
                self.log(f"  已添加 {added_dynamic} 个动态追踪到的导入")

        # 添加 Qt 插件支持（修复暗黑模式显示问题）
        if qt_framework:
            self.log(f"\n配置 {qt_framework} 插件支持...")

            # PyInstaller需要手动收集Qt插件数据
            # 收集platforms、styles、imageformats插件
            try:
                qt_path = None
                # 获取 Qt 库的路径
                if qt_framework == "PyQt6":
                    from PyQt6 import QtCore  # type: ignore
                    qt_path = os.path.dirname(QtCore.__file__)
                elif qt_framework == "PyQt5":
                    from PyQt5 import QtCore  # type: ignore
                    qt_path = os.path.dirname(QtCore.__file__)
                elif qt_framework == "PySide6":
                    from PySide6 import QtCore  # type: ignore
                    qt_path = os.path.dirname(QtCore.__file__)
                elif qt_framework == "PySide2":
                    from PySide2 import QtCore  # type: ignore
                    qt_path = os.path.dirname(QtCore.__file__)

                # 添加 Qt 插件目录
                if qt_path:
                    # 确定插件目录路径（不同Qt版本路径不同）
                    possible_plugin_dirs = []
                    if qt_framework in ["PyQt6", "PySide6"]:
                        possible_plugin_dirs = [
                            os.path.join(qt_path, "Qt6", "plugins"),
                            os.path.join(qt_path, "Qt", "plugins"),
                        ]
                    else:  # PyQt5或PySide2
                        possible_plugin_dirs = [
                            os.path.join(qt_path, "Qt5", "plugins"),
                            os.path.join(qt_path, "Qt", "plugins"),
                        ]

                    qt_plugins_dir = None
                    for plugin_dir in possible_plugin_dirs:
                        if os.path.exists(plugin_dir):
                            qt_plugins_dir = plugin_dir
                            break

                    if qt_plugins_dir and os.path.exists(qt_plugins_dir):
                        # 收集关键插件（platforms、styles、imageformats）
                        plugins_found = []
                        for plugin_type in ["platforms", "styles", "imageformats"]:
                            plugin_path = os.path.join(qt_plugins_dir, plugin_type)
                            if os.path.exists(plugin_path):
                                cmd.extend(["--add-data", f"{plugin_path}{os.pathsep}{plugin_type}"])
                                plugins_found.append(plugin_type)

                        if plugins_found:
                            self.log(f"已添加 Qt 插件: {', '.join(plugins_found)}")
                            self.log("这将确保暗黑模式和自定义样式正确显示")
                        else:
                            self.log(f"警告: Qt 插件目录存在但未找到插件子目录: {qt_plugins_dir}")
                    else:
                        # 插件目录不存在 - 提供详细的诊断信息
                        self.log(f"警告: 未找到 Qt 插件目录")
                        self.log(f"  Qt 路径: {qt_path}")
                        self.log(f"  尝试的插件路径: {', '.join(possible_plugin_dirs)}")

                        if qt_framework == "PyQt5":
                            self.log("")
                            self.log("  ** PyQt5 插件缺失解决方案 **")
                            self.log("  PyQt5 需要同时安装 PyQt5-Qt5 包才能获得完整的插件支持")
                            self.log("  请在虚拟环境中执行以下命令：")
                            self.log(f"    {python_path} -m pip install PyQt5-Qt5")
                            self.log("")
                            self.log("  或者考虑重新安装 PyQt5：")
                            self.log(f"    {python_path} -m pip uninstall PyQt5 PyQt5-Qt5 -y")
                            self.log(f"    {python_path} -m pip install PyQt5 PyQt5-Qt5")
                            self.log("")

                            # 尝试自动修复
                            self.log("  尝试自动安装 PyQt5-Qt5...")
                            try:
                                result = subprocess.run(
                                    [python_path, "-m", "pip", "install", "PyQt5-Qt5"],
                                    capture_output=True,
                                    text=True,
                                    encoding="utf-8",
                                    creationflags=CREATE_NO_WINDOW,
                                    timeout=120
                                )
                                if result.returncode == 0:
                                    self.log("  ✓ PyQt5-Qt5 安装成功！请重新运行打包")
                                else:
                                    self.log(f"  ✗ PyQt5-Qt5 安装失败: {result.stderr}")
                            except Exception as e:
                                self.log(f"  ✗ 自动安装失败: {str(e)}")

                        self.log("")
                        self.log("  注意: 缺少 Qt 插件可能导致以下问题：")
                        self.log("  - 程序启动时提示 'could not find platform plugin'")
                        self.log("  - GUI 界面无法显示")
                        self.log("  - 如果遇到这些问题，请按上述方法修复后重新打包")

            except ImportError as e:
                self.log(f"警告: 无法导入 {qt_framework}: {str(e)}")
                if qt_framework == "PyQt5":
                    self.log("  提示: 请确保已正确安装 PyQt5 和 PyQt5-Qt5")
                    self.log(f"  安装命令: {python_path} -m pip install PyQt5 PyQt5-Qt5")
            except Exception as e:
                self.log(f"警告: 配置 Qt 插件时出错: {str(e)}")

        # ========== Kivy 支持 ==========
        if uses_kivy:
            self.log(f"\n配置 Kivy 框架支持...")
            # Kivy 需要收集数据和依赖
            cmd.extend(["--collect-all", "kivy"])
            # Kivy 依赖包
            try:
                import importlib.util
                if importlib.util.find_spec("kivy_deps"):
                    cmd.extend(["--collect-all", "kivy_deps.sdl2"])
                    cmd.extend(["--collect-all", "kivy_deps.glew"])
                    self.log("已添加 Kivy 依赖包 (sdl2, glew)")
            except:
                pass
            self.log("已配置 Kivy 框架支持")

        # ========== Flet 支持 ==========
        if uses_flet:
            self.log(f"\n配置 Flet 框架支持...")
            cmd.extend(["--collect-all", "flet"])
            cmd.extend(["--collect-all", "flet_core"])
            cmd.extend(["--hidden-import", "httpx"])
            cmd.extend(["--hidden-import", "websockets"])
            self.log("已配置 Flet 框架支持")

        # ========== CustomTkinter 支持 ==========
        if uses_customtkinter:
            self.log(f"\n配置 CustomTkinter 框架支持...")
            cmd.extend(["--collect-all", "customtkinter"])
            cmd.extend(["--hidden-import", "darkdetect"])
            self.log("已配置 CustomTkinter 框架支持（含主题文件）")

        # ========== Eel 支持 ==========
        if uses_eel:
            self.log(f"\n配置 Eel 框架支持...")
            cmd.extend(["--hidden-import", "eel"])
            cmd.extend(["--hidden-import", "bottle"])
            cmd.extend(["--hidden-import", "bottle_websocket"])
            cmd.extend(["--hidden-import", "gevent"])
            cmd.extend(["--hidden-import", "geventwebsocket"])
            # Eel 需要包含 web 目录
            web_dir = os.path.join(project_dir if project_dir else os.path.dirname(script_path), "web")
            if os.path.exists(web_dir):
                cmd.extend(["--add-data", f"{web_dir}{os.pathsep}web"])
                self.log(f"已添加 Eel web 目录: {web_dir}")
            else:
                self.log("提示: 未找到 web 目录，如果 Eel 应用需要 web 文件，请确保包含")
            self.log("已配置 Eel 框架支持")

        # ========== DearPyGui 支持 ==========
        if uses_dearpygui:
            self.log(f"\n配置 DearPyGui 框架支持...")
            cmd.extend(["--collect-all", "dearpygui"])
            self.log("已配置 DearPyGui 框架支持")

        # ========== Toga 支持 ==========
        if uses_toga:
            self.log(f"\n配置 Toga 框架支持...")
            cmd.extend(["--collect-all", "toga"])
            cmd.extend(["--collect-all", "toga_winforms"])
            cmd.extend(["--hidden-import", "clr"])
            cmd.extend(["--hidden-import", "pythonnet"])
            self.log("已配置 Toga 框架支持（Windows 后端）")

        # ========== Textual 支持 ==========
        if uses_textual:
            self.log(f"\n配置 Textual 框架支持...")
            cmd.extend(["--collect-all", "textual"])
            cmd.extend(["--collect-all", "rich"])
            self.log("已配置 Textual 框架支持")

        # ========== PySimpleGUI 支持 ==========
        if uses_pysimplegui:
            self.log(f"\n配置 PySimpleGUI 框架支持...")
            cmd.extend(["--hidden-import", "PySimpleGUI"])
            cmd.extend(["--hidden-import", "tkinter"])
            cmd.extend(["--hidden-import", "tkinter.ttk"])
            cmd.extend(["--hidden-import", "tkinter.filedialog"])
            cmd.extend(["--hidden-import", "tkinter.messagebox"])
            self.log("已配置 PySimpleGUI 框架支持")

        # ========== wxPython 支持 ==========
        if uses_wx:
            self.log(f"\n配置 wxPython 框架支持...")
            cmd.extend(["--hidden-import", "wx"])
            cmd.extend(["--hidden-import", "wx.adv"])
            cmd.extend(["--hidden-import", "wx.lib"])
            self.log("已配置 wxPython 框架支持")

        # ========== Tkinter 支持 ==========
        if uses_tkinter:
            self.log(f"\n配置 Tkinter 框架支持...")
            cmd.extend(["--hidden-import", "tkinter"])
            cmd.extend(["--hidden-import", "tkinter.ttk"])
            cmd.extend(["--hidden-import", "tkinter.filedialog"])
            cmd.extend(["--hidden-import", "tkinter.messagebox"])
            cmd.extend(["--hidden-import", "tkinter.simpledialog"])
            cmd.extend(["--hidden-import", "tkinter.colorchooser"])
            cmd.extend(["--hidden-import", "_tkinter"])
            self.log("已配置 Tkinter 框架支持")

        # ========== Pygame 支持 ==========
        if uses_pygame:
            self.log(f"\n配置 Pygame 框架支持...")
            cmd.extend(["--collect-all", "pygame"])
            self.log("已配置 Pygame 框架支持")

        # ========== Matplotlib 支持 ==========
        if uses_matplotlib:
            self.log(f"\n配置 Matplotlib 库支持...")
            cmd.extend(["--collect-all", "matplotlib"])
            cmd.extend(["--hidden-import", "matplotlib.backends.backend_tkagg"])
            cmd.extend(["--hidden-import", "matplotlib.backends.backend_agg"])
            cmd.extend(["--hidden-import", "matplotlib.figure"])
            cmd.extend(["--hidden-import", "PIL"])
            cmd.extend(["--hidden-import", "PIL.Image"])
            self.log("已配置 Matplotlib 库支持")

        # ========== NumPy 支持 ==========
        if uses_numpy:
            self.log(f"\n配置 NumPy 库支持...")
            cmd.extend(["--collect-all", "numpy"])
            cmd.extend(["--hidden-import", "numpy.core._multiarray_umath"])
            cmd.extend(["--hidden-import", "numpy.core._dtype_ctypes"])
            cmd.extend(["--hidden-import", "numpy.random.common"])
            cmd.extend(["--hidden-import", "numpy.random.bounded_integers"])
            cmd.extend(["--hidden-import", "numpy.random.entropy"])
            cmd.extend(["--hidden-import", "numpy.random.mtrand"])
            self.log("已配置 NumPy 库支持")

        # ========== SciPy 支持 ==========
        if uses_scipy:
            self.log(f"\n配置 SciPy 库支持...")
            cmd.extend(["--collect-all", "scipy"])
            cmd.extend(["--hidden-import", "scipy.integrate"])
            cmd.extend(["--hidden-import", "scipy.optimize"])
            cmd.extend(["--hidden-import", "scipy.linalg"])
            cmd.extend(["--hidden-import", "scipy.sparse"])
            cmd.extend(["--hidden-import", "scipy.special"])
            self.log("已配置 SciPy 库支持")

        # ========== Pandas 支持 ==========
        if uses_pandas:
            self.log(f"\n配置 Pandas 库支持...")
            cmd.extend(["--collect-all", "pandas"])
            cmd.extend(["--hidden-import", "pandas._libs"])
            cmd.extend(["--hidden-import", "pandas._libs.tslibs"])
            cmd.extend(["--hidden-import", "pandas._libs.tslibs.np_datetime"])
            cmd.extend(["--hidden-import", "pandas._libs.tslibs.nattype"])
            cmd.extend(["--hidden-import", "pandas._libs.tslibs.timedeltas"])
            self.log("已配置 Pandas 库支持")

        # ========== OpenCV 支持 ==========
        if uses_opencv:
            self.log(f"\n配置 OpenCV 库支持...")
            cmd.extend(["--collect-all", "cv2"])
            cmd.extend(["--hidden-import", "cv2"])
            cmd.extend(["--hidden-import", "numpy"])
            cmd.extend(["--hidden-import", "numpy.core._multiarray_umath"])
            self.log("已配置 OpenCV 库支持")

        # ========== Pillow 支持 ==========
        if uses_pillow:
            self.log(f"\n配置 Pillow 库支持...")
            cmd.extend(["--collect-all", "PIL"])
            cmd.extend(["--hidden-import", "PIL._tkinter_finder"])
            cmd.extend(["--hidden-import", "PIL._imaging"])
            self.log("已配置 Pillow 库支持")

        # ========== SQLAlchemy 支持 ==========
        if uses_sqlalchemy:
            self.log(f"\n配置 SQLAlchemy 库支持...")
            cmd.extend(["--collect-all", "sqlalchemy"])
            cmd.extend(["--hidden-import", "sqlalchemy.dialects.sqlite"])
            cmd.extend(["--hidden-import", "sqlalchemy.dialects.mysql"])
            cmd.extend(["--hidden-import", "sqlalchemy.dialects.postgresql"])
            cmd.extend(["--hidden-import", "sqlalchemy.sql.default_comparator"])
            self.log("已配置 SQLAlchemy 库支持")

        # ========== Cryptography 支持 ==========
        if uses_cryptography:
            self.log(f"\n配置 Cryptography 库支持...")
            cmd.extend(["--collect-all", "cryptography"])
            cmd.extend(["--hidden-import", "cryptography.hazmat.backends.openssl"])
            cmd.extend(["--hidden-import", "cryptography.hazmat.bindings._rust"])
            cmd.extend(["--hidden-import", "_cffi_backend"])
            self.log("已配置 Cryptography 库支持")

        # ========== Requests 支持 ==========
        if uses_requests:
            self.log(f"\n配置 Requests 库支持...")
            cmd.extend(["--collect-all", "requests"])
            cmd.extend(["--hidden-import", "urllib3"])
            cmd.extend(["--hidden-import", "charset_normalizer"])
            cmd.extend(["--hidden-import", "idna"])
            # requests 依赖 certifi，确保包含
            if not uses_certifi:
                cmd.extend(["--collect-all", "certifi"])
                self.log("  已自动包含 certifi（SSL证书）")
            self.log("已配置 Requests 库支持")

        # ========== Certifi 支持（SSL证书数据文件）==========
        if uses_certifi:
            self.log(f"\n配置 Certifi 库支持...")
            cmd.extend(["--collect-all", "certifi"])
            self.log("已配置 Certifi 库支持（包含CA证书）")

        # 输出目录
        cmd.extend(["--distpath", output_dir])

        # 工作目录
        work_dir = os.path.join(os.path.dirname(output_dir), "build_temp")
        cmd.extend(["--workpath", work_dir])

        # 创建 runtime hook 脚本（在用户脚本执行前运行）
        os.makedirs(work_dir, exist_ok=True)

        # 创建 runtime hook 用于图标修复
        runtime_hook_script = os.path.join(work_dir, "_runtime_hook_icon_fix.py")
        with open(runtime_hook_script, "w", encoding="utf-8") as f:
            runtime_hook_code = '''# PyInstaller Runtime Hook - Icon Fix
import os
import sys
import ctypes
import threading
import time

def _setup_icon():
    """设置应用程序图标"""
    if not sys.platform.startswith('win'):
        return

    if not (getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')):
        return

    # 设置 AppUserModelID（修复任务栏图标分组）
    try:
        import hashlib
        exe_path = sys.executable
        path_hash = hashlib.md5(exe_path.encode('utf-8')).hexdigest()[:8]
        app_id = f"PythonApp.{path_hash}"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    except:
        pass

    # 查找图标文件并设置环境变量
    _icon_path = None
    try:
        for filename in os.listdir(sys._MEIPASS):
            if filename.lower().endswith('.ico'):
                icon_path = os.path.join(sys._MEIPASS, filename)
                if os.path.exists(icon_path):
                    os.environ['APP_ICON_PATH'] = icon_path
                    _icon_path = icon_path
                    break
    except:
        pass

    # 启动后台线程修复窗口图标
    if _icon_path:
        def _fix_window_icons():
            """后台线程：修复窗口左上角图标"""
            try:
                from ctypes import wintypes
                user32 = ctypes.WinDLL('user32')
                shell32 = ctypes.WinDLL('shell32')
                kernel32 = ctypes.WinDLL('kernel32')

                HWND = wintypes.HWND
                LPARAM = wintypes.LPARAM
                HICON = wintypes.HICON
                UINT = wintypes.UINT
                BOOL = wintypes.BOOL
                DWORD = wintypes.DWORD

                # 选择正确的 SetClassLong 函数
                if ctypes.sizeof(ctypes.c_void_p) == 8:
                    _handle_type = ctypes.c_longlong
                    _set_class_long = user32.SetClassLongPtrW
                else:
                    _handle_type = ctypes.c_long
                    _set_class_long = user32.SetClassLongW

                _set_class_long.argtypes = [HWND, ctypes.c_int, _handle_type]
                _set_class_long.restype = _handle_type

                EnumWindowsProc = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
                user32.EnumWindows.argtypes = [EnumWindowsProc, LPARAM]
                user32.EnumWindows.restype = BOOL
                user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(DWORD)]
                user32.GetWindowThreadProcessId.restype = DWORD
                user32.SendMessageW.argtypes = [HWND, UINT, wintypes.WPARAM, LPARAM]
                user32.SendMessageW.restype = LPARAM

                shell32.ExtractIconExW.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
                                                   ctypes.POINTER(HICON), ctypes.POINTER(HICON), UINT]
                shell32.ExtractIconExW.restype = UINT
                kernel32.GetCurrentProcessId.restype = DWORD

                GCLP_HICON = -14
                GCLP_HICONSM = -34
                WM_SETICON = 0x0080
                ICON_BIG = 1
                ICON_SMALL = 0

                def _apply_icon():
                    try:
                        exe_path = sys.executable
                        large = HICON()
                        small = HICON()
                        count = shell32.ExtractIconExW(exe_path, 0, ctypes.byref(large), ctypes.byref(small), 1)
                        hicon_large = large.value if large.value else 0
                        hicon_small = small.value if small.value else hicon_large

                        if count == 0 or not (hicon_large or hicon_small):
                            return

                        pid = kernel32.GetCurrentProcessId()

                        @EnumWindowsProc
                        def _enum_callback(hwnd, lparam):
                            try:
                                window_pid = DWORD()
                                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
                                if window_pid.value == pid:
                                    if hicon_large:
                                        _set_class_long(hwnd, GCLP_HICON, _handle_type(hicon_large))
                                        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_large)
                                    if hicon_small:
                                        _set_class_long(hwnd, GCLP_HICONSM, _handle_type(hicon_small))
                                        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
                            except:
                                pass
                            return True

                        user32.EnumWindows(_enum_callback, 0)
                    except:
                        pass

                # 多次尝试，覆盖窗口创建的不同时机
                for _ in range(30):
                    _apply_icon()
                    time.sleep(0.15)

            except:
                pass

        t = threading.Thread(target=_fix_window_icons, daemon=True)
        t.start()

    # Qt框架图标补丁
    if _icon_path:
        class _QtIconPatcher:
            """拦截Qt模块导入，自动为窗口设置图标"""
            _qt_modules = ['PyQt6.QtWidgets', 'PyQt5.QtWidgets', 'PySide6.QtWidgets', 'PySide2.QtWidgets']

            def find_module(self, fullname, path=None):
                if fullname in self._qt_modules:
                    return self
                return None

            def load_module(self, fullname):
                if fullname in sys.modules:
                    module = sys.modules[fullname]
                else:
                    import importlib
                    module = importlib.import_module(fullname)

                try:
                    QWidget = getattr(module, 'QWidget', None)
                    if QWidget and not getattr(QWidget, '_icon_patched', False):
                        # 根据框架导入 QIcon
                        if 'PyQt6' in fullname:
                            from PyQt6.QtGui import QIcon
                        elif 'PyQt5' in fullname:
                            from PyQt5.QtGui import QIcon
                        elif 'PySide6' in fullname:
                            from PySide6.QtGui import QIcon
                        elif 'PySide2' in fullname:
                            from PySide2.QtGui import QIcon
                        else:
                            return module

                        _orig_init = QWidget.__init__
                        _icon = QIcon(_icon_path)

                        def _patched_init(self, *args, **kwargs):
                            _orig_init(self, *args, **kwargs)
                            try:
                                if self.isWindow() and (not self.windowIcon() or self.windowIcon().isNull()):
                                    self.setWindowIcon(_icon)
                            except:
                                pass

                        QWidget.__init__ = _patched_init
                        QWidget._icon_patched = True
                except:
                    pass

                return module

        sys.meta_path.insert(0, _QtIconPatcher())

    # 创建 qt.conf 修复 Qt 插件路径
    try:
        qt_conf = os.path.join(sys._MEIPASS, 'qt.conf')
        if not os.path.exists(qt_conf):
            with open(qt_conf, 'w', encoding='utf-8') as qc:
                qc.write("[Paths]\\nPrefix = .\\nPlugins = .\\n")
    except:
        pass

_setup_icon()
'''
            f.write(runtime_hook_code)

        # 使用 --runtime-hook 而不是替换入口脚本
        # 这样 PyInstaller 可以正确分析原始脚本的依赖
        cmd.extend(["--runtime-hook", runtime_hook_script])

        self.log("\n已创建 Runtime Hook，包含图标修复功能:")
        self.log("  ✓ 设置 AppUserModelID (修复任务栏图标)")
        self.log("  ✓ 后台线程修复窗口左上角图标")
        self.log("  ✓ 自动为 Qt 窗口设置图标")
        self.log("  ✓ Qt 插件路径修复")

        # 指定输出文件名（使用临时名称避免中文编码问题）
        cmd.extend(["--name", build_name])

        # 版权信息（版本信息文件）
        version_info = config.get("version_info")
        if version_info:
            self.log("\n添加版权信息...")
            version_file = self._create_version_info_file(config, output_dir)
            if version_file:
                cmd.extend(["--version-file", version_file])
                self.log(f"  产品名称: {version_info.get('product_name', 'N/A')}")
                self.log(f"  公司名称: {version_info.get('company_name', 'N/A')}")
                self.log(f"  文件描述: {version_info.get('file_description', 'N/A')}")
                self.log(f"  版权信息: {version_info.get('copyright', 'N/A')}")
                self.log(f"  版本号: {version_info.get('version', '1.0.0')}")

        # Python优化
        if config.get("python_opt", True):
            self.log("\n已启用Python字节码优化，这将：")
            self.log("  - 移除文档字符串（docstrings）")
            self.log("  - 禁用断言语句（assert）")
            self.log("  - 启用Python -O优化")

        # 使用原始脚本作为入口（不再使用启动器脚本）
        # 这样 PyInstaller 可以正确分析所有依赖
        cmd.append(script_path)

        # 执行打包
        self.log(f"执行命令: {' '.join(cmd)}")
        self.log("")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )

            # 通知GUI进程已创建
            if self.process_callback:
                self.process_callback(process)

            # 实时输出日志
            if process.stdout:
                for line in process.stdout:
                    # 检查是否取消
                    if self.cancel_flag and self.cancel_flag():
                        self.log("检测到取消请求，正在终止进程...")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        return False, "打包已被用户取消"

                    self.log(line.rstrip())

            process.wait()

            # 检查是否被取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已被用户取消"

            if process.returncode == 0:
                # 如果使用了临时名称，需要重命名
                if temp_name:
                    temp_exe = os.path.join(output_dir, f"{temp_name}.exe")
                    final_exe = os.path.join(output_dir, f"{script_name}.exe")

                    self.log("\n" + "=" * 50)
                    self.log("处理中文程序名...")
                    self.log("=" * 50)
                    self.log(f"临时名称: {temp_name}")
                    self.log(f"最终名称: {script_name}")
                    self.log(f"检查临时文件: {temp_exe}")

                    # 列出输出目录中的所有文件
                    try:
                        files_in_output = os.listdir(output_dir)
                        self.log(f"输出目录中的文件: {files_in_output}")
                    except Exception as e:
                        self.log(f"无法列出输出目录: {str(e)}")

                    if os.path.exists(temp_exe):
                        try:
                            # 如果目标文件已存在，先删除
                            if os.path.exists(final_exe):
                                os.remove(final_exe)
                                self.log(f"删除已存在的目标文件")

                            # 使用 shutil.move 更可靠
                            import shutil
                            shutil.move(temp_exe, final_exe)
                            self.log(f"重命名成功: {temp_name}.exe -> {script_name}.exe")
                            exe_path = final_exe
                        except Exception as e:
                            self.log(f"重命名文件时出错: {str(e)}")
                            self.log(f"将使用临时文件名: {temp_name}.exe")
                            exe_path = temp_exe
                    else:
                        self.log(f"警告: 未找到临时输出文件: {temp_exe}")
                        # 尝试直接查找中文名文件（可能直接成功了）
                        final_exe = os.path.join(output_dir, f"{script_name}.exe")
                        if os.path.exists(final_exe):
                            self.log(f"找到最终文件（可能已直接生成）: {final_exe}")
                            exe_path = final_exe
                        else:
                            # 尝试查找任何 .exe 文件
                            self.log("尝试在输出目录中查找任何 .exe 文件...")
                            exe_files = [f for f in os.listdir(output_dir) if f.endswith('.exe')]
                            if exe_files:
                                self.log(f"找到以下 exe 文件: {exe_files}")
                                # 使用第一个找到的 exe
                                found_exe = os.path.join(output_dir, exe_files[0])
                                self.log(f"使用找到的 exe 文件: {found_exe}")
                                # 尝试重命名为中文名
                                try:
                                    import shutil
                                    if os.path.exists(final_exe):
                                        os.remove(final_exe)
                                    shutil.move(found_exe, final_exe)
                                    self.log(f"成功重命名为: {script_name}.exe")
                                    exe_path = final_exe
                                except Exception as e:
                                    self.log(f"重命名失败: {str(e)}")
                                    exe_path = found_exe
                            else:
                                return False, "打包完成，但未找到输出文件"
                else:
                    exe_name = f"{script_name}.exe"
                    exe_path = os.path.join(output_dir, exe_name)

                if os.path.exists(exe_path):
                    # 清理构建缓存
                    if config.get("clean", True):
                        self.log("\n清理构建缓存...")
                        cleaned_count = 0

                        # 1. 清理 build_temp 目录
                        work_dir = os.path.join(os.path.dirname(output_dir), "build_temp")
                        if os.path.exists(work_dir):
                            try:
                                import shutil
                                shutil.rmtree(work_dir)
                                self.log(f"已清理: build_temp")
                                cleaned_count += 1
                            except Exception as e:
                                self.log(f"清理 build_temp 时出错: {str(e)}")

                        # 2. 清理 PyInstaller 在输出目录中生成的缓存目录
                        pyinstaller_cache_dirs = [
                            os.path.join(output_dir, "build"),
                            os.path.join(output_dir, f"{build_name}"),  # dist 子目录（有时会生成）
                        ]

                        # 如果使用了临时名称，也清理最终名称的缓存
                        if temp_name and script_name != build_name:
                            pyinstaller_cache_dirs.extend([
                                os.path.join(output_dir, f"{script_name}"),
                            ])

                        for cache_dir in pyinstaller_cache_dirs:
                            if os.path.exists(cache_dir) and os.path.isdir(cache_dir):
                                # 确保不删除包含 exe 的主目录
                                if cache_dir != output_dir:
                                    try:
                                        import shutil
                                        shutil.rmtree(cache_dir)
                                        self.log(f"已清理: {os.path.basename(cache_dir)}")
                                        cleaned_count += 1
                                    except Exception as e:
                                        self.log(f"清理 {os.path.basename(cache_dir)} 时出错: {str(e)}")

                        # 3. 清理 spec 文件（可能在多个位置）
                        possible_spec_locations = [
                            os.path.join(os.path.dirname(script_path), f"{build_name}.spec"),  # 脚本目录
                            os.path.join(os.getcwd(), f"{build_name}.spec"),  # 当前工作目录
                            os.path.join(output_dir, f"{build_name}.spec"),  # 输出目录
                        ]

                        # 如果使用了临时名称，也清理最终名称的 spec
                        if temp_name and script_name != build_name:
                            possible_spec_locations.extend([
                                os.path.join(os.path.dirname(script_path), f"{script_name}.spec"),
                                os.path.join(os.getcwd(), f"{script_name}.spec"),
                                os.path.join(output_dir, f"{script_name}.spec"),
                            ])

                        for spec_file in possible_spec_locations:
                            if os.path.exists(spec_file):
                                try:
                                    os.remove(spec_file)
                                    self.log(f"已删除: {os.path.basename(spec_file)}")
                                    cleaned_count += 1
                                except Exception as e:
                                    self.log(f"删除 {os.path.basename(spec_file)} 时出错: {str(e)}")

                        # 4. 清理临时生成的图标文件 (app_icon.ico)
                        temp_icon_path = os.path.join(output_dir, "app_icon.ico")
                        if os.path.exists(temp_icon_path):
                            try:
                                os.remove(temp_icon_path)
                                self.log(f"已删除: app_icon.ico")
                                cleaned_count += 1
                            except Exception as e:
                                self.log(f"删除 app_icon.ico 时出错: {str(e)}")

                        if cleaned_count > 0:
                            self.log(f"共清理了 {cleaned_count} 个缓存文件/目录")
                        else:
                            self.log("没有找到需要清理的缓存文件/目录")

                    # 保存 exe 路径用于后续打开目录
                    self._last_exe_path = exe_path
                    return True, f"打包成功！\n\n输出文件: {exe_path}"
                else:
                    return False, "打包完成，但未找到输出文件"
            else:
                error_msg = f"PyInstaller执行失败，返回码: {process.returncode}"

                # 添加诊断信息
                self.log("\n" + "=" * 50)
                self.log("打包失败诊断")
                self.log("=" * 50)

                # 检查是否是 Qt 插件问题
                if "Qt plugin directory" in error_msg or "does not exist" in error_msg:
                    self.log("检测到 Qt 插件目录缺失问题")
                    self.log("")
                    self.log("解决方案：")
                    self.log("1. 重新安装 PyQt5 及其插件包：")
                    self.log(f"   {python_path} -m pip uninstall PyQt5 PyQt5-Qt5 -y")
                    self.log(f"   {python_path} -m pip install PyQt5 PyQt5-Qt5")
                    self.log("")
                    self.log("2. 如果问题依然存在，尝试使用其他 Qt 版本：")
                    self.log(f"   {python_path} -m pip install PyQt6 PyQt6-Qt6")
                    self.log("")

                # 检查是否是编码/中文路径问题
                if "encoding" in error_msg.lower() or "codec" in error_msg.lower():
                    self.log("检测到编码相关问题")
                    self.log("")
                    self.log("解决方案：")
                    self.log("1. 确保所有文件使用 UTF-8 编码")
                    self.log("2. 避免在路径中使用中文字符")
                    self.log("3. 将项目移至纯英文路径（如 C:/Projects/myapp）")
                    self.log("")

                return False, error_msg

        except Exception as e:
            error_msg = f"执行PyInstaller时出错: {str(e)}"

            # 添加通用诊断信息
            self.log("\n" + "=" * 50)
            self.log("打包异常诊断")
            self.log("=" * 50)
            self.log(f"错误类型: {type(e).__name__}")
            self.log(f"错误信息: {str(e)}")
            self.log("")
            self.log("常见解决方法：")
            self.log("1. 检查所有依赖包是否正确安装")
            self.log("2. 确保 Python 环境没有损坏")
            self.log("3. 尝试在新的虚拟环境中重新打包")
            self.log("4. 检查是否有路径过长或包含特殊字符的问题")
            self.log("")

            return False, error_msg

    def _test_exe_for_missing_modules(
        self,
        exe_path: str,
        timeout: int = 10
    ) -> Tuple[bool, Set[str]]:
        """
        测试exe运行，检测是否有缺失的模块

        改进：使用 Popen 启动进程，快速检测启动状态，
        如果进程正常启动则立即返回，无需等待超时。

        Args:
            exe_path: exe文件路径
            timeout: 最大等待时间（秒），仅作为安全上限

        Returns:
            (运行成功, 缺失的模块集合)
        """
        self.log("\n" + "=" * 50)
        self.log("第三层防护：打包后自动测试")
        self.log("=" * 50)
        self.log(f"测试运行: {exe_path}")

        if not os.path.exists(exe_path):
            self.log("⚠️ exe文件不存在，跳过测试")
            return True, set()

        missing_modules = set()
        process = None

        try:
            import time

            # 使用 Popen 启动进程，不阻塞等待
            process = subprocess.Popen(
                [exe_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            self.log("正在检测程序启动状态...")

            # 短暂等待，检查进程是否立即崩溃（通常是模块缺失导致）
            # 分多次检查，每次间隔较短，总时间不超过3秒
            check_interval = 0.3  # 每次检查间隔
            max_checks = 10  # 最多检查次数（总共3秒）
            collected_output = ""

            for i in range(max_checks):
                time.sleep(check_interval)

                # 检查进程是否还在运行
                poll_result = process.poll()

                if poll_result is not None:
                    # 进程已结束，获取输出
                    stdout, stderr = process.communicate()
                    collected_output = (stdout or "") + (stderr or "")

                    # 检查是否有模块缺失错误
                    if "ModuleNotFoundError" in collected_output or "No module named" in collected_output:
                        missing_modules = self._parse_missing_modules(collected_output)
                        if missing_modules:
                            self.log(f"✗ 检测到缺失模块: {', '.join(sorted(missing_modules))}")
                            return False, missing_modules
                        else:
                            self.log("⚠️ 检测到模块错误但无法解析具体模块名")
                            return False, set()

                    # 进程正常退出
                    if poll_result == 0:
                        self.log(f"✓ exe运行测试通过（程序正常退出，耗时 {(i+1)*check_interval:.1f}秒）")
                        return True, set()
                    else:
                        # 非零返回码，检查是否有严重错误
                        if "Error" not in collected_output and "Exception" not in collected_output:
                            self.log(f"✓ exe可以启动（返回码 {poll_result}，可能是正常情况）")
                            return True, set()
                        else:
                            self.log(f"⚠️ exe运行出错，返回码: {poll_result}")
                            if collected_output:
                                preview = collected_output[:500]
                                self.log(f"输出预览: {preview}")
                            return True, set()  # 不认为是模块缺失问题

            # 进程仍在运行，说明启动成功（GUI程序或长时间运行的服务）
            self.log(f"✓ exe启动成功（程序正常运行中，检测耗时 {max_checks*check_interval:.1f}秒）")

            # 终止测试进程
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

            return True, set()

        except FileNotFoundError:
            self.log("⚠️ exe文件不存在或无法执行")
            return True, set()
        except Exception as e:
            self.log(f"⚠️ 测试过程出错: {str(e)}")
            return True, set()  # 出错时不阻止流程
        finally:
            # 确保进程被清理
            if process is not None:
                try:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=2)
                except Exception:
                    try:
                        process.kill()
                    except Exception:
                        pass

    def _parse_missing_modules(self, output: str) -> Set[str]:
        """
        从输出中解析缺失的模块名

        Args:
            output: 程序输出内容

        Returns:
            缺失的模块名集合
        """
        import re

        missing_modules = set()

        # 匹配模式: No module named 'xxx' 或 ModuleNotFoundError: No module named 'xxx'
        patterns = [
            r"No module named ['\"]([^'\"]+)['\"]",
            r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
            r"ImportError: No module named ['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, output)
            for match in matches:
                # 获取根模块名
                root_module = match.split('.')[0]
                missing_modules.add(match)
                if root_module != match:
                    missing_modules.add(root_module)

        return missing_modules

    def _package_with_nuitka(
        self, python_path: str, config: Dict, output_dir: str
    ) -> Tuple[bool, str]:
        """使用Nuitka打包"""
        self.log("\n" + "=" * 50)
        self.log("使用Nuitka打包（已优化）...")
        self.log("=" * 50)

        script_path = config["script_path"]
        project_dir = config.get("project_dir")

        # 确定输出文件名：优先级：用户指定 > 项目名 > 脚本名
        if config.get("program_name"):
            script_name = config["program_name"]
            self.log(f"使用用户指定的程序名称: {script_name}")
        elif project_dir and os.path.basename(project_dir):
            script_name = os.path.basename(project_dir)
            self.log(f"使用项目名称: {script_name}")
        else:
            script_name = Path(script_path).stem
            self.log(f"使用脚本名称: {script_name}")

        # 检测项目使用的 GUI 框架
        # 使用依赖分析器已检测的主要 Qt 框架（避免多 Qt 绑定冲突）
        qt_framework = self.dependency_analyzer.primary_qt_framework
        if qt_framework:
            self.log(f"使用主要 Qt 框架: {qt_framework}")

        uses_wx = False
        uses_tkinter = False
        uses_kivy = False
        uses_flet = False
        uses_customtkinter = False
        uses_eel = False
        uses_dearpygui = False
        uses_toga = False
        uses_textual = False
        uses_pysimplegui = False
        uses_pygame = False
        uses_matplotlib = False
        uses_numpy = False
        uses_scipy = False
        uses_pandas = False
        uses_opencv = False
        uses_pillow = False
        uses_sqlalchemy = False
        uses_cryptography = False
        uses_requests = False
        uses_certifi = False

        # 使用 AST 精确检测项目中实际导入的模块
        actual_imports = self._detect_actual_imports(script_path, project_dir)
        self.log(f"AST 检测到的实际导入模块: {len(actual_imports)} 个")

        # 验证包是否实际安装的辅助函数
        def is_package_installed(package_name: str) -> bool:
            try:
                result = subprocess.run(
                    [python_path, "-c", f"import {package_name}"],
                    capture_output=True,
                    timeout=5,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                return result.returncode == 0
            except:
                return False

        # 检测模块是真正的包（目录）还是单文件模块
        def is_real_package(module_name: str) -> bool:
            """
            检测一个模块是否是真正的包（有 __path__ 属性）。
            单文件模块（如 img2pdf.py）不是包，不能使用 --include-package。
            """
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
                return output == "package"
            except:
                # 默认假设是包，保守处理
                return True

        # 检测 wxPython（需要实际导入 wx 且包已安装）
        if 'wx' in actual_imports and is_package_installed('wx'):
            uses_wx = True
            self.log(f"检测到 wxPython 框架（已验证安装）")

        # 检测 Tkinter（标准库，不需要验证安装）
        tkinter_imports = {'tkinter', 'Tkinter', 'ttk', 'tkinter.ttk',
                          'tkinter.filedialog', 'tkinter.messagebox',
                          'tkinter.simpledialog', 'tkinter.colorchooser'}
        if any(imp in actual_imports or imp.startswith('tkinter.') for imp in actual_imports) or \
           actual_imports & tkinter_imports:
            uses_tkinter = True
            self.log(f"检测到 Tkinter 框架")

        # 检测其他 GUI 框架（需要实际导入且包已安装）
        if 'kivy' in actual_imports and is_package_installed('kivy'):
            uses_kivy = True
            self.log(f"检测到 Kivy 框架（已验证安装）")
        if 'flet' in actual_imports and is_package_installed('flet'):
            uses_flet = True
            self.log(f"检测到 Flet 框架（已验证安装）")
        if 'customtkinter' in actual_imports and is_package_installed('customtkinter'):
            uses_customtkinter = True
            self.log(f"检测到 CustomTkinter 框架（已验证安装）")
        if 'eel' in actual_imports and is_package_installed('eel'):
            uses_eel = True
            self.log(f"检测到 Eel 框架（已验证安装）")
        if 'dearpygui' in actual_imports and is_package_installed('dearpygui'):
            uses_dearpygui = True
            self.log(f"检测到 DearPyGui 框架（已验证安装）")
        if 'toga' in actual_imports and is_package_installed('toga'):
            uses_toga = True
            self.log(f"检测到 Toga 框架（已验证安装）")
        if 'textual' in actual_imports and is_package_installed('textual'):
            uses_textual = True
            self.log(f"检测到 Textual 框架（已验证安装）")
        if 'PySimpleGUI' in actual_imports and is_package_installed('PySimpleGUI'):
            uses_pysimplegui = True
            self.log(f"检测到 PySimpleGUI 框架（已验证安装）")

        # 检测 pygame
        if 'pygame' in actual_imports and is_package_installed('pygame'):
            uses_pygame = True
            self.log(f"检测到 Pygame 框架（已验证安装）")

        # 检测 matplotlib
        if 'matplotlib' in actual_imports and is_package_installed('matplotlib'):
            uses_matplotlib = True
            self.log(f"检测到 Matplotlib 库（已验证安装）")

        # 检测 numpy
        if 'numpy' in actual_imports and is_package_installed('numpy'):
            uses_numpy = True
            self.log(f"检测到 NumPy 库（已验证安装）")

        # 检测 scipy
        if 'scipy' in actual_imports and is_package_installed('scipy'):
            uses_scipy = True
            self.log(f"检测到 SciPy 库（已验证安装）")

        # 检测 pandas
        if 'pandas' in actual_imports and is_package_installed('pandas'):
            uses_pandas = True
            self.log(f"检测到 Pandas 库（已验证安装）")

        # 检测 opencv
        if 'cv2' in actual_imports and is_package_installed('cv2'):
            uses_opencv = True
            self.log(f"检测到 OpenCV 库（已验证安装）")

        # 检测 PIL/Pillow
        if ('PIL' in actual_imports or 'pillow' in actual_imports) and is_package_installed('PIL'):
            uses_pillow = True
            self.log(f"检测到 Pillow 库（已验证安装）")

        # 检测 sqlalchemy
        if 'sqlalchemy' in actual_imports and is_package_installed('sqlalchemy'):
            uses_sqlalchemy = True
            self.log(f"检测到 SQLAlchemy 库（已验证安装）")

        # 检测 cryptography
        if 'cryptography' in actual_imports and is_package_installed('cryptography'):
            uses_cryptography = True
            self.log(f"检测到 Cryptography 库（已验证安装）")

        # 检测 requests
        if 'requests' in actual_imports and is_package_installed('requests'):
            uses_requests = True
            self.log(f"检测到 Requests 库（已验证安装）")

        # 检测 certifi（SSL证书库，需要包含数据文件）
        if 'certifi' in actual_imports and is_package_installed('certifi'):
            uses_certifi = True
            self.log(f"检测到 Certifi 库（已验证安装）")

        # 检测中文字符，使用临时英文名避免编码问题
        has_chinese = any('\u4e00' <= char <= '\u9fff' for char in script_name)
        temp_name = None
        if has_chinese:
            import uuid
            temp_name = f"temp_{uuid.uuid4().hex[:8]}"
            self.log(f"检测到中文名称，使用临时名称打包: {temp_name}")
            build_name = temp_name
        else:
            build_name = script_name

        # 获取优化建议
        exclude_modules, hidden_imports, _ = (
            self.dependency_analyzer.get_optimization_suggestions(python_path)
        )

        # 确保排除打包工具本身及其子模块（防止Nuitka编译失败）
        packaging_tools = {'pyinstaller', 'nuitka', 'PyInstaller'}
        exclude_modules = list(set(exclude_modules) | packaging_tools)

        # 获取需要排除的冲突 Qt 绑定（避免 Nuitka 多 Qt 绑定问题）
        qt_exclusions = self.dependency_analyzer.get_qt_exclusion_list()
        if qt_exclusions:
            self.log(f"\n排除冲突的 Qt 绑定: {', '.join(qt_exclusions)}")
            exclude_modules = list(set(exclude_modules) | set(qt_exclusions))

        # 合并用户自定义的排除模块
        user_exclude_modules = config.get("exclude_modules", [])
        if user_exclude_modules:
            self.log(f"\n用户手动指定排除模块: {', '.join(user_exclude_modules)}")
            self.log(f"自动分析建议排除模块: {', '.join(sorted(exclude_modules))}")
            exclude_modules = list(set(exclude_modules) | set(user_exclude_modules))
            self.log(f"最终排除模块（合并去重后）: {', '.join(sorted(exclude_modules))}")
        else:
            self.log(f"\n使用自动分析的排除模块（共 {len(exclude_modules)} 个）")

        # 处理GCC（如果提供）
        gcc_path = config.get("gcc_path", "")

        # 处理GCC路径 - 现在gcc_path应该是mingw64或mingw32目录
        if not gcc_path or not os.path.exists(gcc_path):
            self.log("未指定GCC路径，尝试自动获取...")
            # 尝试从默认位置获取mingw目录
            from utils.gcc_downloader import GCCDownloader
            mingw_path = GCCDownloader.get_default_mingw_path()
            if mingw_path:
                gcc_path = mingw_path
                self.log(f"找到已缓存的GCC工具链: {gcc_path}")
            else:
                self.log("警告: 无法自动获取GCC工具链")

        if gcc_path and os.path.exists(gcc_path):
            # 验证是否是有效的mingw目录
            from utils.gcc_downloader import GCCDownloader
            is_valid, msg = GCCDownloader.validate_mingw_directory(gcc_path)
            if is_valid:
                self.log(f"使用GCC工具链: {gcc_path}")
                # 直接使用mingw目录，将bin目录添加到PATH
                gcc_bin = os.path.join(gcc_path, "bin")
                if os.path.exists(gcc_bin):
                    os.environ["PATH"] = gcc_bin + os.pathsep + os.environ["PATH"]
                    self.log(f"已将GCC添加到PATH: {gcc_bin}")
                else:
                    self.log(f"警告: GCC bin目录不存在: {gcc_bin}")
            else:
                self.log(f"警告: GCC目录验证失败: {msg}")
                self.log("将尝试使用系统GCC")

        # 构建Nuitka命令
        cmd = [python_path, "-m", "nuitka"]

        # 指定输出文件名（使用 = 连接参数和值，使用临时名称避免中文编码问题）
        cmd.append(f"--output-filename={build_name}.exe")

        # 单文件模式（使用 --mode 参数，兼容 Nuitka 2.8.9+）
        if config.get("onefile", True):
            cmd.append("--mode=onefile")
        else:
            cmd.append("--mode=standalone")

        # 控制台窗口（使用新的参数格式）
        if not config.get("console", False):
            cmd.append("--windows-console-mode=disable")
        else:
            cmd.append("--windows-console-mode=force")

        # 图标 - 转换为绝对路径
        icon_path = config.get("icon_path")
        if icon_path:
            # 如果是相对路径，转换为绝对路径
            if not os.path.isabs(icon_path):
                # 相对于项目目录或脚本目录
                if project_dir:
                    icon_path = os.path.join(project_dir, icon_path)
                else:
                    icon_path = os.path.join(os.path.dirname(script_path), icon_path)

            # 验证图标文件存在
            if not os.path.exists(icon_path):
                self.log(f"警告: 图标文件不存在: {icon_path}")
                icon_path = None  # 重置为 None，后续逻辑会跳过

        # 版权信息处理
        # 由于 MSVC 编译器在命令行中处理中文字符会导致编码错误(C4819, C2001)，
        # 当检测到中文字符时，创建 Windows 资源文件(.rc)并编译为 .res 文件
        version_info = config.get("version_info")
        use_rc_file = False  # 标记是否使用了资源文件

        if version_info:
            self.log("\n添加版权信息...")
            product_name = version_info.get("product_name", "") or script_name
            company_name = version_info.get("company_name", "")
            file_description = version_info.get("file_description", "") or script_name
            copyright_text = version_info.get("copyright", "")
            version_str = version_info.get("version", "1.0.0")

            # 检测是否包含非 ASCII 字符（中文等）
            def has_non_ascii(text):
                if not text:
                    return False
                try:
                    text.encode('ascii')
                    return False
                except UnicodeEncodeError:
                    return True

            any_chinese = any(has_non_ascii(v) for v in [product_name, company_name, file_description, copyright_text])

            if any_chinese:
                # 使用 Windows 资源文件方式处理中文版本信息
                # 检测Nuitka版本以决定是否支持 --windows-force-rc-file
                nuitka_version = None
                try:
                    result = subprocess.run(
                        [python_path, "-m", "nuitka", "--version"],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
                    if result.returncode == 0:
                        # 提取版本号，格式如 "2.8.9" 或 "2.9.0"
                        import re
                        version_match = re.search(r'(\d+)\.(\d+)\.(\d+)', result.stdout)
                        if version_match:
                            major = int(version_match.group(1))
                            minor = int(version_match.group(2))
                            nuitka_version = (major, minor)
                            self.log(f"检测到 Nuitka 版本: {major}.{minor}")
                except:
                    pass

                # Nuitka 2.9+ 支持 --windows-force-rc-file
                supports_rc_file = nuitka_version and nuitka_version >= (2, 9)

                if supports_rc_file:
                    self.log("Nuitka 2.9+ 检测到，将尝试创建资源文件...")
                    res_file = self._create_version_resource_file(
                        output_dir=output_dir,
                        script_name=script_name,
                        product_name=product_name,
                        company_name=company_name,
                        file_description=file_description,
                        copyright_text=copyright_text,
                        version_str=version_str,
                        icon_path=icon_path if icon_path and os.path.exists(icon_path) else None
                    )

                    if res_file and os.path.exists(res_file):
                        # 使用 Nuitka 的 --windows-force-rc-file 参数
                        cmd.append(f"--windows-force-rc-file={res_file}")
                        use_rc_file = True  # 标记已使用资源文件
                        self.log(f"  ✓ 已创建并编译资源文件: {res_file}")
                        self.log(f"  ✓ 产品名称: {product_name}")
                        self.log(f"  ✓ 公司名称: {company_name}")
                        self.log(f"  ✓ 文件描述: {file_description}")
                        self.log(f"  ✓ 版权信息: {copyright_text}")
                        self.log(f"  ✓ 版本号: {version_str}")
                        if icon_path:
                            self.log(f"  ✓ 图标已包含在资源文件中")
                        # 版本号只包含数字和点，可以安全传递
                        if version_str:
                            cmd.append(f"--product-version={version_str}")
                            cmd.append(f"--file-version={version_str}")
                    else:
                        self.log("⚠️  资源文件创建失败，将使用命令行参数")
                        # 回退到命令行参数（即使是中文，也尝试写入）
                        self._add_version_info_cmdline(cmd, product_name, company_name,
                                                       file_description, copyright_text, version_str)
                else:
                    # Nuitka 2.8.x 不支持 --windows-force-rc-file
                    self.log("检测到 Nuitka 2.8.x，不支持 --windows-force-rc-file")
                    self.log("⚠️  将使用命令行参数设置版本信息（中文可尝试写入）")
                    self.log("⚠️  建议升级到 Nuitka 2.9+ 以获得完整中文支持")
                    # 使用命令行参数写入元信息（尝试中文）
                    self._add_version_info_cmdline(cmd, product_name, company_name,
                                                   file_description, copyright_text, version_str)
            else:
                # 没有中文字符，直接使用命令行参数
                self._add_version_info_cmdline(cmd, product_name, company_name,
                                               file_description, copyright_text, version_str)

        # 处理图标（仅在未使用资源文件时）
        # 如果使用了资源文件，图标已经包含在其中，不需要再单独添加
        if icon_path and os.path.exists(icon_path) and not use_rc_file:
            self.log(f"\n" + "=" * 50)
            self.log("处理图标文件...")
            self.log("=" * 50)
            self.log(f"使用图标: {icon_path}")

            # 直接使用原始图标文件（与 1.bat 一致）
            # Nuitka使用--windows-icon-from-ico参数，会自动嵌入到exe资源中
            cmd.append(f"--windows-icon-from-ico={icon_path}")

            # 添加图标为数据文件到根目录（固定名称为 icon.ico）
            cmd.append(f"--include-data-file={icon_path}=icon.ico")
            self.log(f"已添加图标数据文件: icon.ico")

            # 同时保持原始目录结构（兼容从 resources/icons/icon.ico 加载的代码）
            icon_dir = os.path.dirname(icon_path)
            if icon_dir and os.path.exists(icon_dir):
                # 检查是否是 resources/icons 目录结构
                icon_dir_name = os.path.basename(icon_dir)
                parent_dir = os.path.dirname(icon_dir)
                parent_dir_name = os.path.basename(parent_dir) if parent_dir else ""

                if icon_dir_name == "icons" and parent_dir_name == "resources":
                    # 包含整个 resources 目录以保持目录结构
                    resources_dir = parent_dir
                    if os.path.exists(resources_dir):
                        cmd.append(f"--include-data-dir={resources_dir}=resources")
                        self.log(f"已添加资源目录: resources/")
        elif icon_path and os.path.exists(icon_path) and use_rc_file:
            # 资源文件已包含图标，只添加图标为数据文件（供应用程序内部使用）
            cmd.append(f"--include-data-file={icon_path}=icon.ico")
            self.log(f"已添加图标数据文件: icon.ico (图标资源已在 .res 中)")

            # 同时保持原始目录结构
            icon_dir = os.path.dirname(icon_path)
            if icon_dir and os.path.exists(icon_dir):
                icon_dir_name = os.path.basename(icon_dir)
                parent_dir = os.path.dirname(icon_dir)
                parent_dir_name = os.path.basename(parent_dir) if parent_dir else ""

                if icon_dir_name == "icons" and parent_dir_name == "resources":
                    resources_dir = parent_dir
                    if os.path.exists(resources_dir):
                        cmd.append(f"--include-data-dir={resources_dir}=resources")
                        self.log(f"已添加资源目录: resources/")

        # 添加排除模块（优化）
        # 额外添加更多应排除的大型/不必要模块（与 build_universal.bat 一致）
        extra_exclude_modules = {
            # 测试框架
            'pytest', 'unittest', 'doctest', 'coverage', 'nose', 'mock', 'tox',
            # 开发工具
            'sphinx', 'docutils', 'IPython', 'jupyter', 'notebook', 'ipython', 'ipykernel',
            # 大型科学计算库（通常不需要）
            'matplotlib', 'seaborn', 'pandas', 'numpy', 'scipy', 'sklearn',
            'tensorflow', 'torch', 'cv2', 'opencv',
            # GUI 框架冲突（已由 Qt 排除处理，这里再次确认）
            'tkinter', 'wxpy', 'wxpython', 'PyQt4', 'PySide', 'PyQt5', 'PySide2', 'PySide6',
            # 其他
            'polib', 'distutils', 'pkg_resources',
        }

        # 根据实际使用情况，从排除列表中移除需要的模块
        if uses_tkinter or uses_customtkinter:
            extra_exclude_modules.discard('tkinter')
        if uses_pillow:
            extra_exclude_modules.discard('PIL')
            extra_exclude_modules.discard('pillow')
        if uses_matplotlib:
            extra_exclude_modules.discard('matplotlib')
        if uses_numpy:
            extra_exclude_modules.discard('numpy')
        if uses_scipy:
            extra_exclude_modules.discard('scipy')
        if uses_pandas:
            extra_exclude_modules.discard('pandas')
        if uses_opencv:
            extra_exclude_modules.discard('cv2')
            extra_exclude_modules.discard('opencv')

        all_exclude_modules = set(exclude_modules) | extra_exclude_modules

        if all_exclude_modules:
            self.log(f"\n应用优化: 排除 {len(all_exclude_modules)} 个不必要的模块")
            for module in all_exclude_modules:
                # Nuitka使用不同的排除语法
                if not module.startswith("*"):
                    cmd.append(f"--nofollow-import-to={module}")

        # 添加包含模块（如果需要）
        # 注意：不自动添加所有依赖，让 Nuitka 自动分析，避免打包不必要的模块导致文件过大
        if hidden_imports:
            # 过滤掉打包工具本身（pyinstaller 和 nuitka）及其所有子模块
            def should_include_module(module_name):
                # 精确匹配打包工具名
                if module_name in {'pyinstaller', 'nuitka', 'PyInstaller'}:
                    return False
                # 排除打包工具的所有子模块
                if module_name.startswith(('pyinstaller.', 'nuitka.', 'PyInstaller.')):
                    return False
                return True

            filtered_imports = [m for m in hidden_imports if should_include_module(m)]
            self.log(f"应用优化: 包含 {len(filtered_imports)} 个必要模块")
            for module in filtered_imports:
                cmd.append(f"--include-module={module}")

        # ========== 增强Analysis阶段：对未配置的库使用完整收集 ==========
        unconfigured_libs = self.dependency_analyzer._unconfigured_libraries
        if unconfigured_libs:
            # 过滤掉打包工具本身（排除 pyinstaller 和 nuitka）
            def should_collect_lib(lib_name):
                lib_lower = lib_name.lower()
                if lib_lower in {'pyinstaller', 'nuitka'}:
                    return False
                return True

            filtered_libs = [lib for lib in unconfigured_libs if should_collect_lib(lib)]
            if filtered_libs:
                self.log(f"\n增强Analysis阶段: 对 {len(filtered_libs)} 个未配置的库使用完整收集")
                for lib in sorted(filtered_libs):
                    # 先检测是否是真正的包（目录）还是单文件模块
                    if is_real_package(lib):
                        # 真正的包：使用 --include-package 收集整个包
                        self.log(f"  收集 {lib} 的所有模块（包）...")
                        cmd.append(f"--include-package={lib}")
                        # 同时包含包的数据文件
                        cmd.append(f"--include-package-data={lib}")
                    else:
                        # 单文件模块：使用 --include-module
                        self.log(f"  收集 {lib}（单文件模块）...")
                        cmd.append(f"--include-module={lib}")
                self.log(f"  ✓ 已为未配置的库启用完整收集模式")

        # 添加自动收集到的子模块
        auto_collected = self.dependency_analyzer._auto_collected_modules
        if auto_collected:
            self.log(f"\n添加自动收集的子模块...")
            added_count = 0
            for lib, submodules in auto_collected.items():
                # 跳过打包工具本身（所有变体）
                lib_lower = lib.lower()
                if lib_lower in {'pyinstaller', 'nuitka'}:
                    continue
                for submodule in submodules:
                    # 跳过打包工具的所有子模块（所有变体）
                    if (submodule.startswith(('pyinstaller.', 'nuitka.', 'PyInstaller.')) or
                        submodule.lower().startswith(('pyinstaller.', 'nuitka.'))):
                        continue
                    if submodule not in hidden_imports:
                        cmd.append(f"--include-module={submodule}")
                        added_count += 1
            if added_count > 0:
                self.log(f"  已添加 {added_count} 个自动收集的子模块")

        # 添加动态追踪到的导入
        dynamic_imports = self.dependency_analyzer._dynamic_imports
        if dynamic_imports:
            self.log(f"\n添加动态追踪到的导入...")
            added_dynamic = 0
            for imp in dynamic_imports:
                # 跳过已添加的
                if imp in hidden_imports:
                    continue
                # 跳过标准库
                root_module = imp.split('.')[0]
                if self.dependency_analyzer._is_stdlib(root_module):
                    continue
                # 跳过打包工具本身（所有变体）
                root_lower = root_module.lower()
                if root_lower in {'pyinstaller', 'nuitka'}:
                    continue
                # 跳过打包工具的子模块
                if imp.lower().startswith(('pyinstaller.', 'nuitka.')):
                    continue
                cmd.append(f"--include-module={imp}")
                added_dynamic += 1
            if added_dynamic > 0:
                self.log(f"  已添加 {added_dynamic} 个动态追踪到的导入")

        # 添加Qt插件支持（仅当检测到Qt框架时）
        # 这是必要的，否则PyQt应用会报错：no Qt platform plugin could be initialized
        if qt_framework:
            self.log(f"\n配置 {qt_framework} 插件支持...")

            # 启用对应的Qt插件
            if qt_framework == "PyQt6":
                cmd.append("--enable-plugin=pyqt6")
            elif qt_framework == "PyQt5":
                cmd.append("--enable-plugin=pyqt5")
            elif qt_framework == "PySide6":
                cmd.append("--enable-plugin=pyside6")
            elif qt_framework == "PySide2":
                cmd.append("--enable-plugin=pyside2")

            # 包含必要的Qt插件（包括图标引擎和图像格式支持）
            cmd.append("--include-qt-plugins=sensible,platforms,styles,iconengines,imageformats")
            self.log("已启用Qt插件支持（包含platforms、styles、iconengines、imageformats）")

            # 包含 PyQt6 的数据文件（DLLs等）
            cmd.append(f"--include-package-data={qt_framework}")
            self.log(f"已包含 {qt_framework} 数据文件")

        # ========== Tkinter 支持 ==========
        # Tkinter 程序需要启用 tk-inter 插件，否则 TCL/TK 不会被包含
        if uses_tkinter or uses_customtkinter:
            self.log(f"\n配置 Tkinter 框架支持...")
            cmd.append("--enable-plugin=tk-inter")
            self.log("已启用 tk-inter 插件（包含 TCL/TK 运行时）")

        # 添加 wxPython 支持（仅当检测到 wxPython 框架时）
        # 注意：只有在确实使用 wx 时才添加，避免不必要的打包
        if uses_wx:
            self.log(f"\n配置 wxPython 支持...")
            # 让 Nuitka 自动处理 wx，不强制包含整个包
            # 如果遇到问题，可以取消下面的注释
            # cmd.append("--include-package=wx")
            self.log("wxPython 将由 Nuitka 自动处理")

        # ========== Kivy 支持 ==========
        if uses_kivy:
            self.log(f"\n配置 Kivy 框架支持...")
            # Kivy 需要包含大量模块和数据文件
            cmd.append("--include-package=kivy")
            cmd.append("--include-package-data=kivy")
            # Kivy 依赖
            cmd.append("--include-module=kivy.core.window")
            cmd.append("--include-module=kivy.core.text")
            cmd.append("--include-module=kivy.core.image")
            cmd.append("--include-module=kivy.graphics")
            cmd.append("--include-module=kivy.uix")
            # Windows 上 Kivy 的依赖包
            try:
                import importlib.util
                if importlib.util.find_spec("kivy_deps"):
                    cmd.append("--include-package=kivy_deps.sdl2")
                    cmd.append("--include-package=kivy_deps.glew")
                    self.log("已添加 Kivy 依赖包 (sdl2, glew)")
            except:
                pass
            self.log("已配置 Kivy 框架支持")

        # ========== Flet 支持 ==========
        if uses_flet:
            self.log(f"\n配置 Flet 框架支持...")
            # Flet 需要包含 Flutter 引擎和数据文件
            cmd.append("--include-package=flet")
            cmd.append("--include-package=flet_core")
            cmd.append("--include-package-data=flet")
            cmd.append("--include-package-data=flet_core")
            # Flet 依赖
            cmd.append("--include-module=httpx")
            cmd.append("--include-module=websockets")
            self.log("已配置 Flet 框架支持")

        # ========== CustomTkinter 支持 ==========
        if uses_customtkinter:
            self.log(f"\n配置 CustomTkinter 框架支持...")
            # CustomTkinter 需要主题 JSON 文件
            cmd.append("--include-package=customtkinter")
            cmd.append("--include-package-data=customtkinter")
            # 依赖 darkdetect 检测系统主题
            cmd.append("--include-module=darkdetect")
            self.log("已配置 CustomTkinter 框架支持（含主题文件）")

        # ========== Eel 支持 ==========
        if uses_eel:
            self.log(f"\n配置 Eel 框架支持...")
            cmd.append("--include-package=eel")
            cmd.append("--include-module=bottle")
            cmd.append("--include-module=bottle_websocket")
            cmd.append("--include-module=gevent")
            cmd.append("--include-module=geventwebsocket")
            # Eel 需要包含 web 目录（用户需要确保 web 目录在项目中）
            # 检查是否有 web 目录
            web_dir = os.path.join(project_dir if project_dir else os.path.dirname(script_path), "web")
            if os.path.exists(web_dir):
                cmd.append(f"--include-data-dir={web_dir}=web")
                self.log(f"已添加 Eel web 目录: {web_dir}")
            else:
                self.log("提示: 未找到 web 目录，如果 Eel 应用需要 web 文件，请确保包含")
            self.log("已配置 Eel 框架支持")

        # ========== DearPyGui 支持 ==========
        if uses_dearpygui:
            self.log(f"\n配置 DearPyGui 框架支持...")
            cmd.append("--include-package=dearpygui")
            cmd.append("--include-package-data=dearpygui")
            self.log("已配置 DearPyGui 框架支持")

        # ========== Toga 支持 ==========
        if uses_toga:
            self.log(f"\n配置 Toga 框架支持...")
            cmd.append("--include-package=toga")
            cmd.append("--include-package=toga_winforms")  # Windows 后端
            cmd.append("--include-module=clr")
            cmd.append("--include-module=pythonnet")
            self.log("已配置 Toga 框架支持（Windows 后端）")

        # ========== Textual 支持 ==========
        if uses_textual:
            self.log(f"\n配置 Textual 框架支持...")
            cmd.append("--include-package=textual")
            cmd.append("--include-package-data=textual")
            cmd.append("--include-package=rich")
            self.log("已配置 Textual 框架支持")

        # ========== PySimpleGUI 支持 ==========
        if uses_pysimplegui:
            self.log(f"\n配置 PySimpleGUI 框架支持...")
            cmd.append("--include-package=PySimpleGUI")
            # PySimpleGUI默认使用tkinter，确保启用tk-inter插件
            if not uses_tkinter and not uses_customtkinter:
                cmd.append("--enable-plugin=tk-inter")
                self.log("已启用 tk-inter 插件（PySimpleGUI 依赖）")
            cmd.append("--include-module=tkinter")
            cmd.append("--include-module=tkinter.ttk")
            cmd.append("--include-module=tkinter.filedialog")
            cmd.append("--include-module=tkinter.messagebox")
            self.log("已配置 PySimpleGUI 框架支持")

        # ========== Pygame 支持 ==========
        if uses_pygame:
            self.log(f"\n配置 Pygame 框架支持...")
            cmd.append("--include-package=pygame")
            cmd.append("--include-package-data=pygame")
            # pygame 需要一些数据文件
            cmd.append("--include-module=pygame.base")
            cmd.append("--include-module=pygame.constants")
            cmd.append("--include-module=pygame.display")
            cmd.append("--include-module=pygame.event")
            cmd.append("--include-module=pygame.image")
            cmd.append("--include-module=pygame.mixer")
            cmd.append("--include-module=pygame.font")
            self.log("已配置 Pygame 框架支持")

        # ========== Matplotlib 支持 ==========
        if uses_matplotlib:
            self.log(f"\n配置 Matplotlib 库支持...")
            cmd.append("--include-package=matplotlib")
            cmd.append("--include-package-data=matplotlib")
            # matplotlib 后端
            cmd.append("--include-module=matplotlib.backends.backend_tkagg")
            cmd.append("--include-module=matplotlib.backends.backend_agg")
            cmd.append("--include-module=matplotlib.figure")
            cmd.append("--include-module=matplotlib.pyplot")
            # 如果使用 tkinter 后端，确保启用 tk-inter 插件
            if not uses_tkinter and not uses_customtkinter:
                cmd.append("--enable-plugin=tk-inter")
                self.log("已启用 tk-inter 插件（Matplotlib TkAgg 后端依赖）")
            self.log("已配置 Matplotlib 库支持")

        # ========== NumPy 支持 ==========
        if uses_numpy:
            self.log(f"\n配置 NumPy 库支持...")
            cmd.append("--include-package=numpy")
            cmd.append("--include-package-data=numpy")
            cmd.append("--include-module=numpy.core._multiarray_umath")
            cmd.append("--include-module=numpy.core._dtype_ctypes")
            cmd.append("--include-module=numpy.random.common")
            cmd.append("--include-module=numpy.random.bounded_integers")
            cmd.append("--include-module=numpy.random.entropy")
            cmd.append("--include-module=numpy.random.mtrand")
            cmd.append("--include-module=numpy.fft")
            self.log("已配置 NumPy 库支持")

        # ========== SciPy 支持 ==========
        if uses_scipy:
            self.log(f"\n配置 SciPy 库支持...")
            cmd.append("--include-package=scipy")
            cmd.append("--include-package-data=scipy")
            cmd.append("--include-module=scipy.integrate")
            cmd.append("--include-module=scipy.optimize")
            cmd.append("--include-module=scipy.linalg")
            cmd.append("--include-module=scipy.sparse")
            cmd.append("--include-module=scipy.special")
            cmd.append("--include-module=scipy.stats")
            cmd.append("--include-module=scipy.signal")
            self.log("已配置 SciPy 库支持")

        # ========== Pandas 支持 ==========
        if uses_pandas:
            self.log(f"\n配置 Pandas 库支持...")
            cmd.append("--include-package=pandas")
            cmd.append("--include-package-data=pandas")
            cmd.append("--include-module=pandas._libs")
            cmd.append("--include-module=pandas._libs.tslibs")
            cmd.append("--include-module=pandas._libs.tslibs.np_datetime")
            cmd.append("--include-module=pandas._libs.tslibs.nattype")
            cmd.append("--include-module=pandas._libs.tslibs.timedeltas")
            cmd.append("--include-module=pandas.core.ops")
            self.log("已配置 Pandas 库支持")

        # ========== OpenCV 支持 ==========
        if uses_opencv:
            self.log(f"\n配置 OpenCV 库支持...")
            cmd.append("--include-package=cv2")
            cmd.append("--include-package-data=cv2")
            cmd.append("--include-module=cv2")
            # OpenCV 依赖 numpy
            if not uses_numpy:
                cmd.append("--include-module=numpy")
                cmd.append("--include-module=numpy.core._multiarray_umath")
            self.log("已配置 OpenCV 库支持")

        # ========== Pillow 支持 ==========
        if uses_pillow:
            self.log(f"\n配置 Pillow 库支持...")
            cmd.append("--include-package=PIL")
            cmd.append("--include-package-data=PIL")
            cmd.append("--include-module=PIL._tkinter_finder")
            cmd.append("--include-module=PIL._imaging")
            cmd.append("--include-module=PIL.Image")
            cmd.append("--include-module=PIL.ImageDraw")
            cmd.append("--include-module=PIL.ImageFont")
            self.log("已配置 Pillow 库支持")

        # ========== SQLAlchemy 支持 ==========
        if uses_sqlalchemy:
            self.log(f"\n配置 SQLAlchemy 库支持...")
            cmd.append("--include-package=sqlalchemy")
            cmd.append("--include-package-data=sqlalchemy")
            cmd.append("--include-module=sqlalchemy.dialects.sqlite")
            cmd.append("--include-module=sqlalchemy.dialects.mysql")
            cmd.append("--include-module=sqlalchemy.dialects.postgresql")
            cmd.append("--include-module=sqlalchemy.sql.default_comparator")
            cmd.append("--include-module=sqlalchemy.ext.baked")
            self.log("已配置 SQLAlchemy 库支持")

        # ========== Cryptography 支持 ==========
        if uses_cryptography:
            self.log(f"\n配置 Cryptography 库支持...")
            cmd.append("--include-package=cryptography")
            cmd.append("--include-package-data=cryptography")
            cmd.append("--include-module=cryptography.hazmat.backends.openssl")
            cmd.append("--include-module=cryptography.hazmat.bindings._rust")
            cmd.append("--include-module=_cffi_backend")
            self.log("已配置 Cryptography 库支持")

        # ========== Requests 支持 ==========
        if uses_requests:
            self.log(f"\n配置 Requests 库支持...")
            cmd.append("--include-package=requests")
            cmd.append("--include-module=urllib3")
            cmd.append("--include-module=charset_normalizer")
            cmd.append("--include-module=idna")
            # requests 依赖 certifi，确保包含
            if not uses_certifi:
                cmd.append("--include-package=certifi")
                cmd.append("--include-package-data=certifi")
                self.log("  已自动包含 certifi（SSL证书）")
            self.log("已配置 Requests 库支持")

        # ========== Certifi 支持（SSL证书数据文件）==========
        if uses_certifi:
            self.log(f"\n配置 Certifi 库支持...")
            cmd.append("--include-package=certifi")
            cmd.append("--include-package-data=certifi")
            self.log("已配置 Certifi 库支持（包含CA证书）")

        # LTO链接时优化
        if config.get("lto", True):
            cmd.append("--lto=yes")
            self.log("\n已启用LTO链接时优化，这将：")
            self.log("  - 减小最终可执行文件体积")
            self.log("  - 提升运行时性能")
            self.log("  - 编译时间会略微增加")

        # Python优化
        if config.get("python_opt", True):
            cmd.append("--python-flag=no_docstrings")
            cmd.append("--python-flag=no_asserts")
            self.log("\n已启用Python字节码优化，这将：")
            self.log("  - 移除文档字符串（docstrings）")
            self.log("  - 禁用断言语句（assert）")

        # 与 1.bat 一致的优化参数
        # 注意：--no-pyi-file 仅在模块模式下有效，standalone模式不需要
        # 注意：--follow-stdlib 是 standalone 模式的默认行为，无需显式指定
        cmd.append("--no-prefer-source-code")
        cmd.append("--assume-yes-for-downloads")

        # 输出目录
        cmd.append(f"--output-dir={output_dir}")

        # 显示输出信息
        cmd.append("--show-progress")
        cmd.append("--show-memory")

        # 直接使用原始脚本作为入口（与 1.bat 一致，不注入任何代码）
        cmd.append(script_path)

        self.log("\n图标说明:")
        self.log("  ✓ 图标已通过 --windows-icon-from-ico 嵌入到 exe 资源中")
        self.log("  ✓ 图标数据文件已包含（icon.ico）")
        self.log("  ✓ 任务栏和窗口图标由 Windows/应用程序自动处理")

        # 执行打包
        self.log(f"执行命令: {' '.join(cmd)}")
        self.log("")
        self.log("注意: Nuitka首次运行可能需要较长时间下载依赖...")
        self.log("")

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )

            # 通知GUI进程已创建
            if self.process_callback:
                self.process_callback(process)

            # 实时输出日志
            if process.stdout:
                for line in process.stdout:
                    # 检查是否取消
                    if self.cancel_flag and self.cancel_flag():
                        self.log("检测到取消请求，正在终止进程...")
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        return False, "打包已被用户取消"

                    self.log(line.rstrip())

            process.wait()

            # 检查是否被取消
            if self.cancel_flag and self.cancel_flag():
                return False, "打包已被用户取消"

            if process.returncode == 0:
                # Nuitka输出文件在output_dir中
                # 如果使用了临时名称，需要重命名
                if temp_name:
                    temp_exe_name = f"{temp_name}.exe"
                    # Nuitka的.dist目录名称基于输入脚本的基本名（不是输出文件名）
                    script_base_name = Path(script_path).stem  # main.py -> main
                    possible_temp_paths = [
                        os.path.join(output_dir, temp_exe_name),
                        os.path.join(output_dir, temp_name + ".dist", temp_exe_name),
                        os.path.join(output_dir, script_base_name + ".dist", temp_exe_name),
                        os.path.join(output_dir, script_base_name + ".dist", f"{script_base_name}.exe"),
                    ]

                    self.log("\n" + "=" * 50)
                    self.log("处理中文程序名...")
                    self.log("=" * 50)
                    self.log(f"临时名称: {temp_name}")
                    self.log(f"最终名称: {script_name}")

                    # 列出输出目录中的所有内容
                    try:
                        items_in_output = os.listdir(output_dir)
                        self.log(f"输出目录中的项目: {items_in_output}")
                    except Exception as e:
                        self.log(f"无法列出输出目录: {str(e)}")

                    self.log("查找临时文件...")
                    temp_exe_path = None
                    for path in possible_temp_paths:
                        self.log(f"检查: {path}")
                        if os.path.exists(path):
                            temp_exe_path = path
                            self.log(f"找到临时文件: {path}")
                            break

                    if temp_exe_path:
                        final_exe = os.path.join(os.path.dirname(temp_exe_path), f"{script_name}.exe")
                        self.log(f"目标文件路径: {final_exe}")

                        try:
                            # 如果目标文件已存在，先删除
                            if os.path.exists(final_exe):
                                os.remove(final_exe)
                                self.log("删除已存在的目标文件")

                            # 使用 shutil.move 更可靠
                            import shutil
                            shutil.move(temp_exe_path, final_exe)
                            self.log(f"重命名成功: {temp_exe_name} -> {script_name}.exe")
                            exe_path = final_exe
                        except Exception as e:
                            self.log(f"重命名文件时出错: {str(e)}")
                            self.log(f"将使用临时文件名: {temp_name}.exe")
                            exe_path = temp_exe_path
                    else:
                        self.log("警告: 未在以下位置找到临时输出文件:")
                        for path in possible_temp_paths:
                            self.log(f"  - {path}")

                        # 尝试直接查找中文名文件（可能直接成功了）
                        script_base_name = Path(script_path).stem
                        possible_final_paths = [
                            os.path.join(output_dir, f"{script_name}.exe"),
                            os.path.join(output_dir, script_name + ".dist", f"{script_name}.exe"),
                            os.path.join(output_dir, script_base_name + ".dist", f"{script_name}.exe"),
                            os.path.join(output_dir, script_base_name + ".dist", f"{script_base_name}.exe"),
                        ]

                        exe_path = None
                        for path in possible_final_paths:
                            if os.path.exists(path):
                                self.log(f"找到最终文件（可能已直接生成）: {path}")
                                exe_path = path
                                break

                        if not exe_path:
                            # 尝试查找任何 .exe 文件
                            self.log("尝试在输出目录中查找任何 .exe 文件...")
                            for root, dirs, files in os.walk(output_dir):
                                exe_files = [f for f in files if f.endswith('.exe')]
                                if exe_files:
                                    self.log(f"在 {root} 找到: {exe_files}")
                                    found_exe = os.path.join(root, exe_files[0])
                                    self.log(f"使用找到的 exe 文件: {found_exe}")
                                    # 尝试重命名或移动到正确位置
                                    try:
                                        final_exe = os.path.join(output_dir, f"{script_name}.exe")
                                        import shutil
                                        if os.path.exists(final_exe):
                                            os.remove(final_exe)
                                        shutil.copy2(found_exe, final_exe)
                                        self.log(f"成功复制并重命名为: {script_name}.exe")
                                        exe_path = final_exe
                                    except Exception as e:
                                        self.log(f"复制文件失败: {str(e)}")
                                        exe_path = found_exe
                                    break

                            if not exe_path:
                                return False, "打包完成，但未找到输出文件"
                else:
                    exe_name = f"{script_name}.exe"
                    # Nuitka的.dist目录名称基于输入脚本的基本名（不是输出文件名）
                    script_base_name = Path(script_path).stem
                    possible_paths = [
                        os.path.join(output_dir, exe_name),
                        os.path.join(output_dir, script_name + ".dist", exe_name),
                        os.path.join(output_dir, build_name + ".dist", exe_name),
                        os.path.join(output_dir, script_base_name + ".dist", exe_name),
                        os.path.join(output_dir, script_base_name + ".dist", f"{script_base_name}.exe"),
                    ]

                    self.log("\n查找输出文件...")
                    exe_path = None
                    for path in possible_paths:
                        self.log(f"检查: {path}")
                        if os.path.exists(path):
                            exe_path = path
                            self.log(f"找到输出文件: {path}")
                            break

                    if not exe_path:
                        # 尝试查找任何 .exe 文件
                        self.log("在预定义路径未找到，尝试在输出目录中查找任何 .exe 文件...")
                        for root, dirs, files in os.walk(output_dir):
                            exe_files = [f for f in files if f.endswith('.exe')]
                            if exe_files:
                                self.log(f"在 {root} 找到: {exe_files}")
                                found_exe = os.path.join(root, exe_files[0])
                                self.log(f"使用找到的 exe 文件: {found_exe}")
                                exe_path = found_exe
                                break

                        if not exe_path:
                            self.log("错误: 未在输出目录中找到任何 .exe 文件")
                            return False, "打包完成，但未找到输出文件"

                if exe_path:
                    # 清理构建缓存
                    if config.get("clean", True):
                        self.log("\n清理构建缓存...")
                        self.log(f"输出目录: {output_dir}")
                        self.log(f"脚本名称: {script_name}, 构建名称: {build_name}")

                        # 判断是否为单文件模式
                        is_onefile = config.get("onefile", True)
                        self.log(f"打包模式: {'单文件' if is_onefile else '独立目录'}")

                        # 确定最终exe所在的目录（不能删除）
                        exe_dir = os.path.dirname(exe_path)
                        self.log(f"最终程序位置: {exe_path}")

                        # 扫描输出目录，找出所有 Nuitka 缓存目录
                        cache_dirs = []

                        try:
                            # 列出输出目录中的所有项
                            if os.path.exists(output_dir):
                                for item in os.listdir(output_dir):
                                    item_path = os.path.join(output_dir, item)
                                    # 检查是否是目录，并且是 Nuitka 缓存目录
                                    if os.path.isdir(item_path):
                                        # .build 和 .onefile-build 总是可以删除
                                        if item.endswith('.build') or item.endswith('.onefile-build'):
                                            cache_dirs.append(item_path)
                                            self.log(f"发现缓存目录: {item}")
                                        # .dist 目录需要判断
                                        elif item.endswith('.dist'):
                                            # 如果是单文件模式，.dist 是缓存，可以删除
                                            # 如果是独立目录模式，需要检查是否包含最终的exe
                                            if is_onefile:
                                                cache_dirs.append(item_path)
                                                self.log(f"发现缓存目录: {item} (单文件模式)")
                                            else:
                                                # 检查这个.dist目录是否包含最终的exe
                                                if os.path.normpath(item_path) == os.path.normpath(exe_dir):
                                                    self.log(f"保留目录: {item} (包含最终程序)")
                                                else:
                                                    cache_dirs.append(item_path)
                                                    self.log(f"发现缓存目录: {item}")
                        except Exception as e:
                            self.log(f"扫描缓存目录时出错: {str(e)}")

                        # 清理所有找到的缓存目录
                        cleaned_count = 0
                        for cache_dir in cache_dirs:
                            try:
                                import shutil
                                shutil.rmtree(cache_dir)
                                self.log(f"✓ 已清理: {os.path.basename(cache_dir)}")
                                cleaned_count += 1
                            except Exception as e:
                                self.log(f"✗ 清理 {os.path.basename(cache_dir)} 时出错: {str(e)}")

                        # 清理临时生成的图标文件 (app_icon.ico)
                        temp_icon_path = os.path.join(output_dir, "app_icon.ico")
                        if os.path.exists(temp_icon_path):
                            try:
                                os.remove(temp_icon_path)
                                self.log(f"✓ 已清理: app_icon.ico")
                                cleaned_count += 1
                            except Exception as e:
                                self.log(f"✗ 清理临时图标文件时出错: {str(e)}")

                        # 清理资源文件（.rc 和 .res）
                        rc_file_path = os.path.join(output_dir, "version_info.rc")
                        if os.path.exists(rc_file_path):
                            try:
                                os.remove(rc_file_path)
                                self.log(f"✓ 已清理: version_info.rc")
                                cleaned_count += 1
                            except Exception as e:
                                self.log(f"✗ 清理资源文件时出错: {str(e)}")

                        res_file_path = os.path.join(output_dir, "version_info.res")
                        if os.path.exists(res_file_path):
                            try:
                                os.remove(res_file_path)
                                self.log(f"✓ 已清理: version_info.res")
                                cleaned_count += 1
                            except Exception as e:
                                self.log(f"✗ 清理资源文件时出错: {str(e)}")

                        # 清理其他可能的临时资源文件（RC开头的临时文件）
                        try:
                            for item in os.listdir(output_dir):
                                if os.path.isfile(os.path.join(output_dir, item)):
                                    # 清理形如 RCa08700 的临时文件
                                    if item.startswith('RC') and len(item) <= 10 and item[2:].isalnum():
                                        temp_file = os.path.join(output_dir, item)
                                        try:
                                            os.remove(temp_file)
                                            self.log(f"✓ 已清理: {item}")
                                            cleaned_count += 1
                                        except Exception as e:
                                            self.log(f"✗ 清理 {item} 时出错: {str(e)}")
                        except Exception as e:
                            self.log(f"扫描临时文件时出错: {str(e)}")

                        if cleaned_count > 0:
                            self.log(f"共清理了 {cleaned_count} 个缓存文件/目录")
                        else:
                            self.log("无需清理缓存文件")

                    # 保存 exe 路径用于后续打开目录
                    self._last_exe_path = exe_path
                    return True, f"打包成功！\n\n输出文件: {exe_path}"

                return False, "打包完成，但未找到输出文件"
            else:
                return False, f"Nuitka执行失败，返回码: {process.returncode}"

        except Exception as e:
            return False, f"执行Nuitka时出错: {str(e)}"



    def _detect_actual_imports(self, script_path: str, project_dir: Optional[str] = None) -> Set[str]:
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
                dirs[:] = [d for d in dirs if d not in {'.venv', 'venv', 'build', 'dist', '__pycache__', '.git', 'node_modules', 'site-packages'}]

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

    def _extract_gcc(self, gcc_zip_path: str, extract_base_dir: str) -> Optional[str]:
        """
        解压GCC工具链到下载目录

        Args:
            gcc_zip_path: GCC zip文件路径
            extract_base_dir: 解压基础目录（通常是下载目录）

        Returns:
            解压后的mingw64目录路径，失败返回None
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(gcc_zip_path):
                self.log(f"错误: GCC文件不存在: {gcc_zip_path}")
                return None

            # 获取文件大小（正常的GCC包不低于250MB）
            file_size = os.path.getsize(gcc_zip_path)
            min_size = 250 * 1024 * 1024  # 250MB
            if file_size < min_size:
                self.log(f"错误: GCC文件太小({file_size / 1024 / 1024:.1f} MB)，正常的GCC包不低于250MB，可能已损坏或下载不完整")
                return None

            # 确保解压目录存在
            os.makedirs(extract_base_dir, exist_ok=True)

            # 首先检查解压目录中是否已存在mingw64目录（必须是mingw64）
            mingw64_path = os.path.join(extract_base_dir, "mingw64")
            if os.path.exists(mingw64_path) and os.path.isdir(mingw64_path):
                # 验证该目录是否有效（检查bin目录和gcc.exe）
                bin_dir = os.path.join(mingw64_path, "bin")
                gcc_exe = os.path.join(bin_dir, "gcc.exe")
                if os.path.exists(bin_dir) and os.path.exists(gcc_exe):
                    self.log(f"发现已解压的GCC工具链: {mingw64_path}")
                    return mingw64_path

            self.log("正在验证zip文件...")

            # 检查zip文件是否完整
            if not zipfile.is_zipfile(gcc_zip_path):
                self.log(f"错误: 指定的文件不是有效的zip文件: {gcc_zip_path}")
                self.log(f"文件大小: {file_size} 字节")
                return None

            # 测试zip文件完整性
            with zipfile.ZipFile(gcc_zip_path, "r") as zip_ref:
                # 检查文件列表
                file_list = zip_ref.namelist()
                if len(file_list) == 0:
                    self.log("错误: zip文件为空")
                    return None

                # 检查是否包含mingw64目录
                has_mingw64 = any(
                    name.startswith("mingw64/") or name == "mingw64"
                    for name in file_list
                )
                if not has_mingw64:
                    self.log("错误: zip文件中未找到mingw64目录")
                    self.log("请确保下载的是正确的GCC工具链压缩包（应包含mingw64目录）")
                    return None

                # 测试所有文件是否可读
                bad_file = zip_ref.testzip()
                if bad_file:
                    self.log(f"错误: zip文件中包含损坏的文件: {bad_file}")
                    return None

            self.log(f"zip文件验证通过，开始解压 GCC (大小: {file_size / 1024 / 1024:.1f} MB)...")

            # 解压到下载目录
            with zipfile.ZipFile(gcc_zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_base_dir)

            self.log("GCC工具链解压完成")

            # 验证解压后的mingw64目录
            if os.path.exists(mingw64_path) and os.path.isdir(mingw64_path):
                bin_dir = os.path.join(mingw64_path, "bin")
                gcc_exe = os.path.join(bin_dir, "gcc.exe")
                if os.path.exists(bin_dir) and os.path.exists(gcc_exe):
                    self.log(f"✓ GCC工具链解压成功: {mingw64_path}")
                    return mingw64_path
                else:
                    self.log("错误: 解压后的mingw64目录结构不正确，缺少bin/gcc.exe")
                    return None
            else:
                self.log("错误: 解压后未找到mingw64目录")
                self.log("请确保下载的是正确的GCC工具链压缩包")
                return None

        except zipfile.BadZipFile as e:
            self.log(f"错误: zip文件已损坏: {e}")
            return None
        except PermissionError as e:
            self.log(f"错误: 权限不足，无法解压到目标目录: {e}")
            return None
        except Exception as e:
            self.log(f"解压GCC时出错: {e}")
            return None
