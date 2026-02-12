"""
Python打包工具 - 版本信息

统一管理应用程序的版本号和相关元数据信息，方便修改维护。
"""

# 版本号
__version__ = "1.5.3"
VERSION = __version__

# 构建日期（用于显示，不参与Windows文件版本号）
BUILD_DATE = "20260212"

# 完整显示版本（用于UI显示）
DISPLAY_VERSION = f"{__version__}.{BUILD_DATE}"

# 版本号元组，方便比较
VERSION_TUPLE = tuple(int(x) for x in __version__.split("."))

# 应用程序信息
APP_NAME = "Python脚本打包工具"
APP_NAME_EN = "Python Packaging Tool"
APP_NOTICE = "免费软件，禁止贩卖！"
APP_TITLE = f"{APP_NAME} v{DISPLAY_VERSION}  - {APP_NOTICE}"

# 作者信息
AUTHOR = "徽哥"
AUTHOR_EMAIL = "love-left@qq.com"

# 版权信息
COPYRIGHT = f"Copyright © 2026 {AUTHOR}"
DESCRIPTION = "一个简单易用的Python脚本打包工具，支持PyInstaller和Nuitka两种打包方式。"
DESCRIPTION_EN = "A simple and easy-to-use Python script packaging tool, supporting PyInstaller and Nuitka packing methods."

# 自述信息
ABOUT_TEXT = "可有偿提供各种python脚本定制、修改等服务。"

# 项目链接（可选）
PROJECT_URL = ""
ISSUE_URL = ""


def get_version() -> str:
    """获取版本号字符串"""
    return __version__


def get_version_tuple() -> tuple:
    """获取版本号元组"""
    return VERSION_TUPLE


def get_app_info() -> dict:
    """获取应用程序完整信息"""
    return {
        "version": DISPLAY_VERSION,
        "version_tuple": VERSION_TUPLE,
        "app_name": APP_NAME,
        "app_name_en": APP_NAME_EN,
        "app_title": APP_TITLE,
        "author": AUTHOR,
        "author_email": AUTHOR_EMAIL,
        "copyright": COPYRIGHT,
        "description": DESCRIPTION,
        "about_text": ABOUT_TEXT,
    }


def get_about_html() -> str:
    """获取关于对话框的HTML内容"""
    return f"""
<h2>{APP_NAME}</h2>
<p><b>版本：</b>{DISPLAY_VERSION}</p>
<p><b>作者：</b>{AUTHOR}</p>
<p><strong>---------------------------------------------------</strong><br/><br/>{ABOUT_TEXT}<br/><br/><strong>---------------------------------------------------</strong></p>
<p><b>联系邮箱：</b>{AUTHOR_EMAIL}</p>
"""
