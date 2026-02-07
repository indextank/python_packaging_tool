"""
版本信息对话框模块

本模块包含版本信息配置对话框的实现。
从 main_window.py 拆分出来，遵循单一职责原则。
"""

import os
from typing import TYPE_CHECKING, Any, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from gui.styles.themes import ThemeManager


class VersionInfoDialog(QDialog):
    """版本信息配置对话框"""

    def __init__(
        self,
        parent: Any = None,
        theme_manager: Optional["ThemeManager"] = None,
        current_info: Optional[Dict[str, str]] = None,
        detected_info: Optional[Dict[str, str]] = None,
        is_nuitka: bool = False,
        sdk_supported: bool = False,
        sdk_message: str = "",
        source_file: Optional[str] = None,
        project_dir: Optional[str] = None,
    ):
        """
        初始化版本信息对话框

        Args:
            parent: 父窗口
            theme_manager: 主题管理器
            current_info: 当前版本信息
            detected_info: 检测到的版本信息
            is_nuitka: 是否使用 Nuitka 打包
            sdk_supported: 是否支持 Windows SDK
            sdk_message: SDK 支持消息
            source_file: 检测到版本信息的源文件路径
            project_dir: 项目目录路径
        """
        super().__init__(parent)

        self.theme_manager = theme_manager
        self.current_info = current_info or {}
        self.detected_info = detected_info or {}
        self.is_nuitka = is_nuitka
        self.sdk_supported = sdk_supported
        self.sdk_message = sdk_message
        self.source_file = source_file
        self.project_dir = project_dir

        # 结果
        self.result_info: Dict[str, str] = {}

        self._init_ui()
        self._apply_theme()
        self._merge_detected_info()

    def _init_ui(self) -> None:
        """初始化 UI"""
        self.setWindowTitle("添加版权信息")
        self.setMinimumWidth(450)

        # 设置对话框标志
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)

        # 添加 Nuitka 提示
        if self.is_nuitka:
            self._add_nuitka_tip(layout)

        # 添加检测提示
        if any(self.detected_info.values()):
            self._add_detection_tip(layout)

        # 表单布局
        form_layout = QFormLayout()

        # 产品名称
        self.product_name_edit = QLineEdit()
        self.product_name_edit.setPlaceholderText("eg. My Application")
        form_layout.addRow("产品名称:", self.product_name_edit)

        # 公司名称
        self.company_name_edit = QLineEdit()
        self.company_name_edit.setPlaceholderText("eg. XXX Tech Co., Ltd.")
        form_layout.addRow("公司名称:", self.company_name_edit)

        # 文件描述
        self.file_desc_edit = QLineEdit()
        self.file_desc_edit.setPlaceholderText("eg. This is a useful tool")
        form_layout.addRow("文件描述:", self.file_desc_edit)

        # 版权信息
        self.copyright_edit = QLineEdit()
        self.copyright_edit.setPlaceholderText("eg. Copyright © 2024 XXX Company")
        form_layout.addRow("版权信息:", self.copyright_edit)

        # 版本号
        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("eg. 1.0.0")
        form_layout.addRow("版本号:", self.version_edit)

        layout.addLayout(form_layout)

        # 按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.ok_btn = QPushButton("确定")
        self.ok_btn.setProperty("buttonType", "primary")
        self.ok_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

    def _apply_theme(self) -> None:
        """应用主题样式"""
        if not self.theme_manager:
            return

        colors = self.theme_manager.colors

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.background_primary};
                color: {colors.text_primary};
            }}
            QLabel {{
                color: {colors.text_primary};
                background-color: transparent;
            }}
            QLineEdit {{
                background-color: {colors.background_secondary};
                border: 1px solid {colors.border_primary};
                border-radius: 3px;
                padding: 5px;
                color: {colors.text_primary};
            }}
            QLineEdit:focus {{
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
        """)

        # 取消按钮样式
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {colors.background_tertiary};
                color: {colors.text_primary};
                border: 1px solid {colors.border_primary};
            }}
            QPushButton:hover {{
                background-color: {colors.border_secondary};
            }}
        """)

    def _add_nuitka_tip(self, layout: QVBoxLayout) -> None:
        """添加 Nuitka 相关提示"""
        if not self.theme_manager:
            return

        colors = self.theme_manager.colors

        if self.sdk_supported:
            tip_label = QLabel(f"""
<b>✓ 支持中文版本信息</b><br>
{self.sdk_message}<br>
<span style="color: {colors.success};">您可以填写中文信息，系统将自动处理。</span>
            """)
            tip_label.setWordWrap(True)
            tip_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {colors.background_secondary};
                    border: 1px solid {colors.success};
                    border-radius: 5px;
                    padding: 10px;
                    color: {colors.text_primary};
                }}
            """)
        else:
            tip_label = QLabel(f"""
