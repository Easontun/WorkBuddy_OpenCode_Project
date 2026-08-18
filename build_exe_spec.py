"""
WorkBuddy OpenCode - 精简打包脚本
只收集必要的 Qt 模块，减小体积
"""

import PyInstaller.__main__
import os
import shutil

app_dir = os.path.dirname(os.path.abspath(__file__))
dist_dir = os.path.join(app_dir, 'dist')
build_dir = os.path.join(app_dir, 'build')

# 清理旧文件
for folder in [build_dir, dist_dir]:
    if os.path.exists(folder):
        shutil.rmtree(folder)

# 创建精简的 spec 文件内容
spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import os

app_dir = os.path.dirname(os.path.abspath(SPECPATH))

a = Analysis(
    ['app.py'],
    pathex=[app_dir],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'sqlite3',
        'json',
        'hashlib',
        'subprocess',
        'threading',
        'datetime',
        're',
        'urllib.request',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大型模块
        'matplotlib',
        'numpy',
        'scipy',
        'pandas',
        'PIL',
        'cv2',
        'torch',
        'tensorflow',
        'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtBluetooth',
        'PyQt5.QtDBus',
        'PyQt5.QtDesigner',
        'PyQt5.QtHelp',
        'PyQt5.QtLocation',
        'PyQt5.QtNfc',
        'PyQt5.QtOpenGL',
        'PyQt5.QtQml',
        'PyQt5.QtQuick',
        'PyQt5.QtQuick3D',
        'PyQt5.QtQuickWidgets',
        'PyQt5.QtRemoteObjects',
        'PyQt5.QtSensors',
        'PyQt5.QtSerialPort',
        'PyQt5.QtSql',
        'PyQt5.QtSvg',
        'PyQt5.QtTest',
        'PyQt5.QtTextToSpeech',
        'PyQt5.QtWebChannel',
        'PyQt5.QtWebSockets',
        'PyQt5.QtX11Extras',
        'PyQt5.QtXml',
        'PyQt5.QtXmlPatterns',
        'PyQt5.Qt3D',
        'PyQt5.Qt3DCore',
        'PyQt5.Qt3DExtras',
        'PyQt5.Qt3DInput',
        'PyQt5.Qt3DLogic',
        'PyQt5.Qt3DRender',
        'PyQt5.QtPositioning',
        'PyQt5.QtPrintSupport',
        'PyQt5.QtWebView',
        'PyQt5.QtPdf',
        'PyQt5.QtGamepad',
        'PyQt5.QtDataVisualization',
        'PyQt5.QtCharts',
        'PyQt5.QtUiTools',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='WorkBuddy_OpenCode',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''

# 写入 spec 文件
spec_path = os.path.join(app_dir, 'WorkBuddy_OpenCode.spec')
with open(spec_path, 'w') as f:
    f.write(spec_content)

print("=" * 60)
print("🚀 WorkBuddy OpenCode - EXE 打包工具 (精简版)")
print("=" * 60)
print("\n开始打包...\n")

try:
    PyInstaller.__main__.run([
        spec_path,
        '--clean',
        '--noconfirm',
    ])
    
    exe_path = os.path.join(dist_dir, 'WorkBuddy_OpenCode')
    exe_path_win = os.path.join(dist_dir, 'WorkBuddy_OpenCode.exe')
    
    # 检查输出
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024*1024)
        print(f"\n✅ 打包完成！文件大小: {size_mb:.1f} MB")
        print(f"📁 路径: {exe_path}")
    elif os.path.exists(exe_path_win):
        size_mb = os.path.getsize(exe_path_win) / (1024*1024)
        print(f"\n✅ 打包完成！文件大小: {size_mb:.1f} MB")
        print(f"📁 路径: {exe_path_win}")
    
    # 创建 README
    readme = """============================================
  WorkBuddy OpenCode v1.0.0
  带有记忆功能的 AI 编程助手
============================================

【功能特性】
  💬 AI 对话 - 支持接入 LLM API / 本地模式
  🧠 持久记忆 - 跨会话记住你的偏好
  📝 代码编辑器 - 多语言语法高亮
  ⚡ 终端集成 - 内置命令执行
  📂 项目管理 - 文件结构分析
  🎨 深色/浅色主题
  🔒 本地 SQLite 数据存储

【快捷键】
  Ctrl+N    - 新建对话
  Ctrl+S    - 保存代码
  Ctrl+Enter - 发送消息

【配置 API】
  设置 → 填入 API URL + Key + 模型名
  不配置也能用本地智能模式

【数据文件】
  workbuddy.db - 数据库（记忆/对话/代码片段）
  config.json  - API 配置

【技术栈】
  Python 3.10 + PyQt5 + SQLite
"""
    
    with open(os.path.join(dist_dir, 'README.txt'), 'w', encoding='utf-8') as f:
        f.write(readme)
    
    print("\n📄 README.txt 已创建")
    print("🎉 打包完成！可在 Windows 上运行。")
    
except Exception as e:
    print(f"\n❌ 打包失败: {e}")
    raise
