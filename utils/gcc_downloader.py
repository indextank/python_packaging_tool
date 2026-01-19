"""
GCC下载器工具

从GitHub releases多线程下载GCC工具链，支持重试、进度报告和zip验证。
"""

import os
import platform
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, List, Optional, Tuple

import requests


# 下载配置常量
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
TIMEOUT = 60
NUM_THREADS = 8
MAX_RETRIES = 3
MIN_GCC_SIZE_MB = 250  # 最小有效GCC包大小（MB）

# GitHub API
GITHUB_API_URL = "https://api.github.com/repos/brechtsanders/winlibs_mingw/releases/latest"

# 备用下载URL
FALLBACK_URLS = {
    "x86_64": "https://github.com/brechtsanders/winlibs_mingw/releases/download/15.2.0posix-19.1.7-13.0.0-msvcrt-r5/winlibs-x86_64-posix-seh-gcc-15.2.0-mingw-w64msvcrt-13.0.0-r5.zip",
    "i686": "https://github.com/brechtsanders/winlibs_mingw/releases/download/15.2.0posix-19.1.7-13.0.0-msvcrt-r5/winlibs-i686-posix-dwarf-gcc-15.2.0-mingw-w64msvcrt-13.0.0-r5.zip",
}

# mingw必需文件（x64和x86相同）
REQUIRED_FILES = ["bin/gcc.exe", "bin/g++.exe", "bin/c++.exe", "bin/cpp.exe"]

# 架构特定的可选文件（至少存在一个）
OPTIONAL_FILES = {
    "x86_64": ["bin/x86_64-w64-mingw32-gcc.exe", "bin/x86_64-w64-mingw32-c++.exe"],
    "i686": ["bin/i686-w64-mingw32-gcc.exe", "bin/i686-w64-mingw32-c++.exe"],
}


def _get_system_arch() -> str:
    """获取系统架构：x86_64 或 i686"""
    machine = platform.machine().lower()
    return "x86_64" if machine in ("amd64", "x86_64", "x64") else "i686"


def _get_nuitka_cache_dir() -> str:
    """获取Nuitka缓存下载目录"""
    return os.path.join(os.path.expanduser("~"), "AppData", "Local", "Nuitka", "Nuitka", "Cache", "downloads")


