"""
版本信息处理模块

本模块负责处理 Windows 可执行文件的版本信息，包括：
- 版本号格式化和转换
- 命令行参数生成
- Windows 资源文件(.rc)生成和编译
- 使用 rcedit/Resource Hacker 后处理嵌入版本信息

从 packager.py 拆分出来，遵循单一职责原则。
"""

import os
import re
import shutil
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Tuple

from utils.constants import CREATE_NO_WINDOW


class VersionInfoHandler:
    """版本信息处理器"""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        """
        初始化版本信息处理器

        Args:
            log_callback: 日志回调函数
        """
        self.log = log_callback or print
        self._pending_version_info: Optional[Dict] = None

    def normalize_windows_version(self, version_str: str) -> str:
        """
        规范化 Windows 版本号，确保符合格式要求。

        Windows 版本号必须是最多 4 个整数，每个整数不超过 65535。
        例如：1.0.0, 1.2.3.4

        处理规则：
        - 日期格式 YYYYMMDD：转换为 MM.DD.0.0
        - 普通版本号：保留前4段
        - 非数字部分：忽略

        Args:
            version_str: 原始版本号字符串

        Returns:
            规范化后的版本号字符串
        """
        if not version_str:
            return "1.0.0.0"

        # 移除前缀 v 或 V
        version_str = version_str.lstrip("vV")

        # 尝试解析为日期格式 YYYYMMDD
        if len(version_str) == 8 and version_str.isdigit():
            month = version_str[4:6]
            day = version_str[6:8]
            return f"{int(month)}.{int(day)}.0.0"

        # 分割版本号
        parts = version_str.replace("-", ".").replace("_", ".").split(".")
        result = []
        for part in parts[:4]:
            # 只保留数字部分
            digits = "".join(c for c in part if c.isdigit())
            if digits:
                num = int(digits)
                # 限制在 65535 以内
                result.append(str(min(num, 65535)))
            else:
                result.append("0")

        # 补足4段
        while len(result) < 4:
            result.append("0")

        return ".".join(result[:4])

    def sanitize_for_cmdline(self, text: str) -> str:
        """
        将文本转换为命令行安全的 ASCII 格式。

        解决 Nuitka 2.8.x 不支持 --windows-force-rc-file 时，
        中文字符导致 MSVC 编译器报错的问题（C4819/C2001 错误）。

        Args:
            text: 原始文本

        Returns:
            ASCII 安全的文本
        """
        if not text:
            return text

        try:
            text.encode('ascii')
            return text
        except UnicodeEncodeError:
            # 移除非 ASCII 字符，只保留 ASCII 部分
            ascii_chars = []
            for char in text:
                if ord(char) < 128:
                    ascii_chars.append(char)
                elif ascii_chars and ascii_chars[-1] != ' ':
                    ascii_chars.append(' ')

            result = ''.join(ascii_chars).strip()
            return result if result else "Application"

    def convert_version_to_windows_format(self, version_str: str) -> str:
        """
        将版本号转换为 Windows 格式（4 个整数：major.minor.build.revision）

        Windows 版本号要求：
        - 必须是 4 个整数
        - 每个整数不能超过 65535

        Args:
            version_str: 原始版本号字符串，如 "1.0.20260123" 或 "1.0.0"

        Returns:
            Windows 格式的版本号，如 "1.0.2026.123" 或 "1.0.0.0"
        """
        if not version_str:
            return "1.0.0.0"

        # 移除前缀 v 或 V
        version_str = version_str.lstrip("vV")

        # 移除所有非数字和非点号的字符
        cleaned = re.sub(r'[^\d.]', '', version_str)

        # 按点号分割
        parts = cleaned.split('.')

        # 提取数字部分并处理超过 65535 的情况
        numeric_parts = []
        for part in parts:
            if part:
                try:
                    num = int(part)
                    # Windows 版本号每个部分不能超过 65535
                    if num > 65535:
                        # 如果数字超过 65535，尝试拆分
                        # 例如：20260123 -> 2026 和 123（年份和日期）
                        if len(part) == 8 and part.isdigit():
                            # 可能是日期格式 YYYYMMDD
                            year = int(part[:4])
                            month = int(part[4:6])
                            day = int(part[6:8])
                            # 限制在有效范围内
                            numeric_parts.append(str(min(year, 65535)))
                            numeric_parts.append(str(min(month, 65535)))
                            numeric_parts.append(str(min(day, 65535)))
                        else:
                            # 其他情况：取前 5 位和后 5 位（如果可能）
                            num_str = str(num)
                            if len(num_str) > 5:
                                # 拆分：前部分和后部分
                                mid = len(num_str) // 2
                                part1 = int(num_str[:mid])
                                part2 = int(num_str[mid:])
                                numeric_parts.append(str(min(part1, 65535)))
                                numeric_parts.append(str(min(part2, 65535)))
                            else:
                                # 如果无法合理拆分，直接限制为 65535
                                numeric_parts.append("65535")
                    else:
                        numeric_parts.append(str(num))
                except ValueError:
                    continue

        # 如果没有任何数字部分，返回默认版本
        if not numeric_parts:
            return "1.0.0.0"

        # 确保至少有 4 个部分，不足的用 0 补齐
        while len(numeric_parts) < 4:
            numeric_parts.append("0")

        # 如果超过 4 个部分，只取前 4 个
        if len(numeric_parts) > 4:
            numeric_parts = numeric_parts[:4]

        return ".".join(numeric_parts)

    def escape_for_windows_version_info(self, text: str) -> str:
        r"""
        转义 Windows 版本信息中的特殊字符，确保能正确显示。

        对于 subprocess 的列表形式，不需要手动转义，
        subprocess 会自动处理引号和特殊字符。

        Args:
            text: 需要转义的文本

        Returns:
            转义后的文本
        """
        if not text:
            return text
        return text

    def add_version_info_cmdline(
        self,
        cmd: List[str],
        product_name: str,
        company_name: str,
        file_description: str,
        copyright_text: str,
        version_str: str,
        sanitize_non_ascii: bool = False
    ) -> None:
        """
        通过命令行参数添加 Windows 版本信息

        Args:
            cmd: 命令行参数列表（会被修改）
            product_name: 产品名称
            company_name: 公司名称
            file_description: 文件描述
            copyright_text: 版权信息
            version_str: 版本号
            sanitize_non_ascii: 是否将非 ASCII 字符转换为安全格式
        """
        if sanitize_non_ascii:
            product_name = self.sanitize_for_cmdline(product_name)
            company_name = self.sanitize_for_cmdline(company_name)
            file_description = self.sanitize_for_cmdline(file_description)
            copyright_text = self.sanitize_for_cmdline(copyright_text)

        def add_version_arg(key: str, value: str) -> None:
            """添加版本信息参数"""
            if not value:
                return
            # 使用 subprocess 列表模式时，不需要手动添加引号
            cmd.append(f"{key}={value}")

        if product_name:
            add_version_arg("--windows-product-name", product_name)
            self.log(f"  ✓ 产品名称: {product_name}")
        if company_name:
            add_version_arg("--windows-company-name", company_name)
            self.log(f"  ✓ 公司名称: {company_name}")
        if file_description:
            add_version_arg("--windows-file-description", file_description)
            self.log(f"  ✓ 文件描述: {file_description}")
        if copyright_text:
            add_version_arg("--copyright", copyright_text)
            self.log(f"  ✓ 版权信息: {copyright_text}")
        if version_str:
            # 转换为 Windows 格式（4 个整数）
            windows_version = self.convert_version_to_windows_format(version_str)
            cmd.append(f"--windows-product-version={windows_version}")
            cmd.append(f"--windows-file-version={windows_version}")
            self.log(f"  ✓ 版本号: {version_str} (Windows格式: {windows_version})")

    def set_pending_version_info(self, info: Dict) -> None:
        """
        设置待后处理的版本信息

        Args:
            info: 版本信息字典
        """
        self._pending_version_info = info

    def get_pending_version_info(self) -> Optional[Dict]:
        """
        获取待后处理的版本信息

        Returns:
            版本信息字典，如果没有则返回 None
        """
        return self._pending_version_info

    def clear_pending_version_info(self) -> None:
        """清除待后处理的版本信息"""
        self._pending_version_info = None


