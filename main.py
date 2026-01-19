"""
Python打包工具 - 主入口

简单易用的Python脚本打包工具，支持PyInstaller和Nuitka两种打包方式。
"""

import os
import sys
from typing import Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow
from version import APP_TITLE


def _find_icon() -> Optional[str]:
    """
    查找应用程序图标路径。
    
    按优先级搜索：PyInstaller临时目录 > exe目录 > 工作目录 > 开发目录
    """
    icon_name = "icon.ico"
    search_paths = []

    if getattr(sys, 'frozen', False):
        # 打包模式
        exe_dir = os.path.dirname(sys.executable)
        meipass = getattr(sys, '_MEIPASS', None)
        
        if meipass:
            search_paths.extend([
                os.path.join(meipass, icon_name),
                os.path.join(meipass, "resources", "icons", icon_name),
            ])
        
        search_paths.extend([
            os.path.join(exe_dir, icon_name),
            os.path.join(exe_dir, "resources", "icons", icon_name),
            os.path.join(os.getcwd(), icon_name),
            os.path.join(os.getcwd(), "resources", "icons", icon_name),
        ])
    else:
        # 开发模式
        project_root = os.path.dirname(os.path.abspath(__file__))
        search_paths.append(os.path.join(project_root, "resources", "icons", icon_name))

    for path in search_paths:
        if os.path.exists(path):
            return path
    return None


def _create_icon(icon_path: Optional[str]) -> Optional[QIcon]:
    """创建QIcon对象，路径无效时返回None"""
    if not icon_path:
        return None
    icon = QIcon(icon_path)
    return icon if not icon.isNull() else None


def main() -> None:
    """主程序入口"""
    try:
        app = QApplication(sys.argv)

        # 设置应用程序图标
        icon = _create_icon(_find_icon())
        if icon:
            app.setWindowIcon(icon)

        # 创建并显示主窗口
        window = MainWindow()
        window.setWindowTitle(APP_TITLE)
        if icon:
            window.setWindowIcon(icon)
        window.show()

        sys.exit(app.exec())

    except KeyboardInterrupt:
        print("\n程序被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"程序发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
