"""
PyInstaller 打包脚本 - 将 WorkBuddy OpenCode 打包为单个 exe
"""

import PyInstaller.__main__
import os
import shutil

# 清理旧的构建文件
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        shutil.rmtree(folder)

# 收集所有数据文件
app_dir = os.path.dirname(os.path.abspath(__file__))

# PyInstaller 参数
params = [
    'app.py',
    '--name=WorkBuddy_OpenCode',
    '--windowed',          # 无控制台窗口
    '--onefile',           # 打包为单个 exe
    '--icon=NONE',         # 无图标（可后续添加）
    '--clean',             # 清理缓存
    '--noconfirm',         # 不确认覆盖
    '--collect-all=PyQt5', # 收集 PyQt5 所有依赖
    '--hidden-import=PyQt5.QtCore',
    '--hidden-import=PyQt5.QtGui',
    '--hidden-import=PyQt5.QtWidgets',
    '--hidden-import=sqlite3',
    '--hidden-import=json',
    '--hidden-import=hashlib',
    '--hidden-import=subprocess',
    '--hidden-import=threading',
    '--hidden-import=datetime',
    '--hidden-import=re',
    '--hidden-import=urllib.request',
    f'--workpath={os.path.join(app_dir, "build")}',
    f'--distpath={os.path.join(app_dir, "dist")}',
    f'--specpath={app_dir}',
]

print("=" * 60)
print("🚀 WorkBuddy OpenCode - EXE 打包工具")
print("=" * 60)
print("\n开始打包...\n")

try:
    PyInstaller.__main__.run(params)
    
    print("\n" + "=" * 60)
    print("✅ 打包完成！")
    print(f"📁 EXE 路径: {os.path.join(app_dir, 'dist', 'WorkBuddy_OpenCode.exe')}")
    print("=" * 60)
    
    # 复制数据库初始化脚本到 dist
    db_init = os.path.join(app_dir, 'init_db.py')
    if os.path.exists(db_init):
        shutil.copy(db_init, os.path.join(app_dir, 'dist', 'init_db.py'))
    
    # 创建 README
    readme_content = """# WorkBuddy OpenCode

一个带有记忆功能的 AI 编程助手桌面应用。

## 功能特性

- 💬 **AI 对话** - 支持接入 GPT/Claude 等 LLM API，也可离线使用本地模式
- 🧠 **持久记忆** - 记住用户的编码偏好、技术栈、项目约定
- 📝 **代码编辑器** - 内置多语言代码编辑器，支持语法高亮
- ⚡ **终端集成** - 内置终端，支持快捷命令一键执行
- 📂 **项目管理** - 打开项目文件夹，自动分析文件结构
- 🎨 **主题切换** - 支持深色/浅色主题
- 🔒 **本地存储** - 所有数据存储在本地 SQLite 数据库

## 使用说明

1. 双击 `WorkBuddy_OpenCode.exe` 启动
2. 在设置中配置 LLM API（可选，不配置也能用本地模式）
3. 开始使用！

## 快捷键

- `Ctrl+N` - 新建对话
- `Ctrl+S` - 保存代码
- `Ctrl+Enter` - 发送消息

## 配置 API

在设置中填入：
- API URL: 如 `https://api.openai.com/v1/chat/completions`
- API Key: 你的密钥
- 模型: 如 `gpt-3.5-turbo`

## 数据文件

- `workbuddy.db` - SQLite 数据库（记忆、对话、代码片段等）
- `config.json` - API 配置文件

## 技术栈

- Python 3.x
- PyQt5 (GUI)
- SQLite (数据存储)
"""
    
    with open(os.path.join(app_dir, 'dist', 'README.txt'), 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("\n📄 README.txt 已创建")
    print("\n🎉 一切就绪！可以将 dist 文件夹分发给用户。")
    
except Exception as e:
    print(f"\n❌ 打包失败: {e}")
    print("\n请确保已安装 PyInstaller:")
    print("  pip install pyinstaller")
    raise