class WindowsResourceHandler:
    """Windows 资源文件处理器"""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        """
        初始化 Windows 资源处理器

        Args:
            log_callback: 日志回调函数
        """
        self.log = log_callback or print
        self.version_handler = VersionInfoHandler(log_callback)

    def check_windows_sdk_support(self) -> Tuple[bool, str]:
        """
        检查系统是否支持中文版本信息（Windows SDK/Visual Studio）

        Returns:
            (是否支持, 描述信息)
        """
        rc_exe = self.find_rc_exe()
        if rc_exe:
            include_dirs = self.get_windows_sdk_include_dirs()
            if not include_dirs:
                return False, "检测到 rc.exe，但未找到 Windows SDK Include 目录（windows.h），请安装 Windows SDK C++ 组件"

            if "Windows Kits" in rc_exe:
                return True, f"检测到 Windows SDK (rc.exe: {rc_exe})"
            elif "Visual Studio" in rc_exe:
                return True, f"检测到 Visual Studio (rc.exe: {rc_exe})"
            else:
                return True, f"检测到资源编译器 (rc.exe: {rc_exe})"

        # 检查是否存在 Windows SDK 或 Visual Studio 目录
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

    def find_rc_exe(self) -> Optional[str]:
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

        for sdk_root in sdk_roots:
            if not os.path.exists(sdk_root):
                continue

            try:
                versions = []
                for item in os.listdir(sdk_root):
                    item_path = os.path.join(sdk_root, item)
                    if os.path.isdir(item_path) and item.startswith("10."):
                        versions.append(item)

                versions.sort(reverse=True)

                for version in versions:
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
                for vs_year in sorted(os.listdir(vs_root), reverse=True):
                    vs_year_path = os.path.join(vs_root, vs_year)
                    if not os.path.isdir(vs_year_path):
                        continue

                    for edition in os.listdir(vs_year_path):
                        sdk_bin = os.path.join(vs_year_path, edition, "VC", "Tools", "MSVC")
                        if not os.path.exists(sdk_bin):
                            continue

                        for msvc_ver in sorted(os.listdir(sdk_bin), reverse=True):
                            for arch in ["x64", "x86"]:
                                rc_path = os.path.join(
                                    sdk_bin, msvc_ver, "bin", f"Host{arch}", arch, "rc.exe"
                                )
                                if os.path.exists(rc_path):
                                    return rc_path
            except Exception:
                continue

        return None

    def get_windows_sdk_include_dirs(self) -> List[str]:
        """
        获取 Windows SDK Include 目录

        Returns:
            Include 目录列表
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

    def create_version_resource_file(
        self,
        output_dir: str,
        script_name: str,
        product_name: str,
        company_name: str,
        file_description: str,
        copyright_text: str,
        version_str: str,
        icon_path: Optional[str] = None
    ) -> Optional[str]:
        """
        创建 Windows 资源文件(.rc)并编译为 .res 文件

        Args:
            output_dir: 输出目录
            script_name: 脚本名称
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

            def escape_rc_string(s: str) -> str:
                """转义 .rc 文件中的特殊字符"""
                if not s:
                    return ""
                s = s.replace("\\", "\\\\")
                s = s.replace('"', '\\"')
                return s

            product_name_escaped = escape_rc_string(product_name)
            company_name_escaped = escape_rc_string(company_name)
            file_description_escaped = escape_rc_string(file_description)
            copyright_text_escaped = escape_rc_string(copyright_text)

            # 构建 .rc 文件内容
            rc_content = '''// 版本信息资源 - 由 Python打包工具 自动生成
// 支持中文字符

#ifndef VS_VERSION_INFO
#define VS_VERSION_INFO 1
#endif
#define VOS_NT_WINDOWS32 0x00040004L
#define VFT_APP 0x00000001L

'''
            if icon_path:
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

            # 写入 .rc 文件
            rc_file_path = os.path.join(output_dir, "version_info.rc")
            with open(rc_file_path, "w", encoding="utf-8-sig") as f:
                f.write(rc_content)

            self.log(f"  已创建资源文件: {rc_file_path}")

            # 查找 rc.exe
            rc_exe = self.find_rc_exe()
            if not rc_exe:
                self.log("  ⚠️  未找到 Windows SDK 资源编译器 (rc.exe)")
                return None

            self.log(f"  使用资源编译器: {rc_exe}")

            # 编译 .rc 为 .res
            res_file_path = os.path.join(output_dir, "version_info.res")
            include_dirs = self.get_windows_sdk_include_dirs()
            include_args: List[str] = []
            for include_dir in include_dirs:
                include_args.extend(["/I", include_dir])

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
                if result.stderr:
                    self.log(f"  stderr: {result.stderr.strip()}")
                return None

        except Exception as e:
            self.log(f"  ⚠️  创建资源文件时出错: {str(e)}")
            return None


