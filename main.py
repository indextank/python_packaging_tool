import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from gui.main_window import MainWindow

# 应用程序版本号 - 在此处统一管理，方便修改
APP_VERSION = "1.3"
APP_TITLE = f"Python脚本打包工具 v{APP_VERSION}"


def _get_icon_path() -> str:
    """获取应用程序图标路径（兼容开发模式和打包后的exe）"""
    # 可能的图标文件名
    icon_filename = "icon.ico"

    if getattr(sys, 'frozen', False):
        # 打包后的exe模式
        exe_dir = os.path.dirname(sys.executable)

        # 按优先级尝试不同路径
        possible_paths = [
            # Nuitka onefile 解压后的路径
            os.path.join(exe_dir, icon_filename),
            os.path.join(exe_dir, "resources", "icons", icon_filename),
            # 当前工作目录
            os.path.join(os.getcwd(), icon_filename),
            os.path.join(os.getcwd(), "resources", "icons", icon_filename),
        ]

        # PyInstaller的_MEIPASS
        meipass = getattr(sys, '_MEIPASS', None)
        if meipass:
            possible_paths.insert(0, os.path.join(meipass, icon_filename))
            possible_paths.insert(1, os.path.join(meipass, "resources", "icons", icon_filename))

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return ""
    else:
        # 开发模式：从项目资源目录加载
        project_root = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(project_root, "resources", "icons", icon_filename)
        if os.path.exists(icon_path):
            return icon_path
        return ""


def main():
    """主程序入口"""
    try:
        # 创建Qt应用程序
        app = QApplication(sys.argv)

        # 设置应用程序图标（用于任务栏和窗口）
        icon_path = _get_icon_path()
        if icon_path and os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            if not app_icon.isNull():
                app.setWindowIcon(app_icon)

        # 创建并显示主窗口
        window = MainWindow()
        window.setWindowTitle(APP_TITLE)

        # 确保窗口也设置了图标
        if icon_path and os.path.exists(icon_path):
            window_icon = QIcon(icon_path)
            if not window_icon.isNull():
                window.setWindowIcon(window_icon)

        window.show()

        # 进入事件循环
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
