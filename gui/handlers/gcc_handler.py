"""
GCC 处理器 Mixin

本模块包含 MainWindow 中与 GCC 下载和管理相关的方法。
从 main_window.py 拆分出来，遵循单一职责原则。
"""

import json
import os
import threading
import webbrowser
from typing import Optional

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QMessageBox


class GCCHandlerMixin:
    """
    GCC 处理器 Mixin 类

    提供 GCC 下载和管理相关的方法。
    设计为与 MainWindow 一起使用的 Mixin。

    注意：此类使用 Mixin 模式，self 实际上是 MainWindow 实例
    """

    def get_nuitka_cache_dir(self) -> str:
        """
        获取 Nuitka 缓存目录

        Returns:
            Nuitka 缓存目录路径
        """
        user_home = os.path.expanduser("~")
        return os.path.join(
            user_home, "AppData", "Local", "Nuitka", "Nuitka", "Cache", "downloads"
        )

    def find_gcc_in_cache(self) -> Optional[str]:
        """
        在 Nuitka 缓存中查找 GCC mingw 目录

        Returns:
            找到的 mingw 目录路径，未找到返回 None
        """
        from utils.gcc_downloader import GCCDownloader

        return GCCDownloader.get_default_mingw_path()

    def load_gcc_config(self) -> None:
        """加载 GCC 配置（mingw 目录）"""
        from utils.gcc_downloader import validate_mingw_directory

        if self.gcc_config_loading:  # type: ignore[attr-defined]
            return

        self.gcc_config_loading = True  # type: ignore[attr-defined]

        try:
            # 首先尝试从配置文件加载
            if os.path.exists(self.gcc_config_file):  # type: ignore[attr-defined]
                with open(self.gcc_config_file, "r", encoding="utf-8") as f:  # type: ignore[attr-defined]
                    config = json.load(f)
                    gcc_path = config.get("gcc_path", "")
                    if gcc_path and os.path.exists(gcc_path):
                        # 验证路径是否是有效的 mingw 目录
                        is_valid, _ = validate_mingw_directory(gcc_path)
                        if is_valid:
                            self.gcc_path_edit.setText(gcc_path)  # type: ignore[attr-defined]
                            self.gcc_config_loaded = True  # type: ignore[attr-defined]
                            self.gcc_config_loading = False  # type: ignore[attr-defined]
                            self._update_gcc_download_button_visibility()  # type: ignore[attr-defined]
                            return

            # 尝试在 Nuitka 缓存中查找 mingw 目录
            cached_gcc = self.find_gcc_in_cache()
            if cached_gcc:
                self.gcc_path_edit.setText(cached_gcc)  # type: ignore[attr-defined]
                self.save_gcc_config()

            self.gcc_config_loaded = True  # type: ignore[attr-defined]
            self._update_gcc_download_button_visibility()  # type: ignore[attr-defined]

        except Exception as e:
            print(f"加载GCC配置失败: {e}")
        finally:
            self.gcc_config_loading = False  # type: ignore[attr-defined]

    def save_gcc_config(self) -> None:
        """保存 GCC 配置"""
        try:
            gcc_path = self.gcc_path_edit.text().strip()  # type: ignore[attr-defined]
            config = {"gcc_path": gcc_path}
            with open(self.gcc_config_file, "w", encoding="utf-8") as f:  # type: ignore[attr-defined]
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存GCC配置失败: {e}")

    def _update_gcc_download_button_visibility(self) -> None:
        """根据 GCC 路径可用性更新 GCC 下载按钮的可见性"""
        from utils.gcc_downloader import validate_mingw_directory

        gcc_path = self.gcc_path_edit.text().strip()  # type: ignore[attr-defined]
        # 如果 GCC 路径已设置且是有效的 mingw 目录，则隐藏下载按钮
        if gcc_path and os.path.exists(gcc_path):
            is_valid, _ = validate_mingw_directory(gcc_path)
            if is_valid:
                self.gcc_download_btn.setVisible(False)  # type: ignore[attr-defined]
                return
        # 如果没有有效的 GCC 路径，则显示下载按钮
        self.gcc_download_btn.setVisible(True)  # type: ignore[attr-defined]

    def on_gcc_path_changed(self, text: str) -> None:
        """
        GCC 路径变更处理

        Args:
            text: 新的 GCC 路径
        """
        if self.gcc_config_loading:  # type: ignore[attr-defined]
            return

        gcc_path = text.strip()
        if gcc_path and os.path.exists(gcc_path):
            self.save_gcc_config()

        self._update_gcc_download_button_visibility()  # type: ignore[attr-defined]

    def download_gcc(self) -> None:
        """下载 GCC 工具链（支持多线程下载、重试、验证和自动解压）"""
        from utils.gcc_downloader import GCCDownloader

        if self.is_downloading:  # type: ignore[attr-defined]
            # 取消下载
            self.cancel_download = True  # type: ignore[attr-defined]
            self.gcc_download_btn.setText("自动下载")  # type: ignore[attr-defined]
            self.gcc_download_btn.setStyleSheet("")  # 重置为默认样式  # type: ignore[attr-defined]
            self.gcc_download_label.setText("正在取消...")  # type: ignore[attr-defined]
            return

        self.is_downloading = True  # type: ignore[attr-defined]
        self.cancel_download = False  # type: ignore[attr-defined]
        self.gcc_download_btn.setText("取消下载")  # type: ignore[attr-defined]
        # 应用与取消打包按钮相同的危险按钮样式
        style = self.theme_manager.get_danger_button_style()  # type: ignore[attr-defined]
        self.gcc_download_btn.setStyleSheet(style)  # type: ignore[attr-defined]
        self.gcc_download_label.setText("准备下载...")  # type: ignore[attr-defined]

        def download_task():
            try:
                # 创建日志和进度回调
                def log_callback(msg: str) -> None:
                    self.log_signal.emit(msg)  # type: ignore[attr-defined]

                def progress_callback(msg: str) -> None:
                    self.update_download_progress_signal.emit(msg)  # type: ignore[attr-defined]

                def cancel_check() -> bool:
                    return self.cancel_download  # type: ignore[attr-defined]

                # 使用 GCCDownloader 进行下载和解压
                downloader = GCCDownloader(
                    log_callback=log_callback,
                    progress_callback=progress_callback,
                    cancel_check=cancel_check,
                )

                # 首先检查是否已存在有效的 mingw 目录
                existing_mingw = downloader.find_existing_gcc()
                if existing_mingw:
                    self.update_download_progress_signal.emit("发现已存在的有效GCC工具链")  # type: ignore[attr-defined]
                    self.gcc_download_complete_signal.emit(existing_mingw)  # type: ignore[attr-defined]
                    self.update_download_progress_signal.emit("已加载现有工具链")  # type: ignore[attr-defined]
                    return

                # 执行下载和解压
                result_path = downloader.download()

                if self.cancel_download:  # type: ignore[attr-defined]
                    self.update_download_progress_signal.emit("下载已取消")  # type: ignore[attr-defined]
                elif result_path:
                    self.update_download_progress_signal.emit("下载并解压完成！")  # type: ignore[attr-defined]
                    # 在 UI 中更新 GCC 路径
                    self.gcc_download_complete_signal.emit(result_path)  # type: ignore[attr-defined]
                else:
                    self.update_download_progress_signal.emit("下载失败，请重试")  # type: ignore[attr-defined]
                    self._show_gcc_download_failed_dialog()  # type: ignore[attr-defined]

            except Exception as e:
                self.update_download_progress_signal.emit(f"下载出错: {str(e)}")  # type: ignore[attr-defined]
                self._show_gcc_download_failed_dialog()  # type: ignore[attr-defined]
            finally:
                self.is_downloading = False  # type: ignore[attr-defined]
                self.gcc_download_reset_button_signal.emit()  # type: ignore[attr-defined]

        self.download_thread = threading.Thread(target=download_task, daemon=True)  # type: ignore[attr-defined]
        self.download_thread.start()  # type: ignore[attr-defined]

    def _on_gcc_download_complete(self, gcc_path: str) -> None:
        """
        GCC 下载完成处理

        Args:
            gcc_path: 下载完成的 GCC 路径
        """
        self.gcc_path_edit.setText(gcc_path)  # type: ignore[attr-defined]
        self.save_gcc_config()
        self._update_gcc_download_button_visibility()

    def _on_gcc_download_reset_button(self) -> None:
        """重置 GCC 下载按钮状态"""
        self.gcc_download_btn.setText("自动下载")  # type: ignore[attr-defined]
        self.gcc_download_btn.setStyleSheet("")  # type: ignore[attr-defined]

    @pyqtSlot()
    def _show_gcc_download_failed_dialog(self) -> None:
        """显示 GCC 下载失败对话框，提示用户手动下载"""
        from utils.gcc_downloader import GCCDownloader

        # 根据系统架构提示下载对应版本
        arch = GCCDownloader.get_system_arch()
        if arch == "x86_64":
            arch_hint = "x86_64-posix-seh"
        else:
            arch_hint = "i686-posix-dwarf"

        msg_box = QMessageBox(self)  # type: ignore[arg-type]
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("GCC下载失败")
        msg_box.setText(
            "自动下载GCC工具链失败，可能是网络问题。\n\n"
            "您可以：\n"
            "1. 点击「重试」再次尝试自动下载\n"
            "2. 点击「手动下载」打开下载页面，下载zip文件后手动解压到：\n"
            f"   {GCCDownloader.get_nuitka_cache_dir()}\n"
            "   然后使用「浏览」按钮选择解压后的 mingw64 或 mingw32 目录\n\n"
            "下载地址：\n"
            "https://github.com/brechtsanders/winlibs_mingw/releases/latest\n\n"
            f"请下载包含 {arch_hint} 的zip文件（当前系统架构: {arch}）。"
        )
        retry_btn = msg_box.addButton("重试", QMessageBox.ButtonRole.AcceptRole)
        manual_btn = msg_box.addButton("手动下载", QMessageBox.ButtonRole.ActionRole)
        msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        clicked_btn = msg_box.clickedButton()
        if clicked_btn == retry_btn:
            # 重新开始下载
            self.download_gcc()
        elif clicked_btn == manual_btn:
            # 打开浏览器
            webbrowser.open("https://github.com/brechtsanders/winlibs_mingw/releases/latest")

    def validate_gcc_path(self, gcc_path: str) -> tuple[bool, str]:
        """
        验证 GCC 路径是否有效

        Args:
            gcc_path: GCC 路径

        Returns:
            (是否有效, 错误消息)
        """
        from utils.gcc_downloader import validate_mingw_directory

        if not gcc_path:
            return False, "GCC 路径为空"

        if not os.path.exists(gcc_path):
            return False, f"GCC 路径不存在: {gcc_path}"

        is_valid, msg = validate_mingw_directory(gcc_path)
        if not is_valid:
            return False, msg

        return True, "GCC 路径有效"

    def ensure_gcc_available(self) -> tuple[bool, str]:
        """
        确保 GCC 可用

        如果已配置则验证，否则尝试从缓存加载。

        Returns:
            (是否可用, GCC 路径或错误消息)
        """
        gcc_path = self.gcc_path_edit.text().strip()  # type: ignore[attr-defined]

        if gcc_path:
            is_valid, msg = self.validate_gcc_path(gcc_path)
            if is_valid:
                return True, gcc_path
            else:
                return False, msg

        # 尝试从缓存加载
        cached_gcc = self.find_gcc_in_cache()
        if cached_gcc:
            self.gcc_path_edit.setText(cached_gcc)  # type: ignore[attr-defined]
            self.save_gcc_config()
            return True, cached_gcc

        return False, "未找到 GCC 工具链，请下载或手动指定路径"
