"""
项目级共享常量模块

本模块定义了项目中多处使用的共享常量，避免在多个文件中重复定义。
"""

import sys

# Windows 子进程隐藏控制台窗口标志
# 在 Windows 上运行子进程时使用此标志可以隐藏控制台窗口
# 在非 Windows 平台上为 0（无效果）
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# 跳过扫描的目录集合（用于遍历项目文件时）
SKIP_DIRECTORIES = frozenset({
    '.venv', 'venv', '.env', 'env',  # 虚拟环境
    'build', 'dist', 'output',  # 构建输出
    '__pycache__', '.pytest_cache',  # Python 缓存
    '.git', '.svn', '.hg',  # 版本控制
    'node_modules',  # Node.js
    'site-packages',  # 已安装包
    '.idea', '.vscode', '.zed',  # IDE 配置
    'eggs', '*.egg-info',  # Python 包元数据
})

# 常见的虚拟环境目录名
VENV_DIRECTORY_NAMES = frozenset({'.venv', 'venv', '.env', 'env'})
