"""
包检测模块

本模块负责检测 Python 模块是否是真正的包（有 __path__ 属性），
用于正确选择打包策略（--include-package vs --include-module）。

功能：
- 检测模块是包还是单文件模块
- 支持标准包、命名空间包、C 扩展模块等
- 处理包名和导入名不一致的情况
"""

import subprocess
import sys
from typing import Dict, Optional, Set

from utils.constants import CREATE_NO_WINDOW


class PackageDetector:
    """包检测器，用于检测模块是包还是单文件模块"""

    # 包名到导入名的映射（处理安装名和导入名不一致的情况）
    PACKAGE_IMPORT_MAP: Dict[str, str] = {
        'dnspython': 'dns',
        'pillow': 'PIL',
        'beautifulsoup4': 'bs4',
        'pyyaml': 'yaml',
        'python-dateutil': 'dateutil',
        'opencv-python': 'cv2',
        'opencv-contrib-python': 'cv2',
        'pymysql': 'pymysql',
        'mysql-connector-python': 'mysql.connector',
        'requests': 'requests',
        'urllib3': 'urllib3',
        'certifi': 'certifi',
        'charset-normalizer': 'charset_normalizer',
        'idna': 'idna',
    }

    # 已知的单文件模块（明确不是包）
    KNOWN_SINGLE_FILE_MODULES: Set[str] = {
        'img2pdf', 'pyperclip', 'keyboard', 'mouse', 'pynput',
        'colorama', 'tqdm', 'click',
    }

    # 已知的标准库包（明确是包）
    KNOWN_STDLIB_PACKAGES: Set[str] = {
        'email', 'http', 'urllib', 'xml', 'json', 'logging',
        'multiprocessing', 'concurrent', 'asyncio', 'collections',
        'distutils', 'unittest', 'doctest', 'pdb', 'pydoc',
    }

    def __init__(self):
        """初始化包检测器"""
        self._module_type_cache: Dict[str, bool] = {}

    def get_import_name(self, module_name: str) -> str:
        """
        获取模块的实际导入名

        Args:
            module_name: 模块名（可能是 PyPI 包名）

        Returns:
            实际的导入名
        """
        return self.PACKAGE_IMPORT_MAP.get(module_name.lower(), module_name)

    def is_real_package(
        self, module_name: str, python_path: Optional[str] = None
    ) -> bool:
        """
        强化版包检测方法，支持所有类型的 Python 项目/脚本。

        检测一个模块是否是真正的包（有 __path__ 属性）。
        单文件模块（如 img2pdf.py）不是包，不能使用 --include-package。

        支持的情况：
        1. 标准包（有 __init__.py 的目录）
        2. 命名空间包（PEP 420，没有 __init__.py）
        3. 单文件模块（.py 文件）
        4. C 扩展模块（.pyd/.so）
        5. 内建模块
        6. 标准库模块
        7. 包名和导入名不一致的情况（如 dnspython -> dns）
        8. 导入失败的情况（保守处理，假设是包）

        Args:
            module_name: 模块名（可能是包名或导入名）
            python_path: Python解释器路径（可选）

        Returns:
            True 如果是包，False 如果是单文件模块
        """
        # 检查缓存
        if module_name in self._module_type_cache:
            return self._module_type_cache[module_name]

        if not python_path:
            python_path = sys.executable

        # 快速检查：已知的单文件模块
        if module_name.lower() in self.KNOWN_SINGLE_FILE_MODULES:
            self._module_type_cache[module_name] = False
            return False

        # 快速检查：已知的标准库包
        if module_name.lower() in self.KNOWN_STDLIB_PACKAGES:
            self._module_type_cache[module_name] = True
            return True

        # 获取实际导入名
        import_name = self.get_import_name(module_name)

        # 增强的检测代码，支持多种检测方式
        check_code = f'''
import sys
import importlib
import os
from pathlib import Path

def detect_module_type(module_name):
    """检测模块类型：package, module, builtin, error"""
    try:
        # 尝试导入模块
        mod = importlib.import_module(module_name)

        # 检查是否是内建模块
        if module_name in sys.builtin_module_names:
            # 内建模块通常是单文件模块
            return "module"

        # 检查是否有 __path__ 属性（包的特征）
        if hasattr(mod, "__path__"):
            # 有 __path__ 属性，是包
            # 进一步验证：检查 __path__ 是否指向目录
            path = mod.__path__
            if isinstance(path, (list, tuple)) and len(path) > 0:
                first_path = path[0]
                if os.path.exists(first_path) and os.path.isdir(first_path):
                    return "package"
            return "package"

        # 检查是否有 __file__ 属性
        if hasattr(mod, "__file__"):
            file_path = mod.__file__
            if file_path:
                # 检查文件扩展名
                if file_path.endswith(('.py', '.pyc', '.pyo')):
                    # Python 源文件或字节码文件
                    # 检查是否是 __init__.py（包的标志）
                    if os.path.basename(file_path) in ('__init__.py', '__init__.pyc', '__init__.pyo'):
                        return "package"
                    # 检查父目录是否有 __init__.py（标准包）
                    parent_dir = os.path.dirname(file_path)
                    if os.path.exists(os.path.join(parent_dir, '__init__.py')):
                        return "package"
                    # 否则是单文件模块
                    return "module"
                elif file_path.endswith(('.pyd', '.so')):
                    # C 扩展模块，通常是单文件模块
                    return "module"

        # 如果没有 __file__ 和 __path__，可能是命名空间包
        # 命名空间包也有 __path__，但如果检测不到，可能是特殊情况
        # 保守处理：假设是包
        return "package"

    except ImportError as e:
        # 导入失败，尝试通过文件系统查找
        # 检查 site-packages 目录
        for path in sys.path:
            if 'site-packages' in path or 'dist-packages' in path:
                module_path = os.path.join(path, module_name)
                if os.path.isdir(module_path):
                    # 是目录，可能是包
                    # 检查是否有 __init__.py（标准包）或没有（命名空间包）
                    init_file = os.path.join(module_path, '__init__.py')
                    if os.path.exists(init_file) or not os.listdir(module_path):
                        return "package"
                elif os.path.isfile(module_path + '.py'):
                    # 是 .py 文件，是单文件模块
                    return "module"
                elif os.path.isfile(module_path + '.pyd') or os.path.isfile(module_path + '.so'):
                    # 是 C 扩展模块，是单文件模块
                    return "module"

        # 无法确定，保守处理：假设是包
        return "package"
    except Exception as e:
        # 其他错误，保守处理：假设是包
        return "package"

result = detect_module_type("{import_name}")
print(result)
'''
        try:
            result = subprocess.run(
                [python_path, "-c", check_code],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            output = result.stdout.strip()

            if output == "package":
                self._module_type_cache[module_name] = True
                return True
            elif output == "module":
                self._module_type_cache[module_name] = False
                return False
            else:
                # 输出不是预期的值，可能是错误
                # 对于已知的包名映射，如果检测失败，默认假设是包
                if module_name.lower() in self.PACKAGE_IMPORT_MAP:
                    self._module_type_cache[module_name] = True
                    return True
                # 其他情况：保守处理，假设是包（避免遗漏）
                self._module_type_cache[module_name] = True
                return True
        except subprocess.TimeoutExpired:
            # 超时：保守处理，假设是包
            if module_name.lower() in self.PACKAGE_IMPORT_MAP:
                self._module_type_cache[module_name] = True
                return True
            self._module_type_cache[module_name] = True
            return True
        except Exception:
            # 其他异常：保守处理，假设是包
            if module_name.lower() in self.PACKAGE_IMPORT_MAP:
                self._module_type_cache[module_name] = True
                return True
            self._module_type_cache[module_name] = True
            return True

    def clear_cache(self) -> None:
        """清除模块类型缓存"""
        self._module_type_cache.clear()

    def get_cached_results(self) -> Dict[str, bool]:
        """
        获取缓存的检测结果

        Returns:
            模块名到是否为包的映射
        """
        return self._module_type_cache.copy()
