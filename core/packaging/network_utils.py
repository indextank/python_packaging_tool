"""
网络工具模块

本模块负责网络相关的功能，包括：
- 网络环境检测（国内/国外）
- pip 镜像源管理
- 多镜像源自动切换安装

功能：
- 自动检测网络环境
- 根据网络环境选择最优镜像源
- 支持镜像源故障自动切换
"""

import subprocess
import sys
import time
from typing import Callable, List, Optional, Tuple

from core.packaging.base import CREATE_NO_WINDOW


class NetworkUtils:
    """网络工具类"""

    # 国内镜像源列表（国内网络环境优先使用）
    PIP_MIRRORS_DOMESTIC: List[Tuple[str, Optional[str]]] = [
        ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
        ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
        ("腾讯云", "https://mirrors.cloud.tencent.com/pypi/simple"),
        ("华为云", "https://repo.huaweicloud.com/repository/pypi/simple"),
        ("中科大", "https://pypi.mirrors.ustc.edu.cn/simple"),
        ("豆瓣", "https://pypi.douban.com/simple"),
        ("默认源", None),  # 默认 PyPI 放在最后
    ]

    # 国外镜像源列表（国外网络环境优先使用）
    PIP_MIRRORS_INTERNATIONAL: List[Tuple[str, Optional[str]]] = [
        ("默认源", None),  # 默认 PyPI 优先
        ("阿里云", "https://mirrors.aliyun.com/pypi/simple"),
        ("清华大学", "https://pypi.tuna.tsinghua.edu.cn/simple"),
        ("腾讯云", "https://mirrors.cloud.tencent.com/pypi/simple"),
        ("华为云", "https://repo.huaweicloud.com/repository/pypi/simple"),
        ("中科大", "https://pypi.mirrors.ustc.edu.cn/simple"),
        ("豆瓣", "https://pypi.douban.com/simple"),
    ]

    def __init__(self):
        """初始化网络工具"""
        self.log: Callable = print
        self._is_domestic_network: Optional[bool] = None
        self._pip_mirrors: Optional[List[Tuple[str, Optional[str]]]] = None
        self._current_mirror_index = 0

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback

    def detect_network_environment(self) -> bool:
        """
        检测网络环境（国内/国外）

        通过尝试访问国内和国外的服务器来判断网络环境。

        Returns:
            True 表示国内网络，False 表示国外网络
        """
        if self._is_domestic_network is not None:
            return self._is_domestic_network

        self.log("\n检测网络环境...")

        # 测试国内源的连通性
        domestic_urls = [
            "https://mirrors.aliyun.com",
            "https://pypi.tuna.tsinghua.edu.cn",
        ]

        # 测试 PyPI 官方源的连通性
        pypi_url = "https://pypi.org"

        domestic_time = float('inf')
        pypi_time = float('inf')

        # 测试国内源
        for url in domestic_urls:
            response_time = self._test_url_response_time(url)
            if response_time is not None and response_time < domestic_time:
                domestic_time = response_time

        # 测试 PyPI 官方源
        pypi_time = self._test_url_response_time(pypi_url) or float('inf')

        # 判断网络环境
        if domestic_time < pypi_time:
            self._is_domestic_network = True
            self.log(f"  检测结果: 国内网络 (国内源响应: {domestic_time:.2f}s)")
        else:
            self._is_domestic_network = False
            self.log(f"  检测结果: 国外网络 (PyPI响应: {pypi_time:.2f}s)")

        return self._is_domestic_network

    def _test_url_response_time(
        self,
        url: str,
        timeout: int = 5,
    ) -> Optional[float]:
        """
        测试 URL 响应时间

        Args:
            url: 要测试的 URL
            timeout: 超时时间（秒）

        Returns:
            响应时间（秒），失败返回 None
        """
        try:
            import urllib.request

            start_time = time.time()
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'Python-packaging-tool/1.0'}
            )
            urllib.request.urlopen(request, timeout=timeout)
            return time.time() - start_time
        except Exception:
            return None

    def get_pip_mirrors(self) -> List[Tuple[str, Optional[str]]]:
        """
        获取当前网络环境适用的镜像源列表

        Returns:
            镜像源列表，每项为 (名称, URL) 元组
        """
        if self._pip_mirrors is not None:
            return self._pip_mirrors

        # 检测网络环境
        try:
            self.detect_network_environment()
        except Exception:
            # 默认使用国内镜像源
            self._is_domestic_network = True
            self.log("网络环境检测失败，默认使用国内镜像源配置")

        # 根据网络环境选择镜像源列表
        if self._is_domestic_network:
            self._pip_mirrors = self.PIP_MIRRORS_DOMESTIC
        else:
            self._pip_mirrors = self.PIP_MIRRORS_INTERNATIONAL

        return self._pip_mirrors

    def pip_install_with_mirrors(
        self,
        python_path: str,
        packages: List[str],
        upgrade: bool = False,
        timeout: int = 60,
        cancel_flag: Optional[Callable] = None,
    ) -> bool:
        """
        使用多镜像源安装 pip 包，自动切换镜像源以应对网络问题

        Args:
            python_path: Python 解释器路径
            packages: 要安装的包列表
            upgrade: 是否使用 --upgrade 参数
            timeout: 每个镜像源的超时时间（秒）
            cancel_flag: 取消标志回调函数

        Returns:
            安装是否成功
        """
        # 验证 Python 解释器是否存在
        import os
        if not os.path.exists(python_path):
            self.log(f"错误: Python 解释器不存在，无法安装包")
            self.log(f"  路径: {python_path}")
            self.log(f"  包列表: {packages}")
            # 尝试提供诊断信息
            parent_dir = os.path.dirname(python_path)
            if os.path.exists(parent_dir):
                try:
                    contents = os.listdir(parent_dir)
                    self.log(f"  父目录内容: {contents}")
                except Exception as e:
                    self.log(f"  无法列出父目录内容: {e}")
            else:
                self.log(f"  父目录也不存在: {parent_dir}")
            return False

        # 获取当前网络环境对应的镜像源列表
        pip_mirrors = self.get_pip_mirrors()

        # 每次安装新包时，从第一个镜像源开始尝试（重置索引）
        self._current_mirror_index = 0
        tried_mirrors = 0
        total_mirrors = len(pip_mirrors)

        while tried_mirrors < total_mirrors:
            # 检查是否取消
            if cancel_flag and cancel_flag():
                return False

            mirror_name, mirror_url = pip_mirrors[self._current_mirror_index]

            # 构建 pip install 命令
            cmd = [
                python_path, "-m", "pip", "install",
                "--disable-pip-version-check",
                "--no-warn-script-location",
            ]

            if upgrade:
                cmd.append("--upgrade")

            # 添加镜像源参数
            if mirror_url:
                cmd.extend(["-i", mirror_url, "--trusted-host", self._get_host_from_url(mirror_url)])

            # 添加包
            cmd.extend(packages)

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )

                if result.returncode == 0:
                    return True
                else:
                    # 安装失败，记录错误并尝试下一个镜像源
                    error_msg = result.stderr[:200] if result.stderr else "未知错误"
                    self.log(f"  使用 {mirror_name} 安装失败: {error_msg}")

            except subprocess.TimeoutExpired:
                self.log(f"  使用 {mirror_name} 超时")
            except FileNotFoundError as e:
                self.log(f"  使用 {mirror_name} 出错: [WinError 2] 系统找不到指定的文件。")
                self.log(f"    Python 路径: {python_path}")
                self.log(f"    命令: {' '.join(cmd[:5])}...")
                self.log(f"    详细错误: {str(e)}")
                # 这是致命错误，不应继续尝试其他镜像源
                self.log(f"警告: 安装 {' '.join(packages)} 失败（已尝试所有镜像源）")
                return False
            except Exception as e:
                self.log(f"  使用 {mirror_name} 出错: {str(e)}")
                self.log(f"    错误类型: {type(e).__name__}")

            # 切换到下一个镜像源
            self._current_mirror_index = (self._current_mirror_index + 1) % total_mirrors
            tried_mirrors += 1

            if tried_mirrors < total_mirrors:
                next_mirror = pip_mirrors[self._current_mirror_index][0]
                self.log(f"  切换到 {next_mirror}...")

        self.log(f"警告: 安装 {' '.join(packages)} 失败（已尝试所有镜像源）")
        return False

    def _get_host_from_url(self, url: str) -> str:
        """
        从 URL 中提取主机名

        Args:
            url: URL 字符串

        Returns:
            主机名
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            # 简单的字符串处理作为后备
            if "://" in url:
                url = url.split("://")[1]
            if "/" in url:
                url = url.split("/")[0]
            return url

    def test_mirror_connectivity(
        self,
        mirror_url: str,
        timeout: int = 5,
    ) -> Tuple[bool, float]:
        """
        测试镜像源连通性

        Args:
            mirror_url: 镜像源 URL
            timeout: 超时时间（秒）

        Returns:
            (是否可连通, 响应时间)
        """
        response_time = self._test_url_response_time(mirror_url, timeout)
        if response_time is not None:
            return True, response_time
        return False, float('inf')

    def get_best_mirror(self) -> Tuple[str, Optional[str]]:
        """
        获取当前最佳镜像源

        通过测试各个镜像源的响应时间，选择最快的镜像源。

        Returns:
            (镜像源名称, 镜像源 URL)
        """
        pip_mirrors = self.get_pip_mirrors()

        best_mirror = pip_mirrors[0]
        best_time = float('inf')

        for mirror_name, mirror_url in pip_mirrors:
            if mirror_url is None:
                # 默认 PyPI 源
                test_url = "https://pypi.org"
            else:
                test_url = mirror_url

            is_ok, response_time = self.test_mirror_connectivity(test_url)
            if is_ok and response_time < best_time:
                best_time = response_time
                best_mirror = (mirror_name, mirror_url)

        self.log(f"最佳镜像源: {best_mirror[0]} ({best_time:.2f}s)")
        return best_mirror

    def reset_mirror_index(self) -> None:
        """重置镜像源索引"""
        self._current_mirror_index = 0

    def clear_cache(self) -> None:
        """清除缓存的网络检测结果"""
        self._is_domestic_network = None
        self._pip_mirrors = None
        self._current_mirror_index = 0
