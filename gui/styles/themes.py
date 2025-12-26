"""
PyQt6主题管理器 - 集中式主题和样式管理

本模块遵循PyQt6最佳实践：
1. 将样式定义与UI逻辑分离
2. 提供清晰的主题管理API
3. 支持系统主题检测
4. 全面使用类型提示
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

# 尝试导入darkdetect用于系统主题检测
try:
    import darkdetect
    HAS_DARKDETECT = True
except ImportError:
    HAS_DARKDETECT = False


class ThemeMode(Enum):
    """主题模式枚举"""
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ThemeColors:
    """主题颜色定义"""
    # 背景颜色
    background_primary: str
    background_secondary: str
    background_tertiary: str

    # 文本颜色
    text_primary: str
    text_secondary: str
    text_disabled: str

    # 边框颜色
    border_primary: str
    border_secondary: str

    # 强调颜色
    accent_primary: str
    accent_hover: str
    accent_pressed: str

    # 状态颜色
    danger: str
    danger_hover: str
    danger_pressed: str
    warning: str
    success: str

    # 滚动条颜色
    scrollbar_background: str
    scrollbar_handle: str
    scrollbar_handle_hover: str
    scrollbar_handle_pressed: str


# 浅色主题调色板
LIGHT_COLORS = ThemeColors(
    background_primary="#f5f5f5",
    background_secondary="#ffffff",
    background_tertiary="#e8e8e8",
    text_primary="#333333",
    text_secondary="#666666",
    text_disabled="#999999",
    border_primary="#cccccc",
    border_secondary="#dddddd",
    accent_primary="#0078d4",
    accent_hover="#106ebe",
    accent_pressed="#005a9e",
    danger="#dc3545",
    danger_hover="#c82333",
    danger_pressed="#bd2130",
    warning="#ffc107",
    success="#28a745",
    scrollbar_background="#f0f0f0",
    scrollbar_handle="#c0c0c0",
    scrollbar_handle_hover="#a0a0a0",
    scrollbar_handle_pressed="#808080",
)

# 深色主题调色板
DARK_COLORS = ThemeColors(
    background_primary="#1e1e1e",
    background_secondary="#252526",
    background_tertiary="#3c3c3c",
    text_primary="#d4d4d4",
    text_secondary="#9e9e9e",
    text_disabled="#6e6e6e",
    border_primary="#3c3c3c",
    border_secondary="#4a4a4a",
    accent_primary="#0078d4",
    accent_hover="#1e90ff",
    accent_pressed="#005a9e",
    danger="#dc3545",
    danger_hover="#c82333",
    danger_pressed="#bd2130",
    warning="#FFD700",
    success="#28a745",
    scrollbar_background="#1e1e1e",
    scrollbar_handle="#505050",
    scrollbar_handle_hover="#606060",
    scrollbar_handle_pressed="#707070",
)


def generate_base_stylesheet(colors: ThemeColors) -> str:
    """为给定的颜色调色板生成基础样式表"""
    return f"""
        * {{
            background-color: transparent;
        }}

        QMainWindow {{
            background-color: {colors.background_primary};
        }}

        QWidget#centralWidget {{
            background-color: {colors.background_primary};
        }}

        QGroupBox {{
            font-weight: bold;
            border: 1px solid {colors.border_primary};
            border-radius: 5px;
            margin-top: 10px;
            padding-top: 10px;
            background-color: {colors.background_secondary};
            color: {colors.text_primary};
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            background-color: {colors.background_secondary};
            color: {colors.text_primary};
        }}

        QLineEdit {{
            background-color: {colors.background_secondary};
            border: 1px solid {colors.border_primary};
            border-radius: 3px;
            padding: 5px;
            color: {colors.text_primary};
        }}

        QTextEdit {{
            background-color: {colors.background_secondary};
            border: 1px solid {colors.border_primary};
            border-radius: 3px;
            padding: 5px;
            color: {colors.text_primary};
        }}

        QLineEdit:focus, QTextEdit:focus {{
            border: 1px solid {colors.accent_primary};
        }}

        QPushButton {{
            background-color: {colors.accent_primary};
            color: white;
            border: none;
            border-radius: 3px;
            padding: 8px 16px;
            min-width: 80px;
        }}

        QPushButton:hover {{
            background-color: {colors.accent_hover};
        }}

        QPushButton:pressed {{
            background-color: {colors.accent_pressed};
        }}

        QPushButton:disabled {{
            background-color: {colors.border_primary};
            color: {colors.text_disabled};
        }}

        QCheckBox {{
            color: {colors.text_primary};
            background-color: transparent;
            spacing: 5px;
        }}

        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {colors.text_secondary};
            border-radius: 3px;
            background-color: {colors.background_secondary};
        }}

        QCheckBox::indicator:hover {{
            border: 2px solid {colors.accent_primary};
        }}

        QCheckBox::indicator:checked {{
            background-color: {colors.background_secondary};
            border: 2px solid {colors.accent_primary};
        }}

        QRadioButton {{
            color: {colors.text_primary};
            background-color: transparent;
            spacing: 5px;
        }}

        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {colors.text_secondary};
            border-radius: 9px;
            background-color: {colors.background_secondary};
        }}

        QRadioButton::indicator:hover {{
            border: 2px solid {colors.accent_primary};
        }}

        QRadioButton::indicator:checked {{
            width: 18px;
            height: 18px;
            border: 2px solid {colors.accent_primary};
            border-radius: 9px;
            background-color: {colors.background_secondary};
        }}

        QLabel {{
            color: {colors.text_primary};
            background-color: transparent;
        }}

        QToolButton {{
            background-color: {colors.background_tertiary};
            border: 1px solid {colors.border_primary};
            border-radius: 3px;
            padding: 5px 10px;
            color: {colors.text_primary};
        }}

        QToolButton:hover {{
            background-color: {colors.border_secondary};
        }}

        QToolButton::menu-indicator {{
            image: none;
        }}

        QMenu {{
            background-color: {colors.background_secondary};
            border: 1px solid {colors.border_primary};
            color: {colors.text_primary};
        }}

        QMenu::item {{
            padding: 5px 20px;
            background-color: {colors.background_secondary};
        }}

        QMenu::item:selected {{
            background-color: {colors.accent_primary};
            color: white;
        }}

        QHBoxLayout, QVBoxLayout {{
            background-color: transparent;
        }}

        /* Modern Scrollbar Styling */
        QScrollBar:vertical {{
            background-color: {colors.scrollbar_background};
            width: 12px;
            border: none;
            border-radius: 6px;
            margin: 0px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {colors.scrollbar_handle};
            min-height: 30px;
            border-radius: 6px;
            margin: 2px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {colors.scrollbar_handle_hover};
        }}

        QScrollBar::handle:vertical:pressed {{
            background-color: {colors.scrollbar_handle_pressed};
        }}

        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
            background: none;
        }}

        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            background-color: {colors.scrollbar_background};
            height: 12px;
            border: none;
            border-radius: 6px;
            margin: 0px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {colors.scrollbar_handle};
            min-width: 30px;
            border-radius: 6px;
            margin: 2px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {colors.scrollbar_handle_hover};
        }}

        QScrollBar::handle:horizontal:pressed {{
            background-color: {colors.scrollbar_handle_pressed};
        }}

        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
            background: none;
        }}

        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}

        /* MessageBox Styling */
        QMessageBox {{
            background-color: {colors.background_secondary};
            color: {colors.text_primary};
        }}

        QMessageBox QLabel {{
            color: {colors.text_primary};
            background-color: transparent;
            padding: 10px;
        }}

        QMessageBox QPushButton {{
            background-color: {colors.accent_primary};
            color: white;
            border: none;
            border-radius: 3px;
            padding: 6px 20px;
            min-width: 80px;
        }}

        QMessageBox QPushButton:hover {{
            background-color: {colors.accent_hover};
        }}

        QMessageBox QPushButton:pressed {{
            background-color: {colors.accent_pressed};
        }}

        /* FileDialog Styling */
        QFileDialog {{
            background-color: {colors.background_secondary};
            color: {colors.text_primary};
        }}

        QFileDialog QLabel {{
            color: {colors.text_primary};
        }}

        QFileDialog QPushButton {{
            background-color: {colors.accent_primary};
            color: white;
            border: none;
            border-radius: 3px;
            padding: 6px 16px;
            min-width: 80px;
        }}

        QFileDialog QPushButton:hover {{
            background-color: {colors.accent_hover};
        }}
    """


def get_danger_button_stylesheet(colors: ThemeColors) -> str:
    """生成危险按钮样式表（例如：取消按钮）"""
    return f"""
        QPushButton {{
            background-color: {colors.danger};
            color: white;
            border: none;
            border-radius: 3px;
            padding: 8px 16px;
            min-width: 80px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {colors.danger_hover};
        }}
        QPushButton:pressed {{
            background-color: {colors.danger_pressed};
        }}
    """


def get_message_box_stylesheet(colors: ThemeColors) -> str:
    """生成消息框专用样式表"""
    return f"""
        QMessageBox {{
            background-color: {colors.background_secondary};
            color: {colors.text_primary};
        }}
        QMessageBox QLabel {{
            color: {colors.text_primary};
            background-color: transparent;
        }}
        QMessageBox QPushButton {{
            background-color: {colors.accent_primary};
            color: white;
            border: none;
            border-radius: 3px;
            padding: 6px 20px;
            min-width: 80px;
            min-height: 24px;
        }}
        QMessageBox QPushButton:hover {{
            background-color: {colors.accent_hover};
        }}
        QMessageBox QPushButton:pressed {{
            background-color: {colors.accent_pressed};
        }}
    """


class ThemeManager(QObject):
    """
    遵循PyQt6最佳实践的集中式主题管理器。

    提供：
    - 系统主题检测
    - 带信号的主题切换
    - 一致的样式生成
    - 主题复选框/单选按钮的图标路径管理
    """

    # 主题改变时发出的信号
    theme_changed = pyqtSignal(bool)  # True = 深色模式, False = 浅色模式

    def __init__(self, app_dir: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._current_mode = ThemeMode.SYSTEM
        self._app_dir = app_dir
        self._cached_is_dark: Optional[bool] = None

    @property
    def current_mode(self) -> ThemeMode:
        """获取当前主题模式"""
        return self._current_mode

    @current_mode.setter
    def current_mode(self, mode: ThemeMode) -> None:
        """设置当前主题模式，如果改变则发出信号"""
        if self._current_mode != mode:
            self._current_mode = mode
            self._cached_is_dark = None  # 清除缓存
            self.theme_changed.emit(self.is_dark)

    @property
    def is_dark(self) -> bool:
        """确定当前有效主题是否为深色"""
        if self._cached_is_dark is not None:
            return self._cached_is_dark

        if self._current_mode == ThemeMode.DARK:
            self._cached_is_dark = True
        elif self._current_mode == ThemeMode.LIGHT:
            self._cached_is_dark = False
        else:
            self._cached_is_dark = self._detect_system_dark_mode()

        return self._cached_is_dark

    @property
    def colors(self) -> ThemeColors:
        """获取当前主题颜色"""
        return DARK_COLORS if self.is_dark else LIGHT_COLORS

    def _detect_system_dark_mode(self) -> bool:
        """检测系统是否使用深色模式"""
        if HAS_DARKDETECT:
            try:
                return bool(darkdetect.isDark())
            except Exception:
                pass

        # 回退方案：使用Qt调色板检测
        try:
            app = QApplication.instance()
            if app:
                palette = app.palette()
                bg_color = palette.color(QPalette.ColorRole.Window)
                return bg_color.lightness() < 128
        except Exception:
            pass

        # 默认为深色（现代美学）
        return True

    def get_stylesheet(self, check_icon_path: str, radio_icon_path: str) -> str:
        """
        为当前主题生成完整的样式表。

        参数:
            check_icon_path: 复选框选中图标的路径
            radio_icon_path: 单选按钮选中图标的路径

        返回:
            完整的样式表字符串
        """
        base_style = generate_base_stylesheet(self.colors)

        # 规范化CSS路径（使用正斜杠）
        check_icon = check_icon_path.replace("\\", "/")
        radio_icon = radio_icon_path.replace("\\", "/")

        icon_style = f"""
            QCheckBox::indicator:checked {{
                image: url({check_icon});
            }}
            QRadioButton::indicator:checked {{
                image: url({radio_icon});
            }}
        """

        return base_style + icon_style

    def get_danger_button_style(self) -> str:
        """获取当前主题的危险按钮样式表"""
        return get_danger_button_stylesheet(self.colors)

    def get_message_box_style(self) -> str:
        """获取当前主题的消息框样式表"""
        return get_message_box_stylesheet(self.colors)

    def get_label_color(self, variant: str = "primary") -> str:
        """
        获取当前主题的适当标签颜色。

        参数:
            variant: 颜色变体 - 'primary', 'secondary', 'warning', 'danger'

        返回:
            颜色十六进制字符串
        """
        colors = self.colors
        color_map = {
            "primary": colors.text_primary,
            "secondary": colors.text_secondary,
            "warning": colors.warning,
            "danger": colors.danger,
            "success": colors.success,
            "accent": colors.accent_primary,
        }
        return color_map.get(variant, colors.text_primary)

    def invalidate_cache(self) -> None:
        """使缓存的主题检测失效（当系统主题可能已改变时调用）"""
        self._cached_is_dark = None


# 用于快速主题检测的便捷函数
def detect_system_dark_mode() -> bool:
    """检测系统深色模式的独立函数"""
    if HAS_DARKDETECT:
        try:
            return bool(darkdetect.isDark())
        except Exception:
            pass

    try:
        app = QApplication.instance()
        if app:
            palette = app.palette()
            bg_color = palette.color(QPalette.ColorRole.Window)
            return bg_color.lightness() < 128
    except Exception:
        pass

    return True
