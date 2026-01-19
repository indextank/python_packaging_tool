"""
工作线程模块

基于QRunnable/QThread的后台任务工作线程，支持取消操作和线程安全通信。
"""

import subprocess
import sys
import traceback
from typing import Any, Callable, Dict, Optional

from PyQt6.QtCore import QMutex, QObject, QRunnable, QThread, pyqtSignal, pyqtSlot

# Windows子进程隐藏控制台窗口标志
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _handle_worker_exception(signals: "WorkerSignals", prefix: str, e: Exception) -> None:
    """统一处理工作线程异常"""
    error_msg = str(e)
    tb = traceback.format_exc()
    signals.error.emit(error_msg, tb)
    signals.finished.emit(False, f"{prefix}: {error_msg}")


class WorkerSignals(QObject):
    """
    工作线程用于与主线程通信的信号。

    此类定义工作线程可以发出的所有信号，
    以安全地与UI线程通信。
    """

    # 通用信号
    started = pyqtSignal()
    finished = pyqtSignal(bool, str)  # (成功, 消息)
    error = pyqtSignal(str, str)  # (错误消息, 堆栈跟踪)
    progress = pyqtSignal(int)  # 进度百分比 (0-100)

    # 日志
    log = pyqtSignal(str)

    # 数据信号
    result = pyqtSignal(object)  # 通用结果
    update_exclude_modules = pyqtSignal(str)  # 模块列表更新
    update_download_progress = pyqtSignal(str)  # 下载进度文本


class BaseWorker(QRunnable):
    """
    使用QRunnable与QThreadPool的基础工作类。

    此模式适用于不需要直接线程控制的即发即弃任务。
    对于需要暂停/恢复或复杂状态管理的长时间运行任务，
    请使用基于QThread的工作线程。
    """

    def __init__(self):
        super().__init__()
        self.signals = WorkerSignals()
        self._is_cancelled = False
        self._mutex = QMutex()

    def cancel(self) -> None:
        """请求取消工作线程"""
        self._mutex.lock()
        self._is_cancelled = True
        self._mutex.unlock()

    def is_cancelled(self) -> bool:
        """检查是否请求了取消（线程安全）"""
        self._mutex.lock()
        cancelled = self._is_cancelled
        self._mutex.unlock()
        return cancelled

    @pyqtSlot()
    def run(self) -> None:
        """执行工作线程任务 - 在子类中重写"""
        raise NotImplementedError("子类必须实现run()方法")


class PackagingWorker(BaseWorker):
    """
    打包操作工作线程（PyInstaller/Nuitka）。

    在后台线程中运行打包过程，并发出
    进度/日志信号以更新UI。
    """

    def __init__(
        self,
        packager: Any,
        config: Dict[str, Any],
    ):
        super().__init__()
        self.packager = packager
        self.config = config
        self._process: Optional[subprocess.Popen] = None

    def get_process(self) -> Optional[subprocess.Popen]:
        """获取当前子进程（用于外部取消）"""
        return self._process

    def set_process(self, process: subprocess.Popen) -> None:
        """设置当前子进程"""
        self._process = process

    @pyqtSlot()
    def run(self) -> None:
        """执行打包操作"""
        self.signals.started.emit()

        try:
            # 为打包器定义回调函数
            def log_callback(message: str) -> None:
                if not self.is_cancelled():
                    self.signals.log.emit(message)

            def cancel_check() -> bool:
                return self.is_cancelled()

            def process_callback(process: subprocess.Popen) -> None:
                self.set_process(process)

            # 运行打包器
            success, message, exe_path = self.packager.package(
                self.config,
                log_callback=log_callback,
                cancel_flag=cancel_check,
                process_callback=process_callback,
            )

            if self.is_cancelled():
                self.signals.finished.emit(False, "打包已取消")
            else:
                if success and exe_path:
                    self.signals.result.emit(exe_path)
                self.signals.finished.emit(success, message)

        except Exception as e:
            _handle_worker_exception(self.signals, "打包出错", e)

    def terminate_process(self) -> None:
        """终止正在运行的子进程（如果有）"""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass


class DependencyAnalysisWorker(BaseWorker):
    """
    分析项目依赖的工作线程。
    """

    def __init__(
        self,
        analyzer: Any,
        script_path: str,
        project_dir: Optional[str] = None,
    ):
        super().__init__()
        self.analyzer = analyzer
        self.script_path = script_path
        self.project_dir = project_dir

    @pyqtSlot()
    def run(self) -> None:
        """执行依赖分析"""
        self.signals.started.emit()

        try:
            def log_callback(message: str) -> None:
                if not self.is_cancelled():
                    self.signals.log.emit(message)

            # 分析依赖
            self.signals.log.emit("正在分析项目依赖...")

            deps = self.analyzer.analyze(
                self.script_path,
                project_dir=self.project_dir,
            )

            if self.is_cancelled():
                self.signals.finished.emit(False, "分析已取消")
                return

            # 生成排除模块建议
            exclude_modules = self.analyzer.suggest_excludes(deps)
            if exclude_modules:
                modules_str = ",".join(exclude_modules)
                self.signals.update_exclude_modules.emit(modules_str)
                self.signals.log.emit(f"建议排除模块: {modules_str}")

            self.signals.result.emit(deps)
            self.signals.finished.emit(True, "依赖分析完成")

        except Exception as e:
            _handle_worker_exception(self.signals, "分析出错", e)


