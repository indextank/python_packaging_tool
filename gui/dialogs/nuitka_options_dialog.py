"""
Nuitka 高级选项对话框

基于 Nuitka 官方文档的最佳实践，提供高级配置选项。
"""

from typing import TYPE_CHECKING, Any, Dict, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from gui.styles.themes import ThemeManager


class ArrowSpinBox(QSpinBox):
    """带有文本箭头按钮的 QSpinBox"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)

        # 设置按钮文本
        for child in self.children():
            if isinstance(child, QToolButton):
                # 获取按钮方向
                if child.y() == 0 or "up" in child.objectName().lower():
                    child.setText("▲")
                else:
                    child.setText("▼")
                child.setStyleSheet("font-size: 10px;")


class NuitkaOptionsDialog(QDialog):
    """
    Nuitka 高级选项配置对话框

    基于 Nuitka 官方文档 (https://nuitka.net/user-documentation/) 的最佳实践，
    提供以下配置选项：

    1. 编译优化选项
    2. Anti-bloat 配置（减少依赖膨胀）
    3. Python 标志优化
    4. 部署模式配置
    5. 缓存控制
    6. 编译报告
    7. Onefile 配置
    """

    def __init__(
        self,
        parent=None,
        current_options: Optional[Dict[str, Any]] = None,
        theme_manager: Optional["ThemeManager"] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Nuitka 高级选项")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)

        # 存储主题管理器
        self.theme_manager = theme_manager

        # 存储父窗口（用于获取图标路径）
        self._parent_window = parent

        # 存储当前选项
        self.options = current_options or self._get_default_options()

        # 应用主题样式
        self._apply_theme()

        self._init_ui()
        self._load_options()

    def _get_checkbox_icon_style(self) -> str:
        """获取复选框选中图标样式（与主界面一致）"""
        if self.theme_manager is None:
            return ""
        if self._parent_window is None:
            return ""
        if not hasattr(self._parent_window, 'icon_generator'):
            return ""

        icon_name = "check_dark.png" if self.theme_manager.is_dark else "check_light.png"
        icon_path = self._parent_window.icon_generator.get_icon_path(f"resources/icons/{icon_name}")
        icon_path = icon_path.replace("\\", "/")

        return f"QCheckBox::indicator:checked {{ image: url({icon_path}); }}"

    def _apply_theme(self) -> None:
        """应用与主窗口一致的主题样式"""
        if self.theme_manager is None:
            return

        colors = self.theme_manager.colors
        check_icon_style = self._get_checkbox_icon_style()

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {colors.background_primary};
                color: {colors.text_primary};
            }}
            QWidget {{
                background-color: {colors.background_primary};
                color: {colors.text_primary};
            }}
            QTabWidget::pane {{
                background-color: {colors.background_secondary};
                border: 1px solid {colors.border_primary};
                border-radius: 3px;
            }}
            QTabBar::tab {{
                background-color: {colors.background_tertiary};
                color: {colors.text_primary};
                border: 1px solid {colors.border_primary};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 16px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background-color: {colors.background_secondary};
                border-bottom: 1px solid {colors.background_secondary};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {colors.accent_hover};
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
            QLabel {{
                color: {colors.text_primary};
                background-color: transparent;
            }}
            QCheckBox {{
                color: {colors.text_primary};
                background-color: transparent;
                spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {colors.border_primary};
                border-radius: 3px;
                background-color: {colors.background_secondary};
            }}
            QCheckBox::indicator:hover {{ border-color: {colors.accent_primary}; }}
            {check_icon_style}
            QLineEdit {{
                background-color: {colors.background_secondary};
                border: 1px solid {colors.border_primary};
                border-radius: 3px;
                padding: 5px;
                color: {colors.text_primary};
            }}
            QLineEdit:focus {{
                border-color: {colors.accent_primary};
            }}
            QLineEdit:disabled {{
                background-color: {colors.background_tertiary};
                color: {colors.text_disabled};
            }}
            QSpinBox {{
                background-color: {colors.background_secondary};
                border: 1px solid {colors.border_primary};
                border-radius: 3px;
                padding: 5px;
                padding-right: 22px;
                color: {colors.text_primary};
                min-height: 22px;
            }}
            QSpinBox:focus {{
                border-color: {colors.accent_primary};
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 18px;
                border-left: 1px solid {colors.border_primary};
                border-top-right-radius: 2px;
                background-color: {colors.background_tertiary};
            }}
            QSpinBox::up-button:hover {{
                background-color: {colors.accent_hover};
            }}
            QSpinBox::up-button:pressed {{
                background-color: {colors.accent_pressed};
            }}
            QSpinBox::up-arrow {{
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 5px solid {colors.text_primary};
                margin: 2px;
            }}
            QSpinBox::up-button:hover QSpinBox::up-arrow {{
                border-bottom-color: white;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 18px;
                border-left: 1px solid {colors.border_primary};
                border-top: 1px solid {colors.border_primary};
                border-bottom-right-radius: 2px;
                background-color: {colors.background_tertiary};
            }}
            QSpinBox::down-button:hover {{
                background-color: {colors.accent_hover};
            }}
            QSpinBox::down-button:pressed {{
                background-color: {colors.accent_pressed};
            }}
            QSpinBox::down-arrow {{
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 5px solid {colors.text_primary};
                margin: 2px;
            }}
            QSpinBox::down-button:hover QSpinBox::down-arrow {{
                border-top-color: white;
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

    def _get_default_options(self) -> Dict[str, Any]:
        """获取默认选项（基于最佳实践）"""
        return {
            # 编译优化
            "lto": True,                      # 链接时优化
            "low_memory": False,              # 低内存模式
            "jobs": None,                     # 并行任务数（None = 自动）

            # Python 标志
            "python_no_docstrings": True,     # 移除文档字符串
            "python_no_asserts": True,        # 禁用断言
            "python_no_warnings": True,       # 禁用警告（默认启用）
            "python_no_annotations": True,    # 移除类型注解（默认启用）

            # Anti-bloat（减少依赖膨胀）
            "noinclude_pytest": True,         # 排除 pytest
            "noinclude_setuptools": True,     # 排除 setuptools
            "noinclude_unittest": True,       # 排除 unittest
            "noinclude_ipython": True,        # 排除 IPython
            "noinclude_dask": True,           # 排除 dask

            # 部署模式
            "deployment": True,               # 部署模式（默认启用）

            # Onefile 配置
            "onefile_tempdir_spec": "{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}",  # 默认使用缓存目录
            "onefile_use_cache": True,        # 使用缓存目录（默认启用）

            # 编译报告
            "generate_report": False,         # 生成编译报告
            "report_path": "",                # 报告路径

            # 缓存配置
            "custom_cache_dir": "",           # 自定义缓存目录
            "clean_cache_after_build": True,  # 打包完成后清理编译缓存

            # 显示选项
            "show_progress": True,            # 显示进度
            "show_memory": True,              # 显示内存使用
            "show_scons": False,              # 显示 scons 命令

            # 自动下载
            "assume_yes_downloads": True,     # 自动确认下载

            # 用户包配置
            "user_package_config": "",        # 用户自定义包配置文件
        }

    def _init_ui(self) -> None:
        """初始化UI"""
        layout = QVBoxLayout(self)

        # 创建选项卡
        tab_widget = QTabWidget()

        # 编译优化选项卡
        tab_widget.addTab(self._create_optimization_tab(), "编译优化")

        # Python 标志选项卡
        tab_widget.addTab(self._create_python_flags_tab(), "Python 标志")

        # Anti-bloat 选项卡
        tab_widget.addTab(self._create_anti_bloat_tab(), "Anti-bloat")

        # Onefile 配置选项卡
        tab_widget.addTab(self._create_onefile_tab(), "Onefile 配置")

        # 高级选项卡
        tab_widget.addTab(self._create_advanced_tab(), "高级选项")

        layout.addWidget(tab_widget)

        # 按钮栏
        button_layout = QHBoxLayout()

        # 重置为默认按钮
        reset_btn = QPushButton("重置为默认")
        reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(reset_btn)

        button_layout.addStretch()

        # 确定和取消按钮
        ok_btn = QPushButton("确定")
        ok_btn.setProperty("buttonType", "primary")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(ok_btn)

        layout.addLayout(button_layout)

    def _create_optimization_tab(self) -> QWidget:
        """创建编译优化选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # LTO 优化组
        lto_group = QGroupBox("链接时优化 (LTO)")
        lto_layout = QVBoxLayout(lto_group)

        self.lto_check = QCheckBox("启用 LTO 链接时优化")
        self.lto_check.setToolTip(
            "链接时优化可以减小可执行文件体积并提升性能，\n"
            "但会增加编译时间和内存使用。"
        )
        lto_layout.addWidget(self.lto_check)

        lto_note = QLabel(
            "<i>注意：LTO 会显著增加编译时间，但能减小最终文件体积。</i>"
        )
        lto_note.setWordWrap(True)
        lto_layout.addWidget(lto_note)

        layout.addWidget(lto_group)

        # 内存和并行组
        memory_group = QGroupBox("内存和并行编译")
        memory_layout = QFormLayout(memory_group)

        self.low_memory_check = QCheckBox("启用低内存模式")
        self.low_memory_check.setToolTip(
            "低内存模式会减少编译时的内存使用，\n"
            "但会增加编译时间。适用于内存有限的系统。"
        )
        memory_layout.addRow(self.low_memory_check)

        jobs_layout = QHBoxLayout()
        self.jobs_spin = QSpinBox()
        self.jobs_spin.setRange(0, 64)
        self.jobs_spin.setSpecialValueText("自动")
        self.jobs_spin.setButtonSymbols(QSpinBox.ButtonSymbols.PlusMinus)
        self.jobs_spin.setToolTip(
            "并行编译任务数。0 表示自动检测 CPU 核心数。\n"
            "减少任务数可以降低内存使用。"
        )
        jobs_layout.addWidget(self.jobs_spin)
        jobs_layout.addWidget(QLabel("(0 = 自动)"))
        jobs_layout.addStretch()
        memory_layout.addRow("并行任务数:", jobs_layout)

        layout.addWidget(memory_group)

        # 显示选项组
        display_group = QGroupBox("编译显示选项")
        display_layout = QVBoxLayout(display_group)

        self.show_progress_check = QCheckBox("显示编译进度")
        self.show_progress_check.setToolTip("显示编译过程的进度信息")
        display_layout.addWidget(self.show_progress_check)

        self.show_memory_check = QCheckBox("显示内存使用")
        self.show_memory_check.setToolTip("显示编译过程中的内存使用情况")
        display_layout.addWidget(self.show_memory_check)

        self.show_scons_check = QCheckBox("显示 Scons 命令")
        self.show_scons_check.setToolTip("显示底层 Scons 编译命令（调试用）")
        display_layout.addWidget(self.show_scons_check)

        layout.addWidget(display_group)

        layout.addStretch()
        return widget

    def _create_python_flags_tab(self) -> QWidget:
        """创建 Python 标志选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        flags_group = QGroupBox("Python 编译标志")
        flags_layout = QVBoxLayout(flags_group)

        # 文档字符串
        self.no_docstrings_check = QCheckBox("移除文档字符串 (-OO)")
        self.no_docstrings_check.setToolTip(
            "移除所有文档字符串，减小可执行文件体积。\n"
            "等效于 Python 的 -OO 标志。"
        )
        flags_layout.addWidget(self.no_docstrings_check)

        # 断言
        self.no_asserts_check = QCheckBox("禁用断言语句 (-O)")
        self.no_asserts_check.setToolTip(
            "禁用所有 assert 语句，提升运行时性能。\n"
            "等效于 Python 的 -O 标志。"
        )
        flags_layout.addWidget(self.no_asserts_check)

        # 警告
        self.no_warnings_check = QCheckBox("禁用运行时警告")
        self.no_warnings_check.setToolTip(
            "禁用 Python 的 warnings 模块输出。"
        )
        flags_layout.addWidget(self.no_warnings_check)

        # 类型注解
        self.no_annotations_check = QCheckBox("移除类型注解")
        self.no_annotations_check.setToolTip(
            "移除函数和变量的类型注解，减小体积。\n"
            "如果程序运行时不需要类型注解信息，可以启用。"
        )
        flags_layout.addWidget(self.no_annotations_check)

        layout.addWidget(flags_group)

        # 说明
        note_label = QLabel(
            "<b>说明：</b><br>"
            "这些标志可以优化编译后的程序：<br>"
            "• 移除文档字符串和类型注解可减小文件体积<br>"
            "• 禁用断言可提升运行时性能<br>"
            "• 建议在生产环境中启用这些优化"
        )
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        layout.addStretch()
        return widget

    def _create_anti_bloat_tab(self) -> QWidget:
        """创建 Anti-bloat 选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 说明
        intro_label = QLabel(
            "<b>Anti-bloat 插件</b>可以排除不必要的依赖，减少编译时间和文件体积。<br>"
            "以下是常见的可以安全排除的开发/测试包："
        )
        intro_label.setWordWrap(True)
        layout.addWidget(intro_label)

        # 预定义排除
        predefined_group = QGroupBox("预定义排除包")
        predefined_layout = QVBoxLayout(predefined_group)

        self.noinclude_pytest_check = QCheckBox("排除 pytest（测试框架）")
        self.noinclude_pytest_check.setToolTip("排除 pytest 及其依赖")
        predefined_layout.addWidget(self.noinclude_pytest_check)

        self.noinclude_setuptools_check = QCheckBox("排除 setuptools（打包工具）")
        self.noinclude_setuptools_check.setToolTip("排除 setuptools 及 pkg_resources")
        predefined_layout.addWidget(self.noinclude_setuptools_check)

        self.noinclude_unittest_check = QCheckBox("排除 unittest（标准测试库）")
        self.noinclude_unittest_check.setToolTip("排除标准库中的 unittest 模块")
        predefined_layout.addWidget(self.noinclude_unittest_check)

        self.noinclude_ipython_check = QCheckBox("排除 IPython（交互式解释器）")
        self.noinclude_ipython_check.setToolTip("排除 IPython 及其大量依赖")
        predefined_layout.addWidget(self.noinclude_ipython_check)

        self.noinclude_dask_check = QCheckBox("排除 dask（分布式计算）")
        self.noinclude_dask_check.setToolTip("排除 dask 并行计算框架")
        predefined_layout.addWidget(self.noinclude_dask_check)

        layout.addWidget(predefined_group)

        # 说明
        note_label = QLabel(
            '<i>提示：如需排除其他模块，请使用主界面"打包选项"中的"排除模块"功能。</i>'
        )
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        layout.addStretch()
        return widget

    def _create_onefile_tab(self) -> QWidget:
        """创建 Onefile 配置选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 临时目录配置
        tempdir_group = QGroupBox("临时目录配置")
        tempdir_layout = QVBoxLayout(tempdir_group)

        tempdir_intro = QLabel(
            "Onefile 模式下，程序会解压到临时目录运行。\n"
            "可以配置临时目录路径以避免 Windows 防火墙每次都询问。"
        )
        tempdir_intro.setWordWrap(True)
        tempdir_layout.addWidget(tempdir_intro)

        self.use_cache_check = QCheckBox("使用缓存目录（推荐）")
        self.use_cache_check.setToolTip(
            "使用用户缓存目录而非临时目录，\n"
            "可以避免每次运行都被防火墙询问。"
        )
        self.use_cache_check.stateChanged.connect(self._on_use_cache_changed)
        tempdir_layout.addWidget(self.use_cache_check)

        tempdir_form = QFormLayout()
        self.tempdir_spec_edit = QLineEdit()
        self.tempdir_spec_edit.setPlaceholderText(
            "{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}"
        )
        self.tempdir_spec_edit.setToolTip(
            "可用变量：\n"
            "• {TEMP} - 临时目录\n"
            "• {CACHE_DIR} - 用户缓存目录\n"
            "• {COMPANY} - 公司名\n"
            "• {PRODUCT} - 产品名\n"
            "• {VERSION} - 版本号\n"
            "• {PID} - 进程 ID\n"
            "• {TIME} - 时间戳"
        )
        tempdir_form.addRow("临时目录规范:", self.tempdir_spec_edit)
        tempdir_layout.addLayout(tempdir_form)

        layout.addWidget(tempdir_group)

        layout.addStretch()
        return widget

    def _create_advanced_tab(self) -> QWidget:
        """创建高级选项卡"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 部署模式
        deploy_group = QGroupBox("部署模式")
        deploy_layout = QVBoxLayout(deploy_group)

        self.deployment_check = QCheckBox("启用部署模式")
        self.deployment_check.setToolTip(
            "部署模式会移除所有调试助手和安全检查，\n"
            "减小文件体积。仅在最终发布时启用。"
        )
        deploy_layout.addWidget(self.deployment_check)

        deploy_note = QLabel(
            "<i>警告：部署模式会移除 fork bomb 检测等安全功能，\n"
            "建议在开发阶段保持禁用。</i>"
        )
        deploy_note.setWordWrap(True)
        deploy_layout.addWidget(deploy_note)

        layout.addWidget(deploy_group)

        # 编译报告
        report_group = QGroupBox("编译报告")
        report_layout = QVBoxLayout(report_group)

        self.generate_report_check = QCheckBox("生成编译报告 (XML)")
        self.generate_report_check.setToolTip(
            "生成详细的 XML 编译报告，\n"
            "包含模块使用、时间统计等信息，便于调试。"
        )
        self.generate_report_check.stateChanged.connect(self._on_generate_report_changed)
        report_layout.addWidget(self.generate_report_check)

        report_form = QFormLayout()
        self.report_path_edit = QLineEdit()
        self.report_path_edit.setPlaceholderText("compilation-report.xml")
        self.report_path_edit.setEnabled(False)
        report_form.addRow("报告文件名:", self.report_path_edit)
        report_layout.addLayout(report_form)

        layout.addWidget(report_group)

        # 缓存配置
        cache_group = QGroupBox("缓存配置")
        cache_layout = QVBoxLayout(cache_group)

        cache_form = QFormLayout()
        self.custom_cache_edit = QLineEdit()
        self.custom_cache_edit.setPlaceholderText("留空使用默认缓存目录")
        self.custom_cache_edit.setToolTip(
            "自定义 Nuitka 缓存目录。\n"
            "对于 CI/CD 环境，可以指定持久化目录加速构建。"
        )
        cache_form.addRow("缓存目录:", self.custom_cache_edit)
        cache_layout.addLayout(cache_form)

        self.clean_cache_after_build_check = QCheckBox("打包完成后清理编译缓存（推荐）")
        self.clean_cache_after_build_check.setToolTip(
            "打包成功后自动清理 Nuitka 的全局编译缓存目录，\n"
            "包括 clcache、ccache、bytecode、dll_dependencies 等。\n\n"
            "这些缓存默认存储在系统盘：\n"
            "  C:\\Users\\<用户名>\\AppData\\Local\\Nuitka\\Nuitka\\Cache\n\n"
            "长期多次打包会导致缓存持续增长占满 C 盘，\n"
            "启用此选项可在每次打包完成后自动释放空间。\n\n"
            "注意：清理缓存后下次打包会稍慢（需重新编译），\n"
            "但可以避免 C 盘空间不足的问题。"
        )
        cache_layout.addWidget(self.clean_cache_after_build_check)

        layout.addWidget(cache_group)

        # 用户包配置
        user_config_group = QGroupBox("用户包配置")
        user_config_layout = QVBoxLayout(user_config_group)

        user_config_note = QLabel(
            "可以提供自定义的 Nuitka 包配置文件 (YAML 格式)，\n"
            "用于处理特殊的第三方包需求。"
        )
        user_config_note.setWordWrap(True)
        user_config_layout.addWidget(user_config_note)

        config_form = QFormLayout()
        self.user_package_config_edit = QLineEdit()
        self.user_package_config_edit.setPlaceholderText(
            "my.nuitka-package.config.yml"
        )
        config_form.addRow("配置文件:", self.user_package_config_edit)
        user_config_layout.addLayout(config_form)

        layout.addWidget(user_config_group)

        # 自动下载
        download_group = QGroupBox("自动下载")
        download_layout = QVBoxLayout(download_group)

        self.assume_yes_check = QCheckBox("自动确认下载 (推荐)")
        self.assume_yes_check.setToolTip(
            "自动确认下载 Nuitka 所需的依赖工具，\n"
            "如 ccache、依赖分析工具等。"
        )
        download_layout.addWidget(self.assume_yes_check)

        layout.addWidget(download_group)

        layout.addStretch()
        return widget

    def _on_use_cache_changed(self, state: int) -> None:
        """当使用缓存目录选项改变时"""
        is_checked = state == Qt.CheckState.Checked.value
        if is_checked:
            self.tempdir_spec_edit.setText("{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}")
        self.tempdir_spec_edit.setEnabled(not is_checked)

    def _on_generate_report_changed(self, state: int) -> None:
        """当生成报告选项改变时"""
        self.report_path_edit.setEnabled(state == Qt.CheckState.Checked.value)

    def _load_options(self) -> None:
        """从选项字典加载到 UI"""
        # 编译优化
        self.lto_check.setChecked(self.options.get("lto", True))
        self.low_memory_check.setChecked(self.options.get("low_memory", False))
        jobs = self.options.get("jobs")
        self.jobs_spin.setValue(jobs if jobs is not None else 0)

        # 显示选项
        self.show_progress_check.setChecked(self.options.get("show_progress", True))
        self.show_memory_check.setChecked(self.options.get("show_memory", True))
        self.show_scons_check.setChecked(self.options.get("show_scons", False))

        # Python 标志
        self.no_docstrings_check.setChecked(self.options.get("python_no_docstrings", True))
        self.no_asserts_check.setChecked(self.options.get("python_no_asserts", True))
        self.no_warnings_check.setChecked(self.options.get("python_no_warnings", True))
        self.no_annotations_check.setChecked(self.options.get("python_no_annotations", True))

        # Anti-bloat
        self.noinclude_pytest_check.setChecked(self.options.get("noinclude_pytest", True))
        self.noinclude_setuptools_check.setChecked(self.options.get("noinclude_setuptools", True))
        self.noinclude_unittest_check.setChecked(self.options.get("noinclude_unittest", True))
        self.noinclude_ipython_check.setChecked(self.options.get("noinclude_ipython", True))
        self.noinclude_dask_check.setChecked(self.options.get("noinclude_dask", True))

        # 部署模式
        self.deployment_check.setChecked(self.options.get("deployment", True))

        # Onefile 配置
        use_cache = self.options.get("onefile_use_cache", True)
        self.use_cache_check.setChecked(use_cache)
        self.tempdir_spec_edit.setText(self.options.get("onefile_tempdir_spec", "{CACHE_DIR}/{COMPANY}/{PRODUCT}/{VERSION}"))
        self.tempdir_spec_edit.setEnabled(not use_cache)

        # 编译报告
        generate_report = self.options.get("generate_report", False)
        self.generate_report_check.setChecked(generate_report)
        self.report_path_edit.setText(self.options.get("report_path", ""))
        self.report_path_edit.setEnabled(generate_report)

        # 缓存配置
        self.custom_cache_edit.setText(self.options.get("custom_cache_dir", ""))
        self.clean_cache_after_build_check.setChecked(
            self.options.get("clean_cache_after_build", True)
        )

        # 用户包配置
        self.user_package_config_edit.setText(self.options.get("user_package_config", ""))

        # 自动下载
        self.assume_yes_check.setChecked(self.options.get("assume_yes_downloads", True))

    def _save_options(self) -> None:
        """从 UI 保存到选项字典"""
        # 编译优化
        self.options["lto"] = self.lto_check.isChecked()
        self.options["low_memory"] = self.low_memory_check.isChecked()
        jobs = self.jobs_spin.value()
        self.options["jobs"] = jobs if jobs > 0 else None

        # 显示选项
        self.options["show_progress"] = self.show_progress_check.isChecked()
        self.options["show_memory"] = self.show_memory_check.isChecked()
        self.options["show_scons"] = self.show_scons_check.isChecked()

        # Python 标志
        self.options["python_no_docstrings"] = self.no_docstrings_check.isChecked()
        self.options["python_no_asserts"] = self.no_asserts_check.isChecked()
        self.options["python_no_warnings"] = self.no_warnings_check.isChecked()
        self.options["python_no_annotations"] = self.no_annotations_check.isChecked()

        # Anti-bloat
        self.options["noinclude_pytest"] = self.noinclude_pytest_check.isChecked()
        self.options["noinclude_setuptools"] = self.noinclude_setuptools_check.isChecked()
        self.options["noinclude_unittest"] = self.noinclude_unittest_check.isChecked()
        self.options["noinclude_ipython"] = self.noinclude_ipython_check.isChecked()
        self.options["noinclude_dask"] = self.noinclude_dask_check.isChecked()

        # 部署模式
        self.options["deployment"] = self.deployment_check.isChecked()

        # Onefile 配置
        self.options["onefile_use_cache"] = self.use_cache_check.isChecked()
        self.options["onefile_tempdir_spec"] = self.tempdir_spec_edit.text().strip()

        # 编译报告
        self.options["generate_report"] = self.generate_report_check.isChecked()
        self.options["report_path"] = self.report_path_edit.text().strip()

        # 缓存配置
        self.options["custom_cache_dir"] = self.custom_cache_edit.text().strip()
        self.options["clean_cache_after_build"] = self.clean_cache_after_build_check.isChecked()

        # 用户包配置
        self.options["user_package_config"] = self.user_package_config_edit.text().strip()

        # 自动下载
        self.options["assume_yes_downloads"] = self.assume_yes_check.isChecked()

    def _reset_to_defaults(self) -> None:
        """重置为默认选项"""
        self.options = self._get_default_options()
        self._load_options()

    def accept(self) -> None:
        """确认对话框"""
        self._save_options()
        super().accept()

    def get_options(self) -> Dict[str, Any]:
        """获取当前选项"""
        return self.options.copy()

    def get_nuitka_args(self) -> list:
        """
        根据选项生成 Nuitka 命令行参数

        Returns:
            Nuitka 命令行参数列表
        """
        args = []

        # 编译优化
        if self.options.get("lto", True):
            args.append("--lto=yes")
        else:
            args.append("--lto=no")

        if self.options.get("low_memory", False):
            args.append("--low-memory")

        jobs = self.options.get("jobs")
        if jobs is not None and jobs > 0:
            args.append(f"--jobs={jobs}")

        # 显示选项
        if self.options.get("show_progress", True):
            args.append("--show-progress")
        if self.options.get("show_memory", True):
            args.append("--show-memory")
        if self.options.get("show_scons", False):
            args.append("--show-scons")

        # Python 标志
        if self.options.get("python_no_docstrings", True):
            args.append("--python-flag=no_docstrings")
        if self.options.get("python_no_asserts", True):
            args.append("--python-flag=no_asserts")
        if self.options.get("python_no_warnings", False):
            args.append("--python-flag=no_warnings")
        if self.options.get("python_no_annotations", False):
            args.append("--python-flag=no_annotations")

        # Anti-bloat
        if self.options.get("noinclude_pytest", True):
            args.append("--noinclude-pytest-mode=nofollow")
        if self.options.get("noinclude_setuptools", True):
            args.append("--noinclude-setuptools-mode=nofollow")
        if self.options.get("noinclude_unittest", True):
            args.append("--noinclude-unittest-mode=nofollow")
        if self.options.get("noinclude_ipython", True):
            args.append("--noinclude-IPython-mode=nofollow")
        if self.options.get("noinclude_dask", True):
            args.append("--noinclude-dask-mode=nofollow")

        # 部署模式
        if self.options.get("deployment", False):
            args.append("--deployment")

        # Onefile 配置
        tempdir_spec = self.options.get("onefile_tempdir_spec", "")
        if tempdir_spec:
            args.append(f"--onefile-tempdir-spec={tempdir_spec}")

        # 编译报告
        if self.options.get("generate_report", False):
            report_path = self.options.get("report_path", "") or "compilation-report.xml"
            args.append(f"--report={report_path}")

        # 用户包配置
        user_config = self.options.get("user_package_config", "")
        if user_config:
            args.append(f"--user-package-configuration-file={user_config}")

        # 自动下载
        if self.options.get("assume_yes_downloads", True):
            args.append("--assume-yes-for-downloads")

        return args
