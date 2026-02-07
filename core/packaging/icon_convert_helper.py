"""
图标转换辅助脚本（独立运行）

本脚本设计为可通过 subprocess 在任意 Python 环境中执行，
用于解决打包工具自身被打包为 exe 后无法直接使用 Pillow 的问题。

使用方式：
    python icon_convert_helper.py <source_image_path> <output_ico_path> [--svg]

功能：
    - 将 PNG/JPG/JPEG/BMP 图片转换为多尺寸 ICO 文件
    - 将 SVG 图片转换为多尺寸 ICO 文件（需要 cairosvg 或 Pillow SVG 支持）
    - 检查并重新生成不合规的 ICO 文件
    - 256x256 使用 PNG 压缩，其余使用 BMP 格式（Windows Explorer 兼容性最佳）
    - 输出 JSON 格式结果到 stdout，便于主进程解析

输出格式（JSON）：
    成功: {"success": true, "ico_path": "...", "sizes": [...], "warnings": [...]}
    失败: {"success": false, "error": "...", "warnings": [...]}
"""

import io
import json
import os
import struct
import sys

# 确保 stdout 使用 UTF-8 编码，避免 Windows 控制台 GBK 编码导致中文乱码
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ICO 文件需要包含的尺寸（从大到小排列）
ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]

# 256x256 使用 PNG 压缩阈值
PNG_THRESHOLD = 256

# 必需的最小尺寸（用于验证）
REQUIRED_SIZES = [(16, 16), (32, 32), (48, 48)]


def make_ico_bmp_entry(img) -> bytes:
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
    bih = struct.pack(
        '<IIIHHIIIIII',
        40,                                 # biSize
        w,                                  # biWidth
        h * 2,                              # biHeight（×2，包含 XOR + AND）
        1,                                  # biPlanes
        32,                                 # biBitCount
        0,                                  # biCompression (BI_RGB)
        len(xor_data) + len(and_data),      # biSizeImage
        0,                                  # biXPelsPerMeter
        0,                                  # biYPelsPerMeter
        0,                                  # biClrUsed
        0,                                  # biClrImportant
    )

    return bih + bytes(xor_data) + bytes(and_data)