class DownloadWorker(BaseWorker):
    """
    下载文件的工作线程（例如：GCC工具链、UPX）。

    支持进度报告和取消操作。
    """

    def __init__(
        self,
        download_func: Callable[..., bool],
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__()
        self.download_func = download_func
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self) -> None:
        """执行下载操作"""
        self.signals.started.emit()

        try:
            # 如果函数支持，将取消检查添加到kwargs
            self.kwargs["cancel_check"] = self.is_cancelled

            # 添加进度回调
            def progress_callback(message: str) -> None:
                if not self.is_cancelled():
                    self.signals.update_download_progress.emit(message)
                    self.signals.log.emit(message)

            self.kwargs["progress_callback"] = progress_callback

            # 执行下载
            result = self.download_func(*self.args, **self.kwargs)

            if self.is_cancelled():
                self.signals.finished.emit(False, "下载已取消")
            else:
                self.signals.result.emit(result)
                self.signals.finished.emit(
                    bool(result),
                    "下载完成" if result else "下载失败"
                )

        except TypeError:
            # 函数不支持我们的回调，尝试不使用它们
            try:
                self.kwargs.pop("cancel_check", None)
                self.kwargs.pop("progress_callback", None)
                result = self.download_func(*self.args, **self.kwargs)
                self.signals.result.emit(result)
                self.signals.finished.emit(bool(result), "下载完成" if result else "下载失败")
            except Exception as e:
                _handle_worker_exception(self.signals, "下载出错", e)

        except Exception as e:
            _handle_worker_exception(self.signals, "下载出错", e)


class GenericWorker(BaseWorker):
    """
    在后台线程中运行任何可调用对象的通用工作线程。

    用于不需要专门处理的简单后台任务。
    """

    def __init__(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    @pyqtSlot()
    def run(self) -> None:
        """执行可调用对象"""
        self.signals.started.emit()

        try:
            result = self.func(*self.args, **self.kwargs)

            if self.is_cancelled():
                self.signals.finished.emit(False, "任务已取消")
            else:
                self.signals.result.emit(result)
                self.signals.finished.emit(True, "任务完成")

        except Exception as e:
            _handle_worker_exception(self.signals, "任务出错", e)


class LongRunningWorker(QThread):
    """
    基于QThread的工作线程，用于需要直接线程控制的长时间运行任务。

    当您需要以下功能时使用此模式：
    - 暂停/恢复功能
    - 复杂的状态管理
    - 直接的线程生命周期控制

    对于更简单的任务，优先使用基于QRunnable的工作线程与QThreadPool。
    """

    # 信号
    started_signal = pyqtSignal()
    finished_signal = pyqtSignal(bool, str)
    error_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    log_signal = pyqtSignal(str)
    result_signal = pyqtSignal(object)

    def __init__(
        self,
        func: Callable[..., Any],
        *args: Any,
        parent: Optional[QObject] = None,
        **kwargs: Any,
    ):
        super().__init__(parent)
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self._is_cancelled = False
        self._is_paused = False
        self._mutex = QMutex()

    def cancel(self) -> None:
        """请求取消"""
        self._mutex.lock()
        self._is_cancelled = True
        self._mutex.unlock()

    def is_cancelled(self) -> bool:
        """检查是否已取消（线程安全）"""
        self._mutex.lock()
        cancelled = self._is_cancelled
        self._mutex.unlock()
        return cancelled

    def pause(self) -> None:
        """暂停工作线程"""
        self._mutex.lock()
        self._is_paused = True
        self._mutex.unlock()

    def resume(self) -> None:
        """恢复工作线程"""
        self._mutex.lock()
        self._is_paused = False
        self._mutex.unlock()

    def is_paused(self) -> bool:
        """检查是否已暂停（线程安全）"""
        self._mutex.lock()
        paused = self._is_paused
        self._mutex.unlock()
        return paused

    def run(self) -> None:
        """执行任务"""
        self.started_signal.emit()

        try:
            # 如果函数支持，将取消检查注入到kwargs中
            self.kwargs["cancel_check"] = self.is_cancelled
            self.kwargs["pause_check"] = self.is_paused

            result = self.func(*self.args, **self.kwargs)

            if self.is_cancelled():
                self.finished_signal.emit(False, "任务已取消")
            else:
                self.result_signal.emit(result)
                self.finished_signal.emit(True, "任务完成")

        except TypeError:
            # 函数不支持我们的回调
            try:
                self.kwargs.pop("cancel_check", None)
                self.kwargs.pop("pause_check", None)
                result = self.func(*self.args, **self.kwargs)
                self.result_signal.emit(result)
                self.finished_signal.emit(True, "任务完成")
            except Exception as e:
                self._emit_error("任务出错", e)

        except Exception as e:
            self._emit_error("任务出错", e)

    def _emit_error(self, prefix: str, e: Exception) -> None:
        """发出错误信号"""
        self.error_signal.emit(str(e), traceback.format_exc())
        self.finished_signal.emit(False, f"{prefix}: {e}")
