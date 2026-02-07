"""
打包处理器 Mixin

本模块包含 MainWindow 中与打包操作相关的方法。
从 main_window.py 拆分出来，遵循单一职责原则。
"""

import os
import platform
import subprocess
import threading


class PackagingHandlerMixin:
    """
    打包处理器 Mixin 类

    提供打包操作相关的方法。
    设计为与 MainWindow 一起使用的 Mixin。

    注意：此类使用 Mixin 模式，self 实际上是 MainWindow 实例
    """

    def toggle_packaging(self) -> None:
        """切换打包状态（开始/取消）"""
        if self.is_packaging:  # type: ignore[attr-defined]
            self.cancel_packaging_process()  # type: ignore[attr-defined]
        else:
            self.start_packaging()  # type: ignore[attr-defined]

    def cancel_packaging_process(self) -> None:
        """取消打包进程"""
        self.append_log("\n请求取消打包...")  # type: ignore[attr-defined]
        self.cancel_packaging = True  # type: ignore[attr-defined]

        # 终止打包进程
        if self.packaging_process:  # type: ignore[attr-defined]
            try:
                self.packaging_process.terminate()  # type: ignore[attr-defined]
                self.append_log("正在终止打包进程...")  # type: ignore[attr-defined]
                # 尝试强制终止
                try:
                    self.packaging_process.wait(timeout=3)  # type: ignore[attr-defined]
                except subprocess.TimeoutExpired:
                    self.packaging_process.kill()  # type: ignore[attr-defined]
                    self.append_log("已强制终止进程")  # type: ignore[attr-defined]
            except Exception as e:
                self.append_log(f"终止进程时出错: {str(e)}")  # type: ignore[attr-defined]

        # 如果使用 QThreadPool，取消 worker
        if self._current_packaging_worker:  # type: ignore[attr-defined]
            self._current_packaging_worker.cancel()  # type: ignore[attr-defined]

        # 更新按钮文本显示取消中状态
        self.package_btn.setText("取消中...")  # type: ignore[attr-defined]
        self.package_btn.setEnabled(False)  # type: ignore[attr-defined]

    def start_packaging(self) -> None:
        """开始打包流程"""
        from core.packager import Packager

        # 验证脚本路径
        script_path = self.script_path_edit.text().strip()  # type: ignore[attr-defined]
        if not script_path:
            self._show_warning("警告", "请选择运行脚本！")  # type: ignore[attr-defined]
            return

        if not os.path.exists(script_path):
            self._show_warning("警告", "脚本文件不存在！")  # type: ignore[attr-defined]
            return

        # 验证 Nuitka 的 GCC 路径
        if self.nuitka_radio.isChecked():  # type: ignore[attr-defined]
            gcc_path = self.gcc_path_edit.text().strip()  # type: ignore[attr-defined]
            if gcc_path and not gcc_path.endswith(".zip") and not os.path.isdir(gcc_path):
                self._show_warning("警告", "GCC路径必须是.zip文件或目录！")  # type: ignore[attr-defined]
                return

        # 获取配置
        config = self.get_config()  # type: ignore[attr-defined]

        # 清空并初始化日志
        self.log_text.clear()  # type: ignore[attr-defined]
        self.append_log("=" * 50)  # type: ignore[attr-defined]
        self.append_log("开始打包流程...")  # type: ignore[attr-defined]
        self.append_log(f"工具: {config['tool']}")  # type: ignore[attr-defined]
        self.append_log(f"脚本: {config['script_path']}")  # type: ignore[attr-defined]
        if config.get("exclude_modules"):
            self.append_log(f"排除模块: {', '.join(config['exclude_modules'])}")  # type: ignore[attr-defined]
        self.append_log("=" * 50)  # type: ignore[attr-defined]

        # 设置打包状态
        self.is_packaging = True  # type: ignore[attr-defined]
        self.cancel_packaging = False  # type: ignore[attr-defined]
        self.packaging_process = None  # type: ignore[attr-defined]
        self.package_btn.setText("取消打包")  # type: ignore[attr-defined]
        self._set_cancel_button_style()  # type: ignore[attr-defined]

        # 禁用其他按钮
        self.analyze_btn.setEnabled(False)  # type: ignore[attr-defined]
        self.clear_btn.setEnabled(False)  # type: ignore[attr-defined]

        def task():
            try:
                def log_callback(msg: str) -> None:
                    self.log_signal.emit(msg)  # type: ignore[attr-defined]

                def process_callback(process: subprocess.Popen) -> None:
                    self.packaging_process = process  # type: ignore[attr-defined]

                packager = Packager()
                success, message, exe_path = packager.package(
                    config,
                    log_callback=log_callback,
                    cancel_flag=lambda: self.cancel_packaging,  # type: ignore[attr-defined]
                    process_callback=process_callback,
                )

                if success:
                    self.log_signal.emit("\n" + "=" * 50)  # type: ignore[attr-defined]
                    self.log_signal.emit("打包成功！")  # type: ignore[attr-defined]
                    self.log_signal.emit("=" * 50)  # type: ignore[attr-defined]

                    self.finished_signal.emit(True, message)  # type: ignore[attr-defined]

                    if exe_path:
                        self.open_output_directory(exe_path)  # type: ignore[attr-defined]
                else:
                    self.log_signal.emit("\n" + "=" * 50)  # type: ignore[attr-defined]
                    self.log_signal.emit("打包失败！")  # type: ignore[attr-defined]
                    self.log_signal.emit("=" * 50)  # type: ignore[attr-defined]
                    self.finished_signal.emit(False, message)  # type: ignore[attr-defined]

            except Exception as e:
                self.log_signal.emit(f"打包过程发生错误: {str(e)}")  # type: ignore[attr-defined]
                self.finished_signal.emit(False, str(e))  # type: ignore[attr-defined]

        threading.Thread(target=task, daemon=True).start()

    def on_packaging_finished(self, success: bool, message: str) -> None:
        """
        打包完成处理

        Args:
            success: 是否成功
            message: 结果消息
        """
        # 重置状态
        was_cancelled = self.cancel_packaging  # type: ignore[attr-defined]

        self.is_packaging = False  # type: ignore[attr-defined]
        self.cancel_packaging = False  # type: ignore[attr-defined]
        self.packaging_process = None  # type: ignore[attr-defined]
        self._current_packaging_worker = None  # type: ignore[attr-defined]
        self.package_btn.setText("开始打包")  # type: ignore[attr-defined]
        self.package_btn.setEnabled(True)  # type: ignore[attr-defined]
        self._reset_package_button_style()  # type: ignore[attr-defined]

        self.set_buttons_enabled(True)  # type: ignore[attr-defined]

        # 如果是取消操作，不显示消息框
        if was_cancelled:
            self.append_log("打包已取消")  # type: ignore[attr-defined]
            return

        if success:
            self._show_info("成功", message)  # type: ignore[attr-defined]
        else:
            self._show_error("失败", message)  # type: ignore[attr-defined]

    def open_output_directory(self, exe_path: str) -> None:
        """
        打开输出目录并选中生成的 exe 文件

        Args:
            exe_path: exe 文件路径
        """
        try:
            if not os.path.exists(exe_path):
                self.append_log(f"文件不存在: {exe_path}")  # type: ignore[attr-defined]
                return

            directory = os.path.dirname(exe_path)
            system = platform.system()

            if system == "Windows":
                # 使用 os.startfile 打开目录
                try:
                    os.startfile(directory)
                except Exception:
                    # 备用方法：使用 shell 命令
                    try:
                        normalized_path = os.path.normpath(exe_path)
                        subprocess.run(
                            f'explorer /select,"{normalized_path}"',
                            shell=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
                    except Exception:
                        subprocess.run(
                            f'explorer "{os.path.normpath(directory)}"',
                            shell=True,
                            creationflags=subprocess.CREATE_NO_WINDOW,
                        )
            elif system == "Darwin":
                subprocess.Popen(["open", "-R", exe_path])
            else:
                try:
                    subprocess.Popen(["xdg-open", directory])
                except Exception:
                    subprocess.Popen(["nautilus", directory])

            self.append_log(f"\n已打开输出目录: {directory}")  # type: ignore[attr-defined]

        except Exception as e:
            self.append_log(f"打开目录时出错: {str(e)}")  # type: ignore[attr-defined]

    def get_config(self) -> dict:
        """
        获取打包配置

        Returns:
            打包配置字典
        """
        config = {
            "project_dir": self.project_dir_edit.text().strip(),  # type: ignore[attr-defined]
            "script_path": self.script_path_edit.text().strip(),  # type: ignore[attr-defined]
            "output_dir": self.output_dir_edit.text().strip(),  # type: ignore[attr-defined]
            "program_name": self.program_name_edit.text().strip(),  # type: ignore[attr-defined]
            "icon_path": self.icon_path_edit.text().strip(),  # type: ignore[attr-defined]
            "python_path": self.python_path_edit.text().strip(),  # type: ignore[attr-defined]
            "console": self.console_check.isChecked(),  # type: ignore[attr-defined]
            "onefile": self.onefile_check.isChecked(),  # type: ignore[attr-defined]
            "tool": "nuitka" if self.nuitka_radio.isChecked() else "pyinstaller",  # type: ignore[attr-defined]
            "exclude_modules": [],
        }

        # 添加版本信息（如果已配置）
        if hasattr(self, "version_info") and self.version_info:  # type: ignore[attr-defined]
            if self.version_info_check.isChecked():  # type: ignore[attr-defined]
                config["version_info"] = self.version_info  # type: ignore[attr-defined]

        # 添加排除模块
        if hasattr(self, "exclude_modules_list") and self.exclude_modules_list:  # type: ignore[attr-defined]
            config["exclude_modules"] = list(self.exclude_modules_list)  # type: ignore[attr-defined]

        # Nuitka 特定配置
        if self.nuitka_radio.isChecked():  # type: ignore[attr-defined]
            config["gcc_path"] = self.gcc_path_edit.text().strip()  # type: ignore[attr-defined]
            # 添加 Nuitka 选项
            if hasattr(self, "nuitka_options") and self.nuitka_options:  # type: ignore[attr-defined]
                config["nuitka_options"] = self.nuitka_options  # type: ignore[attr-defined]

        return config

    def set_buttons_enabled(self, enabled: bool) -> None:
        """
        设置按钮启用状态

        Args:
            enabled: 是否启用
        """
        self.analyze_btn.setEnabled(enabled)  # type: ignore[attr-defined]
        self.clear_btn.setEnabled(enabled)  # type: ignore[attr-defined]

    def _set_cancel_button_style(self) -> None:
        """设置取消按钮样式（危险按钮样式）"""
        style = self.theme_manager.get_danger_button_style()  # type: ignore[attr-defined]
        self.package_btn.setStyleSheet(style)  # type: ignore[attr-defined]

    def _reset_package_button_style(self) -> None:
        """重置打包按钮样式"""
        self.package_btn.setStyleSheet("")  # type: ignore[attr-defined]

    def analyze_dependencies(self) -> None:
        """分析项目依赖"""
        from core.dependency_analyzer import DependencyAnalyzer

        project_dir = self.project_dir_edit.text().strip()  # type: ignore[attr-defined]
        script_path = self.script_path_edit.text().strip()  # type: ignore[attr-defined]

        if not project_dir and not script_path:
            self._show_warning("警告", "请先选择项目目录或脚本文件！")  # type: ignore[attr-defined]
            return

        # 确定分析目标
        target_path = project_dir if project_dir else os.path.dirname(script_path)

        self.append_log("\n" + "=" * 50)  # type: ignore[attr-defined]
        self.append_log("开始分析依赖...")  # type: ignore[attr-defined]
        self.append_log("=" * 50)  # type: ignore[attr-defined]

        self.analyze_btn.setEnabled(False)  # type: ignore[attr-defined]
        self.analyze_btn.setText("分析中...")  # type: ignore[attr-defined]

        def task():
            try:
                def log_callback(msg: str) -> None:
                    self.log_signal.emit(msg)  # type: ignore[attr-defined]

                analyzer = DependencyAnalyzer()
                analyzer.log = log_callback  # type: ignore[method-assign]

                # 检测 Qt 框架
                if script_path:
                    analyzer.detect_primary_qt_framework(script_path, project_dir)

                # 分析项目
                analyzer.analyze(target_path)

                # 获取优化建议
                python_path_text = self.python_path_edit.text().strip()  # type: ignore[attr-defined]
                python_path = python_path_text if python_path_text else None
                exclude_modules, hidden_imports, _ = analyzer.get_optimization_suggestions(
                    python_path or ""
                )

                # 更新 UI
                self.exclude_modules_signal.emit(list(exclude_modules))  # type: ignore[attr-defined]

                self.log_signal.emit("\n" + "=" * 50)  # type: ignore[attr-defined]
                self.log_signal.emit("依赖分析完成！")  # type: ignore[attr-defined]
                self.log_signal.emit(f"建议排除模块: {len(exclude_modules)} 个")  # type: ignore[attr-defined]
                self.log_signal.emit(f"建议隐藏导入: {len(hidden_imports)} 个")  # type: ignore[attr-defined]
                self.log_signal.emit("=" * 50)  # type: ignore[attr-defined]

                self.finished_signal.emit(True, "依赖分析完成")  # type: ignore[attr-defined]

            except Exception as e:
                self.log_signal.emit(f"依赖分析出错: {str(e)}")  # type: ignore[attr-defined]
                self.finished_signal.emit(False, str(e))  # type: ignore[attr-defined]

        threading.Thread(target=task, daemon=True).start()

    def _on_analyze_finished(self) -> None:
        """依赖分析完成处理"""
        self.analyze_btn.setEnabled(True)  # type: ignore[attr-defined]
        self.analyze_btn.setText("分析依赖")  # type: ignore[attr-defined]

    def update_exclude_modules_ui(self, modules: list) -> None:
        """
        更新排除模块 UI

        Args:
            modules: 排除模块列表
        """
        if not hasattr(self, "exclude_modules_list"):
            self.exclude_modules_list = set()  # type: ignore[attr-defined]

        self.exclude_modules_list.update(modules)  # type: ignore[attr-defined]
        self.append_log(f"已更新排除模块列表: {len(self.exclude_modules_list)} 个")  # type: ignore[attr-defined]
