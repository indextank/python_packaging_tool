"""
图标生成器工具 - PyQt6最佳实践实现

使用Qt原生绘图功能生成主题图标，支持任意DPI完美缩放。
"""

import os
import sys
import tempfile
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


# 主题图标文件名
THEME_ICONS = ("check_light.png", "check_dark.png", "radio_light.png", "radio_dark.png")


def _find_resource_file(filename: str) -> Optional[str]:
    """
    查找资源文件路径（兼容开发模式和打包后的exe）。
    
    参数:
        filename: 文件名（不含目录）
    
    返回:
        找到的文件完整路径，未找到则返回None
    """
    search_paths: List[str] = []

    if getattr(sys, 'frozen', False):
        # 打包模式
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, '_MEIPASS', None)
        
        if meipass:
            search_paths.extend([
                os.path.join(meipass, filename),
                os.path.join(meipass, "resources", "icons", filename),
            ])
        
        search_paths.extend([
            os.path.join(exe_dir, filename),
            os.path.join(exe_dir, "resources", "icons", filename),
            os.path.join(os.getcwd(), filename),
            os.path.join(os.getcwd(), "resources", "icons", filename),
        ])
    else:
        # 开发模式：从当前文件向上三级找项目根目录
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        search_paths.append(os.path.join(project_root, "resources", "icons", filename))

    for path in search_paths:
        if os.path.exists(path):
            return path
    return None


