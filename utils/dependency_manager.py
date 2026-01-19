"""
依赖管理器

负责自动下载和安装UPX、GCC等工具，支持多镜像源pip安装。
"""

import os
import subprocess
import sys
import zipfile
from typing import Callable, List, Optional

import requests

# Windows 子进程隐藏标志
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class DependencyManager:
    """依赖管理器，负责自动下载和安装UPX、GCC等工具"""

    # 多镜像源列表，按优先级排序
    PIP_MIRRORS = [
        ("默认源", None),  # 使用默认 PyPI
        ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
        ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
        ("腾讯云", "https://mirrors.cloud.tencent.com/pypi/simple"),
        ("华为云", "https://repo.huaweicloud.com/repository/pypi/simple"),
        ("中科大", "https://pypi.mirrors.ustc.edu.cn/simple"),
        ("豆瓣", "https://pypi.douban.com/simple"),
    ]

    def __init__(self, log_callback: Optional[Callable] = None):
        self.log = log_callback if log_callback else print
        self._current_mirror_index = 0  # 当前使用的镜像源索引

    def get_appdata_dir(self) -> str:
        """获取当前用户的AppData目录"""
        return os.path.expanduser(r"~\AppData")

    def get_upx_install_dir(self) -> str:
        """获取UPX安装目录"""
        appdata = self.get_appdata_dir()
        return os.path.join(appdata, "UPX")

    def get_nuitka_cache_dir(self) -> str:
        """获取Nuitka缓存目录"""
        user_home = os.path.expanduser("~")
        return os.path.join(user_home, "AppData", "Local", "Nuitka", "Nuitka", "Cache", "downloads")

    def validate_mingw_directory(self, mingw_path: str) -> bool:
        """验证mingw目录是否有效"""
        if not os.path.exists(mingw_path):
            return False

        if not os.path.isdir(mingw_path):
            return False

        # 检查目录名
        dir_name = os.path.basename(mingw_path).lower()
        if dir_name not in ("mingw64", "mingw32"):
            return False

        # 检查bin目录是否存在
        bin_dir = os.path.join(mingw_path, "bin")
        if not os.path.exists(bin_dir):
            return False

        # 检查必需文件
        required_files = ["gcc.exe", "g++.exe", "c++.exe", "cpp.exe"]
        for file_name in required_files:
            if not os.path.exists(os.path.join(bin_dir, file_name)):
                return False

        return True

    def is_upx_installed(self) -> bool:
        """检查UPX是否已安装"""
        try:
            result = subprocess.run(
                ["upx", "--version"],
                capture_output=True,
                timeout=5,
                creationflags=CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except Exception:
            return False

    def add_to_system_path(self, directory: str) -> bool:
        """将目录永久添加到系统PATH环境变量"""
        if sys.platform != "win32":
            return False
            
        try:
            import ctypes
            import winreg
            
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Environment", 0,
                winreg.KEY_READ | winreg.KEY_WRITE
            )

            try:
                current_path, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current_path = ""

            paths = [p.strip() for p in current_path.split(';') if p.strip()]
            directory = os.path.normpath(directory)

            if directory not in paths:
                paths.append(directory)
                winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ';'.join(paths))
                self.log(f"已将 {directory} 添加到系统PATH")

                # 广播环境变量变更消息
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "Environment")

            winreg.CloseKey(key)

            # 添加到当前进程PATH
            if directory not in os.environ["PATH"]:
                os.environ["PATH"] = directory + os.pathsep + os.environ["PATH"]

            return True

        except Exception as e:
            self.log(f"添加到PATH失败: {str(e)}")
            return False

    def download_upx(self) -> Optional[str]:
        """下载并安装UPX到AppData目录"""
        try:
            self.log("正在下载UPX...")

            # 获取安装目录
            install_dir = self.get_upx_install_dir()
            os.makedirs(install_dir, exist_ok=True)

            upx_exe = os.path.join(install_dir, "upx.exe")

            # 如果已存在，检查是否可用
            if os.path.exists(upx_exe):
                self.log(f"UPX已存在: {upx_exe}")
                # 验证是否可用
                try:
                    result = subprocess.run(
                        [upx_exe, "--version"],
                        capture_output=True,
                        timeout=5,
                        creationflags=CREATE_NO_WINDOW,
                    )
                    if result.returncode == 0:
                        self.log("UPX已安装且可用")
                        return upx_exe
                except Exception:
                    self.log("现有UPX不可用，重新下载...")

            # 获取最新版本
            api_url = "https://api.github.com/repos/upx/upx/releases/latest"
            headers = {'User-Agent': 'Python-Packaging-Tool'}

            self.log("获取UPX最新版本...")
            response = requests.get(api_url, headers=headers, timeout=30)
            response.raise_for_status()

            release_data = response.json()
            assets = release_data.get('assets', [])

            # 查找win64版本
            download_url = None
            for asset in assets:
                name = asset.get('name', '')
                if 'win64.zip' in name or 'win64' in name.lower():
                    download_url = asset.get('browser_download_url')
                    break

            if not download_url:
                self.log("未找到UPX win64版本，尝试下载稳定版本...")
                download_url = "https://github.com/upx/upx/releases/download/v4.2.2/upx-4.2.2-win64.zip"

            # 下载zip文件
            zip_path = os.path.join(install_dir, "upx.zip")
            self.log(f"下载URL: {download_url}")

            response = requests.get(download_url, headers=headers, stream=True, timeout=120)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded_size = 0

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            if progress % 10 == 0:
                                self.log(f"下载进度: {progress}%")

            self.log("下载完成，正在解压...")

            # 解压
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(install_dir)

            # 查找upx.exe
            for root, dirs, files in os.walk(install_dir):
                if 'upx.exe' in files:
                    src = os.path.join(root, 'upx.exe')
                    dst = os.path.join(install_dir, 'upx.exe')
                    if src != dst:
                        import shutil
                        shutil.copy2(src, dst)
                    break

            # 清理zip文件
            if os.path.exists(zip_path):
                os.remove(zip_path)

            # 验证安装
            if os.path.exists(upx_exe):
                self.log(f"UPX安装成功: {upx_exe}")
                return upx_exe
            else:
                self.log("错误: UPX安装失败，未找到upx.exe")
                return None

        except Exception as e:
            self.log(f"下载UPX失败: {str(e)}")
            return None

    def ensure_upx_installed(self) -> bool:
        """确保UPX已安装并在PATH中"""
        # 检查是否已在PATH中
        if self.is_upx_installed():
            self.log("✓ UPX 已安装在系统PATH中")
            return True

        self.log("UPX未安装，开始自动下载...")

        # 下载UPX
        upx_exe = self.download_upx()
        if not upx_exe:
            self.log("警告: UPX自动安装失败")
            return False

        # 添加到PATH
        install_dir = os.path.dirname(upx_exe)
        if self.add_to_system_path(install_dir):
            self.log("✓ UPX已安装并添加到系统PATH")
            return True
        else:
            self.log("警告: UPX已安装但添加到PATH失败")
            # 至少添加到当前进程PATH
            os.environ["PATH"] = install_dir + os.pathsep + os.environ["PATH"]
            return True

    def download_gcc_with_retry(self, max_retries: int = 3) -> Optional[str]:
        """下载GCC工具链，失败自动重试"""
        cache_dir = self.get_nuitka_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)

        for attempt in range(1, max_retries + 1):
            try:
                self.log(f"尝试下载GCC工具链 (第{attempt}/{max_retries}次)...")

                # 获取下载链接
                api_url = "https://api.github.com/repos/brechtsanders/winlibs_mingw/releases/latest"
                headers = {'User-Agent': 'Python-Packaging-Tool'}

                response = requests.get(api_url, headers=headers, timeout=30)
                response.raise_for_status()

                release_data = response.json()
                assets = release_data.get('assets', [])

                # 查找合适的版本
                download_url: Optional[str] = None
                file_name: Optional[str] = None

                for asset in assets:
                    name = asset.get('name', '')
                    if not name:
                        continue
                    name_lower = name.lower()
                    if (name_lower.endswith('.zip') and
                        'x86_64' in name_lower and
                        'posix' in name_lower and
                        'seh' in name_lower and
                        'ucrt' in name_lower):
                        download_url = asset.get('browser_download_url')
                        file_name = name
                        break

                if not download_url or not file_name:
                    for asset in assets:
                        name = asset.get('name', '')
                        if name and name.endswith('.zip'):
                            download_url = asset.get('browser_download_url')
                            file_name = name
                            break

                if not download_url or not file_name:
                    self.log("错误: 未找到可下载的GCC文件")
                    continue

                # 此时file_name和download_url必定不为None
                file_path = os.path.join(cache_dir, file_name)
                temp_path = file_path + ".tmp"

                self.log(f"下载: {file_name}")
                self.log(f"URL: {download_url}")

                # 下载到临时文件
                response = requests.get(download_url, headers=headers, stream=True, timeout=120)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0

                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            if total_size > 0:
                                progress = int((downloaded_size / total_size) * 100)
                                if progress % 10 == 0:
                                    self.log(f"下载进度: {progress}%")

                self.log("下载完成，验证文件完整性...")

                # 验证zip文件
                if not self.verify_zip_file(temp_path):
                    self.log(f"警告: 第{attempt}次下载的文件验证失败，重试...")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    continue

                # 测试解压
                try:
                    with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                        # 只测试第一个文件
                        first_file = zip_ref.namelist()[0]
                        zip_ref.getinfo(first_file)
                    self.log("✓ 文件完整性验证通过")
                except Exception as e:
                    self.log(f"警告: 解压测试失败: {str(e)}，重试...")
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    continue

                # 重命名为正式文件
                if os.path.exists(file_path):
                    os.remove(file_path)
                os.rename(temp_path, file_path)

                self.log(f"✓ GCC工具链下载成功: {file_path}")
                return file_path

            except requests.exceptions.Timeout:
                self.log(f"第{attempt}次下载超时，重试...")
            except requests.exceptions.RequestException as e:
                self.log(f"第{attempt}次下载失败: {str(e)}，重试...")
            except Exception as e:
                self.log(f"第{attempt}次下载出错: {str(e)}，重试...")

            # 清理临时文件
            temp_path = os.path.join(cache_dir, "*.tmp")
            import glob
            for tmp_file in glob.glob(temp_path):
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass

        self.log(f"错误: GCC下载失败，已尝试{max_retries}次")
        return None

    def find_gcc_in_cache(self) -> Optional[str]:
        """在缓存目录中查找有效的mingw目录"""
        cache_dir = self.get_nuitka_cache_dir()
        if not os.path.exists(cache_dir):
            return None

        # 优先查找mingw64目录
        mingw64_path = os.path.join(cache_dir, "mingw64")
        if os.path.exists(mingw64_path) and self.validate_mingw_directory(mingw64_path):
            return mingw64_path

        # 其次查找mingw32目录
        mingw32_path = os.path.join(cache_dir, "mingw32")
        if os.path.exists(mingw32_path) and self.validate_mingw_directory(mingw32_path):
            return mingw32_path

        return None

    def ensure_gcc_available(self) -> Optional[str]:
        """确保GCC工具链可用"""
        # 先查找缓存中的mingw目录
        gcc_path = self.find_gcc_in_cache()
        if gcc_path:
            self.log(f"✓ 找到已缓存的GCC: {gcc_path}")
            return gcc_path

        # 如果没有找到，返回None（不再自动下载，由GUI处理）
        self.log("未找到GCC工具链，请使用GUI的自动下载功能")
        return None

    def ensure_package_installed(self, python_path: str, package: str, version: Optional[str] = None) -> bool:
        """确保Python包已安装且版本正确（支持多镜像源）"""
        try:
            # 检查Python版本兼容性
            if not self._check_package_python_compatibility(python_path, package):
                return False

            # 包名到导入名的映射表（处理包名和导入名不一致的情况）
            package_import_mapping = {
                'charset-normalizer': 'charset_normalizer',
                'wxPython': 'wx',
                'Pillow': 'PIL',
                'opencv-python': 'cv2',
                'python-dateutil': 'dateutil',
                'beautifulsoup4': 'bs4',
                'scikit-learn': 'sklearn',
                'scikit-image': 'skimage',
                'PyYAML': 'yaml',
                'msgpack-python': 'msgpack',
            }

            # 获取实际的导入名
            import_name = package_import_mapping.get(package, package)

            # 检查是否已安装
            if version:
                check_cmd = f"import {import_name}; exit(0 if hasattr({import_name}, '__version__') and {import_name}.__version__ == '{version}' else 1)"
            else:
                check_cmd = f"import {import_name}"

            result = subprocess.run(
                [python_path, "-c", check_cmd],
                capture_output=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
            )

            if result.returncode == 0:
                self.log(f"✓ {package} 已安装")
                return True

            # 需要安装或升级，使用多镜像源
            self.log(f"安装/升级 {package}...")

            # 构建包名（带版本号）
            package_spec = f"{package}=={version}" if version else package

            # 使用多镜像源安装
            return self._pip_install_with_mirrors(python_path, [package_spec], upgrade=True)

        except Exception as e:
            self.log(f"错误: 检查/安装 {package} 时出错: {str(e)}")
            return False

    def _check_package_python_compatibility(self, python_path: str, package: str) -> bool:
        """
        检查包是否与当前Python版本兼容

        Args:
            python_path: Python解释器路径
            package: 包名

        Returns:
            是否兼容
        """
        # 获取Python版本
        try:
            result = subprocess.run(
                [python_path, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
            )
            if result.returncode != 0:
                return True  # 无法获取版本时默认兼容

            python_version = result.stdout.strip()
            major, minor = map(int, python_version.split('.'))
        except Exception:
            return True  # 出错时默认兼容

        # 不兼容包列表：包名 -> (最大支持的Python主版本, 最大支持的Python次版本)
        # 例如 PySide2 最高支持 Python 3.10
        incompatible_packages = {
            'PySide2': (3, 10),      # PySide2 不支持 Python 3.11+
            'shiboken2': (3, 10),    # shiboken2 是 PySide2 的依赖
        }

        package_lower = package.lower()
        for pkg_name, (max_major, max_minor) in incompatible_packages.items():
            if package_lower == pkg_name.lower():
                if major > max_major or (major == max_major and minor > max_minor):
                    self.log(f"跳过 {package}：不支持 Python {python_version}（最高支持 Python {max_major}.{max_minor}）")
                    return False

        return True

    def _pip_install_with_mirrors(
        self,
        python_path: str,
        packages: list,
        upgrade: bool = False,
        timeout: int = 120
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
        start_index = self._current_mirror_index
        tried_mirrors = 0
        total_mirrors = len(self.PIP_MIRRORS)

        while tried_mirrors < total_mirrors:
            mirror_name, mirror_url = self.PIP_MIRRORS[self._current_mirror_index]

            # 构建 pip install 命令
            cmd = [python_path, "-m", "pip", "install"]
            if upgrade:
                cmd.append("--upgrade")

            # 添加镜像源参数
            if mirror_url:
                cmd.extend(["-i", mirror_url, "--trusted-host", mirror_url.split("//")[1].split("/")[0]])

            cmd.extend(packages)

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=timeout,
                    creationflags=CREATE_NO_WINDOW,
                )

                if result.returncode == 0:
                    # 安装成功
                    if mirror_url and tried_mirrors > 0:
                        self.log(f"  (使用镜像源: {mirror_name})")
                    self.log(f"✓ {', '.join(packages)} 安装成功")
                    return True
                else:
                    # 安装失败，检查是否是网络问题
                    stderr_lower = result.stderr.lower() if result.stderr else ""
                    is_network_error = any(keyword in stderr_lower for keyword in [
                        "connection", "timeout", "network", "ssl", "certificate",
                        "could not find a version", "no matching distribution",
                        "retrying", "failed to establish"
                    ])

                    if is_network_error and tried_mirrors < total_mirrors - 1:
                        # 网络问题，切换到下一个镜像源
                        self._current_mirror_index = (self._current_mirror_index + 1) % total_mirrors
                        next_mirror_name = self.PIP_MIRRORS[self._current_mirror_index][0]
                        self.log(f"  镜像源 {mirror_name} 连接失败，切换到 {next_mirror_name}...")
                        tried_mirrors += 1
                        continue
                    else:
                        # 非网络问题或已尝试所有镜像源
                        if result.stderr:
                            error_lines = result.stderr.strip().split('\n')
                            if error_lines:
                                self.log(f"  错误: {error_lines[-1][:100]}")
                        return False

            except subprocess.TimeoutExpired:
                self.log(f"  镜像源 {mirror_name} 连接超时...")
                self._current_mirror_index = (self._current_mirror_index + 1) % total_mirrors
                tried_mirrors += 1
                continue

            except Exception as e:
                self.log(f"  安装时发生异常: {str(e)[:50]}")
                self._current_mirror_index = (self._current_mirror_index + 1) % total_mirrors
                tried_mirrors += 1
                continue

        # 所有镜像源都失败
        self.log(f"警告: 所有镜像源均安装失败")
        self._current_mirror_index = 0
        return False
