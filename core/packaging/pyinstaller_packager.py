"""
PyInstaller 打包器模块

本模块负责使用 PyInstaller 进行打包，包括：
- 构建 PyInstaller 命令行参数
- 处理隐藏导入和排除模块
- 处理数据文件和资源
- 执行打包过程

功能：
- 支持单文件和目录模式
- 支持 GUI 和控制台模式
- 支持图标和版本信息
- 支持 UPX 压缩
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.packaging.base import CREATE_NO_WINDOW, BasePackager, verify_tool


class PyInstallerPackager(BasePackager):
    """PyInstaller 打包器"""

    def __init__(self):
        """初始化 PyInstaller 打包器"""
        super().__init__()

    def verify_pyinstaller(self, python_path: str) -> Tuple[bool, str]:
        """验证 PyInstaller 是否可用"""
        return verify_tool(python_path, "PyInstaller")

    def build_command(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        script_name: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str] = None,
    ) -> List[str]:
        """
        构建 PyInstaller 命令行参数

        Args:
            python_path: Python 解释器路径
            config: 打包配置
            output_dir: 输出目录
            script_name: 脚本名称
            hidden_imports: 隐藏导入列表
            exclude_modules: 排除模块列表
            icon_path: 图标路径

        Returns:
            命令行参数列表
        """
        script_path = config["script_path"]

        cmd = [
            python_path,
            "-m", "PyInstaller",
            "--noconfirm",
            "--clean",
            f"--name={script_name}",
            f"--distpath={output_dir}",
            f"--workpath={os.path.join(output_dir, 'build')}",
            f"--specpath={output_dir}",
        ]

        # 单文件模式
        if config.get("onefile", True):
            cmd.append("--onefile")

            # 创建并添加运行时 hook，用于切换工作目录到解压目录
            # 这使得相对路径资源加载（如图标）像在源码运行或 Nuitka 中一样工作
            try:
                hook_path = os.path.join(output_dir, "rthook_chdir.py")
                os.makedirs(output_dir, exist_ok=True)
                with open(hook_path, "w", encoding="utf-8") as f:
                    f.write("import sys\n")
                    f.write("import os\n")
                    f.write("if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):\n")
                    f.write("    os.chdir(sys._MEIPASS)\n")
                cmd.append(f"--runtime-hook={hook_path}")
            except Exception:
                pass
        else:
            cmd.append("--onedir")

        # 控制台模式
        if not config.get("console", False):
            cmd.append("--windowed")

        # 图标
        if icon_path and os.path.exists(icon_path):
            cmd.append(f"--icon={icon_path}")

        # UPX 压缩 - 默认强制禁用以防止文件损坏
        # PyInstaller 的 UPX 经常导致 exe 无法运行或被杀毒软件误报
        if config.get("upx", False):
            upx_path = config.get("upx_path")
            if upx_path and os.path.exists(upx_path):
                cmd.append(f"--upx-dir={os.path.dirname(upx_path)}")
        else:
            cmd.append("--noupx")

        # 自动包含图标文件作为数据文件
        separator = ";" if sys.platform == "win32" else ":"
        original_icon = config.get("icon_path") or config.get("icon")

        if original_icon and os.path.exists(original_icon):
            # 将图标文件添加到根目录
            cmd.append(f"--add-data={original_icon}{separator}.")

            # 1. 以标准名称 icon<ext> 包含副本
            # 这样即使用户代码写死加载 "icon.png" 也能工作
            basename = os.path.basename(original_icon)
            ext = os.path.splitext(original_icon)[1]
            std_name = f"icon{ext}"

            if basename.lower() != std_name.lower():
                try:
                    import shutil
                    std_icon_path = os.path.join(output_dir, std_name)
                    shutil.copy2(original_icon, std_icon_path)
                    cmd.append(f"--add-data={std_icon_path}{separator}.")
                except Exception:
                    pass

            # 如果使用了转换后的图标，也添加进去
            if icon_path and icon_path != original_icon and os.path.exists(icon_path):
                cmd.append(f"--add-data={icon_path}{separator}.")

                # 2. 如果是转换后的 ICO，也提供一个 icon.ico 的副本
                if icon_path.endswith('.ico') and "icon_converted.ico" in os.path.basename(icon_path):
                    try:
                        import shutil
                        std_ico_path = os.path.join(output_dir, "icon.ico")
                        shutil.copy2(icon_path, std_ico_path)
                        cmd.append(f"--add-data={std_ico_path}{separator}.")
                    except Exception:
                        pass

        # 隐藏导入
        for hidden in hidden_imports:
            cmd.append(f"--hidden-import={hidden}")

        # 排除模块
        for exclude in exclude_modules:
            cmd.append(f"--exclude-module={exclude}")

        # 额外数据文件
        extra_data = config.get("extra_data", [])
        for data in extra_data:
            if os.path.exists(data):
                cmd.append(f"--add-data={data}{os.pathsep}.")

        # 版本信息
        version_file = config.get("version_file")
        if version_file and os.path.exists(version_file):
            cmd.append(f"--version-file={version_file}")

        # 添加脚本路径
        cmd.append(script_path)

        return cmd

    def package(
        self,
        python_path: str,
        config: Dict,
        output_dir: str,
        hidden_imports: List[str],
        exclude_modules: List[str],
        icon_path: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        执行 PyInstaller 打包

        Args:
            python_path: Python 解释器路径
            config: 打包配置
            output_dir: 输出目录
            hidden_imports: 隐藏导入列表
            exclude_modules: 排除模块列表
            icon_path: 图标路径

        Returns:
            (是否成功, 消息)
        """
        # 验证 PyInstaller
        is_available, version_info = self.verify_pyinstaller(python_path)
        if not is_available:
            return False, f"PyInstaller 不可用: {version_info}"

        self.log(f"✓ PyInstaller 版本: {version_info}")

        script_path = config["script_path"]
        project_dir = config.get("project_dir")

        # 确定输出文件名
        if config.get("program_name"):
            script_name = config["program_name"]
        elif project_dir and os.path.basename(project_dir):
            script_name = os.path.basename(project_dir)
        else:
            script_name = Path(script_path).stem

        self.log(f"输出文件名: {script_name}")

        # 构建命令
        cmd = self.build_command(
            python_path,
            config,
            output_dir,
            script_name,
            hidden_imports,
            exclude_modules,
            icon_path,
        )

        self.log(f"\n执行命令: {' '.join(cmd)}...")

        try:
            # 执行打包
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
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
                exe_path = self._find_output_exe(output_dir, script_name, config)

                if exe_path and os.path.exists(exe_path):
                    self._last_exe_path = exe_path
                    # 清理构建临时文件
                    self.clean_build_files(output_dir, script_name)
                    return True, f"打包成功！\n\n输出文件: {exe_path}"
                else:
                    return False, "打包完成，但未找到输出文件"
            else:
                return False, f"PyInstaller 执行失败，返回码: {process.returncode}"

        except Exception as e:
            return False, f"执行 PyInstaller 时出错: {str(e)}"

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
        if config.get("onefile", True):
            # 单文件模式
            exe_path = os.path.join(output_dir, f"{script_name}.exe")
            if os.path.exists(exe_path):
                return exe_path
        else:
            # 目录模式
            exe_path = os.path.join(output_dir, script_name, f"{script_name}.exe")
            if os.path.exists(exe_path):
                return exe_path

        # 尝试其他可能的位置
        for pattern in [f"{script_name}.exe", f"{script_name}/{script_name}.exe"]:
            path = os.path.join(output_dir, pattern)
            if os.path.exists(path):
                return path

        return None

    def test_exe_for_missing_modules(
        self,
        exe_path: str,
        timeout: int = 10,
    ) -> Tuple[bool, Set[str]]:
        """
        测试 exe 运行，检测是否有缺失的模块

        Args:
            exe_path: exe 文件路径
            timeout: 超时时间

        Returns:
            (运行成功, 缺失的模块集合)
        """
        self.log("\n" + "=" * 50)
        self.log("第三层防护：打包后自动测试")
        self.log("=" * 50)
        self.log(f"测试运行: {exe_path}")

        if not os.path.exists(exe_path):
            self.log("⚠️ exe 文件不存在，跳过测试")
            return True, set()

        missing_modules = set()
        process = None

        try:
            import time

            process = subprocess.Popen(
                [exe_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            self.log("正在检测程序启动状态...")

            # 等待一小段时间检测启动状态
            start_time = time.time()
            while time.time() - start_time < timeout:
                poll_result = process.poll()
                if poll_result is not None:
                    # 进程已退出
                    if poll_result != 0:
                        # 非正常退出，检查错误
                        _, stderr = process.communicate()
                        missing = self._parse_missing_modules(stderr)
                        if missing:
                            missing_modules.update(missing)
                            self.log(f"⚠️ 检测到缺失模块: {', '.join(missing)}")
                            return False, missing_modules
                    break

                time.sleep(0.5)

            # 如果进程还在运行，说明启动成功
            if process.poll() is None:
                self.log("✓ 程序启动成功")
                process.terminate()
                return True, set()

            return True, set()

        except Exception as e:
            self.log(f"⚠️ 测试时出错: {e}")
            return True, set()
        finally:
            if process and process.poll() is None:
                try:
                    process.terminate()
                except Exception:
                    pass

    def _parse_missing_modules(self, error_output: str) -> Set[str]:
        """
        解析错误输出，提取缺失的模块

        Args:
            error_output: 错误输出内容

        Returns:
            缺失的模块集合
        """
        import re

        missing_modules = set()

        # 匹配模式：ModuleNotFoundError: No module named 'xxx'
        patterns = [
            r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
            r"ImportError: No module named ['\"]([^'\"]+)['\"]",
            r"No module named ['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, error_output)
            for match in matches:
                root_module = match.split('.')[0]
                missing_modules.add(match)
                if root_module != match:
                    missing_modules.add(root_module)

        return missing_modules

    def clean_build_files(self, output_dir: str, script_name: str) -> None:
        """
        清理构建文件

        Args:
            output_dir: 输出目录
            script_name: 脚本名称
        """
        import shutil

        # 清理 spec 文件
        spec_file = os.path.join(output_dir, f"{script_name}.spec")
        if os.path.exists(spec_file):
            try:
                os.remove(spec_file)
                self.log(f"已删除: {spec_file}")
            except Exception:
                pass

        # 清理运行时 hook 文件
        hook_file = os.path.join(output_dir, "rthook_chdir.py")
        if os.path.exists(hook_file):
            try:
                os.remove(hook_file)
                self.log(f"已删除: {hook_file}")
            except Exception:
                pass

        # 清理版本信息文件
        version_info_file = os.path.join(output_dir, "version_info.txt")
        if os.path.exists(version_info_file):
            try:
                os.remove(version_info_file)
                self.log(f"已删除: {version_info_file}")
            except Exception:
                pass

        # 清理 build 目录
        build_dir = os.path.join(output_dir, "build")
        if os.path.exists(build_dir):
            try:
                shutil.rmtree(build_dir)
                self.log(f"已删除: {build_dir}")
            except Exception:
                pass

        # 清理临时生成的图标文件
        icon_converted_path = os.path.join(output_dir, "icon_converted.ico")
        if os.path.exists(icon_converted_path):
            try:
                os.remove(icon_converted_path)
                self.log(f"已清理临时图标文件: {icon_converted_path}")
            except Exception as e:
                self.log(f"⚠️ 清理临时图标文件失败: {e}")

        # 清理临时复制的标准图标文件
        for ext in ['.ico', '.png', '.jpg', '.jpeg', '.bmp', '.svg']:
            std_icon = os.path.join(output_dir, f"icon{ext}")
            if os.path.exists(std_icon):
                try:
                    os.remove(std_icon)
                except Exception:
                    pass
