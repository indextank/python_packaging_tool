"""
隐藏导入管理模块

本模块负责管理和生成 PyInstaller/Nuitka 打包时需要的隐藏导入列表。
隐藏导入是指那些通过动态导入、字符串导入等方式使用的模块，
静态分析无法检测到，但运行时必须包含的模块。

功能：
- 根据检测到的依赖生成隐藏导入列表
- 支持各种常用库的隐藏导入配置
- 支持 GUI 框架的隐藏导入
- 支持未配置库的通用策略
"""

from typing import Callable, Dict, List, Optional, Set

from core.analyzer_constants import CONFIGURED_LIBRARIES


class HiddenImportsManager:
    """隐藏导入管理器"""

    # PyPI 包名到导入名的映射
    PACKAGE_TO_MODULE_MAPPING: Dict[str, str] = {
        'dnspython': 'dns',
        'pillow': 'PIL',
        'beautifulsoup4': 'bs4',
        'pyyaml': 'yaml',
        'python-dateutil': 'dateutil',
        'opencv-python': 'cv2',
        'opencv-contrib-python': 'cv2',
        'scikit-learn': 'sklearn',
        'scikit-image': 'skimage',
    }

    def __init__(self):
        """初始化隐藏导入管理器"""
        self.log: Callable = print
        self._dynamic_imports: Set[str] = set()
        self._auto_collected_modules: Dict[str, List[str]] = {}
        self._unconfigured_libraries: Set[str] = set()

    def set_log_callback(self, callback: Callable) -> None:
        """设置日志回调函数"""
        self.log = callback

    def set_dynamic_imports(self, imports: Set[str]) -> None:
        """设置动态追踪到的导入"""
        self._dynamic_imports = imports

    def set_auto_collected_modules(self, modules: Dict[str, List[str]]) -> None:
        """设置自动收集的子模块"""
        self._auto_collected_modules = modules

    def get_unconfigured_libraries(self) -> Set[str]:
        """获取未配置的库列表"""
        return self._unconfigured_libraries.copy()

    def get_hidden_imports(
        self,
        dependencies: Set[str],
        primary_qt_framework: Optional[str] = None,
        is_real_package_func: Optional[Callable[[str], bool]] = None,
        is_stdlib_func: Optional[Callable[[str], bool]] = None,
    ) -> List[str]:
        """
        获取可能需要的隐藏导入

        Args:
            dependencies: 依赖包集合
            primary_qt_framework: 主要使用的 Qt 框架
            is_real_package_func: 检测模块是否是包的函数
            is_stdlib_func: 检测模块是否是标准库的函数

        Returns:
            隐藏导入列表
        """
        hidden: List[str] = []

        # ========== Qt 框架 ==========
        hidden.extend(self._get_qt_hidden_imports(dependencies, primary_qt_framework))

        # ========== PySimpleGUI ==========
        hidden.extend(self._get_pysimplegui_hidden_imports(dependencies))

        # ========== Kivy ==========
        hidden.extend(self._get_kivy_hidden_imports(dependencies))

        # ========== Flet ==========
        hidden.extend(self._get_flet_hidden_imports(dependencies))

        # ========== DearPyGui ==========
        hidden.extend(self._get_dearpygui_hidden_imports(dependencies))

        # ========== CustomTkinter ==========
        hidden.extend(self._get_customtkinter_hidden_imports(dependencies))

        # ========== Eel ==========
        hidden.extend(self._get_eel_hidden_imports(dependencies))

        # ========== Toga ==========
        hidden.extend(self._get_toga_hidden_imports(dependencies))

        # ========== Textual ==========
        hidden.extend(self._get_textual_hidden_imports(dependencies))

        # ========== PyForms ==========
        hidden.extend(self._get_pyforms_hidden_imports(dependencies))

        # ========== wxPython ==========
        hidden.extend(self._get_wx_hidden_imports(dependencies))

        # ========== 其他 GUI 框架 ==========
        hidden.extend(self._get_other_gui_hidden_imports(dependencies))

        # ========== 常用库 ==========
        hidden.extend(self._get_common_libs_hidden_imports(dependencies))

        # ========== Web 框架 ==========
        hidden.extend(self._get_web_frameworks_hidden_imports(dependencies))

        # ========== 数据库 ==========
        hidden.extend(self._get_database_hidden_imports(dependencies))

        # ========== 数据科学 ==========
        hidden.extend(self._get_data_science_hidden_imports(dependencies))

        # ========== 机器学习 ==========
        hidden.extend(self._get_ml_hidden_imports(dependencies))

        # ========== 爬虫/自动化 ==========
        hidden.extend(self._get_automation_hidden_imports(dependencies))

        # ========== 办公文档 ==========
        hidden.extend(self._get_office_hidden_imports(dependencies))

        # ========== 任务调度 ==========
        hidden.extend(self._get_scheduler_hidden_imports(dependencies))

        # ========== 加密 ==========
        hidden.extend(self._get_crypto_hidden_imports(dependencies))

        # ========== 实用工具 ==========
        hidden.extend(self._get_utility_hidden_imports(dependencies))

        # ========== 游戏/多媒体 ==========
        hidden.extend(self._get_multimedia_hidden_imports(dependencies))

        # ========== 系统交互 ==========
        hidden.extend(self._get_system_hidden_imports(dependencies))

        # ========== 第一层：动态追踪到的导入 ==========
        if self._dynamic_imports:
            self.log(f"\n添加动态追踪到的 {len(self._dynamic_imports)} 个导入...")
            hidden.extend(list(self._dynamic_imports))

        # ========== 第二层：通用库自动支持 ==========
        hidden.extend(self._get_unconfigured_libs_hidden_imports(
            dependencies, hidden, is_real_package_func, is_stdlib_func
        ))

        # 去重
        return list(set(hidden))

    def _get_qt_hidden_imports(
        self, dependencies: Set[str], primary_qt: Optional[str]
    ) -> List[str]:
        """获取 Qt 框架的隐藏导入"""
        hidden = []

        # 如果未检测主要框架，从依赖中选择一个（按优先级）
        if not primary_qt:
            for qt in ["PyQt6", "PySide6", "PyQt5", "PySide2"]:
                if qt in dependencies:
                    primary_qt = qt
                    break

        # PyQt6相关
        if primary_qt == "PyQt6":
            hidden.extend([
                "PyQt6.QtCore",
                "PyQt6.QtGui",
                "PyQt6.QtWidgets",
                "PyQt6.sip",
            ])

        # PyQt5相关
        elif primary_qt == "PyQt5":
            hidden.extend([
                "PyQt5.QtCore",
                "PyQt5.QtGui",
                "PyQt5.QtWidgets",
                "PyQt5.sip",
            ])

        # PySide6相关
        elif primary_qt == "PySide6":
            hidden.extend([
                "PySide6.QtCore",
                "PySide6.QtGui",
                "PySide6.QtWidgets",
                "shiboken6",
            ])

        # PySide2相关
        elif primary_qt == "PySide2":
            hidden.extend([
                "PySide2.QtCore",
                "PySide2.QtGui",
                "PySide2.QtWidgets",
                "shiboken2",
            ])

        return hidden

    def _get_pysimplegui_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 PySimpleGUI 的隐藏导入"""
        hidden = []

        if "PySimpleGUI" in dependencies or "pysimplegui" in dependencies:
            hidden.extend([
                "PySimpleGUI",
                "tkinter",
                "tkinter.ttk",
                "tkinter.filedialog",
                "tkinter.messagebox",
                "tkinter.colorchooser",
                "tkinter.font",
            ])

        if "PySimpleGUIQt" in dependencies:
            hidden.extend([
                "PySimpleGUIQt",
                "PyQt5.QtCore",
                "PyQt5.QtGui",
                "PyQt5.QtWidgets",
            ])

        if "PySimpleGUIWx" in dependencies:
            hidden.extend([
                "PySimpleGUIWx",
                "wx",
                "wx.adv",
                "wx.lib",
            ])

        return hidden

    def _get_kivy_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 Kivy 的隐藏导入"""
        hidden = []

        if "kivy" in dependencies:
            hidden.extend([
                "kivy",
                "kivy.app",
                "kivy.uix",
                "kivy.uix.widget",
                "kivy.uix.label",
                "kivy.uix.button",
                "kivy.uix.boxlayout",
                "kivy.uix.gridlayout",
                "kivy.uix.floatlayout",
                "kivy.uix.anchorlayout",
                "kivy.uix.relativelayout",
                "kivy.uix.stacklayout",
                "kivy.uix.scrollview",
                "kivy.uix.textinput",
                "kivy.uix.image",
                "kivy.uix.popup",
                "kivy.uix.screenmanager",
                "kivy.uix.spinner",
                "kivy.uix.slider",
                "kivy.uix.switch",
                "kivy.uix.checkbox",
                "kivy.uix.progressbar",
                "kivy.uix.dropdown",
                "kivy.uix.filechooser",
                "kivy.uix.tabbedpanel",
                "kivy.uix.accordion",
                "kivy.uix.carousel",
                "kivy.uix.video",
                "kivy.uix.camera",
                "kivy.uix.recycleview",
                "kivy.core",
                "kivy.core.window",
                "kivy.core.text",
                "kivy.core.image",
                "kivy.core.audio",
                "kivy.core.video",
                "kivy.core.clipboard",
                "kivy.graphics",
                "kivy.graphics.texture",
                "kivy.graphics.vertex_instructions",
                "kivy.graphics.context_instructions",
                "kivy.graphics.fbo",
                "kivy.graphics.shader",
                "kivy.graphics.stencil_instructions",
                "kivy.graphics.svg",
                "kivy.graphics.cgl",
                "kivy.graphics.opengl",
                "kivy.graphics.transformation",
                "kivy.lang",
                "kivy.lang.builder",
                "kivy.lang.parser",
                "kivy.properties",
                "kivy.clock",
                "kivy.base",
                "kivy.config",
                "kivy.logger",
                "kivy.event",
                "kivy.factory",
                "kivy.input",
                "kivy.input.providers",
                "kivy.input.providers.wm_touch",
                "kivy.input.providers.wm_pen",
                "kivy.input.providers.mouse",
                "kivy.animation",
                "kivy.atlas",
                "kivy.cache",
                "kivy.metrics",
                "kivy.modules",
                "kivy.network",
                "kivy.parser",
                "kivy.resources",
                "kivy.storage",
                "kivy.utils",
                "kivy.vector",
                "kivy.weakmethod",
                "kivy_deps.sdl2",
                "kivy_deps.glew",
                "kivy_deps.angle",
                "kivy_deps.gstreamer",
                "PIL",
                "PIL.Image",
                "docutils",
                "pygments",
            ])

        return hidden

    def _get_flet_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 Flet 的隐藏导入"""
        hidden = []

        if "flet" in dependencies:
            hidden.extend([
                "flet",
                "flet.flet",
                "flet_core",
                "flet_runtime",
                "flet.fastapi",
                "flet.utils",
                "flet.version",
                "flet.canvas",
                "flet.matplotlib_chart",
                "flet.plotly_chart",
                "httpx",
                "websockets",
                "watchdog",
                "oauthlib",
                "repath",
                "cookiecutter",
                "copier",
            ])

        return hidden

    def _get_dearpygui_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 DearPyGui 的隐藏导入"""
        hidden = []

        if "dearpygui" in dependencies or "DearPyGui" in dependencies:
            hidden.extend([
                "dearpygui",
                "dearpygui.dearpygui",
                "dearpygui.demo",
                "dearpygui._dearpygui",
            ])

        return hidden

    def _get_customtkinter_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 CustomTkinter 的隐藏导入"""
        hidden = []

        if "customtkinter" in dependencies:
            hidden.extend([
                "customtkinter",
                "customtkinter.windows",
                "customtkinter.windows.widgets",
                "customtkinter.windows.ctk_tk",
                "customtkinter.windows.ctk_toplevel",
                "darkdetect",
                "tkinter",
                "tkinter.ttk",
                "tkinter.filedialog",
                "tkinter.messagebox",
                "tkinter.colorchooser",
                "tkinter.font",
                "PIL",
                "PIL.Image",
                "PIL.ImageTk",
            ])

        return hidden

    def _get_eel_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 Eel 的隐藏导入"""
        hidden = []

        if "eel" in dependencies:
            hidden.extend([
                "eel",
                "bottle",
                "bottle_websocket",
                "gevent",
                "gevent.ssl",
                "gevent._ssl3",
                "gevent.libuv",
                "geventwebsocket",
                "geventwebsocket.handler",
                "geventwebsocket.websocket",
                "whichcraft",
                "pyparsing",
            ])

        return hidden

    def _get_toga_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 Toga 的隐藏导入"""
        hidden = []

        if "toga" in dependencies:
            hidden.extend([
                "toga",
                "toga.app",
                "toga.window",
                "toga.widgets",
                "toga.handlers",
                "toga.icons",
                "toga.images",
                "toga.fonts",
                "toga.colors",
                "toga.keys",
                "toga.platform",
                "toga_winforms",
                "toga_winforms.app",
                "toga_winforms.window",
                "toga_winforms.widgets",
                "System",
                "System.Windows",
                "System.Windows.Forms",
                "System.Drawing",
                "clr",
                "pythonnet",
            ])

        return hidden

    def _get_textual_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 Textual 的隐藏导入"""
        hidden = []

        if "textual" in dependencies:
            hidden.extend([
                "textual",
                "textual.app",
                "textual.widgets",
                "textual.containers",
                "textual.screen",
                "textual.binding",
                "textual.css",
                "textual.dom",
                "textual.driver",
                "textual.events",
                "textual.geometry",
                "textual.keys",
                "textual.message",
                "textual.reactive",
                "textual.timer",
                "textual.worker",
                "rich",
                "rich.console",
                "rich.text",
                "rich.panel",
                "rich.table",
                "rich.syntax",
                "rich.markdown",
                "rich.progress",
                "rich.traceback",
                "rich.logging",
            ])

        return hidden

    def _get_pyforms_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 PyForms 的隐藏导入"""
        hidden = []

        if "pyforms" in dependencies:
            hidden.extend([
                "pyforms",
                "pyforms.gui",
                "pyforms.gui.controls",
                "pyforms_gui",
                "pyforms_gui.controls",
                "AnyQt",
                "PyQt5.QtCore",
                "PyQt5.QtGui",
                "PyQt5.QtWidgets",
            ])

        return hidden

    def _get_wx_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 wxPython 的隐藏导入"""
        hidden = []

        if "wx" in dependencies or "wxPython" in dependencies:
            hidden.extend([
                "wx",
                "wx.adv",
                "wx.lib",
                "wx.lib.agw",
                "wx.lib.buttons",
                "wx.lib.colourdb",
                "wx.lib.embeddedimage",
                "wx.lib.expando",
                "wx.lib.fancytext",
                "wx.lib.floatcanvas",
                "wx.lib.imagebrowser",
                "wx.lib.imageutils",
                "wx.lib.intctrl",
                "wx.lib.masked",
                "wx.lib.mixins",
                "wx.lib.newevent",
                "wx.lib.platebtn",
                "wx.lib.plot",
                "wx.lib.pubsub",
                "wx.lib.scrolledpanel",
                "wx.lib.sized_controls",
                "wx.lib.statbmp",
                "wx.lib.stattext",
                "wx.lib.wordwrap",
                "wx.html",
                "wx.html2",
                "wx.xml",
                "wx.xrc",
                "wx.richtext",
                "wx.stc",
                "wx.grid",
                "wx.dataview",
                "wx.propgrid",
                "wx.ribbon",
                "wx.aui",
                "wx.glcanvas",
                "wx.media",
            ])

        if "wax" in dependencies:
            hidden.extend([
                "wax",
                "wx",
                "wx.adv",
                "wx.lib",
            ])

        return hidden

    def _get_other_gui_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取其他 GUI 框架的隐藏导入"""
        hidden = []

        # PyGUI
        if "GUI" in dependencies or "pygui" in dependencies:
            hidden.extend([
                "GUI",
                "GUI.Application",
                "GUI.Window",
                "GUI.View",
                "GUI.Button",
                "GUI.Label",
                "GUI.TextField",
            ])

        # Libavg
        if "libavg" in dependencies:
            hidden.extend([
                "libavg",
                "libavg.app",
                "libavg.avg",
                "libavg.player",
                "libavg.ui",
                "libavg.utils",
            ])

        return hidden

    def _get_common_libs_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取常用库的隐藏导入"""
        hidden = []

        # requests 相关
        if "requests" in dependencies:
            hidden.extend([
                "urllib3",
                "charset_normalizer",
                "certifi",
                "idna",
            ])

        # dns/dnspython 相关
        if "dns" in dependencies or "dnspython" in dependencies:
            hidden.extend([
                "dns",
                "dns.resolver",
                "dns.rdatatype",
                "dns.rdataclass",
                "dns.rdata",
                "dns.rdtypes",
                "dns.rdtypes.ANY",
                "dns.rdtypes.IN",
                "dns.rdtypes.CH",
                "dns.name",
                "dns.message",
                "dns.query",
                "dns.zone",
                "dns.exception",
                "dns.flags",
                "dns.opcode",
                "dns.rcode",
                "dns.rrset",
                "dns.rdataset",
                "dns.node",
                "dns.entropy",
                "dns.inet",
                "dns.ipv4",
                "dns.ipv6",
                "dns.tokenizer",
                "dns.wire",
                "dns.ttl",
                "dns.set",
                "dns.edns",
                "dns.dnssec",
                "dns.tsig",
                "dns.update",
                "dns.version",
                "dns.asyncquery",
                "dns.asyncresolver",
            ])

        # urllib3 相关
        if "urllib3" in dependencies:
            hidden.extend([
                "urllib3",
                "urllib3.util",
                "urllib3.util.ssl_",
                "urllib3.util.retry",
                "urllib3.util.timeout",
                "urllib3.util.url",
                "urllib3.util.response",
                "urllib3.util.request",
                "urllib3.util.connection",
                "urllib3.util.proxy",
                "urllib3.util.wait",
                "urllib3.connection",
                "urllib3.connectionpool",
                "urllib3.poolmanager",
                "urllib3.response",
                "urllib3.exceptions",
                "urllib3.fields",
                "urllib3.filepost",
                "urllib3._collections",
                "urllib3.contrib",
            ])

        # PIL/Pillow 相关
        if "PIL" in dependencies or "Pillow" in dependencies:
            hidden.extend([
                "PIL",
                "PIL.Image",
                "PIL.ImageTk",
                "PIL.ImageDraw",
                "PIL.ImageFont",
                "PIL.ImageFilter",
                "PIL.ImageEnhance",
                "PIL.ImageOps",
                "PIL.ImageGrab",
                "PIL._imaging",
                "PIL._tkinter_finder",
                "PIL.BmpImagePlugin",
                "PIL.GifImagePlugin",
                "PIL.JpegImagePlugin",
                "PIL.PngImagePlugin",
                "PIL.TiffImagePlugin",
                "PIL.WebPImagePlugin",
            ])

        # pillow-simd
        if "pillow-simd" in dependencies:
            hidden.extend([
                "PIL",
                "PIL.Image",
                "PIL._imaging",
            ])

        # OpenCV 相关
        if "cv2" in dependencies:
            hidden.extend([
                "cv2",
                "numpy",
                "numpy.core._multiarray_umath",
            ])

        # imageio
        if "imageio" in dependencies:
            hidden.extend([
                "imageio",
                "imageio.core",
                "imageio.plugins",
            ])

        # PyYAML 相关
        if "yaml" in dependencies or "pyyaml" in dependencies:
            hidden.extend([
                "yaml",
                "yaml.loader",
                "yaml.dumper",
            ])

        # toml 相关
        if "toml" in dependencies or "tomli" in dependencies:
            hidden.extend([
                "toml",
                "tomli",
            ])

        # loguru 相关
        if "loguru" in dependencies:
            hidden.extend([
                "loguru",
                "loguru._logger",
            ])

        # click 相关
        if "click" in dependencies:
            hidden.extend([
                "click",
                "click.core",
                "click.decorators",
                "click.types",
                "click.utils",
            ])

        # typer 相关
        if "typer" in dependencies:
            hidden.extend([
                "typer",
                "typer.main",
                "click",
            ])

        # tqdm 相关
        if "tqdm" in dependencies:
            hidden.extend([
                "tqdm",
                "tqdm.auto",
                "tqdm.std",
                "tqdm.gui",
                "tqdm.asyncio",
            ])

        # colorama 相关
        if "colorama" in dependencies:
            hidden.extend([
                "colorama",
                "colorama.ansi",
                "colorama.win32",
            ])

        # arrow 相关
        if "arrow" in dependencies:
            hidden.extend([
                "arrow",
                "arrow.arrow",
                "arrow.factory",
            ])

        # pendulum 相关
        if "pendulum" in dependencies:
            hidden.extend([
                "pendulum",
                "pendulum.tz",
                "pendulum.parsing",
            ])

        # httpx 相关
        if "httpx" in dependencies:
            hidden.extend([
                "httpx",
                "httpx._client",
                "httpx._models",
                "httpx._transports",
                "h11",
                "h2",
                "httpcore",
            ])

        # websocket-client 相关
        if "websocket" in dependencies or "websocket-client" in dependencies:
            hidden.extend([
                "websocket",
                "websocket._app",
                "websocket._core",
            ])

        # pytz 相关
        if "pytz" in dependencies:
            hidden.extend(["pytz"])

        # dateutil 相关
        if "dateutil" in dependencies or "python-dateutil" in dependencies:
            hidden.extend([
                "dateutil",
                "dateutil.parser",
                "dateutil.tz",
                "dateutil.relativedelta",
            ])

        # attrs 相关
        if "attrs" in dependencies or "attr" in dependencies:
            hidden.extend([
                "attr",
                "attrs",
            ])

        # pydantic 相关
        if "pydantic" in dependencies:
            hidden.extend([
                "pydantic",
                "pydantic.fields",
                "pydantic.main",
                "pydantic.types",
                "pydantic.validators",
                "pydantic.networks",
                "pydantic.color",
            ])

        # marshmallow 相关
        if "marshmallow" in dependencies:
            hidden.extend([
                "marshmallow",
                "marshmallow.fields",
                "marshmallow.validate",
                "marshmallow.decorators",
            ])

        # python-dotenv 相关
        if "dotenv" in dependencies or "python-dotenv" in dependencies:
            hidden.extend([
                "dotenv",
                "dotenv.main",
            ])

        # tenacity 相关
        if "tenacity" in dependencies:
            hidden.extend([
                "tenacity",
                "tenacity.retry",
                "tenacity.stop",
                "tenacity.wait",
            ])

        # retrying 相关
        if "retrying" in dependencies:
            hidden.extend(["retrying"])

        # faker 相关
        if "faker" in dependencies or "Faker" in dependencies:
            hidden.extend([
                "faker",
                "faker.providers",
            ])

        # cachetools 相关
        if "cachetools" in dependencies:
            hidden.extend([
                "cachetools",
                "cachetools.func",
            ])

        # diskcache 相关
        if "diskcache" in dependencies:
            hidden.extend([
                "diskcache",
                "diskcache.core",
            ])

        # joblib 相关
        if "joblib" in dependencies:
            hidden.extend([
                "joblib",
                "joblib.parallel",
                "joblib.memory",
            ])

        # dill 相关
        if "dill" in dependencies:
            hidden.extend([
                "dill",
                "dill._dill",
            ])

        # cloudpickle 相关
        if "cloudpickle" in dependencies:
            hidden.extend([
                "cloudpickle",
                "cloudpickle.cloudpickle",
            ])

        # watchdog 相关
        if "watchdog" in dependencies:
            hidden.extend([
                "watchdog",
                "watchdog.observers",
                "watchdog.events",
            ])

        # python-magic 相关
        if "magic" in dependencies or "python-magic" in dependencies:
            hidden.extend(["magic"])

        # qrcode 相关
        if "qrcode" in dependencies:
            hidden.extend([
                "qrcode",
                "qrcode.image",
                "qrcode.image.svg",
                "qrcode.image.pure",
            ])

        if "pyqrcode" in dependencies:
            hidden.extend(["pyqrcode"])

        # barcode 相关
        if "barcode" in dependencies or "python-barcode" in dependencies:
            hidden.extend([
                "barcode",
                "barcode.writer",
            ])

        # jieba 相关
        if "jieba" in dependencies:
            hidden.extend([
                "jieba",
                "jieba.analyse",
                "jieba.posseg",
            ])

        # markdown 相关
        if "markdown" in dependencies:
            hidden.extend([
                "markdown",
                "markdown.extensions",
                "markdown.preprocessors",
                "markdown.blockprocessors",
                "markdown.treeprocessors",
                "markdown.inlinepatterns",
                "markdown.postprocessors",
            ])

        # mistune 相关
        if "mistune" in dependencies:
            hidden.extend([
                "mistune",
                "mistune.directives",
                "mistune.plugins",
            ])

        return hidden

    def _get_web_frameworks_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取 Web 框架的隐藏导入"""
        hidden = []

        # Flask 相关
        if "flask" in dependencies or "Flask" in dependencies:
            hidden.extend([
                "flask",
                "flask.app",
                "flask.blueprints",
                "flask.ctx",
                "flask.helpers",
                "flask.json",
                "flask.logging",
                "flask.sessions",
                "flask.signals",
                "flask.templating",
                "flask.views",
                "flask.wrappers",
                "werkzeug",
                "werkzeug.serving",
                "werkzeug.middleware",
                "werkzeug.routing",
                "werkzeug.security",
                "werkzeug.utils",
                "jinja2",
                "jinja2.ext",
                "jinja2.loaders",
                "click",
                "itsdangerous",
                "markupsafe",
            ])

        # Django 相关
        if "django" in dependencies or "Django" in dependencies:
            hidden.extend([
                "django",
                "django.apps",
                "django.conf",
                "django.contrib",
                "django.contrib.admin",
                "django.contrib.auth",
                "django.contrib.contenttypes",
                "django.contrib.sessions",
                "django.contrib.messages",
                "django.contrib.staticfiles",
                "django.core",
                "django.core.management",
                "django.core.wsgi",
                "django.db",
                "django.db.models",
                "django.forms",
                "django.http",
                "django.middleware",
                "django.shortcuts",
                "django.template",
                "django.urls",
                "django.utils",
                "django.views",
                "asgiref",
                "sqlparse",
            ])

        # FastAPI 相关
        if "fastapi" in dependencies:
            hidden.extend([
                "fastapi",
                "fastapi.applications",
                "fastapi.routing",
                "fastapi.params",
                "fastapi.dependencies",
                "fastapi.security",
                "fastapi.middleware",
                "fastapi.responses",
                "fastapi.encoders",
                "fastapi.exceptions",
                "starlette",
                "starlette.applications",
                "starlette.routing",
                "starlette.middleware",
                "starlette.responses",
                "starlette.requests",
                "pydantic",
                "pydantic.fields",
                "pydantic.main",
                "pydantic.types",
                "uvicorn",
                "uvicorn.config",
                "uvicorn.main",
            ])

        # aiohttp 相关
        if "aiohttp" in dependencies:
            hidden.extend([
                "aiohttp",
                "aiohttp.client",
                "aiohttp.web",
                "aiohttp.connector",
                "aiohttp.helpers",
                "multidict",
                "yarl",
                "async_timeout",
                "aiosignal",
            ])

        # tornado 相关
        if "tornado" in dependencies:
            hidden.extend([
                "tornado",
                "tornado.web",
                "tornado.ioloop",
                "tornado.httpserver",
                "tornado.websocket",
            ])

        # gradio 相关
        if "gradio" in dependencies:
            hidden.extend([
                "gradio",
                "gradio.interface",
                "gradio.components",
                "gradio.blocks",
                "gradio.routes",
                "gradio.utils",
                "gradio.processing_utils",
                "gradio.external",
            ])

        # streamlit 相关
        if "streamlit" in dependencies:
            hidden.extend([
                "streamlit",
                "streamlit.components",
                "streamlit.elements",
                "streamlit.delta_generator",
                "streamlit.runtime",
                "streamlit.runtime.scriptrunner",
                "streamlit.web",
            ])

        # dash 相关
        if "dash" in dependencies:
            hidden.extend([
                "dash",
                "dash.dependencies",
                "dash.development",
                "dash.exceptions",
                "dash_core_components",
                "dash_html_components",
                "dash_table",
            ])

        # httptools 相关
        if "httptools" in dependencies:
            hidden.extend([
                "httptools",
                "httptools.parser",
            ])

        # uvloop 相关
        if "uvloop" in dependencies:
            hidden.extend(["uvloop"])

        # gunicorn 相关
        if "gunicorn" in dependencies:
            hidden.extend([
                "gunicorn",
                "gunicorn.app",
                "gunicorn.workers",
                "gunicorn.config",
            ])

        return hidden

    def _get_database_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取数据库相关的隐藏导入"""
        hidden = []

        # SQLAlchemy 相关
        if "sqlalchemy" in dependencies or "SQLAlchemy" in dependencies:
            hidden.extend([
                "sqlalchemy",
                "sqlalchemy.engine",
                "sqlalchemy.orm",
                "sqlalchemy.pool",
                "sqlalchemy.sql",
                "sqlalchemy.ext",
                "sqlalchemy.ext.declarative",
                "sqlalchemy.ext.hybrid",
                "sqlalchemy.dialects",
                "sqlalchemy.dialects.mysql",
                "sqlalchemy.dialects.postgresql",
                "sqlalchemy.dialects.sqlite",
                "sqlalchemy.dialects.mssql",
                "sqlalchemy.dialects.oracle",
            ])

        # sqlmodel 相关
        if "sqlmodel" in dependencies:
            hidden.extend([
                "sqlmodel",
                "sqlmodel.main",
                "sqlmodel.engine",
            ])

        # alembic 相关
        if "alembic" in dependencies:
            hidden.extend([
                "alembic",
                "alembic.config",
                "alembic.migration",
                "alembic.operations",
                "alembic.autogenerate",
                "alembic.script",
            ])

        # peewee 相关
        if "peewee" in dependencies:
            hidden.extend([
                "peewee",
                "playhouse",
                "playhouse.migrate",
                "playhouse.pool",
                "playhouse.shortcuts",
            ])

        # Redis 相关
        if "redis" in dependencies:
            hidden.extend([
                "redis",
                "redis.client",
                "redis.connection",
                "redis.exceptions",
                "redis.sentinel",
                "redis.cluster",
            ])

        # pymysql 相关
        if "pymysql" in dependencies:
            hidden.extend([
                "pymysql",
                "pymysql.cursors",
                "pymysql.connections",
            ])

        # psycopg2 相关
        if "psycopg2" in dependencies:
            hidden.extend([
                "psycopg2",
                "psycopg2.extensions",
                "psycopg2.extras",
                "psycopg2._psycopg",
            ])

        # pymongo 相关
        if "pymongo" in dependencies:
            hidden.extend([
                "pymongo",
                "pymongo.collection",
                "pymongo.database",
                "pymongo.cursor",
                "bson",
                "bson.json_util",
            ])

        # motor 相关
        if "motor" in dependencies:
            hidden.extend([
                "motor",
                "motor.motor_asyncio",
                "motor.motor_tornado",
            ])

        # aiomysql 相关
        if "aiomysql" in dependencies:
            hidden.extend([
                "aiomysql",
                "aiomysql.cursors",
                "aiomysql.connection",
                "aiomysql.pool",
            ])

        # aiopg 相关
        if "aiopg" in dependencies:
            hidden.extend([
                "aiopg",
                "aiopg.pool",
                "aiopg.connection",
                "aiopg.cursor",
            ])

        return hidden

    def _get_data_science_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取数据科学相关的隐藏导入"""
        hidden = []

        # pandas 相关
        if "pandas" in dependencies:
            hidden.extend([
                "pandas._libs",
                "pandas._libs.tslibs",
                "pandas._libs.tslibs.np_datetime",
                "pandas._libs.tslibs.nattype",
                "pandas._libs.tslibs.timedeltas",
            ])

        # numpy 相关
        if "numpy" in dependencies:
            hidden.extend([
                "numpy.core._multiarray_umath",
                "numpy.core._dtype_ctypes",
                "numpy.random.common",
                "numpy.random.bounded_integers",
                "numpy.random.entropy",
                "numpy.fft",
                "numpy.polynomial",
                "numpy.random.mtrand",
                "numpy.random.bit_generator",
                "numpy.random.generator",
            ])

        # matplotlib 相关
        if "matplotlib" in dependencies:
            hidden.extend([
                "matplotlib",
                "matplotlib.pyplot",
                "matplotlib.backends",
                "matplotlib.backends.backend_tkagg",
                "matplotlib.backends.backend_agg",
                "matplotlib.backends.backend_qt5agg",
                "matplotlib.backends.backend_qt6agg",
                "matplotlib.figure",
                "matplotlib.axes",
                "mpl_toolkits",
                "mpl_toolkits.mplot3d",
            ])

        # scipy 相关
        if "scipy" in dependencies:
            hidden.extend([
                "scipy",
                "scipy.integrate",
                "scipy.optimize",
                "scipy.stats",
                "scipy.sparse",
                "scipy.linalg",
                "scipy.signal",
                "scipy.interpolate",
                "scipy.ndimage",
                "scipy.spatial",
                "scipy.special",
            ])

        # plotly 相关
        if "plotly" in dependencies:
            hidden.extend([
                "plotly",
                "plotly.graph_objs",
                "plotly.express",
                "plotly.figure_factory",
                "plotly.io",
                "plotly.offline",
                "plotly.tools",
            ])

        # seaborn 相关
        if "seaborn" in dependencies:
            hidden.extend([
                "seaborn",
                "seaborn.matrix",
                "seaborn.distributions",
                "seaborn.categorical",
                "seaborn.regression",
            ])

        # statsmodels 相关
        if "statsmodels" in dependencies:
            hidden.extend([
                "statsmodels",
                "statsmodels.api",
                "statsmodels.formula",
                "statsmodels.tsa",
                "statsmodels.stats",
                "patsy",
            ])

        # bokeh 相关
        if "bokeh" in dependencies:
            hidden.extend([
                "bokeh",
                "bokeh.plotting",
                "bokeh.models",
                "bokeh.layouts",
                "bokeh.io",
                "bokeh.server",
                "bokeh.palettes",
                "bokeh.transform",
            ])

        # altair 相关
        if "altair" in dependencies:
            hidden.extend([
                "altair",
                "altair.vegalite",
                "altair.utils",
            ])

        return hidden

    def _get_ml_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取机器学习相关的隐藏导入"""
        hidden = []

        # scikit-learn 相关
        if "sklearn" in dependencies or "scikit-learn" in dependencies:
            hidden.extend([
                "sklearn",
                "sklearn.ensemble",
                "sklearn.linear_model",
                "sklearn.tree",
                "sklearn.svm",
                "sklearn.neighbors",
                "sklearn.naive_bayes",
                "sklearn.cluster",
                "sklearn.decomposition",
                "sklearn.model_selection",
                "sklearn.preprocessing",
                "sklearn.feature_extraction",
                "sklearn.metrics",
                "sklearn.pipeline",
                "sklearn.utils",
                "joblib",
            ])

        # TensorFlow 相关
        if "tensorflow" in dependencies or "tf" in dependencies:
            hidden.extend([
                "tensorflow",
                "tensorflow.keras",
                "tensorflow.keras.models",
                "tensorflow.keras.layers",
                "tensorflow.keras.optimizers",
                "tensorflow.keras.callbacks",
                "tensorflow.python",
                "tensorflow.python.framework",
                "tensorflow.python.ops",
                "tensorflow.python.util",
                "tensorflow.lite",
                "tensorboard",
            ])

        # PyTorch 相关
        if "torch" in dependencies or "pytorch" in dependencies:
            hidden.extend([
                "torch",
                "torch.nn",
                "torch.nn.functional",
                "torch.optim",
                "torch.utils",
                "torch.utils.data",
                "torch.autograd",
                "torch.cuda",
                "torch.jit",
                "torchvision",
                "torchvision.models",
                "torchvision.transforms",
                "torchvision.datasets",
            ])

        # transformers 相关
        if "transformers" in dependencies:
            hidden.extend([
                "transformers",
                "transformers.models",
                "transformers.pipelines",
                "transformers.tokenization_utils",
                "transformers.modeling_utils",
                "transformers.configuration_utils",
                "tokenizers",
                "huggingface_hub",
            ])

        # xgboost 相关
        if "xgboost" in dependencies:
            hidden.extend([
                "xgboost",
                "xgboost.sklearn",
                "xgboost.plotting",
            ])

        # lightgbm 相关
        if "lightgbm" in dependencies:
            hidden.extend([
                "lightgbm",
                "lightgbm.sklearn",
            ])

        # catboost 相关
        if "catboost" in dependencies:
            hidden.extend(["catboost"])

        # onnxruntime 相关
        if "onnxruntime" in dependencies:
            hidden.extend([
                "onnxruntime",
                "onnxruntime.capi",
                "onnxruntime.capi.onnxruntime_pybind11_state",
            ])

        # pytesseract 相关
        if "pytesseract" in dependencies:
            hidden.extend(["pytesseract"])

        # easyocr 相关
        if "easyocr" in dependencies:
            hidden.extend([
                "easyocr",
                "easyocr.recognition",
                "easyocr.detection",
                "easyocr.utils",
            ])

        return hidden

    def _get_automation_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取爬虫/自动化相关的隐藏导入"""
        hidden = []

        # Selenium 相关
        if "selenium" in dependencies:
            hidden.extend([
                "selenium",
                "selenium.webdriver",
                "selenium.webdriver.common",
                "selenium.webdriver.common.by",
                "selenium.webdriver.common.keys",
                "selenium.webdriver.common.action_chains",
                "selenium.webdriver.common.desired_capabilities",
                "selenium.webdriver.support",
                "selenium.webdriver.support.ui",
                "selenium.webdriver.support.wait",
                "selenium.webdriver.support.expected_conditions",
                "selenium.webdriver.chrome",
                "selenium.webdriver.chrome.service",
                "selenium.webdriver.chrome.options",
                "selenium.webdriver.chrome.webdriver",
                "selenium.webdriver.firefox",
                "selenium.webdriver.firefox.service",
                "selenium.webdriver.firefox.options",
                "selenium.webdriver.firefox.webdriver",
                "selenium.webdriver.edge",
                "selenium.webdriver.edge.service",
                "selenium.webdriver.edge.options",
                "selenium.webdriver.safari",
                "selenium.webdriver.safari.service",
                "selenium.webdriver.remote",
                "selenium.webdriver.remote.webdriver",
                "selenium.webdriver.remote.webelement",
                "selenium.common",
                "selenium.common.exceptions",
                "urllib3",
                "certifi",
            ])

        # Scrapy 相关
        if "scrapy" in dependencies or "Scrapy" in dependencies:
            hidden.extend([
                "scrapy",
                "scrapy.spiders",
                "scrapy.http",
                "scrapy.selector",
                "scrapy.item",
                "scrapy.loader",
                "scrapy.crawler",
                "scrapy.settings",
                "scrapy.exceptions",
                "scrapy.utils",
                "scrapy.pipelines",
                "scrapy.downloadermiddlewares",
                "scrapy.spidermiddlewares",
                "scrapy.extensions",
                "twisted",
                "twisted.internet",
                "twisted.web",
                "w3lib",
                "parsel",
                "lxml",
                "lxml.html",
                "lxml.etree",
            ])

        # Playwright 相关
        if "playwright" in dependencies:
            hidden.extend([
                "playwright",
                "playwright.sync_api",
                "playwright.async_api",
                "playwright._impl",
                "playwright._impl._api_structures",
                "playwright._impl._browser",
                "playwright._impl._page",
                "greenlet",
            ])

        # BeautifulSoup4 相关
        if "bs4" in dependencies or "beautifulsoup4" in dependencies:
            hidden.extend([
                "bs4",
                "bs4.builder",
                "bs4.element",
                "bs4.dammit",
                "soupsieve",
                "lxml",
                "lxml.html",
                "lxml.etree",
                "html5lib",
            ])

        # lxml 相关
        if "lxml" in dependencies:
            hidden.extend([
                "lxml",
                "lxml.html",
                "lxml.etree",
                "lxml.objectify",
                "lxml._elementpath",
                "lxml.builder",
                "lxml.cssselect",
            ])

        # requests-html 相关
        if "requests_html" in dependencies or "requests-html" in dependencies:
            hidden.extend([
                "requests_html",
                "pyppeteer",
                "websockets",
                "pyee",
                "bs4",
                "lxml",
            ])

        # PyAutoGUI 相关
        if "pyautogui" in dependencies:
            hidden.extend([
                "pyautogui",
                "pymsgbox",
                "pytweening",
                "pyscreeze",
                "pygetwindow",
                "pyrect",
                "pyperclip",
                "mouseinfo",
                "PIL",
                "PIL.Image",
                "PIL.ImageGrab",
            ])

        return hidden

    def _get_office_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取办公文档相关的隐藏导入"""
        hidden = []

        # openpyxl 相关
        if "openpyxl" in dependencies:
            hidden.extend([
                "openpyxl",
                "openpyxl.workbook",
                "openpyxl.worksheet",
                "openpyxl.cell",
                "openpyxl.styles",
                "openpyxl.chart",
                "openpyxl.utils",
                "et_xmlfile",
            ])

        # xlrd/xlwt 相关
        if "xlrd" in dependencies:
            hidden.extend([
                "xlrd",
                "xlrd.book",
                "xlrd.sheet",
            ])

        if "xlwt" in dependencies:
            hidden.extend([
                "xlwt",
                "xlwt.Workbook",
                "xlwt.Style",
            ])

        # pdfplumber / PyPDF2 相关
        if "pdfplumber" in dependencies:
            hidden.extend([
                "pdfplumber",
                "pdfplumber.page",
                "pdfplumber.pdf",
                "pdfminer",
                "pdfminer.high_level",
            ])

        if "PyPDF2" in dependencies or "pypdf" in dependencies:
            hidden.extend([
                "PyPDF2",
                "pypdf",
            ])

        # pymupdf (fitz) 相关
        if "fitz" in dependencies or "pymupdf" in dependencies:
            hidden.extend([
                "fitz",
                "fitz.fitz",
            ])

        # reportlab 相关
        if "reportlab" in dependencies:
            hidden.extend([
                "reportlab",
                "reportlab.pdfgen",
                "reportlab.pdfgen.canvas",
                "reportlab.lib",
                "reportlab.lib.pagesizes",
                "reportlab.lib.styles",
                "reportlab.lib.units",
                "reportlab.lib.colors",
                "reportlab.platypus",
                "reportlab.platypus.paragraph",
                "reportlab.platypus.tables",
                "reportlab.platypus.doctemplate",
            ])

        # python-docx 相关
        if "docx" in dependencies or "python-docx" in dependencies:
            hidden.extend([
                "docx",
                "docx.document",
                "docx.oxml",
                "docx.shared",
            ])

        # python-pptx 相关
        if "pptx" in dependencies or "python-pptx" in dependencies:
            hidden.extend([
                "pptx",
                "pptx.presentation",
                "pptx.slide",
                "pptx.shapes",
            ])

        return hidden

    def _get_scheduler_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取任务调度相关的隐藏导入"""
        hidden = []

        # Celery 相关
        if "celery" in dependencies or "Celery" in dependencies:
            hidden.extend([
                "celery",
                "celery.app",
                "celery.worker",
                "celery.task",
                "celery.result",
                "celery.signals",
                "celery.backends",
                "celery.backends.redis",
                "celery.backends.database",
                "celery.concurrency",
                "celery.utils",
                "kombu",
                "kombu.transport",
                "kombu.serialization",
                "billiard",
                "vine",
            ])

        # schedule 相关
        if "schedule" in dependencies:
            hidden.extend(["schedule"])

        # apscheduler 相关
        if "apscheduler" in dependencies:
            hidden.extend([
                "apscheduler",
                "apscheduler.schedulers",
                "apscheduler.triggers",
                "apscheduler.executors",
                "apscheduler.jobstores",
                "tzlocal",
            ])

        return hidden

    def _get_crypto_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取加密相关的隐藏导入"""
        hidden = []

        # cryptography 相关
        if "cryptography" in dependencies:
            hidden.extend([
                "cryptography",
                "cryptography.fernet",
                "cryptography.hazmat",
                "cryptography.hazmat.primitives",
                "cryptography.hazmat.backends",
                "cryptography.x509",
                "_cffi_backend",
            ])

        # pycryptodome 相关
        if "Crypto" in dependencies or "pycryptodome" in dependencies:
            hidden.extend([
                "Crypto",
                "Crypto.Cipher",
                "Crypto.Hash",
                "Crypto.PublicKey",
                "Crypto.Random",
                "Crypto.Signature",
                "Crypto.Util",
            ])

        # paramiko 相关
        if "paramiko" in dependencies:
            hidden.extend([
                "paramiko",
                "paramiko.client",
                "paramiko.transport",
                "paramiko.channel",
                "paramiko.sftp",
                "paramiko.sftp_client",
            ])

        return hidden

    def _get_utility_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取实用工具相关的隐藏导入"""
        hidden = []

        # pytest 相关
        if "pytest" in dependencies:
            hidden.extend([
                "pytest",
                "pytest.unittest",
                "_pytest",
                "_pytest.assertion",
                "_pytest.config",
                "_pytest.fixtures",
                "_pytest.main",
                "_pytest.python",
                "pluggy",
                "py",
            ])

        return hidden

    def _get_multimedia_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取游戏/多媒体相关的隐藏导入"""
        hidden = []

        # pygame 相关
        if "pygame" in dependencies:
            hidden.extend([
                "pygame",
                "pygame.base",
                "pygame.constants",
                "pygame.rect",
                "pygame.rwobject",
                "pygame.surface",
                "pygame.surflock",
                "pygame.color",
                "pygame.bufferproxy",
                "pygame.math",
                "pygame.mixer",
                "pygame.mixer_music",
                "pygame.font",
                "pygame.image",
                "pygame.joystick",
                "pygame.key",
                "pygame.mouse",
                "pygame.cursors",
                "pygame.display",
                "pygame.draw",
                "pygame.event",
                "pygame.pixelcopy",
                "pygame.transform",
                "pygame.sprite",
                "pygame.time",
            ])

        # pyglet 相关
        if "pyglet" in dependencies:
            hidden.extend([
                "pyglet",
                "pyglet.window",
                "pyglet.app",
                "pyglet.graphics",
                "pyglet.image",
                "pyglet.text",
                "pyglet.font",
                "pyglet.media",
                "pyglet.sprite",
                "pyglet.shapes",
                "pyglet.gl",
            ])

        # arcade 相关
        if "arcade" in dependencies:
            hidden.extend([
                "arcade",
                "arcade.window_commands",
                "arcade.draw_commands",
                "arcade.sprite",
                "arcade.sprite_list",
                "arcade.physics_engines",
                "arcade.tilemap",
            ])

        # panda3d 相关
        if "panda3d" in dependencies:
            hidden.extend([
                "panda3d",
                "direct",
                "direct.showbase",
                "direct.task",
                "direct.actor",
                "direct.gui",
            ])

        # ursina 相关
        if "ursina" in dependencies:
            hidden.extend([
                "ursina",
                "ursina.prefabs",
                "ursina.shaders",
            ])

        # sounddevice 相关
        if "sounddevice" in dependencies:
            hidden.extend([
                "sounddevice",
                "_sounddevice",
            ])

        # soundfile 相关
        if "soundfile" in dependencies:
            hidden.extend([
                "soundfile",
                "_soundfile",
            ])

        # pyaudio 相关
        if "pyaudio" in dependencies:
            hidden.extend([
                "pyaudio",
                "_portaudio",
            ])

        # pydub 相关
        if "pydub" in dependencies:
            hidden.extend([
                "pydub",
                "pydub.audio_segment",
                "pydub.effects",
                "pydub.playback",
            ])

        return hidden

    def _get_system_hidden_imports(self, dependencies: Set[str]) -> List[str]:
        """获取系统交互相关的隐藏导入"""
        hidden = []

        # pywin32 相关
        if any(dep in dependencies for dep in ["win32api", "win32com", "win32gui", "win32process", "pywin32"]):
            hidden.extend([
                "win32api",
                "win32con",
                "win32com",
                "win32com.client",
                "win32com.server",
                "win32gui",
                "win32process",
                "win32file",
                "win32event",
                "win32security",
                "win32service",
                "pywintypes",
                "pythoncom",
            ])

        # pythonnet 相关
        if "pythonnet" in dependencies or "clr" in dependencies:
            hidden.extend([
                "clr",
                "Python.Runtime",
            ])

        # comtypes 相关
        if "comtypes" in dependencies:
            hidden.extend([
                "comtypes",
                "comtypes.client",
                "comtypes.automation",
                "comtypes.server",
            ])

        # pynput 相关
        if "pynput" in dependencies:
            hidden.extend([
                "pynput",
                "pynput.keyboard",
                "pynput.mouse",
            ])

        # keyboard 相关
        if "keyboard" in dependencies:
            hidden.extend([
                "keyboard",
                "keyboard._keyboard_event",
            ])

        # mouse 相关
        if "mouse" in dependencies:
            hidden.extend([
                "mouse",
                "mouse._mouse_event",
            ])

        return hidden

    def _get_unconfigured_libs_hidden_imports(
        self,
        dependencies: Set[str],
        hidden: List[str],
        is_real_package_func: Optional[Callable[[str], bool]],
        is_stdlib_func: Optional[Callable[[str], bool]],
    ) -> List[str]:
        """获取未配置库的隐藏导入（通用策略）"""
        result = []

        # 处理未在已知配置列表中的库
        # 使用字典来合并 PyPI 包名和导入名（如 dns 和 dnspython 都映射到 dns）
        unconfigured_modules: Dict[str, str] = {}  # module_name -> original_dep
        seen_modules: Set[str] = set()

        for dep in dependencies:
            # 跳过标准库
            if is_stdlib_func and is_stdlib_func(dep):
                continue

            # 将 PyPI 包名转换为实际模块名（用于后续检查）
            module_name = self.PACKAGE_TO_MODULE_MAPPING.get(dep, dep)

            # 检查是否已配置（检查多种可能的名称形式）
            dep_lower = dep.lower()
            dep_normalized = dep.replace('-', '_').replace('.', '_')
            module_lower = module_name.lower()

            is_configured = (
                dep in CONFIGURED_LIBRARIES or
                dep_lower in {lib.lower() for lib in CONFIGURED_LIBRARIES} or
                dep_normalized in CONFIGURED_LIBRARIES or
                module_name in CONFIGURED_LIBRARIES or
                module_lower in {lib.lower() for lib in CONFIGURED_LIBRARIES}
            )

            # 检查是否已经在hidden中有相关导入
            has_hidden = (
                any(dep_lower in h.lower() for h in hidden) or
                any(module_lower in h.lower() for h in hidden) or
                any(h.lower().startswith(module_lower + '.') for h in hidden) or
                any(h.lower() == module_lower for h in hidden)
            )

            if not is_configured and not has_hidden:
                # 使用模块名作为键，避免重复处理（如 dns 和 dnspython 都映射到 dns）
                if module_name not in seen_modules:
                    seen_modules.add(module_name)
                    unconfigured_modules[module_name] = dep

        # 对未配置的库使用通用策略
        if unconfigured_modules:
            self.log(f"\n检测到 {len(unconfigured_modules)} 个未配置的库，使用通用策略:")
            for module_name, original_dep in sorted(unconfigured_modules.items()):
                self._unconfigured_libraries.add(module_name)

                # 添加库本身（使用正确的模块名）
                result.append(module_name)

                # 检测是否是真正的包还是单文件模块
                is_package = True
                if is_real_package_func and module_name:
                    is_package = is_real_package_func(module_name)

                # 显示名称：如果原始依赖名和模块名不同，显示映射关系
                display_name = f"{original_dep} -> {module_name}" if original_dep != module_name else module_name

                if is_package:
                    self.log(f"  ⚠️ {display_name} (包)")
                    # 如果已经自动收集了子模块，使用它们
                    if module_name in self._auto_collected_modules:
                        submodules = self._auto_collected_modules[module_name]
                        result.extend(submodules)
                        self.log(f"     已使用自动收集的 {len(submodules)} 个子模块")
                    elif original_dep in self._auto_collected_modules:
                        submodules = self._auto_collected_modules[original_dep]
                        result.extend(submodules)
                        self.log(f"     已使用自动收集的 {len(submodules)} 个子模块")
                    else:
                        # 添加常见子模块模式（使用正确的模块名）
                        common_patterns = [
                            f"{module_name}.utils",
                            f"{module_name}.core",
                            f"{module_name}.base",
                            f"{module_name}.main",
                            f"{module_name}.api",
                            f"{module_name}.models",
                            f"{module_name}.config",
                            f"{module_name}.exceptions",
                            f"{module_name}.helpers",
                            f"{module_name}.common",
                            f"{module_name}._internal",
                        ]
                        result.extend(common_patterns)
                        self.log("     使用常见模式策略（11个常见子模块）")
                else:
                    # 单文件模块，不需要添加子模块
                    self.log(f"  ⚠️ {display_name} (单文件模块)")

        return result