def build_ico_file(source_img, ico_path: str, log_lines: list) -> None:
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
        log_lines: 日志消息列表（用于收集日志）
    """
    from PIL import Image

    count = len(ICO_SIZES)
    image_data_list = []  # (width, height, data_bytes)

    for size in ICO_SIZES:
        w, h = size
        resized = source_img.resize(size, Image.Resampling.LANCZOS)
        fmt = 'PNG' if w >= PNG_THRESHOLD else 'BMP'
        log_lines.append(f"  生成 {w}x{h} 尺寸 ({fmt})")

        if w >= PNG_THRESHOLD:
            # 256x256 使用 PNG 压缩
            png_buf = io.BytesIO()
            resized.save(png_buf, format='PNG')
            image_data_list.append((w, h, png_buf.getvalue()))
        else:
            # ≤128x128 使用 BMP 格式
            bmp_data = make_ico_bmp_entry(resized)
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
            f.write(struct.pack(
                '<BBBBHHII',
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


def verify_ico_file(ico_path: str) -> dict:
    """
    验证生成的 ICO 文件结构

    Args:
        ico_path: ICO 文件路径

    Returns:
        验证结果字典，包含 sizes, count, valid, warnings
    """
    result = {
        "sizes": [],
        "count": 0,
        "valid": False,
        "warnings": [],
        "sizes_info": [],
    }

    try:
        with open(ico_path, 'rb') as f:
            header = f.read(6)
            if len(header) < 6:
                result["warnings"].append("ICO 文件头不完整")
                return result

            reserved, img_type, count = struct.unpack('<HHH', header)
            result["count"] = count

            if img_type != 1:
                result["warnings"].append(f"无效的 ICO 文件类型: {img_type}")
                return result

            if count < 1:
                result["warnings"].append("ICO 文件不包含任何图标")
                return result

            entries = []
            for i in range(count):
                entry = f.read(16)
                if len(entry) < 16:
                    break
                width, height, colors, reserved2, planes, bpp, size, offset = struct.unpack(
                    '<BBBBHHII', entry
                )
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

            # 检查必要尺寸
            missing = [s for s in REQUIRED_SIZES if s not in result["sizes"]]
            if missing:
                result["warnings"].append(
                    f"ICO 文件缺少建议尺寸: {', '.join([f'{w}x{h}' for w, h in missing])}"
                )

            has_256 = (256, 256) in result["sizes"]
            if not has_256:
                result["warnings"].append("ICO 文件缺少 256x256 尺寸")

            if count >= 3 and not missing:
                result["valid"] = True
            else:
                result["valid"] = count >= 1

    except Exception as e:
        result["warnings"].append(f"验证 ICO 文件时出错: {str(e)}")

    return result


def check_ico_needs_regeneration(ico_path: str) -> tuple:
    """
    检查 ICO 文件是否需要重新生成

    Args:
        ico_path: ICO 文件路径

    Returns:
        (needs_regeneration: bool, reason: str)
    """
    try:
        with open(ico_path, 'rb') as f:
            header = f.read(6)
            if len(header) < 6:
                return True, "ICO 文件头不完整"

            reserved, img_type, count = struct.unpack('<HHH', header)
            if img_type != 1 or count < 1:
                return True, "无效的 ICO 文件"

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
                if w < PNG_THRESHOLD:
                    pos = f.tell()
                    f.seek(offset)
                    magic = f.read(4)
                    f.seek(pos)
                    if magic == b'\x89PNG':
                        has_bmp_small = False

            # 检查必要尺寸
            has_all_required = all(s in sizes_found for s in REQUIRED_SIZES)
            has_256 = (256, 256) in sizes_found

            if not has_all_required:
                missing = [s for s in REQUIRED_SIZES if s not in sizes_found]
                return True, f"缺少必要尺寸: {', '.join(f'{w}x{h}' for w, h in missing)}"
            elif not has_256:
                return True, "缺少 256x256 尺寸（影响资源管理器大图标显示）"
            elif not has_bmp_small:
                return True, "小尺寸使用了 PNG 格式，需要转为 BMP 格式以兼容所有 Windows 版本"
            else:
                return False, ""

    except Exception as e:
        return True, f"解析 ICO 文件出错: {e}"


def convert_image_to_ico(source_path: str, output_ico_path: str) -> dict:
    """
    将图片（PNG/JPG/JPEG/BMP/ICO）转换为多尺寸合规 ICO 文件

    Args:
        source_path: 源图片路径
        output_ico_path: 输出 ICO 文件路径

    Returns:
        结果字典
    """
    result = {
        "success": False,
        "ico_path": output_ico_path,
        "sizes": [],
        "sizes_info": [],
        "warnings": [],
        "log": [],
    }

    try:
        from PIL import Image
    except ImportError:
        result["error"] = "Pillow 未安装，无法进行图标转换"
        return result

    try:
        ext = os.path.splitext(source_path)[1].lower()

        # 如果是 ICO 文件，先检查是否需要重新生成
        if ext == '.ico':
            needs_regen, reason = check_ico_needs_regeneration(source_path)
            if not needs_regen:
                # ICO 已经合规，直接返回原路径
                result["success"] = True
                result["ico_path"] = source_path
                result["log"].append(f"ICO 文件已合规，无需转换")
                return result
            else:
                result["log"].append(f"ICO 需要重新生成: {reason}")
                result["warnings"].append(f"原始 ICO 需要重新生成: {reason}")

        # 打开图片
        img = Image.open(source_path)
        original_size = img.size
        result["log"].append(f"源图片尺寸: {original_size[0]}x{original_size[1]}")

        # 检查图片尺寸
        if original_size[0] < 16 or original_size[1] < 16:
            result["warnings"].append(
                f"源图片尺寸过小（{original_size[0]}x{original_size[1]}），可能导致图标模糊"
            )

        # 检查是否为正方形
        if original_size[0] != original_size[1]:
            result["warnings"].append(
                f"源图片不是正方形（{original_size[0]}x{original_size[1]}），将被拉伸为正方形"
            )

        # 确保 RGBA 模式
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

        # 确保输出目录存在
        output_dir = os.path.dirname(output_ico_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # 构建 ICO 文件
        build_ico_file(img, output_ico_path, result["log"])

        img.close()

        # 验证生成的文件
        verify_result = verify_ico_file(output_ico_path)
        result["sizes"] = [f"{w}x{h}" for w, h in verify_result["sizes"]]
        result["sizes_info"] = verify_result["sizes_info"]
        result["warnings"].extend(verify_result["warnings"])

        ico_size = os.path.getsize(output_ico_path)
        result["log"].append(f"ICO 文件: {ico_size} 字节, 包含 {verify_result['count']} 个图标")
        result["log"].append(f"包含尺寸: {', '.join(verify_result['sizes_info'])}")

        if verify_result["valid"]:
            result["log"].append("ICO 文件验证通过")
        else:
            result["log"].append("ICO 文件验证未完全通过（但仍可使用）")

        result["success"] = True

    except Exception as e:
        result["error"] = f"转换图标失败: {str(e)}"
        import traceback
        result["traceback"] = traceback.format_exc()

    return result


def convert_svg_to_ico(source_path: str, output_ico_path: str) -> dict:
    """
    将 SVG 图片转换为多尺寸合规 ICO 文件

    优先使用 cairosvg，回退到 Pillow（有限支持）

    Args:
        source_path: SVG 源文件路径
        output_ico_path: 输出 ICO 文件路径

    Returns:
        结果字典
    """
    result = {
        "success": False,
        "ico_path": output_ico_path,
        "sizes": [],
        "sizes_info": [],
        "warnings": [],
        "log": [],
    }

    png_data = None

    # 尝试使用 cairosvg
    try:
        import cairosvg
        result["log"].append("使用 cairosvg 转换 SVG...")

        png_data = cairosvg.svg2png(
            url=source_path,
            output_width=512,
            output_height=512,
        )
        result["log"].append("cairosvg 转换成功")
    except ImportError:
        result["log"].append("cairosvg 不可用，尝试 Pillow...")
    except Exception as e:
        result["log"].append(f"cairosvg 转换失败: {e}，尝试 Pillow...")

    # 回退到 Pillow
    if png_data is None:
        try:
            from PIL import Image

            img = Image.open(source_path)
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            png_data = buf.getvalue()
            img.close()
            result["log"].append("使用 Pillow 加载 SVG（有限支持）")
        except Exception as e:
            result["error"] = f"无法转换 SVG: cairosvg 和 Pillow 均不可用或转换失败: {e}"
            return result

    if png_data is None:
        result["error"] = "SVG 转换失败：无法生成中间 PNG 数据"
        return result

    # 将 PNG 数据写入临时文件，再调用通用转换
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(png_data))
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # 确保输出目录存在
        output_dir = os.path.dirname(output_ico_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        build_ico_file(img, output_ico_path, result["log"])
        img.close()

        # 验证
        verify_result = verify_ico_file(output_ico_path)
        result["sizes"] = [f"{w}x{h}" for w, h in verify_result["sizes"]]
        result["sizes_info"] = verify_result["sizes_info"]
        result["warnings"].extend(verify_result["warnings"])

        ico_size = os.path.getsize(output_ico_path)
        result["log"].append(f"ICO 文件: {ico_size} 字节, 包含 {verify_result['count']} 个图标")
        result["log"].append(f"包含尺寸: {', '.join(verify_result['sizes_info'])}")

        result["success"] = True

    except ImportError:
        result["error"] = "Pillow 未安装，无法完成 SVG 转换的最后阶段"
    except Exception as e:
        result["error"] = f"SVG 转换最终处理失败: {str(e)}"

    return result


def check_pillow_available() -> dict:
    """
    检查 Pillow 是否可用

    Returns:
        {"available": bool, "version": str or None}
    """
    try:
        import PIL
        from PIL import Image
        version = getattr(PIL, '__version__', 'unknown')
        return {"available": True, "version": version}
    except ImportError:
        return {"available": False, "version": None}


def check_cairosvg_available() -> dict:
    """
    检查 cairosvg 是否可用

    Returns:
        {"available": bool, "version": str or None}
    """
    try:
        import cairosvg
        version = getattr(cairosvg, '__version__', 'unknown')
        return {"available": True, "version": version}
    except ImportError:
        return {"available": False, "version": None}


def main():
    """
    命令行入口

    用法:
        python icon_convert_helper.py convert <source_path> <output_ico_path>
        python icon_convert_helper.py convert-svg <source_path> <output_ico_path>
        python icon_convert_helper.py check-pillow
        python icon_convert_helper.py check-cairosvg
        python icon_convert_helper.py check-ico <ico_path>
        python icon_convert_helper.py verify-ico <ico_path>

    所有命令均输出 JSON 到 stdout
    """
    if len(sys.argv) < 2:
        result = {
            "success": False,
            "error": "缺少命令参数",
            "usage": (
                "用法:\n"
                "  python icon_convert_helper.py convert <source_path> <output_ico_path>\n"
                "  python icon_convert_helper.py convert-svg <source_path> <output_ico_path>\n"
                "  python icon_convert_helper.py check-pillow\n"
                "  python icon_convert_helper.py check-cairosvg\n"
                "  python icon_convert_helper.py check-ico <ico_path>\n"
                "  python icon_convert_helper.py verify-ico <ico_path>\n"
            ),
        }
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(1)

    command = sys.argv[1]

    try:
        if command == "convert":
            if len(sys.argv) < 4:
                result = {"success": False, "error": "缺少参数: convert <source_path> <output_ico_path>"}
            else:
                source_path = sys.argv[2]
                output_ico_path = sys.argv[3]
                result = convert_image_to_ico(source_path, output_ico_path)

        elif command == "convert-svg":
            if len(sys.argv) < 4:
                result = {"success": False, "error": "缺少参数: convert-svg <source_path> <output_ico_path>"}
            else:
                source_path = sys.argv[2]
                output_ico_path = sys.argv[3]
                result = convert_svg_to_ico(source_path, output_ico_path)

        elif command == "check-pillow":
            result = check_pillow_available()

        elif command == "check-cairosvg":
            result = check_cairosvg_available()

        elif command == "check-ico":
            if len(sys.argv) < 3:
                result = {"success": False, "error": "缺少参数: check-ico <ico_path>"}
            else:
                ico_path = sys.argv[2]
                needs_regen, reason = check_ico_needs_regeneration(ico_path)
                result = {
                    "needs_regeneration": needs_regen,
                    "reason": reason,
                }

        elif command == "verify-ico":
            if len(sys.argv) < 3:
                result = {"success": False, "error": "缺少参数: verify-ico <ico_path>"}
            else:
                ico_path = sys.argv[2]
                result = verify_ico_file(ico_path)
                # 将 sizes 中的元组转为列表，使其 JSON 可序列化
                result["sizes"] = [list(s) for s in result["sizes"]]

        else:
            result = {"success": False, "error": f"未知命令: {command}"}

    except Exception as e:
        import traceback
        result = {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }

    # 输出 JSON 结果到 stdout
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