class IconGenerator:
    """
    使用Qt原生绘图生成主题图标。
    
    支持程序化创建图标，无需外部图像文件，任意DPI下完美缩放。
    """

    # 默认强调色（Windows 10/11蓝色）
    DEFAULT_ACCENT_COLOR = "#0078d4"

    def __init__(self, cache_dir: Optional[str] = None):
        """
        初始化图标生成器。

        参数:
            cache_dir: 缓存目录，None时使用系统临时目录
        """
        self._cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), "python_packaging_tool")
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """确保缓存目录存在"""
        try:
            os.makedirs(self._cache_dir, exist_ok=True)
        except Exception:
            self._cache_dir = tempfile.gettempdir()

    @property
    def cache_dir(self) -> str:
        """缓存目录路径"""
        return self._cache_dir

    def create_checkmark_pixmap(
        self,
        size: int = 18,
        color: str = DEFAULT_ACCENT_COLOR,
        line_width: int = 2,
    ) -> QPixmap:
        """
        为复选框创建勾选标记图标。

        参数:
            size: 图标大小（像素）
            color: 勾选标记颜色（十六进制字符串）
            line_width: 勾选标记的线条宽度

        返回:
            包含勾选标记的QPixmap对象
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(QColor(color), line_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        # 根据大小计算勾选标记的点位
        # 勾选标记由两条线绘制成"V"形状
        margin = size * 0.2
        mid_x = size * 0.35
        mid_y = size * 0.7

        # 第一条线：从左上方到中下方
        painter.drawLine(
            int(margin),
            int(size * 0.5),
            int(mid_x),
            int(mid_y)
        )

        # 第二条线：从中下方到右上方
        painter.drawLine(
            int(mid_x),
            int(mid_y),
            int(size - margin),
            int(size * 0.25)
        )

        painter.end()
        return pixmap

    def create_radio_dot_pixmap(
        self,
        size: int = 18,
        color: str = DEFAULT_ACCENT_COLOR,
        dot_ratio: float = 0.45,
    ) -> QPixmap:
        """
        为单选按钮创建填充圆形图标。

        参数:
            size: 图标大小（像素）
            color: 圆点颜色（十六进制字符串）
            dot_ratio: 圆点直径与图标大小的比例

        返回:
            包含填充圆形的QPixmap对象
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)

        # 计算圆点大小和位置
        dot_size = int(size * dot_ratio)
        offset = (size - dot_size) // 2

        painter.drawEllipse(offset, offset, dot_size, dot_size)

        painter.end()
        return pixmap

    def save_checkmark_icon(
        self,
        filename: str,
        size: int = 18,
        color: str = DEFAULT_ACCENT_COLOR,
    ) -> str:
        """
        生成并保存勾选标记图标到文件。

        参数:
            filename: 输出文件名（简单文件名，如 "check_dark.png"）
            size: 图标大小（像素）
            color: 勾选标记颜色

        返回:
            保存的图标文件的完整路径
        """
        pixmap = self.create_checkmark_pixmap(size, color)
        # 只使用文件名，忽略路径部分
        simple_name = os.path.basename(filename)
        filepath = os.path.join(self._cache_dir, simple_name)
        pixmap.save(filepath)
        return filepath

    def save_radio_icon(
        self,
        filename: str,
        size: int = 18,
        color: str = DEFAULT_ACCENT_COLOR,
    ) -> str:
        """
        生成并保存单选按钮图标到文件。

        参数:
            filename: 输出文件名（简单文件名，如 "radio_dark.png"）
            size: 图标大小（像素）
            color: 圆点颜色

        返回:
            保存的图标文件的完整路径
        """
        pixmap = self.create_radio_dot_pixmap(size, color)
        # 只使用文件名，忽略路径部分
        simple_name = os.path.basename(filename)
        filepath = os.path.join(self._cache_dir, simple_name)
        pixmap.save(filepath)
        return filepath

    def generate_theme_icons(
        self,
        accent_color: str = DEFAULT_ACCENT_COLOR,
    ) -> Tuple[str, str, str, str]:
        """
        获取应用程序所需的所有主题图标路径。

        参数:
            accent_color: 已废弃，保留以兼容旧代码

        返回:
            (浅色勾选, 深色勾选, 浅色单选, 深色单选) 路径元组
        """
        return tuple(self.get_icon_path(name) for name in THEME_ICONS)  # type: ignore

    def get_icon_path(self, name: str) -> str:
        """
        获取图标文件路径。

        参数:
            name: 图标文件名或相对路径

        返回:
            图标完整路径（优先资源目录，回退到缓存目录）
        """
        simple_name = os.path.basename(name)
        
        # 主题图标优先从资源目录查找
        if simple_name in THEME_ICONS or "resources" in name:
            resource_path = _find_resource_file(simple_name)
            if resource_path:
                return resource_path
        
        # 回退到缓存路径
        return os.path.join(self._cache_dir, simple_name)

    def create_app_icon(
        self,
        size: int = 256,
        primary_color: str = "#0078d4",
        secondary_color: str = "#ffffff",
    ) -> QIcon:
        """
        创建简单的应用程序图标。

        参数:
            size: 图标大小（像素）
            primary_color: 背景颜色
            secondary_color: 前景颜色

        返回:
            QIcon对象
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 绘制背景圆形
        painter.setBrush(QColor(primary_color))
        painter.setPen(Qt.PenStyle.NoPen)
        margin = size * 0.05
        painter.drawEllipse(
            int(margin),
            int(margin),
            int(size - 2 * margin),
            int(size - 2 * margin)
        )

        # 绘制代表Python的"P"字母
        painter.setPen(QPen(QColor(secondary_color), size * 0.08))
        font_size = int(size * 0.5)
        from PyQt6.QtGui import QFont
        font = QFont("Arial", font_size, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(
            pixmap.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "P"
        )

        painter.end()
        return QIcon(pixmap)


def get_icon_generator(cache_dir: Optional[str] = None) -> IconGenerator:
    """
    工厂函数，获取IconGenerator实例。

    参数:
        cache_dir: 可选的缓存目录路径

    返回:
        IconGenerator实例
    """
    return IconGenerator(cache_dir)


# 用于快速生成图标的便捷函数

def create_themed_checkbox_icons(
    cache_dir: str,
    accent_color: str = IconGenerator.DEFAULT_ACCENT_COLOR,
) -> Tuple[str, str]:
    """
    创建浅色和深色主题的复选框图标。

    参数:
        cache_dir: 保存图标的目录
        accent_color: 勾选标记的强调色

    返回:
        元组，包含(浅色图标路径, 深色图标路径)
    """
    generator = IconGenerator(cache_dir)
    light = generator.save_checkmark_icon("check_light.png", color=accent_color)
    dark = generator.save_checkmark_icon("check_dark.png", color=accent_color)
    return light, dark


def create_themed_radio_icons(
    cache_dir: str,
    accent_color: str = IconGenerator.DEFAULT_ACCENT_COLOR,
) -> Tuple[str, str]:
    """
    创建浅色和深色主题的单选按钮图标。

    参数:
        cache_dir: 保存图标的目录
        accent_color: 圆点的强调色

    返回:
        元组，包含(浅色图标路径, 深色图标路径)
    """
    generator = IconGenerator(cache_dir)
    light = generator.save_radio_icon("radio_light.png", color=accent_color)
    dark = generator.save_radio_icon("radio_dark.png", color=accent_color)
    return light, dark
