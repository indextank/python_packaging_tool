"""
动态导入追踪模块

本模块负责在运行时动态追踪 Python 脚本的导入行为，
用于捕获静态分析无法检测到的动态导入。

功能：
- 运行脚本并追踪所有导入
- 支持 GUI 程序检测和处理
- 超时保护机制
- 导入结果解析
"""

import json
import os
import subprocess
import sys
import tempfile
from typing import Callable, Optional, Set, Tuple

from core.analyzer.gui_detection import GUIDetector
from utils.constants import CREATE_NO_WINDOW


class DynamicImportTracer:
    """动态导入追踪器"""

    def __init__(self):
        """初始化动态导入追踪器"""
        self.log: Callable = print
        self.gui_detector = GUIDetector()
        self._traced_imports: Set[str] = set()

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback

    def get_traced_imports(self) -> Set[str]:
        """获取追踪到的导入"""
        return self._traced_imports.copy()

    def trace_dynamic_imports(
        self,
        script_path: str,
        python_path: str,
        project_dir: Optional[str] = None,
        timeout: int = 20,
        is_stdlib_func: Optional[Callable[[str], bool]] = None,
    ) -> Tuple[bool, Set[str]]:
        """
        动态追踪脚本运行时的所有导入

        Args:
            script_path: Python脚本路径
            python_path: Python解释器路径
            project_dir: 项目目录
            timeout: 超时时间（秒）
            is_stdlib_func: 检测模块是否是标准库的函数

        Returns:
            (是否成功, 追踪到的模块集合)
        """
        self.log("\n" + "=" * 50)
        self.log("第一层防护：动态模块导入追踪")
        self.log("=" * 50)

        # 检测是否是 GUI 程序
        is_gui, gui_framework = self.gui_detector.detect_gui_in_script(script_path)
        if is_gui:
            self.log(f"检测到 GUI 框架: {gui_framework}")
            self.log("将使用静态分析 + 通用策略")
            return False, set()

        # 创建追踪脚本
        tracer_code = self._generate_tracer_code(script_path, timeout)

        # 写入临时文件
        tracer_script = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.py',
                delete=False,
                encoding='utf-8'
            ) as f:
                f.write(tracer_code)
                tracer_script = f.name

            self.log(f"运行脚本进行动态追踪（超时: {timeout}秒）...")

            # 设置工作目录
            cwd = project_dir if project_dir else os.path.dirname(script_path)

            # 运行追踪脚本
            env = os.environ.copy()
            if project_dir:
                env['PYTHONPATH'] = project_dir

            result = subprocess.run(
                [python_path, tracer_script],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # 解析输出
            traced_imports = self._parse_tracer_output(result.stdout, is_stdlib_func)

            if traced_imports is not None:
                self._traced_imports = traced_imports
                self.log(f"✓ 动态追踪成功！捕获到 {len(traced_imports)} 个第三方模块导入")

                # 显示部分结果
                if traced_imports:
                    sample = sorted(list(traced_imports))[:10]
                    self.log(f"  示例: {', '.join(sample)}{'...' if len(traced_imports) > 10 else ''}")

                return True, traced_imports
            else:
                self.log("⚠️ 动态追踪未能获取导入信息")
                if result.stderr:
                    self.log(f"  错误: {result.stderr[:200]}")
                return False, set()

        except subprocess.TimeoutExpired:
            self.log(f"⚠️ 脚本运行超时（{timeout}秒）")
            self.log("  可能是 GUI 程序或长时间运行的脚本，切换到通用策略")
            self._try_terminate_tracer_process(tracer_script)
            return False, set()
        except Exception as e:
            self.log(f"⚠️ 动态追踪失败: {str(e)}")
            self.log("  将使用通用库自动支持策略")
            return False, set()
        finally:
            # 清理临时文件
            try:
                if tracer_script and os.path.exists(tracer_script):
                    os.unlink(tracer_script)
            except Exception:
                pass

    def _generate_tracer_code(self, script_path: str, timeout: int) -> str:
        """生成追踪脚本代码"""
        return '''
import sys
import importlib
import importlib.abc
import json
import threading

class ImportTracer(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.imports = set()

    def find_module(self, fullname, path=None):
        self.imports.add(fullname)
        return None

tracer = ImportTracer()
sys.meta_path.insert(0, tracer)

# 用于标记是否应该退出
_should_exit = False
_import_phase_done = False

def output_and_exit():
    """输出收集到的导入并退出"""
    print("__IMPORTS_START__")
    print(json.dumps(list(tracer.imports)))
    print("__IMPORTS_END__")
    sys.stdout.flush()
    import os
    os._exit(0)

# 设置超时保护
def timeout_handler():
    output_and_exit()

timer = threading.Timer({timeout}, timeout_handler)
timer.daemon = True
timer.start()

# 拦截常见的 GUI 主循环入口，防止进入事件循环
_original_modules = {{}}

class GUIBlocker:
    """阻止 GUI 事件循环启动"""

    @staticmethod
    def block_tkinter():
        try:
            import tkinter
            original_mainloop = tkinter.Tk.mainloop
            def blocked_mainloop(self, n=0):
                output_and_exit()
            tkinter.Tk.mainloop = blocked_mainloop

            # 也拦截 Misc.mainloop
            if hasattr(tkinter, 'Misc'):
                tkinter.Misc.mainloop = blocked_mainloop
        except:
            pass

    @staticmethod
    def block_pyqt():
        for qt_module in ['PyQt6.QtWidgets', 'PyQt5.QtWidgets', 'PySide6.QtWidgets', 'PySide2.QtWidgets']:
            try:
                QtWidgets = importlib.import_module(qt_module)
                original_exec = QtWidgets.QApplication.exec
                def blocked_exec(self=None):
                    output_and_exit()
                QtWidgets.QApplication.exec = blocked_exec
                QtWidgets.QApplication.exec_ = blocked_exec
            except:
                pass

    @staticmethod
    def block_wx():
        try:
            import wx
            original_mainloop = wx.App.MainLoop
            def blocked_mainloop(self):
                output_and_exit()
            wx.App.MainLoop = blocked_mainloop
        except:
            pass

    @staticmethod
    def block_pygame():
        try:
            import pygame
            # pygame 没有显式的主循环，但我们可以在 display.flip 时退出
            original_flip = pygame.display.flip
            _flip_count = [0]
            def blocked_flip():
                _flip_count[0] += 1
                if _flip_count[0] > 2:  # 允许几次初始化
                    output_and_exit()
                return original_flip()
            pygame.display.flip = blocked_flip
        except:
            pass

# 应用所有阻止器
GUIBlocker.block_tkinter()
GUIBlocker.block_pyqt()
GUIBlocker.block_wx()
GUIBlocker.block_pygame()

try:
    # 运行目标脚本
    import runpy
    runpy.run_path("{script_path}", run_name="__main__")
except SystemExit:
    pass
except Exception as e:
    pass
finally:
    timer.cancel()
    output_and_exit()
'''.format(
            timeout=timeout - 2,
            script_path=script_path.replace("\\", "\\\\")
        )

    def _parse_tracer_output(
        self,
        stdout: str,
        is_stdlib_func: Optional[Callable[[str], bool]] = None,
    ) -> Optional[Set[str]]:
        """解析追踪脚本输出"""
        if "__IMPORTS_START__" in stdout and "__IMPORTS_END__" in stdout:
            start = stdout.index("__IMPORTS_START__") + len("__IMPORTS_START__")
            end = stdout.index("__IMPORTS_END__")
            imports_json = stdout[start:end].strip()

            traced_imports = set(json.loads(imports_json))

            # 过滤标准库和内部模块
            filtered_imports = set()
            for imp in traced_imports:
                root_module = imp.split('.')[0]
                if is_stdlib_func:
                    if not is_stdlib_func(root_module):
                        filtered_imports.add(imp)
                else:
                    # 如果没有提供标准库检测函数，保留所有导入
                    filtered_imports.add(imp)

            return filtered_imports

        return None

    def _try_terminate_tracer_process(self, tracer_script: Optional[str]) -> None:
        """尝试终止追踪进程"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and tracer_script and tracer_script in ' '.join(cmdline):
                        proc.terminate()
                except Exception:
                    pass
        except Exception:
            pass

    def check_script_runnable(
        self,
        script_path: str,
        python_path: str,
        project_dir: Optional[str] = None,
    ) -> bool:
        """
        检查脚本是否可以运行（快速语法检查+导入检查）

        Args:
            script_path: 脚本路径
            python_path: Python 解释器路径
            project_dir: 项目目录

        Returns:
            True 如果脚本可以运行
        """
        self.log("\n检查脚本是否可运行...")

        # 1. 语法检查
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                source = f.read()
            compile(source, script_path, 'exec')
            self.log("  ✓ 语法检查通过")
        except SyntaxError as e:
            self.log(f"  ✗ 语法错误: {e}")
            return False

        # 2. 快速导入检查（只检查顶层导入）
        check_code = f'''
import sys
sys.path.insert(0, r"{project_dir or os.path.dirname(script_path)}")
try:
    import ast
    with open(r"{script_path}", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split(".")[0])

    # 尝试导入
    failed = []
    for imp in set(imports):
        if imp in ["__future__"]:
            continue
        try:
            __import__(imp)
        except ImportError:
            failed.append(imp)

    if failed:
        print("IMPORT_FAILED:" + ",".join(failed))
        sys.exit(1)
    else:
        print("IMPORT_OK")
        sys.exit(0)
except Exception as e:
    print(f"CHECK_ERROR:{{e}}")
    sys.exit(1)
'''

        try:
            result = subprocess.run(
                [python_path, '-c', check_code],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if "IMPORT_OK" in result.stdout:
                self.log("  ✓ 导入检查通过")
                return True
            elif "IMPORT_FAILED" in result.stdout:
                failed = result.stdout.split("IMPORT_FAILED:")[1].strip()
                self.log(f"  ⚠️ 部分导入失败: {failed}")
                self.log("  脚本可能无法完整运行，将使用混合策略")
                return False
            else:
                self.log("  ⚠️ 检查结果未知")
                return False

        except subprocess.TimeoutExpired:
            self.log("  ⚠️ 检查超时")
            return False
        except Exception as e:
            self.log(f"  ⚠️ 检查失败: {e}")
            return False