class GCCDownloader:
    """GCC工具链下载器，支持多线程并发下载、完整性校验、自动解压"""

    def __init__(
        self,
        log_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ):
        """初始化下载器"""
        self.log = log_callback or print
        self.progress = progress_callback or (lambda x: None)
        self.cancel_check = cancel_check or (lambda: False)
        self._downloaded_bytes = 0
        self._total_bytes = 0
        self._lock = threading.Lock()

    @staticmethod
    def get_system_arch() -> str:
        """获取当前系统架构"""
        return _get_system_arch()

    @staticmethod
    def get_mingw_dir_name() -> str:
        """根据系统架构获取mingw目录名"""
        return "mingw64" if _get_system_arch() == "x86_64" else "mingw32"

    @staticmethod
    def get_nuitka_cache_dir() -> str:
        """获取Nuitka缓存下载目录"""
        return _get_nuitka_cache_dir()

    @classmethod
    def get_default_mingw_path(cls) -> Optional[str]:
        """获取默认的有效mingw目录路径"""
        cache_dir = _get_nuitka_cache_dir()
        arch = _get_system_arch()

        # 按优先级检查目录
        candidates = ["mingw64", "mingw32"] if arch == "x86_64" else ["mingw32"]
        
        for dir_name in candidates:
            path = os.path.join(cache_dir, dir_name)
            if os.path.exists(path):
                is_valid, _ = cls.validate_mingw_directory(path)
                if is_valid:
                    return path
        return None

    @classmethod
    def validate_mingw_directory(cls, mingw_path: str) -> Tuple[bool, str]:
        """验证mingw目录是否有效"""
        if not os.path.isdir(mingw_path):
            return False, "目录不存在" if not os.path.exists(mingw_path) else "指定的路径不是目录"

        dir_name = os.path.basename(mingw_path).lower()
        if dir_name not in ("mingw64", "mingw32"):
            return False, f"目录名必须是 mingw64 或 mingw32，当前为: {dir_name}"

        bin_dir = os.path.join(mingw_path, "bin")
        if not os.path.exists(bin_dir):
            return False, "缺少 bin 目录"

        # 检查必需文件
        missing = [f for f in REQUIRED_FILES if not os.path.exists(os.path.join(mingw_path, f))]
        if missing:
            return False, f"缺少必需文件: {', '.join(missing)}"

        # 检查可选文件（至少存在一个）
        arch = "x86_64" if dir_name == "mingw64" else "i686"
        optional = OPTIONAL_FILES.get(arch, [])
        if optional and not any(os.path.exists(os.path.join(mingw_path, f)) for f in optional):
            return False, f"缺少架构特定文件，需要以下文件之一: {', '.join(optional)}"

        return True, "验证通过"

    def verify_zip_file(self, zip_path: str) -> Tuple[bool, str]:
        """验证zip文件完整性"""
        if not os.path.exists(zip_path):
            return False, "文件不存在"

        try:
            file_size = os.path.getsize(zip_path)
            min_size = MIN_GCC_SIZE_MB * 1024 * 1024
            if file_size < min_size:
                return False, f"文件太小 ({file_size / 1024 / 1024:.1f} MB)，正常的GCC包不低于{MIN_GCC_SIZE_MB}MB"

            if not zipfile.is_zipfile(zip_path):
                return False, "不是有效的zip文件格式"

            with zipfile.ZipFile(zip_path, "r") as zf:
                file_list = zf.namelist()
                if not file_list:
                    return False, "zip文件为空"

                bad_file = zf.testzip()
                if bad_file:
                    return False, f"zip文件中存在损坏的文件: {bad_file}"

                has_mingw = any(n.startswith(("mingw64/", "mingw32/")) or n in ("mingw64", "mingw32") for n in file_list)
                if not has_mingw:
                    return False, "zip文件中未找到mingw目录，不是有效的GCC工具链"

            return True, "验证通过"

        except zipfile.BadZipFile as e:
            return False, f"损坏的zip文件: {e}"
        except Exception as e:
            return False, f"验证失败: {e}"

    def extract_zip(self, zip_path: str, extract_dir: Optional[str] = None) -> Optional[str]:
        """
        解压zip文件到指定目录

        Args:
            zip_path: zip文件路径
            extract_dir: 解压目录，默认为Nuitka缓存目录

        Returns:
            解压后的mingw目录路径，失败返回None
        """
        if extract_dir is None:
            extract_dir = self.get_nuitka_cache_dir()

        os.makedirs(extract_dir, exist_ok=True)

        try:
            self.log("正在解压GCC工具链...")
            self.progress("正在解压...")

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                # 获取总文件数用于显示进度
                total_files = len(zip_ref.namelist())
                extracted = 0

                for file_info in zip_ref.infolist():
                    if self.cancel_check():
                        self.log("解压已取消")
                        return None

                    zip_ref.extract(file_info, extract_dir)
                    extracted += 1

                    if extracted % 100 == 0 or extracted == total_files:
                        percent = (extracted / total_files) * 100
                        self.progress(f"解压进度: {percent:.1f}% ({extracted}/{total_files})")

            self.log("解压完成")

            # 查找解压后的mingw目录
            mingw64_path = os.path.join(extract_dir, "mingw64")
            mingw32_path = os.path.join(extract_dir, "mingw32")

            if os.path.exists(mingw64_path):
                is_valid, msg = self.validate_mingw_directory(mingw64_path)
                if is_valid:
                    self.log(f"✓ GCC工具链解压成功: {mingw64_path}")
                    return mingw64_path
                else:
                    self.log(f"警告: mingw64目录验证失败: {msg}")

            if os.path.exists(mingw32_path):
                is_valid, msg = self.validate_mingw_directory(mingw32_path)
                if is_valid:
                    self.log(f"✓ GCC工具链解压成功: {mingw32_path}")
                    return mingw32_path
                else:
                    self.log(f"警告: mingw32目录验证失败: {msg}")

            self.log("错误: 解压后未找到有效的mingw目录")
            return None

        except Exception as e:
            self.log(f"解压失败: {e}")
            return None

    def get_latest_release_info(self) -> Optional[Tuple[str, str, int]]:
        """从GitHub获取最新版本信息"""
        arch = _get_system_arch()
        arch_keywords = ["x86_64", "x64"] if arch == "x86_64" else ["i686", "i386"]
        exclude_keywords = ["i686", "i386"] if arch == "x86_64" else ["x86_64", "x64"]

        try:
            self.log("正在获取最新版本信息...")
            response = requests.get(GITHUB_API_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
            response.raise_for_status()

            assets = response.json().get("assets", [])

            # 查找匹配的资源
            for require_posix in (True, False):
                for asset in assets:
                    name = asset.get("name", "")
                    if not name:
                        continue
                    name_lower = name.lower()

                    if any(kw in name_lower for kw in exclude_keywords):
                        continue

                    if not name_lower.endswith(".zip") or not any(kw in name_lower for kw in arch_keywords):
                        continue

                    if require_posix and "posix" not in name_lower:
                        continue

                    file_size = asset.get("size", 0)
                    self.log(f"找到最新版本: {name}")
                    self.log(f"文件大小: {file_size / 1024 / 1024:.1f} MB")
                    return asset.get("browser_download_url"), name, file_size

            self.log("未找到匹配当前架构的版本，使用备用下载链接")
            return None

        except requests.exceptions.Timeout:
            self.log("错误: 获取版本信息超时")
        except requests.exceptions.RequestException as e:
            self.log(f"错误: 网络请求失败: {e}")
        except Exception as e:
            self.log(f"错误: 获取版本信息失败: {e}")
        return None

    def get_fallback_url(self) -> Tuple[str, str]:
        """获取备用下载URL"""
        arch = _get_system_arch()
        url = FALLBACK_URLS.get(arch, FALLBACK_URLS["x86_64"])
        return url, url.split("/")[-1]

    def _download_chunk(
        self,
        url: str,
        start: int,
        end: int,
        temp_file: str,
        chunk_index: int,
    ) -> bool:
        """下载文件的一个分片"""
        headers = {"User-Agent": USER_AGENT, "Range": f"bytes={start}-{end}"}
        chunk_file = f"{temp_file}.part{chunk_index}"
        
        try:
            response = requests.get(url, headers=headers, stream=True, timeout=TIMEOUT)

            with open(chunk_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancel_check():
                        return False
                    if chunk:
                        f.write(chunk)
                        with self._lock:
                            self._downloaded_bytes += len(chunk)

            return True

        except Exception as e:
            self.log(f"分片 {chunk_index} 下载失败: {e}")
            return False
        finally:
            if self.cancel_check() and os.path.exists(chunk_file):
                try:
                    os.remove(chunk_file)
                except Exception:
                    pass

    def _merge_chunks(self, temp_file: str, dest_file: str, num_chunks: int) -> bool:
        """
        合并所有分片文件
        """
        try:
            with open(dest_file, "wb") as dest:
                for i in range(num_chunks):
                    chunk_file = f"{temp_file}.part{i}"
                    if not os.path.exists(chunk_file):
                        self.log(f"错误: 分片文件不存在: {chunk_file}")
                        return False

                    with open(chunk_file, "rb") as src:
                        while True:
                            data = src.read(8192)
                            if not data:
                                break
                            dest.write(data)

                    os.remove(chunk_file)

            return True

        except Exception as e:
            self.log(f"合并分片失败: {e}")
            return False

    def _cleanup_temp_files(self, temp_file: str, num_chunks: int) -> None:
        """清理临时文件，带重试机制"""

        def safe_remove(file_path: str, max_retries: int = 5) -> None:
            for attempt in range(max_retries):
                if not os.path.exists(file_path):
                    return
                try:
                    os.remove(file_path)
                    return
                except PermissionError:
                    time.sleep(0.2 * (attempt + 1))
                except Exception:
                    pass

        for i in range(num_chunks):
            chunk_file = f"{temp_file}.part{i}"
            safe_remove(chunk_file)

        safe_remove(temp_file)

        downloading_file = temp_file
        if not downloading_file.endswith(".downloading"):
            downloading_file = temp_file.replace(".part0", "").rstrip("0123456789")
        safe_remove(downloading_file)

        tmp_file = temp_file.replace(".downloading", ".tmp")
        safe_remove(tmp_file)

    def download_with_multithreading(
        self,
        url: str,
        dest_path: str,
        total_size: int,
    ) -> bool:
        """使用多线程下载文件"""
        self._downloaded_bytes = 0
        self._total_bytes = total_size
        num_chunks = NUM_THREADS
        chunk_size = total_size // num_chunks
        chunks = []

        for i in range(num_chunks):
            start = i * chunk_size
            end = total_size - 1 if i == num_chunks - 1 else (i + 1) * chunk_size - 1
            chunks.append((start, end))

        temp_file = dest_path + ".downloading"

        progress_stop = threading.Event()

        def update_progress():
            while not progress_stop.is_set():
                with self._lock:
                    downloaded = self._downloaded_bytes
                if self._total_bytes > 0:
                    percent = (downloaded / self._total_bytes) * 100
                    downloaded_mb = downloaded / 1024 / 1024
                    total_mb = self._total_bytes / 1024 / 1024
                    self.progress(
                        f"下载进度: {percent:.1f}% ({downloaded_mb:.1f}MB / {total_mb:.1f}MB)"
                    )
                time.sleep(0.5)

        progress_thread = threading.Thread(target=update_progress, daemon=True)
        progress_thread.start()

        try:
            with ThreadPoolExecutor(max_workers=num_chunks) as executor:
                futures = []
                for i, (start, end) in enumerate(chunks):
                    future = executor.submit(
                        self._download_chunk, url, start, end, temp_file, i
                    )
                    futures.append(future)

                results = []
                cancelled = False
                for future in as_completed(futures):
                    if self.cancel_check():
                        cancelled = True
                        for f in futures:
                            f.cancel()
                        break
                    results.append(future.result())

                if cancelled:
                    executor.shutdown(wait=True)
                    time.sleep(0.5)
                    self._cleanup_temp_files(temp_file, num_chunks)
                    return False

                if not all(results):
                    self.log("部分分片下载失败")
                    self._cleanup_temp_files(temp_file, num_chunks)
                    return False

            if self.cancel_check():
                self._cleanup_temp_files(temp_file, num_chunks)
                return False

            self.progress("正在合并文件...")
            if not self._merge_chunks(temp_file, dest_path, num_chunks):
                self.log("合并文件失败")
                return False

            return True

        except Exception as e:
            self.log(f"多线程下载失败: {e}")
            self._cleanup_temp_files(temp_file, num_chunks)
            return False

        finally:
            progress_stop.set()

    def download_single_thread(
        self,
        url: str,
        dest_path: str,
        total_size: int,
    ) -> bool:
        """单线程下载（多线程失败的备选方案）"""
        if self.cancel_check():
            return False

        temp_path = dest_path + ".tmp"
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, stream=True, timeout=TIMEOUT)
            response.raise_for_status()

            downloaded = 0

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.cancel_check():
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            downloaded_mb = downloaded / 1024 / 1024
                            total_mb = total_size / 1024 / 1024
                            self.progress(
                                f"下载进度: {percent:.1f}% ({downloaded_mb:.1f}MB / {total_mb:.1f}MB)"
                            )

            if self.cancel_check():
                return False

            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(temp_path, dest_path)
            return True

        except Exception as e:
            self.log(f"单线程下载失败: {e}")
            return False
        finally:
            if self.cancel_check() or not os.path.exists(dest_path):
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass

    def download(self) -> Optional[str]:
        """下载GCC工具链并解压，返回mingw目录路径"""
        cache_dir = _get_nuitka_cache_dir()
        os.makedirs(cache_dir, exist_ok=True)

        # 首先检查是否已存在有效的mingw目录
        existing_mingw = self.get_default_mingw_path()
        if existing_mingw:
            self.log(f"发现已存在的有效GCC工具链: {existing_mingw}")
            return existing_mingw

        # 获取最新版本信息
        release_info = self.get_latest_release_info()

        if release_info:
            download_url, file_name, file_size = release_info
        else:
            # 使用备用URL
            download_url, file_name = self.get_fallback_url()
            file_size = 0
            self.log(f"使用备用下载链接: {file_name}")

        dest_path = os.path.join(cache_dir, file_name)

        # 检查是否已存在有效的zip文件
        if os.path.exists(dest_path):
            is_valid, msg = self.verify_zip_file(dest_path)
            if is_valid:
                self.log(f"已存在有效的GCC压缩包: {dest_path}")
                # 直接解压
                mingw_path = self.extract_zip(dest_path, cache_dir)
                if mingw_path:
                    return mingw_path
            else:
                self.log(f"已存在的文件无效 ({msg})，将重新下载")
                os.remove(dest_path)

        # 尝试下载
        for attempt in range(1, MAX_RETRIES + 1):
            if self.cancel_check():
                self.log("下载已取消")
                return None

            self.log(f"\n尝试下载 (第 {attempt}/{MAX_RETRIES} 次)...")
            self.log(f"URL: {download_url}")
            self.progress(f"正在下载... (第 {attempt} 次尝试)")

            success = False
            if file_size > 0:
                self.log("使用多线程下载...")
                success = self.download_with_multithreading(
                    download_url, dest_path, file_size
                )

            if self.cancel_check():
                self.log("下载已取消")
                return None

            if not success:
                self.log("多线程下载失败，尝试单线程下载...")
                success = self.download_single_thread(download_url, dest_path, file_size)

                if self.cancel_check():
                    self.log("下载已取消")
                    return None

            if not success:
                self.log(f"第 {attempt} 次下载失败")
                continue

            # 验证下载的文件
            self.progress("正在验证文件完整性...")
            is_valid, msg = self.verify_zip_file(dest_path)
            if is_valid:
                self.log("✓ 文件验证通过")

                # 解压
                mingw_path = self.extract_zip(dest_path, cache_dir)
                if mingw_path:
                    self.log(f"✓ GCC工具链下载并解压成功: {mingw_path}")
                    return mingw_path
                else:
                    self.log("解压失败，重试...")
            else:
                self.log(f"文件验证失败: {msg}")
                if os.path.exists(dest_path):
                    os.remove(dest_path)

        self.log(f"\n错误: GCC下载失败，已尝试 {MAX_RETRIES} 次")
        return None

    def find_existing_gcc(self) -> Optional[str]:
        """在缓存目录中查找已存在的有效mingw目录"""
        return self.get_default_mingw_path()


def validate_gcc_path(gcc_path: str) -> Tuple[bool, str]:
    """验证GCC路径（目录或zip文件）"""
    if not os.path.exists(gcc_path):
        return False, "路径不存在"

    if os.path.isdir(gcc_path):
        return GCCDownloader.validate_mingw_directory(gcc_path)
    if gcc_path.lower().endswith(".zip"):
        return GCCDownloader().verify_zip_file(gcc_path)
    return False, "请选择mingw64/mingw32目录或zip压缩包"


def validate_mingw_directory(mingw_path: str) -> Tuple[bool, str]:
    """验证mingw目录"""
    return GCCDownloader.validate_mingw_directory(mingw_path)