<b>提示：</b><br>当前Nuitka打包默认请填写英文信息。<br>
{self.sdk_message}<br><br>
如需支持中文信息，请先安装以下任一组件：<br>
• <b>Windows SDK</b> (推荐)<br>
• <b>Visual Studio Build Tools</b><br>
• <b>Visual Studio</b> (任意版本)
            """)
            tip_label.setWordWrap(True)
            tip_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {colors.background_secondary};
                    border: 1px solid {colors.border_primary};
                    border-radius: 5px;
                    padding: 10px;
                    color: {colors.text_primary};
                }}
            """)

        layout.addWidget(tip_label)
        layout.addSpacing(10)

    def _add_detection_tip(self, layout: QVBoxLayout) -> None:
        """添加检测到版本信息的提示"""
        if not self.theme_manager:
            return

        colors = self.theme_manager.colors

        # 生成提示文本
        source_text = ""
        if self.source_file:
            if self.project_dir and self.source_file.startswith(self.project_dir):
                rel_path = os.path.relpath(self.source_file, self.project_dir)
                source_text = f"项目 {rel_path}"
            else:
                source_text = f"文件 {os.path.basename(self.source_file)}"

        if source_text:
            detect_tip = QLabel(f"✓ 已从 {source_text} 中检测到版本信息")
        else:
            detect_tip = QLabel("✓ 已检测到版本信息")

        detect_tip.setStyleSheet(f"color: {colors.success}; font-size: 12px;")
        layout.addWidget(detect_tip)
        layout.addSpacing(5)

    def _merge_detected_info(self) -> None:
        """合并检测到的信息到当前信息"""
        # 产品名称
        product_name = (
            self.detected_info.get("product_name") or
            self.detected_info.get("product_name_en") or
            self.current_info.get("product_name", "")
        )
        self.product_name_edit.setText(product_name)

        # 公司名称
        company_name = (
            self.detected_info.get("company_name") or
            self.current_info.get("company_name", "")
        )
        self.company_name_edit.setText(company_name)

        # 文件描述
        file_description = (
            self.detected_info.get("file_description") or
            self.detected_info.get("file_description_en") or
            self.current_info.get("file_description", "")
        )
        self.file_desc_edit.setText(file_description)

        # 版权信息
        copyright_text = (
            self.detected_info.get("copyright") or
            self.current_info.get("copyright", "Copyright © 2026")
        )
        self.copyright_edit.setText(copyright_text)

        # 版本号
        version = (
            self.detected_info.get("version") or
            self.current_info.get("version", "1.0.0")
        )
        self.version_edit.setText(version)

    def _on_accept(self) -> None:
        """确定按钮点击处理"""
        self.result_info = {
            "product_name": self.product_name_edit.text().strip(),
            "company_name": self.company_name_edit.text().strip(),
            "file_description": self.file_desc_edit.text().strip(),
            "copyright": self.copyright_edit.text().strip(),
            "version": self.version_edit.text().strip() or "1.0.0",
        }
        self.accept()

    def get_version_info(self) -> Dict[str, str]:
        """
        获取版本信息

        Returns:
            版本信息字典
        """
        return self.result_info


def show_version_info_dialog(
    parent: Any = None,
    theme_manager: Optional["ThemeManager"] = None,
    current_info: Optional[Dict[str, str]] = None,
    detected_info: Optional[Dict[str, str]] = None,
    is_nuitka: bool = False,
    sdk_supported: bool = False,
    sdk_message: str = "",
    source_file: Optional[str] = None,
    project_dir: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """
    显示版本信息对话框的便捷函数

    Args:
        parent: 父窗口
        theme_manager: 主题管理器
        current_info: 当前版本信息
        detected_info: 检测到的版本信息
        is_nuitka: 是否使用 Nuitka 打包
        sdk_supported: 是否支持 Windows SDK
        sdk_message: SDK 支持消息
        source_file: 检测到版本信息的源文件路径
        project_dir: 项目目录路径

    Returns:
        用户确认的版本信息，取消返回 None
    """
    dialog = VersionInfoDialog(
        parent=parent,
        theme_manager=theme_manager,
        current_info=current_info,
        detected_info=detected_info,
        is_nuitka=is_nuitka,
        sdk_supported=sdk_supported,
        sdk_message=sdk_message,
        source_file=source_file,
        project_dir=project_dir,
    )

    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        return dialog.get_version_info()

    return None
