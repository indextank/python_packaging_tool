"""
图标处理模块

本模块负责处理打包时的图标文件，包括：
- 图标格式检测和验证
- PNG/SVG/JPG/JPEG/BMP 格式转换为 ICO
- 多尺寸 ICO 文件生成（手动构建，确保 Windows Explorer 兼容性）

功能：
- 支持 PNG、JPG、JPEG、BMP、SVG 格式转换
- 自动生成多尺寸 ICO 文件（16x16, 32x32, 48x48, 64x64, 128x128, 256x256）
- 256x256 使用 PNG 压缩，其余尺寸使用标准 BMP 格式，兼容所有 Windows 版本
- 验证 ICO 文件是否包含必要尺寸
- SVG 矢量图形转换支持（使用 cairosvg 或 Pillow）

当打包工具本身作为 exe 运行时（Nuitka/PyInstaller onefile 模式），当前进程无法直接
import Pillow。此时会自动通过 subprocess 在目标项目的虚拟环境 Python 中执行图标转换，
确保图标处理功能在任何运行环境下都能正常工作。
"""

import io
import json
import os
import struct
import subprocess
import sys
from typing import Callable, List, Optional, Tuple

from core.packaging.base import CREATE_NO_WINDOW


def _check_pil_available() -> bool:
    """动态检查 PIL 是否可在当前进程中导入"""
    try:
        # importlib.util.find_spec 在打包后的环境中可能误报，
        # 所以直接尝试导入来确认
        from PIL import Image  # noqa: F401
        return True
    except Exception:
        return False


def _check_cairosvg_available() -> bool:
    """动态检查 cairosvg 是否可在当前进程中导入"""
    try:
        import cairosvg  # noqa: F401
        return True
    except Exception:
        return False


