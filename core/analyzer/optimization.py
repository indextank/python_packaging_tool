"""
优化建议模块

本模块负责生成打包优化建议，包括：
- 建议排除的模块列表
- 包大小分析
- 优化报告生成

功能：
- 分析已安装包的大小
- 生成排除模块建议
- 生成优化报告
"""

import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Set, Tuple

from core.analyzer_constants import DEV_PACKAGES, LARGE_PACKAGES
from utils.constants import CREATE_NO_WINDOW


class OptimizationAdvisor:
    """优化建议生成器"""

    def __init__(self):
        """初始化优化建议生成器"""
        self.log: Callable = print
        self.excluded_modules: Set[str] = set()

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback

    def get_exclude_modules(self, dependencies: Set[str]) -> List[str]:
        """
        获取建议排除的模块列表

        Args:
            dependencies: 依赖包集合

        Returns:
            建议排除的模块列表
        """
        exclude_list = []

        # 1. 排除开发/测试包
        for dep in dependencies:
            if dep in DEV_PACKAGES:
                exclude_list.append(dep)
                self.excluded_modules.add(dep)

        # 2. 排除大型包的测试模块
        for dep in dependencies:
            if dep in LARGE_PACKAGES:
                for submodule in LARGE_PACKAGES[dep]:
                    exclude_list.append(submodule)

        # 3. 添加常见的测试和文档模块
        exclude_list.extend([
            "test",
            "tests",
            "testing",
            "*.tests",
            "*.test",
            "*_test",
            "*_tests",
            "setuptools",
            "pip",
            "wheel",
        ])

        return list(set(exclude_list))

    def get_package_size_info(
        self,
        dependencies: Set[str],
        python_path: str,
    ) -> Dict[str, Dict[str, float]]:
        """
        获取已安装包的大小信息

        Args:
            dependencies: 依赖包集合
            python_path: Python可执行文件路径

        Returns:
            包大小信息字典
        """
        size_info = {}

        for dep in dependencies:
            try:
                # 使用pip show获取包信息
                exe_path = python_path if python_path else sys.executable
                result = subprocess.run(
                    [exe_path, "-m", "pip", "show", dep],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=5,
                    creationflags=CREATE_NO_WINDOW,
                )

                if result.returncode == 0:
                    lines = result.stdout.split("\n")
                    location = None

                    for line in lines:
                        if line.startswith("Location:"):
                            location = line.split(":", 1)[1].strip()
                            break

                    if location:
                        # 计算包目录大小
                        package_path = Path(location) / dep
                        if package_path.exists():
                            size = self._get_dir_size(package_path)
                            size_info[dep] = {
                                "size": size,
                                "size_mb": round(size / (1024 * 1024), 2),
                                "location": str(package_path),
                            }
            except Exception:
                # 忽略错误，继续处理其他包
                pass

        return size_info

    def _get_dir_size(self, path: Path) -> int:
        """递归计算目录大小"""
        total = 0
        try:
            for entry in path.rglob("*"):
                if entry.is_file():
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        pass
        except OSError:
            pass
        return total

    def get_optimization_suggestions(
        self,
        dependencies: Set[str],
        hidden_imports: List[str],
        python_path: str,
    ) -> Tuple[List[str], List[str], Dict[str, Dict[str, float]]]:
        """
        获取打包优化建议

        Args:
            dependencies: 依赖包集合
            hidden_imports: 隐藏导入列表
            python_path: Python可执行文件路径

        Returns:
            (排除模块列表, 隐藏导入列表, 包大小信息)
        """
        exclude_modules = self.get_exclude_modules(dependencies)
        size_info = self.get_package_size_info(dependencies, python_path)

        return exclude_modules, hidden_imports, size_info

    def generate_optimization_report(
        self,
        dependencies: Set[str],
        hidden_imports: List[str],
        python_path: str,
    ) -> str:
        """
        生成优化报告

        Args:
            dependencies: 依赖包集合
            hidden_imports: 隐藏导入列表
            python_path: Python可执行文件路径

        Returns:
            优化报告文本
        """
        exclude_modules, _, size_info = self.get_optimization_suggestions(
            dependencies, hidden_imports, python_path
        )

        report = []
        report.append("=" * 60)
        report.append("打包优化分析报告")
        report.append("=" * 60)
        report.append("")

        # 依赖包列表
        report.append(f"检测到 {len(dependencies)} 个第三方依赖包:")
        for dep in sorted(dependencies):
            if dep in size_info:
                size_mb = size_info[dep]["size_mb"]
                report.append(f"  - {dep} ({size_mb} MB)")
            else:
                report.append(f"  - {dep}")
        report.append("")

        # 大型包警告
        large_packages = [
            dep
            for dep in dependencies
            if dep in size_info and size_info[dep]["size_mb"] > 50
        ]
        if large_packages:
            report.append("⚠ 检测到大型包 (>50MB):")
            for pkg in large_packages:
                report.append(f"  - {pkg} ({size_info[pkg]['size_mb']} MB)")
            report.append("  建议: 确认是否真的需要这些大型库")
            report.append("")

        # 排除建议
        if exclude_modules:
            report.append(f"建议排除 {len(exclude_modules)} 个模块/包:")
            for mod in sorted(set(exclude_modules))[:20]:  # 只显示前20个
                if mod in DEV_PACKAGES:
                    report.append(f"  - {mod} (开发/测试工具)")
                else:
                    report.append(f"  - {mod}")
            if len(exclude_modules) > 20:
                report.append(f"  ... 还有 {len(exclude_modules) - 20} 个")
            report.append("")

        # 隐藏导入建议
        if hidden_imports:
            report.append(f"建议添加 {len(hidden_imports)} 个隐藏导入:")
            for mod in sorted(hidden_imports)[:10]:
                report.append(f"  - {mod}")
            if len(hidden_imports) > 10:
                report.append(f"  ... 还有 {len(hidden_imports) - 10} 个")
            report.append("")

        # 总体建议
        report.append("优化建议:")
        report.append("  1. 使用虚拟环境，只安装必要的依赖")
        report.append("  2. 自动排除开发/测试相关的包")
        report.append("  3. 排除大型库的测试模块")
        report.append("  4. 使用UPX压缩可进一步减小体积")
        report.append("")

        # 预计优化效果
        total_size = sum(info["size_mb"] for info in size_info.values())
        excluded_size = sum(
            size_info[dep]["size_mb"]
            for dep in self.excluded_modules
            if dep in size_info
        )
        if total_size > 0:
            saved_percent = (excluded_size / total_size) * 100 if total_size > 0 else 0
            report.append("预计效果:")
            report.append(f"  - 总依赖大小: {total_size:.2f} MB")
            report.append(f"  - 可排除大小: {excluded_size:.2f} MB")
            report.append(f"  - 预计节省: {saved_percent:.1f}%")
            report.append("")

        report.append("=" * 60)

        return "\n".join(report)

    def auto_collect_submodules(
        self,
        package_name: str,
        python_path: str,
    ) -> List[str]:
        """
        自动收集包的子模块

        Args:
            package_name: 包名
            python_path: Python解释器路径

        Returns:
            子模块列表
        """
        collect_code = f'''
import sys
import importlib
import pkgutil
import json

def get_submodules(package_name, max_depth=2):
    """递归获取包的子模块"""
    submodules = [package_name]

    try:
        pkg = importlib.import_module(package_name)
        if not hasattr(pkg, '__path__'):
            return submodules

        for importer, modname, ispkg in pkgutil.walk_packages(
            pkg.__path__, prefix=package_name + '.', onerror=lambda x: None
        ):
            depth = modname.count('.')
            if depth <= max_depth:
                submodules.append(modname)
                if len(submodules) > 100:
                    break
    except Exception:
        pass

    return submodules

result = get_submodules("{package_name}")
print("__SUBMODULES_START__")
print(json.dumps(result))
print("__SUBMODULES_END__")
'''

        try:
            exe_path = python_path if python_path else sys.executable
            result = subprocess.run(
                [exe_path, "-c", collect_code],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=CREATE_NO_WINDOW,
            )

            stdout = result.stdout
            if "__SUBMODULES_START__" in stdout and "__SUBMODULES_END__" in stdout:
                start = stdout.index("__SUBMODULES_START__") + len("__SUBMODULES_START__")
                end = stdout.index("__SUBMODULES_END__")
                submodules_json = stdout[start:end].strip()

                import json
                submodules = json.loads(submodules_json)
                return submodules

        except Exception as e:
            self.log(f"    ⚠️ 收集子模块失败: {e}")

        # 失败时返回基本模块
        return [package_name]

    def collect_all_unconfigured_submodules(
        self,
        dependencies: Set[str],
        python_path: str,
        configured_libraries: Set[str],
        is_stdlib_func: Callable[[str], bool],
    ) -> Dict[str, List[str]]:
        """
        收集所有未配置库的子模块

        Args:
            dependencies: 依赖包集合
            python_path: Python解释器路径
            configured_libraries: 已配置的库集合
            is_stdlib_func: 检测模块是否是标准库的函数

        Returns:
            未配置库的子模块字典
        """
        self.log("\n" + "=" * 50)
        self.log("第二层防护：自动收集子模块")
        self.log("=" * 50)

        auto_collected_modules: Dict[str, List[str]] = {}

        # PyPI 包名到导入名的映射
        package_to_module: Dict[str, str] = {
            'dnspython': 'dns',
            'pillow': 'PIL',
            'beautifulsoup4': 'bs4',
            'pyyaml': 'yaml',
            'python-dateutil': 'dateutil',
            'opencv-python': 'cv2',
            'opencv-contrib-python': 'cv2',
            'scikit-learn': 'sklearn',
            'scikit-image': 'skimage',
            'pywin32': 'win32api',
            'python-dotenv': 'dotenv',
            'PyMuPDF': 'fitz',
        }

        # 收集未配置的库，同时合并 PyPI 包名和导入名
        unconfigured_modules: Dict[str, str] = {}  # module_name -> original_dep
        seen_modules: Set[str] = set()

        for dep in dependencies:
            if is_stdlib_func(dep):
                continue

            # 获取实际的模块名
            module_name = package_to_module.get(dep, dep)

            # 检查是否已配置
            dep_lower = dep.lower()
            module_lower = module_name.lower()
            is_configured = (
                dep in configured_libraries or
                dep_lower in {lib.lower() for lib in configured_libraries} or
                module_name in configured_libraries or
                module_lower in {lib.lower() for lib in configured_libraries}
            )

            if not is_configured:
                # 使用模块名作为键，避免重复（如 dns 和 dnspython 都映射到 dns）
                if module_name not in seen_modules:
                    seen_modules.add(module_name)
                    unconfigured_modules[module_name] = dep

        if not unconfigured_modules:
            self.log("所有依赖都已有配置，无需自动收集")
            return auto_collected_modules

        self.log(f"发现 {len(unconfigured_modules)} 个未配置的库，开始自动收集子模块:")

        for module_name, original_dep in unconfigured_modules.items():
            display_name = f"{original_dep} ({module_name})" if original_dep != module_name else module_name
            self.log(f"\n  收集 {display_name} 的子模块...")
            submodules = self.auto_collect_submodules(module_name, python_path)

            # 无论是否为单文件模块，都存储结果，避免 fallthrough 到 common patterns
            auto_collected_modules[module_name] = submodules
            if original_dep != module_name:
                auto_collected_modules[original_dep] = submodules
            if len(submodules) > 1:
                self.log(f"    ✓ 收集到 {len(submodules)} 个子模块")
            else:
                self.log("    ✓ 单文件模块，仅包含基础模块")

        return auto_collected_modules