class RceditHandler:
    """rcedit 工具处理器"""

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        """
        初始化 rcedit 处理器

        Args:
            log_callback: 日志回调函数
        """
        self.log = log_callback or print
        self.version_handler = VersionInfoHandler(log_callback)
        self.resource_handler = WindowsResourceHandler(log_callback)

    def _get_tools_dir_rcedit_path(self) -> str:
        """
        获取项目 tools 目录下的 rcedit.exe 路径

        Returns:
            tools/rcedit.exe 的绝对路径
        """
        tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
        return os.path.abspath(os.path.join(tools_dir, "rcedit.exe"))

    def find_rcedit(self) -> Optional[str]:
        """
        查找 rcedit 工具

        优先查找项目 tools 目录，其次查找其他常见位置

        Returns:
            rcedit.exe 的路径
        """
        # 优先检查项目 tools 目录
        tools_rcedit = self._get_tools_dir_rcedit_path()
        if os.path.exists(tools_rcedit):
            return tools_rcedit

        # 其他备选位置
        fallback_paths = [
            os.path.join(os.path.dirname(sys.executable), "rcedit.exe"),
            os.path.join(os.path.dirname(sys.executable), "Scripts", "rcedit.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "rcedit", "rcedit.exe"),
        ]

        for path in fallback_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                return abs_path

        return None

    def download_rcedit(self) -> Optional[str]:
        """
        下载 rcedit 工具

        Returns:
            下载后的 rcedit.exe 路径
        """
        try:
            try:
                import requests
            except ImportError:
                requests = None

            import urllib.error
            import urllib.request

            # 使用多个下载源，优先直接从 GitHub 下载
            urls = [
                "https://github.com/electron/rcedit/releases/download/v2.0.0/rcedit-x64.exe",
                "https://mirror.ghproxy.com/https://github.com/electron/rcedit/releases/download/v2.0.0/rcedit-x64.exe",
                "https://gh-proxy.com/https://github.com/electron/rcedit/releases/download/v2.0.0/rcedit-x64.exe",
            ]

            tools_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools")
            os.makedirs(tools_dir, exist_ok=True)

            rcedit_path = os.path.join(tools_dir, "rcedit.exe")

            for url in urls:
                try:
                    self.log(f"  正在下载 rcedit: {url}")
                    content = None

                    if requests:
                        response = requests.get(url, timeout=60, allow_redirects=True)
                        if response.status_code == 200:
                            content = response.content
                    else:
                        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                        with urllib.request.urlopen(req, timeout=60) as resp:
                            if resp.status == 200:
                                content = resp.read()

                    if content:
                        # 验证下载的内容是否为有效的 PE 文件（Windows 可执行文件）
                        if not self._validate_pe_file(content):
                            self.log("  下载的文件不是有效的 Windows 可执行文件，跳过此源")
                            continue

                        with open(rcedit_path, "wb") as f:
                            f.write(content)
                        self.log(f"  ✓ rcedit 下载成功: {rcedit_path}")
                        return rcedit_path

                except Exception as e:
                    self.log(f"  下载失败: {str(e)}")
                    continue

            self.log("  所有下载源均失败")
            return None

        except Exception as e:
            self.log(f"  下载 rcedit 时出错: {str(e)}")
            return None

    def _validate_pe_file(self, content: bytes) -> bool:
        """
        验证内容是否为有效的 Windows PE 可执行文件

        Args:
            content: 文件内容

        Returns:
            是否为有效的 PE 文件
        """
        if len(content) < 64:
            return False

        # 检查 DOS 头魔数 "MZ"
        if content[:2] != b'MZ':
            return False

        # 获取 PE 头偏移量
        pe_offset = int.from_bytes(content[60:64], 'little')
        if pe_offset + 4 > len(content):
            return False

        # 检查 PE 签名 "PE\0\0"
        if content[pe_offset:pe_offset + 4] != b'PE\x00\x00':
            return False

        return True

    def _is_valid_rcedit(self, path: str) -> bool:
        """
        检查 rcedit.exe 是否有效

        Args:
            path: rcedit.exe 路径

        Returns:
            是否有效
        """
        if not os.path.exists(path):
            return False

        try:
            with open(path, 'rb') as f:
                content = f.read(1024)  # 只读取前 1KB 用于验证
                return self._validate_pe_file(content)
        except Exception:
            return False

    def find_or_download_rcedit(self) -> Optional[str]:
        """
        查找或下载 rcedit 工具

        逻辑：
        1. 优先检查项目 tools 目录下的 rcedit.exe
        2. 如果存在且有效，直接返回
        3. 如果不存在或损坏，执行下载到 tools 目录
        4. 如果 tools 目录下没有，再检查其他备选位置

        Returns:
            rcedit.exe 的路径
        """
        # 优先检查项目 tools 目录
        tools_rcedit = self._get_tools_dir_rcedit_path()

        if os.path.exists(tools_rcedit):
            # tools 目录下存在 rcedit.exe，验证是否有效
            if self._is_valid_rcedit(tools_rcedit):
                self.log(f"  使用项目 tools 目录下的 rcedit: {tools_rcedit}")
                return tools_rcedit
            else:
                # 存在但已损坏，删除后重新下载
                self.log("  检测到 tools 目录下的 rcedit.exe 已损坏，将重新下载...")
                try:
                    os.remove(tools_rcedit)
                except Exception:
                    pass
                return self.download_rcedit()

        # tools 目录下不存在，检查其他备选位置
        rcedit = self.find_rcedit()
        if rcedit:
            # 在其他位置找到了，验证是否有效
            if self._is_valid_rcedit(rcedit):
                self.log(f"  使用备选位置的 rcedit: {rcedit}")
                return rcedit
            else:
                self.log("  检测到备选位置的 rcedit.exe 已损坏，将下载到 tools 目录...")
                try:
                    os.remove(rcedit)
                except Exception:
                    pass

        # 没有找到有效的 rcedit，下载到 tools 目录
        self.log("  tools 目录下未找到 rcedit.exe，开始下载...")
        return self.download_rcedit()

    def post_process_add_version_info(self, exe_path: str, version_info: Dict) -> bool:
        """
        后处理：将版本信息嵌入到已打包的 exe 中

        Args:
            exe_path: exe 文件路径
            version_info: 版本信息字典

        Returns:
            是否成功
        """
        if not version_info:
            return False

        # 验证 exe 文件
        if not os.path.exists(exe_path):
            self.log(f"  错误: exe 文件不存在: {exe_path}")
            return False

        # 检查文件大小，确保文件完整
        try:
            file_size = os.path.getsize(exe_path)
            if file_size < 1024:  # 小于 1KB 的 exe 文件肯定有问题
                self.log(f"  错误: exe 文件太小 ({file_size} 字节)，可能已损坏")
                return False
            self.log(f"  exe 文件大小: {file_size / 1024 / 1024:.2f} MB")
        except OSError as e:
            self.log(f"  错误: 无法读取 exe 文件信息: {e}")
            return False

        product_name = version_info.get('product_name', '')
        company_name = version_info.get('company_name', '')
        file_description = version_info.get('file_description', '')
        # 同时支持 'copyright' 和 'copyright_text' 两种键名
        copyright_text = version_info.get('copyright_text', '') or version_info.get('copyright', '')
        # 同时支持 'version' 和 'version_str' 两种键名
        version_str = version_info.get('version_str', '') or version_info.get('version', '')

        try:
            rcedit_exe = self.find_or_download_rcedit()

            if rcedit_exe and os.path.exists(rcedit_exe):
                self.log(f"  使用 rcedit: {rcedit_exe}")

                # 验证 rcedit 是否可执行
                try:
                    subprocess.run(
                        [rcedit_exe, "--help"],
                        capture_output=True,
                        timeout=10,
                        creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                    )
                    # rcedit --help 返回非零也是正常的
                except Exception as e:
                    self.log(f"  警告: rcedit 验证失败: {e}")

                windows_version = self.version_handler.convert_version_to_windows_format(version_str)
                success = True
                max_retries = 3

                # 设置各项版本信息
                version_fields = [
                    ("ProductName", product_name),
                    ("FileDescription", file_description),
                    ("LegalCopyright", copyright_text),
                    ("CompanyName", company_name),
                ]

                for field_name, field_value in version_fields:
                    if field_value:
                        field_success = False
                        for retry in range(max_retries):
                            try:
                                result = subprocess.run(
                                    [rcedit_exe, exe_path, "--set-version-string", field_name, field_value],
                                    capture_output=True,
                                    text=True,
                                    encoding="utf-8",
                                    errors="replace",
                                    timeout=60,
                                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                                )
                                if result.returncode == 0:
                                    field_success = True
                                    break
                                else:
                                    if retry < max_retries - 1:
                                        self.log(f"  设置 {field_name} 失败，重试 {retry + 2}/{max_retries}...")
                                        import time
                                        time.sleep(0.5)
                                    else:
                                        self.log(f"  设置 {field_name} 失败: {result.stderr}")
                            except subprocess.TimeoutExpired:
                                self.log(f"  设置 {field_name} 超时")
                                break
                            except OSError as e:
                                # WinError 1392 等文件系统错误
                                if retry < max_retries - 1:
                                    self.log(f"  设置 {field_name} 出错: {e}，重试 {retry + 2}/{max_retries}...")
                                    import time
                                    time.sleep(1)  # 等待更长时间
                                else:
                                    self.log(f"  设置 {field_name} 失败: {e}")
                                    break

                        if not field_success:
                            success = False

                # 设置版本号
                if windows_version:
                    for version_type in ["--set-product-version", "--set-file-version"]:
                        version_success = False
                        for retry in range(max_retries):
                            try:
                                result = subprocess.run(
                                    [rcedit_exe, exe_path, version_type, windows_version],
                                    capture_output=True,
                                    text=True,
                                    encoding="utf-8",
                                    errors="replace",
                                    timeout=60,
                                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                                )
                                if result.returncode == 0:
                                    version_success = True
                                    break
                                else:
                                    if retry < max_retries - 1:
                                        import time
                                        time.sleep(0.5)
                            except (subprocess.TimeoutExpired, OSError) as e:
                                if retry < max_retries - 1:
                                    import time
                                    time.sleep(1)
                                else:
                                    self.log(f"  设置版本失败: {e}")
                                    break

                        if not version_success:
                            success = False

                if success:
                    self.log("  ✓ 版本信息已通过 rcedit 嵌入")
                    return True
                else:
                    self.log("  部分版本信息设置失败，尝试其他方法...")

            # 尝试使用 Resource Hacker
            return self._try_resource_hacker(exe_path, version_info)

        except OSError as e:
            # 处理 Windows 文件系统错误
            error_code = getattr(e, 'winerror', None)
            if error_code == 1392:
                self.log("  后处理出错: 文件系统错误 (WinError 1392)")
                self.log("  可能原因: 防病毒软件干扰、文件被占用或磁盘问题")
                self.log("  建议: 1) 暂时禁用防病毒软件实时保护")
                self.log("        2) 确保没有其他程序正在访问该 exe 文件")
                self.log("        3) 尝试将输出目录更改到其他位置")
            else:
                self.log(f"  后处理出错: {str(e)}")
            return False
        except Exception as e:
            self.log(f"  后处理出错: {str(e)}")
            return False

    def _try_resource_hacker(self, exe_path: str, version_info: Dict) -> bool:
        """
        尝试使用 Resource Hacker 嵌入版本信息

        Args:
            exe_path: exe 文件路径
            version_info: 版本信息字典

        Returns:
            是否成功
        """
        rh_paths = [
            r"C:\Program Files (x86)\Resource Hacker\ResourceHacker.exe",
            r"C:\Program Files\Resource Hacker\ResourceHacker.exe",
        ]

        rh_exe = None
        for path in rh_paths:
            if os.path.exists(path):
                rh_exe = path
                break

        if not rh_exe:
            self.log("  未找到可用的资源编辑工具")
            self.log("  ⚠️  无法添加中文版本信息")
            self.log("  提示：手动安装 Resource Hacker 可以支持中文版本信息")
            return False

        self.log(f"  使用 Resource Hacker: {rh_exe}")

        try:
            res_file = self.resource_handler.create_version_resource_file(
                output_dir=version_info.get('output_dir', os.path.dirname(exe_path)),
                script_name=version_info.get('script_name', 'Application'),
                product_name=version_info.get('product_name', ''),
                company_name=version_info.get('company_name', ''),
                file_description=version_info.get('file_description', ''),
                copyright_text=version_info.get('copyright_text', ''),
                version_str=version_info.get('version_str', '1.0.0.0'),
                icon_path=None
            )

            if res_file and os.path.exists(res_file):
                cmd = [
                    rh_exe,
                    "-open", exe_path,
                    "-save", exe_path,
                    "-action", "addoverwrite",
                    "-res", res_file,
                    "-mask", "VERSIONINFO,,"
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=60,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )

                if result.returncode == 0:
                    self.log("  ✓ 版本信息已通过 Resource Hacker 嵌入")
                    return True
                else:
                    self.log(f"  Resource Hacker 执行失败: {result.stderr}")

        except Exception as e:
            self.log(f"  Resource Hacker 处理出错: {str(e)}")

        return False