class IconProcessor:
    """图标处理器"""

    # ICO 文件需要包含的尺寸（从大到小排列）
    ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

    # 256x256 使用 PNG 压缩，其余使用 BMP 格式（Windows Explorer 兼容性最佳）
    PNG_THRESHOLD = 256

    # 必需的最小尺寸（用于验证）
    REQUIRED_SIZES = [(16, 16), (32, 32), (48, 48)]

    # 支持的图标格式
    SUPPORTED_FORMATS = ['.ico', '.png', '.jpg', '.jpeg', '.bmp', '.svg']

    # 需要转换的格式
    CONVERTIBLE_FORMATS = ['.png', '.jpg', '.jpeg', '.bmp', '.svg']

    def __init__(self):
        """初始化图标处理器"""
        self.log: Callable = print

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback

    def is_pillow_available(self) -> bool:
        """检查 Pillow 是否可在当前进程中使用"""
        return _check_pil_available()

    def is_cairosvg_available(self) -> bool:
        """检查 cairosvg 是否可在当前进程中使用"""
        return _check_cairosvg_available()

    # ------------------------------------------------------------------
    #  辅助脚本定位与 subprocess 调用
    # ------------------------------------------------------------------

    def _get_helper_script_path(self) -> Optional[str]:
        """
        获取 icon_convert_helper.py 辅助脚本的路径

        辅助脚本位于与本模块相同的目录中。当打包工具本身被打包为 exe 后，
        需要将辅助脚本写入临时目录以供 subprocess 调用。

        Returns:
            辅助脚本的绝对路径，如果无法获取则返回 None
        """
        # 方式 1：与本文件同目录（从源码运行时）
        this_dir = os.path.dirname(os.path.abspath(__file__))
        helper_path = os.path.join(this_dir, "icon_convert_helper.py")
        if os.path.isfile(helper_path):
            return helper_path

        # 方式 2：在打包后环境中，辅助脚本可能不存在于文件系统
        # 此时尝试从模块中读取并写入临时文件
        try:
            import importlib.resources
            # Python 3.9+ files() API
            if hasattr(importlib.resources, 'files'):
                pkg = importlib.resources.files("core.packaging")
                helper_resource = pkg.joinpath("icon_convert_helper.py")
                if hasattr(helper_resource, 'read_text'):
                    content = helper_resource.read_text(encoding='utf-8')
                    if content:
                        import tempfile
                        tmp_path = os.path.join(tempfile.gettempdir(), "icon_convert_helper.py")
                        with open(tmp_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        return tmp_path
        except Exception:
            pass

        # 方式 3：直接嵌入最小化版本到临时文件
        return self._write_embedded_helper_script()

    def _write_embedded_helper_script(self) -> Optional[str]:
        """
        将内嵌的辅助脚本写入临时文件

        当无法通过文件系统或包资源定位辅助脚本时，
        从内存中生成一个最小化版本。

        Returns:
            临时脚本路径
        """
        import tempfile

        # 读取 icon_convert_helper.py 的源代码
        # 我们尝试从已知位置读取
        possible_locations = []

        # 当前文件的父级目录
        this_dir = os.path.dirname(os.path.abspath(__file__))
        possible_locations.append(os.path.join(this_dir, "icon_convert_helper.py"))

        # 如果是 Nuitka onefile 环境，尝试在解压目录中查找
        if hasattr(sys, '_MEIPASS'):
            possible_locations.append(
                os.path.join(sys._MEIPASS, "core", "packaging", "icon_convert_helper.py")
            )

        # 尝试在 sys.path 中查找
        for p in sys.path:
            candidate = os.path.join(p, "core", "packaging", "icon_convert_helper.py")
            if candidate not in possible_locations:
                possible_locations.append(candidate)

        for loc in possible_locations:
            if os.path.isfile(loc):
                return loc

        # 最终手段：生成内嵌脚本
        helper_content = self._generate_inline_helper_script()
        tmp_path = os.path.join(tempfile.gettempdir(), "icon_convert_helper_embedded.py")
        try:
            with open(tmp_path, 'w', encoding='utf-8') as f:
                f.write(helper_content)
            return tmp_path
        except Exception:
            return None

    def _generate_inline_helper_script(self) -> str:
        """
        生成一段内嵌的辅助脚本源码字符串。

        该脚本包含图标转换所需的全部逻辑，可在任意安装了 Pillow 的
        Python 环境中独立运行。

        Returns:
            完整的 Python 脚本源码
        """
        # 这里直接返回一段自包含的脚本
        return r'''
import io
import json
import os
import struct
import sys

if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
PNG_THRESHOLD = 256
REQUIRED_SIZES = [(16, 16), (32, 32), (48, 48)]


def make_ico_bmp_entry(img):
    w, h = img.size
    pixels = img.load()
    xor_data = bytearray()
    for y in range(h - 1, -1, -1):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            xor_data.extend([b, g, r, a])
    and_row_bytes = ((w + 31) // 32) * 4
    and_data = bytearray(and_row_bytes * h)
    bih = struct.pack('<IIIHHIIIIII',
        40, w, h * 2, 1, 32, 0,
        len(xor_data) + len(and_data), 0, 0, 0, 0)
    return bih + bytes(xor_data) + bytes(and_data)


def build_ico_file(source_img, ico_path, log_lines):
    from PIL import Image
    count = len(ICO_SIZES)
    image_data_list = []
    for size in ICO_SIZES:
        w, h = size
        resized = source_img.resize(size, Image.Resampling.LANCZOS)
        fmt = 'PNG' if w >= PNG_THRESHOLD else 'BMP'
        log_lines.append(f"  \u751f\u6210 {w}x{h} \u5c3a\u5bf8 ({fmt})")
        if w >= PNG_THRESHOLD:
            png_buf = io.BytesIO()
            resized.save(png_buf, format='PNG')
            image_data_list.append((w, h, png_buf.getvalue()))
        else:
            bmp_data = make_ico_bmp_entry(resized)
            image_data_list.append((w, h, bmp_data))
        resized.close()
    header_size = 6
    directory_size = count * 16
    data_offset = header_size + directory_size
    with open(ico_path, 'wb') as f:
        f.write(struct.pack('<HHH', 0, 1, count))
        current_offset = data_offset
        for w, h, data in image_data_list:
            ico_w = 0 if w >= 256 else w
            ico_h = 0 if h >= 256 else h
            data_size = len(data)
            f.write(struct.pack('<BBBBHHII',
                ico_w, ico_h, 0, 0, 1, 32, data_size, current_offset))
            current_offset += data_size
        for _, _, data in image_data_list:
            f.write(data)


def verify_ico_file(ico_path):
    result = {"sizes": [], "count": 0, "valid": False, "warnings": [], "sizes_info": []}
    try:
        with open(ico_path, 'rb') as f:
            header = f.read(6)
            if len(header) < 6:
                result["warnings"].append("ICO file header incomplete")
                return result
            reserved, img_type, count = struct.unpack('<HHH', header)
            result["count"] = count
            if img_type != 1 or count < 1:
                result["warnings"].append("Invalid ICO file")
                return result
            entries = []
            for i in range(count):
                entry = f.read(16)
                if len(entry) < 16:
                    break
                width, height, colors, r2, planes, bpp, size, offset = struct.unpack('<BBBBHHII', entry)
                w = width if width != 0 else 256
                h = height if height != 0 else 256
                entries.append((w, h, size, offset))
            for w, h, sz, offset in entries:
                f.seek(offset)
                magic = f.read(4)
                is_png = magic == b'\x89PNG'
                fmt = 'PNG' if is_png else 'BMP'
                result["sizes"].append((w, h))
                result["sizes_info"].append(f"{w}x{h}({fmt})")
            missing = [s for s in REQUIRED_SIZES if s not in result["sizes"]]
            if missing:
                result["warnings"].append(f"Missing sizes: {missing}")
            has_256 = (256, 256) in result["sizes"]
            if not has_256:
                result["warnings"].append("Missing 256x256")
            result["valid"] = count >= 3 and not missing
    except Exception as e:
        result["warnings"].append(str(e))
    return result


def check_ico_needs_regeneration(ico_path):
    try:
        with open(ico_path, 'rb') as f:
            header = f.read(6)
            if len(header) < 6:
                return True, "ICO header incomplete"
            reserved, img_type, count = struct.unpack('<HHH', header)
            if img_type != 1 or count < 1:
                return True, "Invalid ICO"
            sizes_found = set()
            has_bmp_small = True
            entries_raw = []
            for i in range(count):
                entry = f.read(16)
                if len(entry) < 16:
                    break
                w, h, _, _, _, bpp, sz, offset = struct.unpack('<BBBBHHII', entry)
                w = w if w != 0 else 256
                h = h if h != 0 else 256
                sizes_found.add((w, h))
                entries_raw.append((w, h, sz, offset))
            for w, h, sz, offset in entries_raw:
                if w < PNG_THRESHOLD:
                    pos = f.tell()
                    f.seek(offset)
                    magic = f.read(4)
                    f.seek(pos)
                    if magic == b'\x89PNG':
                        has_bmp_small = False
            has_all_required = all(s in sizes_found for s in REQUIRED_SIZES)
            has_256 = (256, 256) in sizes_found
            if not has_all_required:
                missing = [s for s in REQUIRED_SIZES if s not in sizes_found]
                return True, f"Missing sizes: {missing}"
            elif not has_256:
                return True, "Missing 256x256"
            elif not has_bmp_small:
                return True, "Small sizes use PNG instead of BMP"
            else:
                return False, ""
    except Exception as e:
        return True, str(e)


def convert_image_to_ico(source_path, output_ico_path):
    result = {"success": False, "ico_path": output_ico_path, "sizes": [],
              "sizes_info": [], "warnings": [], "log": []}
    try:
        from PIL import Image
    except ImportError:
        result["error"] = "Pillow not installed"
        return result
    try:
        ext = os.path.splitext(source_path)[1].lower()
        if ext == '.ico':
            needs_regen, reason = check_ico_needs_regeneration(source_path)
            if not needs_regen:
                result["success"] = True
                result["ico_path"] = source_path
                result["log"].append("ICO already compliant")
                return result
            else:
                result["log"].append(f"ICO needs regeneration: {reason}")
                result["warnings"].append(f"Original ICO needs regeneration: {reason}")
        img = Image.open(source_path)
        original_size = img.size
        result["log"].append(f"Source size: {original_size[0]}x{original_size[1]}")
        if original_size[0] < 16 or original_size[1] < 16:
            result["warnings"].append(f"Source too small ({original_size[0]}x{original_size[1]})")
        if original_size[0] != original_size[1]:
            result["warnings"].append(f"Source not square ({original_size[0]}x{original_size[1]})")
        if img.mode != 'RGBA':
            if img.mode == 'P':
                img = img.convert('RGBA')
            elif img.mode in ['RGB', 'L']:
                rgba_img = Image.new('RGBA', img.size, (255, 255, 255, 255))
                if img.mode == 'RGB':
                    rgba_img.paste(img, (0, 0))
                else:
                    rgb_img = img.convert('RGB')
                    rgba_img.paste(rgb_img, (0, 0))
                    rgb_img.close()
                img.close()
                img = rgba_img
            else:
                img = img.convert('RGBA')
        output_dir = os.path.dirname(output_ico_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        build_ico_file(img, output_ico_path, result["log"])
        img.close()
        vr = verify_ico_file(output_ico_path)
        result["sizes"] = [f"{w}x{h}" for w, h in vr["sizes"]]
        result["sizes_info"] = vr["sizes_info"]
        result["warnings"].extend(vr["warnings"])
        ico_size = os.path.getsize(output_ico_path)
        result["log"].append(f"ICO file: {ico_size} bytes, {vr['count']} icons")
        result["log"].append(f"Sizes: {', '.join(vr['sizes_info'])}")
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)
        import traceback
        result["traceback"] = traceback.format_exc()
    return result


def convert_svg_to_ico(source_path, output_ico_path):
    result = {"success": False, "ico_path": output_ico_path, "sizes": [],
              "sizes_info": [], "warnings": [], "log": []}
    png_data = None
    try:
        import cairosvg
        result["log"].append("Using cairosvg...")
        png_data = cairosvg.svg2png(url=source_path, output_width=512, output_height=512)
    except ImportError:
        result["log"].append("cairosvg not available, trying Pillow...")
    except Exception as e:
        result["log"].append(f"cairosvg failed: {e}")
    if png_data is None:
        try:
            from PIL import Image
            img = Image.open(source_path)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            png_data = buf.getvalue()
            img.close()
        except Exception as e:
            result["error"] = f"Cannot convert SVG: {e}"
            return result
    if png_data is None:
        result["error"] = "SVG conversion failed"
        return result
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(png_data))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        output_dir = os.path.dirname(output_ico_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        build_ico_file(img, output_ico_path, result["log"])
        img.close()
        vr = verify_ico_file(output_ico_path)
        result["sizes"] = [f"{w}x{h}" for w, h in vr["sizes"]]
        result["sizes_info"] = vr["sizes_info"]
        result["warnings"].extend(vr["warnings"])
        result["success"] = True
    except ImportError:
        result["error"] = "Pillow not installed"
    except Exception as e:
        result["error"] = str(e)
    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No command"}, ensure_ascii=False))
        sys.exit(1)
    command = sys.argv[1]
    try:
        if command == "convert":
            result = convert_image_to_ico(sys.argv[2], sys.argv[3])
        elif command == "convert-svg":
            result = convert_svg_to_ico(sys.argv[2], sys.argv[3])
        elif command == "check-pillow":
            try:
                import PIL
                from PIL import Image
                result = {"available": True, "version": getattr(PIL, '__version__', 'unknown')}
            except ImportError:
                result = {"available": False, "version": None}
        elif command == "check-ico":
            needs, reason = check_ico_needs_regeneration(sys.argv[2])
            result = {"needs_regeneration": needs, "reason": reason}
        elif command == "verify-ico":
            result = verify_ico_file(sys.argv[2])
            result["sizes"] = [list(s) for s in result["sizes"]]
        else:
            result = {"success": False, "error": f"Unknown command: {command}"}
    except Exception as e:
        import traceback
        result = {"success": False, "error": str(e), "traceback": traceback.format_exc()}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
'''

    def _run_helper_subprocess(
        self,
        python_path: str,
        args: List[str],
        timeout: int = 120,
    ) -> Optional[dict]:
        """
        通过 subprocess 在指定 Python 环境中运行辅助脚本

        Args:
            python_path: 目标 Python 解释器路径
            args: 传给辅助脚本的参数列表（不含 python 和脚本路径）
            timeout: 超时时间（秒）

        Returns:
            解析后的 JSON 结果字典，失败时返回 None
        """
        helper_path = self._get_helper_script_path()
        if not helper_path:
            self.log("  ✗ 无法定位图标转换辅助脚本")
            return None

        cmd = [python_path, helper_path] + args

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            if result.returncode != 0:
                stderr_msg = result.stderr.strip() if result.stderr else ""
                stdout_msg = result.stdout.strip() if result.stdout else ""
                if stderr_msg:
                    self.log(f"  辅助脚本 stderr: {stderr_msg[:500]}")
                # 即使返回码非零，stdout 仍然可能有 JSON 输出
                if stdout_msg:
                    try:
                        return json.loads(stdout_msg)
                    except json.JSONDecodeError:
                        pass
                return None

            stdout = result.stdout.strip()
            if not stdout:
                return None

            # 解析 JSON 输出（取最后一行，避免 Pillow 等库的额外输出干扰）
            lines = stdout.strip().split('\n')
            for line in reversed(lines):
                line = line.strip()
                if line.startswith('{'):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            # 尝试解析全部输出
            try:
                return json.loads(stdout)
            except json.JSONDecodeError:
                self.log(f"  ✗ 无法解析辅助脚本输出")
                return None

        except subprocess.TimeoutExpired:
            self.log("  ✗ 图标转换超时")
            return None
        except Exception as e:
            self.log(f"  ✗ 运行辅助脚本出错: {e}")
            return None

    def _check_pillow_via_subprocess(self, python_path: str) -> bool:
        """
        通过 subprocess 检查目标 Python 环境中是否可用 Pillow

        Args:
            python_path: 目标 Python 解释器路径

        Returns:
            Pillow 是否可用
        """
        result = self._run_helper_subprocess(python_path, ["check-pillow"], timeout=30)
        if result and result.get("available"):
            return True
        return False

    # ------------------------------------------------------------------
    #  包安装
    # ------------------------------------------------------------------

    def _install_package(self, python_path: str, package_name: str) -> bool:
        """
        在目标 Python 环境中安装包

        Args:
            python_path: Python 解释器路径
            package_name: 包名

        Returns:
            是否安装成功
        """
        try:
            result = subprocess.run(
                [python_path, "-m", "pip", "install", package_name, "--quiet"],
                capture_output=True,
                text=True,
                timeout=120,
                creationflags=CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            self.log(f"⚠️ {package_name} 安装超时")
            return False
        except Exception as e:
            self.log(f"⚠️ 安装 {package_name} 时出错: {e}")
            return False

    def ensure_pillow_available(self, python_path: str) -> bool:
        """
        确保 Pillow 可用，如果未安装则尝试安装

        优先检查当前进程，其次检查目标 Python 环境（通过 subprocess）。
        当当前进程中 Pillow 不可用时（如打包后的 exe 环境），
        会安装到目标 Python 环境中并通过 subprocess 使用。

        Args:
            python_path: 目标 Python 解释器路径

        Returns:
            是否可用（当前进程或 subprocess 方式均可）
        """
        # 当前进程可用 → 直接返回
        if self.is_pillow_available():
            return True

        # 检查目标 Python 中是否已有 Pillow
        if self._check_pillow_via_subprocess(python_path):
            self.log("✓ 目标 Python 环境中已安装 Pillow（将通过子进程使用）")
            return True

        # 目标 Python 中也没有，尝试安装
        self.log("正在安装 Pillow 用于图标处理...")
        if self._install_package(python_path, "Pillow"):
            # 验证安装结果
            if self._check_pillow_via_subprocess(python_path):
                self.log("✓ Pillow 安装成功")
                return True
            else:
                self.log("⚠️ Pillow 安装完成但验证失败")
                return False
        else:
            self.log("⚠️ Pillow 安装失败")
            return False

    def ensure_svg_support(self, python_path: str) -> bool:
        """
        确保 SVG 支持可用

        优先尝试 cairosvg，如果不可用则依赖 Pillow（部分支持）

        Args:
            python_path: Python 解释器路径

        Returns:
            是否有 SVG 支持
        """
        if self.is_cairosvg_available():
            return True

        # 尝试安装 cairosvg
        self.log("正在安装 cairosvg 用于 SVG 图标处理...")

        if self._install_package(python_path, "cairosvg"):
            if _check_cairosvg_available():
                self.log("✓ cairosvg 安装成功")
                return True

        # cairosvg 安装失败，检查是否有 Pillow 作为备选
        self.log("⚠️ cairosvg 安装失败，将尝试使用 Pillow 处理 SVG")
        return self.ensure_pillow_available(python_path)

    # ------------------------------------------------------------------
    #  图标验证
    # ------------------------------------------------------------------

    def validate_icon_file(self, icon_path: str) -> Tuple[bool, List[str]]:
        """
        验证图标文件

        Args:
            icon_path: 图标文件路径

        Returns:
            (是否有效, 警告/错误信息列表)
        """
        messages = []

        if not os.path.exists(icon_path):
            return False, ["图标文件不存在"]

        ext = os.path.splitext(icon_path)[1].lower()

        if ext not in self.SUPPORTED_FORMATS:
            return False, [f"不支持的图标格式: {ext}，支持的格式: {', '.join(self.SUPPORTED_FORMATS)}"]

        # 检查文件大小
        file_size = os.path.getsize(icon_path)
        if file_size == 0:
            return False, ["图标文件为空"]

        if file_size > 10 * 1024 * 1024:  # 10MB
            messages.append("图标文件较大（>10MB），可能会影响打包速度")

        # 如果是 ICO 格式，用二进制解析检查尺寸（不依赖 Pillow）
        if ext == '.ico':
            try:
                with open(icon_path, 'rb') as f:
                    header = f.read(6)
                    if len(header) >= 6:
                        reserved, img_type, count = struct.unpack('<HHH', header)
                        if img_type == 1 and count >= 1:
                            sizes = set()
                            for i in range(count):
                                entry = f.read(16)
                                if len(entry) < 16:
                                    break
                                w, h = entry[0], entry[1]
                                w = w if w != 0 else 256
                                h = h if h != 0 else 256
                                sizes.add((w, h))

                            has_required = any(size in sizes for size in self.REQUIRED_SIZES)
                            if not has_required:
                                messages.append("ICO 文件缺少小尺寸图标（16x16, 32x32, 48x48）")
                                sizes_str = ', '.join([f'{w}x{h}' for w, h in sorted(sizes, reverse=True)])
                                messages.append(f"当前包含尺寸: {sizes_str}")
                            else:
                                sizes_str = ', '.join([f'{w}x{h}' for w, h in sorted(sizes, reverse=True)])
                                messages.append(f"✓ ICO 文件包含尺寸: {sizes_str}")
            except Exception as e:
                messages.append(f"检查 ICO 文件时出错: {str(e)}")

        # 如果是其他格式，提示将会转换
        elif ext in self.CONVERTIBLE_FORMATS:
            messages.append(f"检测到 {ext.upper()} 格式，将自动转换为多尺寸 ICO 文件")

        return True, messages

    # ------------------------------------------------------------------
    #  主入口：处理图标文件
    # ------------------------------------------------------------------

    def process_icon_file(
        self,
        icon_path: str,
        output_dir: str,
        python_path: Optional[str] = None,
    ) -> Tuple[Optional[str], List[str]]:
        """
        处理图标文件，支持 PNG/SVG/JPG/JPEG/BMP/ICO 格式
        自动转换为包含多尺寸的 ICO 文件

        当 Pillow 在当前进程中不可用时（如打包后的 exe 环境），
        会自动通过 subprocess 在目标 Python 环境中执行转换。

        Args:
            icon_path: 原始图标文件路径
            output_dir: 输出目录
            python_path: Python 解释器路径（用于安装依赖和 subprocess 调用）

        Returns:
            (processed_icon_path, warnings): 处理后的图标路径和警告信息列表
            如果图标格式不兼容且无法转换，返回 (None, warnings)
        """
        warnings = []

        if not icon_path:
            return None, ["未指定图标文件"]

        if not os.path.exists(icon_path):
            return None, [f"图标文件不存在: {icon_path}"]

        # 确保输出目录存在
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # 获取文件扩展名
        ext = os.path.splitext(icon_path)[1].lower()

        if ext not in self.SUPPORTED_FORMATS:
            warnings.append(f"不支持的图标格式: {ext}")
            warnings.append(f"支持的格式: {', '.join(self.SUPPORTED_FORMATS)}")
            return None, warnings

        # 如果已经是 ICO 格式，检查是否包含必要尺寸
        if ext == '.ico':
            return self._process_ico_file(icon_path, output_dir, warnings, python_path)

        # SVG 格式需要特殊处理
        elif ext == '.svg':
            return self._convert_svg_to_ico(icon_path, output_dir, warnings, python_path)

        # PNG/JPG/JPEG/BMP 格式，使用 Pillow 转换
        elif ext in ['.png', '.jpg', '.jpeg', '.bmp']:
            return self._convert_image_to_ico(icon_path, output_dir, warnings, python_path)

        else:
            warnings.append(f"不支持的图标格式: {ext}")
            return None, warnings

    # ------------------------------------------------------------------
    #  ICO 文件处理
    # ------------------------------------------------------------------

    def _process_ico_file(
        self,
        icon_path: str,
        output_dir: str,
        warnings: List[str],
        python_path: Optional[str] = None,
    ) -> Tuple[Optional[str], List[str]]:
        """
        处理 ICO 格式文件

        检查现有 ICO 文件是否包含必要尺寸和正确格式：
        - 必须包含 16x16, 32x32, 48x48（Explorer 基础尺寸）
        - 必须包含 256x256（Explorer 大图标/超大图标）
        - 小尺寸应为 BMP 格式，256x256 应为 PNG 格式
        如果不符合要求，则重新生成。
        """
        # 先用二进制解析判断 ICO 质量（不依赖 Pillow）
        needs_regeneration = False
        reason = ""

        try:
            with open(icon_path, 'rb') as f:
                header = f.read(6)
                if len(header) < 6:
                    needs_regeneration = True
                    reason = "ICO 文件头不完整"
                else:
                    reserved, img_type, count = struct.unpack('<HHH', header)
                    if img_type != 1 or count < 1:
                        needs_regeneration = True
                        reason = "无效的 ICO 文件"
                    else:
                        sizes_found = set()
                        has_bmp_small = True
                        entries_raw = []

                        for i in range(count):
                            entry = f.read(16)
                            if len(entry) < 16:
                                break
                            w, h, _, _, _, bpp, sz, offset = struct.unpack('<BBBBHHII', entry)
                            w = w if w != 0 else 256
                            h = h if h != 0 else 256
                            sizes_found.add((w, h))
                            entries_raw.append((w, h, sz, offset))

                        # 检查小尺寸是否使用了 BMP 格式
                        for w, h, sz, offset in entries_raw:
                            if w < self.PNG_THRESHOLD:
                                pos = f.tell()
                                f.seek(offset)
                                magic = f.read(4)
                                f.seek(pos)
                                if magic == b'\x89PNG':
                                    has_bmp_small = False

                        # 检查必要尺寸
                        has_all_required = all(s in sizes_found for s in self.REQUIRED_SIZES)
                        has_256 = (256, 256) in sizes_found

                        if not has_all_required:
                            needs_regeneration = True
                            missing = [s for s in self.REQUIRED_SIZES if s not in sizes_found]
                            reason = f"缺少必要尺寸: {', '.join(f'{w}x{h}' for w, h in missing)}"
                        elif not has_256:
                            needs_regeneration = True
                            reason = "缺少 256x256 尺寸（影响资源管理器大图标显示）"
                        elif not has_bmp_small:
                            needs_regeneration = True
                            reason = "小尺寸使用了 PNG 格式，需要转为 BMP 格式以兼容所有 Windows 版本"
                        else:
                            sizes_str = ', '.join(f'{w}x{h}' for w, h in sorted(sizes_found, reverse=True))
                            self.log(f"✓ ICO 文件格式合规，包含 {count} 个尺寸: {sizes_str}")
                            return icon_path, warnings
        except Exception as e:
            needs_regeneration = True
            reason = f"解析 ICO 文件出错: {e}"

        if not needs_regeneration:
            return icon_path, warnings

        # 需要重新生成
        warnings.append(f"原始 ICO 需要重新生成: {reason}")
        self.log(f"  ICO 需要重新生成: {reason}")

        # 尝试转换（优先当前进程 Pillow，其次 subprocess）
        return self._do_convert_to_ico(icon_path, output_dir, warnings, python_path)

    # ------------------------------------------------------------------
    #  图片转 ICO（PNG/JPG/JPEG/BMP）
    # ------------------------------------------------------------------

    def _convert_image_to_ico(
        self,
        source_path: str,
        output_dir: str,
        warnings: List[str],
        python_path: Optional[str] = None,
    ) -> Tuple[Optional[str], List[str]]:
        """将 PNG/JPG/JPEG/BMP 图片转换为 ICO 格式"""
        ext = os.path.splitext(source_path)[1].lower()
        self.log(f"检测到 {ext.upper()} 格式图标，将转换为多尺寸 ICO 文件...")
        return self._do_convert_to_ico(source_path, output_dir, warnings, python_path)

    # ------------------------------------------------------------------
    #  SVG 转 ICO
    # ------------------------------------------------------------------

    def _convert_svg_to_ico(
        self,
        svg_path: str,
        output_dir: str,
        warnings: List[str],
        python_path: Optional[str] = None,
    ) -> Tuple[Optional[str], List[str]]:
        """
        将 SVG 矢量图转换为 ICO 格式

        使用 cairosvg（首选）或 Pillow（备选）进行转换
        """
        self.log("检测到 SVG 格式图标，将转换为多尺寸 ICO 文件...")

        # 尝试方式 1：当前进程中用 cairosvg
        if self.is_cairosvg_available():
            result = self._convert_svg_with_cairosvg_local(svg_path, output_dir, warnings)
            if result[0] is not None:
                return result

        # 尝试方式 2：当前进程中用 Pillow
        if self.is_pillow_available():
            result = self._convert_svg_with_pillow_local(svg_path, output_dir, warnings)
            if result[0] is not None:
                return result

        # 尝试方式 3：subprocess（安装并通过目标 Python 转换）
        if python_path:
            # 先确保目标环境有 Pillow
            if self.ensure_pillow_available(python_path):
                ico_path = os.path.join(output_dir, "icon_converted.ico")
                result = self._run_helper_subprocess(
                    python_path,
                    ["convert-svg", svg_path, ico_path],
                    timeout=120,
                )
                if result and result.get("success"):
                    self._log_subprocess_result(result)
                    warnings.extend(result.get("warnings", []))
                    final_path = result.get("ico_path", ico_path)
                    self._verify_ico_file(final_path, warnings)
                    return final_path, warnings

            # 尝试安装 cairosvg 到目标环境
            self.log("尝试在目标环境中安装 cairosvg...")
            if self._install_package(python_path, "cairosvg"):
                ico_path = os.path.join(output_dir, "icon_converted.ico")
                result = self._run_helper_subprocess(
                    python_path,
                    ["convert-svg", svg_path, ico_path],
                    timeout=120,
                )
                if result and result.get("success"):
                    self._log_subprocess_result(result)
                    warnings.extend(result.get("warnings", []))
                    final_path = result.get("ico_path", ico_path)
                    self._verify_ico_file(final_path, warnings)
                    return final_path, warnings

        # 所有方法都失败
        self._log_svg_support_required_message()
        warnings.append("需要安装 cairosvg 或 Pillow 才能转换 SVG 图标")
        warnings.append("请手动运行: pip install cairosvg 或 pip install Pillow")
        return None, warnings

    def _convert_svg_with_cairosvg_local(
        self,
        svg_path: str,
        output_dir: str,
        warnings: List[str],
    ) -> Tuple[Optional[str], List[str]]:
        """使用当前进程中的 cairosvg 将 SVG 转换为 ICO"""
        try:
            import cairosvg  # type: ignore[import-not-found]
            from PIL import Image

            self.log("使用 cairosvg 处理 SVG 文件...")

            # 将 SVG 渲染为大尺寸 PNG
            png_data = cairosvg.svg2png(
                url=svg_path,
                output_width=512,
                output_height=512,
            )

            img = Image.open(io.BytesIO(png_data))
            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            ico_path = os.path.join(output_dir, "icon_converted.ico")
            self._build_ico_file(img, ico_path)
            img.close()

            self.log(f"✓ 已生成多尺寸 ICO 文件: {ico_path}")
            self._log_ico_diagnostics(ico_path, svg_path)
            self._verify_ico_file(ico_path, warnings)

            return ico_path, warnings

        except Exception as e:
            error_msg = f"使用 cairosvg 转换 SVG 失败: {str(e)}"
            self.log(f"⚠️ {error_msg}")
            warnings.append(error_msg)
            return None, warnings

    def _convert_svg_with_pillow_local(
        self,
        svg_path: str,
        output_dir: str,
        warnings: List[str],
    ) -> Tuple[Optional[str], List[str]]:
        """使用当前进程中的 Pillow 尝试处理 SVG 文件"""
        try:
            from PIL import Image

            self.log("使用 Pillow 处理 SVG 文件（可能不支持复杂 SVG）...")
            warnings.append("Pillow 对 SVG 的支持有限，建议安装 cairosvg 以获得更好的支持")

            try:
                img = Image.open(svg_path)
            except Exception:
                warnings.append("Pillow 无法直接处理此 SVG 文件")
                return None, warnings

            if img.mode != 'RGBA':
                img = img.convert('RGBA')

            original_size = img.size
            self.log(f"源图片尺寸: {original_size[0]}x{original_size[1]}")

            ico_path = os.path.join(output_dir, "icon_converted.ico")
            self._build_ico_file(img, ico_path)
            img.close()

            self.log(f"✓ 已生成多尺寸 ICO 文件: {ico_path}")
            self._log_ico_diagnostics(ico_path, svg_path)
            self._verify_ico_file(ico_path, warnings)

            return ico_path, warnings

        except Exception as e:
            error_msg = f"使用 Pillow 转换 SVG 失败: {str(e)}"
            self.log(f"✗ {error_msg}")
            warnings.append(error_msg)
            return None, warnings

    # ------------------------------------------------------------------
    #  统一转换入口（自动选择本地或 subprocess）
    # ------------------------------------------------------------------

    def _do_convert_to_ico(
        self,
        source_path: str,
        output_dir: str,
        warnings: List[str],
        python_path: Optional[str] = None,
    ) -> Tuple[Optional[str], List[str]]:
        """
        将图片转换为多尺寸 ICO 文件

        自动选择最佳转换方式：
        1. 优先使用当前进程中的 Pillow（从源码运行时）
        2. 如果当前进程没有 Pillow，通过 subprocess 在目标 Python 中转换
           （打包后的 exe 运行时）

        Args:
            source_path: 源图片路径
            output_dir: 输出目录
            warnings: 警告信息列表
            python_path: 目标 Python 解释器路径

        Returns:
            (ico_path, warnings): ICO 文件路径和警告信息
        """
        ico_path = os.path.join(output_dir, "icon_converted.ico")

        # 方式 1：当前进程中直接使用 Pillow（最快）
        if self.is_pillow_available():
            return self._convert_to_ico_local(source_path, output_dir, warnings)

        # 方式 2：通过 subprocess 在目标 Python 环境中转换
        if python_path:
            # 确保目标环境有 Pillow
            if self.ensure_pillow_available(python_path):
                self.log("通过目标 Python 环境进行图标转换...")
                result = self._run_helper_subprocess(
                    python_path,
                    ["convert", source_path, ico_path],
                    timeout=120,
                )
                if result and result.get("success"):
                    final_path = result.get("ico_path", ico_path)
                    # 如果返回的路径是源文件（ICO 已合规），直接使用
                    if final_path != ico_path and os.path.basename(final_path) != "icon_converted.ico":
                        self.log(f"✓ ICO 文件已合规，直接使用: {final_path}")
                        return final_path, warnings

                    self._log_subprocess_result(result)
                    warnings.extend(result.get("warnings", []))
                    self._verify_ico_file(final_path, warnings)
                    return final_path, warnings
                else:
                    error = result.get("error", "未知错误") if result else "辅助脚本执行失败"
                    self.log(f"  ⚠️ subprocess 图标转换失败: {error}")
                    # 输出更多诊断信息
                    if result:
                        for log_line in result.get("log", []):
                            self.log(f"    {log_line}")
                        if result.get("traceback"):
                            for tb_line in result["traceback"].strip().split('\n'):
                                self.log(f"    {tb_line}")

        # 所有方式都失败
        ext = os.path.splitext(source_path)[1].lower()
        self._log_pillow_required_message(ext)
        warnings.append("需要安装 Pillow 才能转换图标格式")
        if python_path:
            warnings.append(f"自动安装 Pillow 失败，请手动运行: {python_path} -m pip install Pillow")
        else:
            warnings.append("自动安装 Pillow 失败，请手动运行: pip install Pillow")
        return None, warnings

    def _log_subprocess_result(self, result: dict) -> None:
        """输出 subprocess 转换结果的日志"""
        for log_line in result.get("log", []):
            self.log(log_line)

        ico_path = result.get("ico_path", "")
        if ico_path and os.path.exists(ico_path):
            ico_size = os.path.getsize(ico_path)
            sizes_info = result.get("sizes_info", [])
            self.log(f"✓ 已生成多尺寸 ICO 文件: {ico_path}")
            if sizes_info:
                self.log(f"  ICO 文件: {ico_size} 字节, 包含 {len(sizes_info)} 个图标")
                self.log(f"  包含尺寸: {', '.join(sizes_info)}")

    # ------------------------------------------------------------------
    #  本地 Pillow 转换（当前进程中直接使用 Pillow）
    # ------------------------------------------------------------------

    def _convert_to_ico_local(
        self,
        source_path: str,
        output_dir: str,
        warnings: List[str],
    ) -> Tuple[Optional[str], List[str]]:
        """
        使用当前进程中的 Pillow 将图片转换为 ICO 文件

        手动构建 ICO 二进制数据，确保 Windows Explorer 完全兼容：
        - 256x256 使用 PNG 压缩（现代 Windows 标准）
        - ≤128x128 使用 BMP 格式（BITMAPINFOHEADER + BGRA + AND mask）

        Args:
            source_path: 源图片路径
            output_dir: 输出目录
            warnings: 警告信息列表

        Returns:
            (ico_path, warnings): ICO 文件路径和警告信息
        """
        if not _check_pil_available():
            self.log("✗ 无法转换图标：当前进程中未安装 Pillow 库")
            warnings.append("需要安装 Pillow 才能转换图标")
            return None, warnings

        try:
            from PIL import Image

            # 打开源图片
            img = Image.open(source_path)
            original_size = img.size
            self.log(f"源图片尺寸: {original_size[0]}x{original_size[1]}")

            # 检查图片尺寸是否太小
            if original_size[0] < 16 or original_size[1] < 16:
                warnings.append(f"源图片尺寸过小（{original_size[0]}x{original_size[1]}），可能导致图标模糊")

            # 检查图片是否为正方形
            if original_size[0] != original_size[1]:
                warnings.append(f"源图片不是正方形（{original_size[0]}x{original_size[1]}），将被拉伸为正方形")

            # 确保是 RGBA 模式（支持透明度）
            if img.mode != 'RGBA':
                if img.mode == 'P':
                    img = img.convert('RGBA')
                elif img.mode in ['RGB', 'L']:
                    rgba_img = Image.new('RGBA', img.size, (255, 255, 255, 255))
                    if img.mode == 'RGB':
                        rgba_img.paste(img, (0, 0))
                    else:
                        rgb_img = img.convert('RGB')
                        rgba_img.paste(rgb_img, (0, 0))
                        rgb_img.close()
                    img.close()
                    img = rgba_img
                else:
                    img = img.convert('RGBA')

            # 生成多尺寸图标并构建 ICO 数据
            ico_path = os.path.join(output_dir, "icon_converted.ico")
            self._build_ico_file(img, ico_path)

            self.log(f"✓ 已生成多尺寸 ICO 文件: {ico_path}")

            # 输出诊断信息
            self._log_ico_diagnostics(ico_path, source_path)

            # 关闭图片
            img.close()

            # 验证生成的 ICO 文件
            self._verify_ico_file(ico_path, warnings)

            return ico_path, warnings

        except Exception as e:
            error_msg = f"转换图标失败: {str(e)}"
            self.log(f"✗ {error_msg}")
            warnings.append(error_msg)
            return None, warnings

    # ------------------------------------------------------------------
    #  ICO 文件构建（二进制层面，不依赖 Pillow 的 ICO 保存功能）
    # ------------------------------------------------------------------

    def _build_ico_file(self, source_img, ico_path: str) -> None:
        """
        手动构建符合 Windows 规范的 ICO 文件

        ICO 文件结构：
        1. ICONDIR 文件头（6 字节）
        2. ICONDIRENTRY 目录条目（每条 16 字节）
        3. 图像数据（BMP 或 PNG 格式）

        256x256 → PNG 压缩（Windows Vista+ 标准）
        ≤128x128 → BMP 格式（BITMAPINFOHEADER + BGRA 像素 + AND 掩码）

        Args:
            source_img: Pillow RGBA 图像对象
            ico_path: 输出 ICO 文件路径
        """
        from PIL import Image

        count = len(self.ICO_SIZES)
        image_data_list = []  # (width, height, data_bytes)

        for size in self.ICO_SIZES:
            w, h = size
            resized = source_img.resize(size, Image.Resampling.LANCZOS)
            self.log(f"  生成 {w}x{h} 尺寸 ({'PNG' if w >= self.PNG_THRESHOLD else 'BMP'})")

            if w >= self.PNG_THRESHOLD:
                # 256x256 使用 PNG 压缩
                png_buf = io.BytesIO()
                resized.save(png_buf, format='PNG')
                image_data_list.append((w, h, png_buf.getvalue()))
            else:
                # ≤128x128 使用 BMP 格式
                bmp_data = self._make_ico_bmp_entry(resized)
                image_data_list.append((w, h, bmp_data))

            resized.close()

        # 计算偏移量
        header_size = 6  # ICONDIR
        directory_size = count * 16  # ICONDIRENTRY × count
        data_offset = header_size + directory_size

        # 构建文件
        with open(ico_path, 'wb') as f:
            # 1. ICONDIR 文件头
            f.write(struct.pack('<HHH', 0, 1, count))  # reserved=0, type=1(ICO), count

            # 2. 计算各条目偏移
            current_offset = data_offset
            for w, h, data in image_data_list:
                # ICO 目录中 width/height: 0 表示 256
                ico_w = 0 if w >= 256 else w
                ico_h = 0 if h >= 256 else h
                data_size = len(data)

                # ICONDIRENTRY: width, height, colors, reserved, planes, bpp, size, offset
                f.write(struct.pack('<BBBBHHII',
                    ico_w,          # bWidth
                    ico_h,          # bHeight
                    0,              # bColorCount (0 = 256+ colors)
                    0,              # bReserved
                    1,              # wPlanes
                    32,             # wBitCount (32-bit ARGB)
                    data_size,      # dwBytesInRes
                    current_offset  # dwImageOffset
                ))
                current_offset += data_size

            # 3. 写入图像数据
            for _, _, data in image_data_list:
                f.write(data)

    @staticmethod
    def _make_ico_bmp_entry(img) -> bytes:
        """
        将 Pillow RGBA 图像转换为 ICO BMP 条目的二进制数据

        ICO 中的 BMP 格式与标准 BMP 不同：
        - 没有 BITMAPFILEHEADER（14 字节的文件头）
        - BITMAPINFOHEADER 的 biHeight 是实际高度的 2 倍（XOR + AND）
        - 像素数据是自底向上的 BGRA 顺序
        - 后跟 1-bit AND 掩码（每行按 4 字节对齐）

        Args:
            img: Pillow RGBA 图像

        Returns:
            ICO BMP 条目的完整字节数据
        """
        w, h = img.size

        # 像素数据：BGRA，自底向上
        pixels = img.load()
        xor_data = bytearray()
        for y in range(h - 1, -1, -1):  # 自底向上
            for x in range(w):
                r, g, b, a = pixels[x, y]
                xor_data.extend([b, g, r, a])  # BGRA 顺序

        # AND 掩码：1-bit，自底向上，每行按 4 字节（32-bit）对齐
        # 对于 32-bit ARGB 图像，AND 掩码全 0（透明度由 alpha 通道控制）
        and_row_bytes = ((w + 31) // 32) * 4  # 每行字节数（向上对齐到 4 字节）
        and_data = bytearray(and_row_bytes * h)  # 全零

        # BITMAPINFOHEADER（40 字节）
        bih = struct.pack('<IIIHHIIIIII',
            40,             # biSize
            w,              # biWidth
            h * 2,          # biHeight（×2，包含 XOR + AND）
            1,              # biPlanes
            32,             # biBitCount
            0,              # biCompression (BI_RGB)
            len(xor_data) + len(and_data),  # biSizeImage
            0,              # biXPelsPerMeter
            0,              # biYPelsPerMeter
            0,              # biClrUsed
            0,              # biClrImportant
        )

        return bih + bytes(xor_data) + bytes(and_data)

    # ------------------------------------------------------------------
    #  诊断与验证
    # ------------------------------------------------------------------

    def _log_ico_diagnostics(self, ico_path: str, source_path: str) -> None:
        """
        输出 ICO 文件诊断信息，帮助排查图标问题

        Args:
            ico_path: 生成的 ICO 文件路径
            source_path: 源图片路径
        """
        try:
            import hashlib

            # 计算源文件哈希
            with open(source_path, 'rb') as f:
                source_hash = hashlib.md5(f.read()).hexdigest()[:8]

            # 计算生成的 ICO 文件信息
            ico_size = os.path.getsize(ico_path)
            with open(ico_path, 'rb') as f:
                ico_hash = hashlib.md5(f.read()).hexdigest()[:8]

            self.log(f"  源文件: {os.path.basename(source_path)} (MD5: {source_hash})")
            self.log(f"  ICO 文件: {ico_size} 字节 (MD5: {ico_hash})")
        except Exception as e:
            self.log(f"  诊断信息获取失败: {e}")

    def _verify_ico_file(self, ico_path: str, warnings: List[str]) -> bool:
        """
        验证生成的 ICO 文件

        通过解析 ICO 文件头来验证实际包含的图标数量、尺寸和格式

        Args:
            ico_path: ICO 文件路径
            warnings: 警告信息列表

        Returns:
            是否验证通过
        """
        try:
            with open(ico_path, 'rb') as f:
                # ICO 文件头: 2 bytes reserved, 2 bytes type (1=ICO), 2 bytes count
                header = f.read(6)
                if len(header) < 6:
                    warnings.append("ICO 文件头不完整")
                    return False

                reserved, img_type, count = struct.unpack('<HHH', header)

                if img_type != 1:
                    warnings.append(f"无效的 ICO 文件类型: {img_type}")
                    return False

                if count < 1:
                    warnings.append("ICO 文件不包含任何图标")
                    return False

                # 读取每个图标的目录项
                entries = []
                for i in range(count):
                    entry = f.read(16)
                    if len(entry) < 16:
                        break
                    width, height, colors, reserved2, planes, bpp, size, offset = struct.unpack('<BBBBHHII', entry)
                    w = width if width != 0 else 256
                    h = height if height != 0 else 256
                    entries.append((w, h, size, offset))

                # 检查每个条目的数据格式
                sizes_info = []
                for w, h, sz, offset in entries:
                    f.seek(offset)
                    magic = f.read(4)
                    is_png = magic == b'\x89PNG'
                    fmt = 'PNG' if is_png else 'BMP'
                    sizes_info.append(f"{w}x{h}({fmt})")

                # 输出验证结果
                file_size = os.path.getsize(ico_path)
                sizes_found = [(w, h) for w, h, _, _ in entries]
                self.log(f"  ICO 文件验证: {file_size} 字节, 包含 {count} 个图标")
                self.log(f"  包含尺寸: {', '.join(sizes_info)}")

                # 检查是否包含必要的尺寸
                required = [(16, 16), (32, 32), (48, 48)]
                missing = [s for s in required if s not in sizes_found]
                if missing:
                    warnings.append(f"ICO 文件缺少建议尺寸: {', '.join([f'{w}x{h}' for w, h in missing])}")

                has_256 = (256, 256) in sizes_found
                if not has_256:
                    warnings.append("ICO 文件缺少 256x256 尺寸（影响资源管理器大图标显示）")

                if count >= 3 and not missing:
                    self.log("  ✓ ICO 文件验证通过，包含多尺寸图标")
                    return True
                else:
                    if count < 3:
                        warnings.append(f"ICO 文件只包含 {count} 个尺寸，建议包含更多尺寸")
                    return count >= 1

        except Exception as e:
            warnings.append(f"验证生成的 ICO 文件时出错: {str(e)}")
            return False

    # ------------------------------------------------------------------
    #  提示信息
    # ------------------------------------------------------------------

    def _log_pillow_required_message(self, ext: str) -> None:
        """输出 Pillow 需求信息"""
        self.log("\n" + "=" * 50)
        self.log("⚠️ 需要安装 Pillow 库才能转换图标格式")
        self.log("=" * 50)
        self.log(f"检测到 {ext.upper()} 格式图标，但无法自动转换为 ICO")
        self.log("解决方案：")
        self.log("  1. 手动安装 Pillow: pip install Pillow")
        self.log("  2. 或手动转换为 .ico 格式后重新选择")
        self.log("  3. 或使用在线工具转换: https://www.icoconverter.com/")

    def _log_svg_support_required_message(self) -> None:
        """输出 SVG 支持需求信息"""
        self.log("\n" + "=" * 50)
        self.log("⚠️ 需要安装额外库才能转换 SVG 图标")
        self.log("=" * 50)
        self.log("检测到 SVG 格式图标，但无法自动转换为 ICO")
        self.log("解决方案：")
        self.log("  1. 安装 cairosvg（推荐）: pip install cairosvg")
        self.log("  2. 或安装 Pillow（有限支持）: pip install Pillow")
        self.log("  3. 或手动将 SVG 转换为 PNG/ICO 格式后重新选择")
        self.log("  4. 或使用在线工具转换: https://www.icoconverter.com/")

    # ------------------------------------------------------------------
    #  信息查询与清理
    # ------------------------------------------------------------------

    def get_icon_info(self, icon_path: str) -> dict:
        """
        获取图标文件信息

        Args:
            icon_path: 图标文件路径

        Returns:
            图标信息字典
        """
        info = {
            "path": icon_path,
            "exists": os.path.exists(icon_path) if icon_path else False,
            "format": None,
            "sizes": [],
            "valid": False,
            "file_size": 0,
        }

        if not icon_path or not info["exists"]:
            return info

        ext = os.path.splitext(icon_path)[1].lower()
        info["format"] = ext[1:] if ext else None
        info["file_size"] = os.path.getsize(icon_path)

        # 对 ICO 文件使用二进制解析（不依赖 Pillow）
        if ext == '.ico':
            try:
                with open(icon_path, 'rb') as f:
                    header = f.read(6)
                    if len(header) >= 6:
                        reserved, img_type, count = struct.unpack('<HHH', header)
                        if img_type == 1:
                            sizes = []
                            for i in range(count):
                                entry = f.read(16)
                                if len(entry) < 16:
                                    break
                                w, h = entry[0], entry[1]
                                w = w if w != 0 else 256
                                h = h if h != 0 else 256
                                sizes.append((w, h))
                            info["sizes"] = sizes
                            info["valid"] = len(sizes) > 0
            except Exception:
                pass
        elif self.is_pillow_available():
            try:
                from PIL import Image
                img = Image.open(icon_path)
                info["sizes"] = [img.size]
                info["valid"] = True
                img.close()
            except Exception:
                pass
        else:
            # 无法获取详细信息，但文件存在且大小 > 0 视为有效
            info["valid"] = info["file_size"] > 0

        return info

    def cleanup_converted_icon(self, output_dir: str) -> None:
        """
        清理转换生成的临时图标文件

        Args:
            output_dir: 输出目录
        """
        icon_converted_path = os.path.join(output_dir, "icon_converted.ico")
        if os.path.exists(icon_converted_path):
            try:
                os.remove(icon_converted_path)
                self.log(f"已清理临时图标文件: {icon_converted_path}")
            except Exception as e:
                self.log(f"⚠️ 清理临时图标文件失败: {e}")
