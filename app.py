"""
WorkBuddy OpenCode - 带有记忆功能的 AI 编程助手
主应用程序入口
"""

import sys
import os
import json
import sqlite3
import datetime
import hashlib
import threading
import subprocess
import re
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QTabWidget, QFileDialog,
    QMessageBox, QSplitter, QListWidget, QListWidgetItem, QComboBox,
    QCheckBox, QProgressBar, QSystemTrayIcon, QMenu, QAction,
    QGroupBox, QScrollArea, QFrame, QTreeWidget, QTreeWidgetItem,
    QStatusBar, QToolBar, QInputDialog, QDialog, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import (
    QFont, QIcon, QTextCursor, QColor, QPalette, QPixmap,
    QSyntaxHighlighter, QTextCharFormat
)
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

# ==================== 配置 ====================
APP_NAME = "WorkBuddy OpenCode"
APP_VERSION = "1.0.0"
DB_PATH = os.path.join(os.path.dirname(__file__), "workbuddy.db")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
THEMES = {
    "dark": {
        "bg": "#1e1e2e",
        "fg": "#cdd6f4",
        "accent": "#89b4fa",
        "secondary": "#313244",
        "border": "#45475a",
        "success": "#a6e3a1",
        "warning": "#f9e2af",
        "error": "#f38ba8",
        "code_bg": "#181825",
        "input_bg": "#11111b",
    },
    "light": {
        "bg": "#ffffff",
        "fg": "#2d2d2d",
        "accent": "#0066cc",
        "secondary": "#f0f0f0",
        "border": "#d0d0d0",
        "success": "#28a745",
        "warning": "#ffc107",
        "error": "#dc3545",
        "code_bg": "#f8f9fa",
        "input_bg": "#f5f5f5",
    }
}

# ==================== 数据库管理 ====================
class Database:
    """管理记忆、对话历史、代码片段等数据的 SQLite 数据库"""
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.init_db()
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # 对话历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 消息表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # 记忆表（长期记忆）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                importance INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 代码片段表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS code_snippets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                language TEXT,
                code TEXT NOT NULL,
                tags TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 项目上下文表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_path TEXT UNIQUE,
                project_name TEXT,
                file_structure TEXT,
                last_opened TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        """)
        
        # 快捷命令表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quick_commands (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                command TEXT NOT NULL,
                description TEXT,
                category TEXT DEFAULT 'general'
            )
        """)
        
        # 插入默认快捷命令
        default_commands = [
            ("查看Python版本", "python --version", "检查当前Python版本", "system"),
            ("列出目录", "dir" if os.name == 'nt' else "ls -la", "列出当前目录内容", "system"),
            ("Git状态", "git status", "查看Git仓库状态", "git"),
            ("安装依赖", "pip install -r requirements.txt", "安装Python项目依赖", "python"),
            ("运行测试", "pytest", "运行项目测试", "python"),
            ("代码格式化", "black .", "使用Black格式化Python代码", "python"),
            ("类型检查", "mypy .", "使用Mypy进行类型检查", "python"),
        ]
        
        for cmd in default_commands:
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO quick_commands (name, command, description, category) VALUES (?, ?, ?, ?)",
                    cmd
                )
            except:
                pass
        
        conn.commit()
        conn.close()
    
    # ========== 对话管理 ==========
    def create_conversation(self, title="新对话"):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO conversations (title) VALUES (?)", (title,))
        conv_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return conv_id
    
    def save_message(self, conversation_id, role, content):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content)
        )
        cursor.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()
        conn.close()
    
    def get_conversation_messages(self, conversation_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (conversation_id,)
        )
        messages = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return messages
    
    def get_all_conversations(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        )
        conversations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return conversations
    
    def delete_conversation(self, conversation_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        conn.commit()
        conn.close()
    
    # ========== 记忆管理 ==========
    def save_memory(self, key, value, category='general', importance=1):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO memories (key, value, category, importance, updated_at) 
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (key, value, category, importance)
        )
        conn.commit()
        conn.close()
    
    def get_memory(self, key):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM memories WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row['value'] if row else None
    
    def get_all_memories(self, category=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if category:
            cursor.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY importance DESC, updated_at DESC",
                (category,)
            )
        else:
            cursor.execute("SELECT * FROM memories ORDER BY importance DESC, updated_at DESC")
        memories = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return memories
    
    def search_memories(self, query):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM memories WHERE key LIKE ? OR value LIKE ? ORDER BY importance DESC",
            (f"%{query}%", f"%{query}%")
        )
        memories = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return memories
    
    def delete_memory(self, key):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE key = ?", (key,))
        conn.commit()
        conn.close()
    
    # ========== 代码片段管理 ==========
    def save_snippet(self, title, language, code, tags=""):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO code_snippets (title, language, code, tags) VALUES (?, ?, ?, ?)",
            (title, language, code, tags)
        )
        conn.commit()
        conn.close()
    
    def get_snippets(self, language=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if language:
            cursor.execute("SELECT * FROM code_snippets WHERE language = ? ORDER BY created_at DESC", (language,))
        else:
            cursor.execute("SELECT * FROM code_snippets ORDER BY created_at DESC")
        snippets = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return snippets
    
    # ========== 项目上下文管理 ==========
    def save_project_context(self, project_path, project_name, file_structure, notes=""):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO project_context (project_path, project_name, file_structure, notes, last_opened)
               VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            (project_path, project_name, file_structure, notes)
        )
        conn.commit()
        conn.close()
    
    def get_project_context(self, project_path):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM project_context WHERE project_path = ?", (project_path,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    # ========== 快捷命令管理 ==========
    def get_quick_commands(self, category=None):
        conn = self.get_connection()
        cursor = conn.cursor()
        if category:
            cursor.execute("SELECT * FROM quick_commands WHERE category = ? ORDER BY name", (category,))
        else:
            cursor.execute("SELECT * FROM quick_commands ORDER BY category, name")
        commands = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return commands
    
    def add_quick_command(self, name, command, description="", category="general"):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO quick_commands (name, command, description, category) VALUES (?, ?, ?, ?)",
            (name, command, description, category)
        )
        conn.commit()
        conn.close()


# ==================== AI 引擎（模拟 LLM 响应）====================
class AIEngine:
    """AI 对话引擎 - 支持接入真实 LLM API"""
    
    def __init__(self, db: Database):
        self.db = db
        self.api_key = ""
        self.api_url = ""
        self.model = "gpt-3.5-turbo"
        self.load_config()
    
    def load_config(self):
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.api_key = config.get('api_key', '')
                    self.api_url = config.get('api_url', '')
                    self.model = config.get('model', 'gpt-3.5-turbo')
            except:
                pass
    
    def save_config(self, api_key="", api_url="", model=""):
        config = {
            'api_key': api_key or self.api_key,
            'api_url': api_url or self.api_url,
            'model': model or self.model
        }
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        self.api_key = config['api_key']
        self.api_url = config['api_url']
        self.model = config['model']
    
    def build_system_prompt(self):
        """构建包含记忆的系统提示"""
        memories = self.db.get_all_memories()
        memory_text = "\n".join([f"- {m['key']}: {m['value']}" for m in memories[:20]])
        
        system_prompt = f"""你是一个专业的编程助手 WorkBuddy，集成在 OpenCode IDE 中。

【用户偏好记忆】
{memory_text if memory_text else '暂无记忆'}

【行为规范】
1. 记住用户的编码偏好、常用技术栈和项目约定
2. 提供准确、可运行的代码
3. 解释代码逻辑，帮助学习
4. 主动建议最佳实践
5. 当用户提到重要信息时，回复中以 [REMEMBER: key=value] 格式标记需要记忆的内容

请用简洁专业的中文回复。"""
        return system_prompt
    
    def chat(self, messages, callback=None):
        """发送聊天请求，支持流式输出"""
        # 尝试调用真实 API
        if self.api_key and self.api_url:
            try:
                import urllib.request
                import json as json_mod
                
                payload = {
                    "model": self.model,
                    "messages": messages,
                    "stream": False
                }
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}'
                }
                
                req = urllib.request.Request(
                    self.api_url,
                    data=json_mod.dumps(payload).encode('utf-8'),
                    headers=headers
                )
                
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json_mod.loads(resp.read().decode('utf-8'))
                    content = result['choices'][0]['message']['content']
                    if callback:
                        callback(content)
                    return content
            except Exception as e:
                error_msg = f"[API调用失败，使用本地模式] {str(e)}"
                if callback:
                    callback(self._local_response(messages[-1]['content']))
                return self._local_response(messages[-1]['content'])
        
        # 本地模拟响应
        user_msg = messages[-1]['content'] if messages else ""
        response = self._local_response(user_msg)
        if callback:
            callback(response)
        return response
    
    def _local_response(self, user_message):
        """本地智能响应（无需 API Key 也能使用）"""
        msg = user_message.lower()
        
        # 记忆提取
        memories = self.db.get_all_memories()
        memory_context = ""
        for m in memories:
            if any(kw in msg for kw in m['key'].lower().split()):
                memory_context += f"\n（回忆：{m['key']} = {m['value']}）"
        
        # 代码生成
        if any(kw in msg for kw in ['写', '生成', '创建', '实现', 'code', 'function', 'class']):
            return self._generate_code_response(user_message) + memory_context
        
        # 解释代码
        if any(kw in msg for kw in ['解释', '说明', '什么意思', 'explain', 'how does']):
            return self._explain_response(user_message) + memory_context
        
        # 调试
        if any(kw in msg for kw in ['错误', '报错', 'bug', 'debug', 'fix', '修复']):
            return self._debug_response(user_message) + memory_context
        
        # 记忆相关
        if any(kw in msg for kw in ['记住', '保存', '记忆', 'remember', 'preference']):
            return self._memory_response(user_message) + memory_context
        
        # 默认回复
        return self._default_response(user_message) + memory_context
    
    def _generate_code_response(self, msg):
        if 'python' in msg.lower() or 'py' in msg.lower():
            return """我来帮你用 Python 实现这个功能：

```python
def example_function():
    \"\"\"示例函数 - 根据你的需求定制\"\"\"
    # TODO: 实现具体逻辑
    result = "Hello, WorkBuddy!"
    return result

if __name__ == "__main__":
    print(example_function())
```

**说明：**
1. 这是一个基础模板，你可以根据实际需求修改
2. 建议添加类型注解和文档字符串
3. 记得写单元测试

需要我针对具体需求生成更详细的代码吗？"""
        elif 'javascript' in msg.lower() or 'js' in msg.lower():
            return """```javascript
// WorkBuddy 生成的代码示例
function exampleFunction() {
    /**
     * 示例函数
     */
    const result = "Hello, WorkBuddy!";
    console.log(result);
    return result;
}

module.exports = { exampleFunction };
```"""
        else:
            return """我可以帮你生成代码！请告诉我：
1. **编程语言**（Python/JavaScript/Java/C++/Go/Rust等）
2. **具体功能**（如：读取CSV文件、搭建Web服务器、排序算法等）
3. **特殊要求**（性能、兼容性、风格偏好等）

我会为你生成完整可运行的代码。"""
    
    def _explain_response(self, msg):
        return """我来帮你分析这段代码的逻辑：

**代码分析步骤：**

1. **功能定位** - 确定代码的核心目的
2. **结构分析** - 梳理函数/类的组织方式
3. **数据流追踪** - 理解数据如何传递和变换
4. **关键点标注** - 标记重要逻辑和潜在问题

请把需要解释的代码发给我，我来逐行分析。"""
    
    def _debug_response(self, msg):
        return """我来帮你排查问题！请提供：

1. **错误信息**（完整的报错堆栈）
2. **相关代码**（出问题的代码片段）
3. **运行环境**（Python版本、操作系统、依赖版本）
4. **已尝试方案**（你已经试过什么方法）

**常见排查思路：**
- 检查变量作用域和生命周期
- 验证数据类型和格式
- 确认依赖版本兼容性
- 查看日志和调试输出

把错误贴给我，我帮你定位根因。"""
    
    def _memory_response(self, msg):
        # 尝试提取记忆
        patterns = [
            r'记住[，,]\s*(.+?)[=是:]\s*(.+)',
            r'remember\s+(.+?)\s*(?:=|:)\s*(.+)',
            r'我的偏好[是:]\s*(.+)',
            r'我喜欢\s*(.+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, msg)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    key, value = groups[0].strip(), groups[1].strip()
                    self.db.save_memory(key, value, category='user_preference', importance=3)
                    return f"✅ 已记住：**{key}** = {value}\n\n以后我会记住这个偏好！"
        
        return """我可以记住以下类型的信息：

- **编码偏好**：如"记住，我喜欢用 4 空格缩进"
- **技术栈**：如"记住，我的项目用 Python 3.11"
- **项目约定**：如"记住，我们用 PEP8 规范"
- **常用路径**：如"记住，项目根目录是 D:/workspace"

说"查看记忆"可以看到所有已记住的内容。"""
    
    def _default_response(self, msg):
        greetings = ['你好', 'hi', 'hello', 'hey', '在吗', '在不在']
        if any(g in msg.lower() for g in greetings):
            return f"""👋 你好！我是 **WorkBuddy**，你的 AI 编程伙伴！

**我能帮你：**
- 💻 生成/解释/调试代码
- 📝 管理代码片段库
- 🧠 记住你的编码偏好
- ⚡ 执行快捷命令
- 📂 分析项目结构

输入"帮助"查看完整功能列表，或者直接告诉我你需要什么！"""
        
        if '帮助' in msg or 'help' in msg.lower():
            return """## 🛠️ WorkBuddy 功能指南

### 对话功能
- 直接输入问题，我会尽力回答
- 支持代码生成、解释、调试
- 配置 API Key 后可接入 GPT/Claude 等模型

### 记忆功能
- 说"记住，XXX"来保存偏好
- 说"查看记忆"查看所有记忆
- 记忆会跨会话持久保存

### 代码执行
- 在"终端"标签页直接运行命令
- 支持快捷命令一键执行

### 项目分析
- 打开项目文件夹自动分析结构
- 保存项目上下文供后续使用

### 快捷键
- `Ctrl+Enter` - 发送消息
- `Ctrl+N` - 新建对话
- `Ctrl+S` - 保存当前代码"""
        
        return f"""收到你的消息："**{msg[:100]}**"

我是 WorkBuddy，可以帮你：
- 💻 写代码 / 解释代码 / 调试
- 🧠 记住你的偏好
- ⚡ 执行命令
- 📂 管理项目

请告诉我具体需要什么帮助？"""


# ==================== 代码高亮 ====================
class CodeHighlighter(QSyntaxHighlighter):
    """简单的代码语法高亮"""
    
    def __init__(self, parent, language="python"):
        super().__init__(parent)
        self.language = language
        self.highlighting_rules = []
        self._setup_rules()
    
    def _setup_rules(self):
        self.highlighting_rules.clear()
        
        # 关键字
        keywords = [
            'def', 'class', 'import', 'from', 'as', 'return', 'if', 'elif', 'else',
            'for', 'while', 'try', 'except', 'finally', 'with', 'pass', 'break',
            'continue', 'lambda', 'yield', 'async', 'await', 'True', 'False', 'None',
            'and', 'or', 'not', 'in', 'is', 'global', 'nonlocal', 'self'
        ]
        
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#c678dd"))
        keyword_format.setFontWeight(QFont.Bold)
        
        for kw in keywords:
            pattern = f"\\b{kw}\\b"
            self.highlighting_rules.append((re.compile(pattern), keyword_format))
        
        # 字符串
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#98c379"))
        self.highlighting_rules.append((re.compile(r'"[^"]*"'), string_format))
        self.highlighting_rules.append((re.compile(r"'[^']*'"), string_format))
        
        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#5c6370"))
        comment_format.setFontItalic(True)
        self.highlighting_rules.append((re.compile(r"#[^\n]*"), comment_format))
        
        # 数字
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#d19a66"))
        self.highlighting_rules.append((re.compile(r"\b\d+\.?\d*\b"), number_format))
        
        # 函数调用
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#61afef"))
        self.highlighting_rules.append((re.compile(r"\b\w+(?=\()"), function_format))
    
    def highlightBlock(self, text):
        for pattern, fmt in self.highlighting_rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


# ==================== 工作线程 ====================
class ChatWorker(QThread):
    """后台聊天处理线程"""
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, ai_engine: AIEngine, messages):
        super().__init__()
        self.ai_engine = ai_engine
        self.messages = messages
    
    def run(self):
        try:
            response = self.ai_engine.chat(self.messages)
            self.response_ready.emit(response)
        except Exception as e:
            self.error_occurred.emit(str(e))


class CommandWorker(QThread):
    """后台命令执行线程"""
    output_ready = pyqtSignal(str)
    finished_signal = pyqtSignal(int)
    
    def __init__(self, command, cwd=None):
        super().__init__()
        self.command = command
        self.cwd = cwd
    
    def run(self):
        try:
            process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.cwd
            )
            
            while True:
                output = process.stdout.readline()
                if output:
                    self.output_ready.emit(output)
                elif process.poll() is not None:
                    break
            
            stderr = process.stderr.read()
            if stderr:
                self.output_ready.emit(stderr)
            
            self.finished_signal.emit(process.returncode)
        except Exception as e:
            self.output_ready.emit(f"错误: {str(e)}\n")
            self.finished_signal.emit(-1)


# ==================== 主窗口 ====================
class MainWindow(QMainWindow):
    """WorkBuddy OpenCode 主窗口"""
    
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.ai_engine = AIEngine(self.db)
        self.current_conversation_id = None
        self.current_theme = "dark"
        self.project_path = None
        
        self.init_ui()
        self.load_conversations()
        self.load_memories()
    
    def init_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # 设置应用图标（用文字代替）
        self.setWindowIcon(self._create_icon())
        
        # 中央部件
        central = QWidget()
        self.setCentralWidget(central)
        
        # 主布局
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 左侧边栏
        self.sidebar = self._create_sidebar()
        main_layout.addWidget(self.sidebar)
        
        # 右侧主区域
        self.main_area = self._create_main_area()
        main_layout.addWidget(self.main_area, 1)
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪 | 未连接 API（使用本地模式）")
        
        # 工具栏
        self._create_toolbar()
        
        # 应用样式
        self.apply_theme()
        
        # 定时器：自动保存
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(30000)  # 30秒
    
    def _create_icon(self):
        """创建应用图标"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        from PyQt5.QtGui import QPainter, QBrush
        painter = QPainter(pixmap)
        painter.setBrush(QBrush(QColor("#89b4fa")))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(4, 4, 56, 56, 12, 12)
        painter.setPen(QColor("white"))
        painter.setFont(QFont("Arial", 24, QFont.Bold))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "W")
        painter.end()
        return QIcon(pixmap)
    
    def _create_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # 新建对话
        new_chat_action = QAction("➕ 新建对话", self)
        new_chat_action.setShortcut("Ctrl+N")
        new_chat_action.triggered.connect(self.new_conversation)
        toolbar.addAction(new_chat_action)
        
        toolbar.addSeparator()
        
        # 打开项目
        open_project_action = QAction("📂 打开项目", self)
        open_project_action.triggered.connect(self.open_project)
        toolbar.addAction(open_project_action)
        
        # 保存代码
        save_code_action = QAction("💾 保存代码", self)
        save_code_action.setShortcut("Ctrl+S")
        save_code_action.triggered.connect(self.save_current_code)
        toolbar.addAction(save_code_action)
        
        toolbar.addSeparator()
        
        # 主题切换
        theme_action = QAction("🎨 切换主题", self)
        theme_action.triggered.connect(self.toggle_theme)
        toolbar.addAction(theme_action)
        
        # 设置
        settings_action = QAction("⚙️ 设置", self)
        settings_action.triggered.connect(self.open_settings)
        toolbar.addAction(settings_action)
    
    def _create_sidebar(self):
        """创建左侧边栏"""
        sidebar = QWidget()
        sidebar.setFixedWidth(280)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        # 标题
        title_label = QLabel(f"🤖 {APP_NAME}")
        title_label.setObjectName("sidebarTitle")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # 新建对话按钮
        new_btn = QPushButton("✨ 新建对话")
        new_btn.setObjectName("newChatBtn")
        new_btn.clicked.connect(self.new_conversation)
        layout.addWidget(new_btn)
        
        # 对话历史
        history_label = QLabel("📋 对话历史")
        history_label.setObjectName("sectionLabel")
        layout.addWidget(history_label)
        
        self.conversation_list = QListWidget()
        self.conversation_list.setObjectName("conversationList")
        self.conversation_list.itemClicked.connect(self.load_conversation_messages)
        layout.addWidget(self.conversation_list, 1)
        
        # 记忆区域
        memory_label = QLabel("🧠 记忆库")
        memory_label.setObjectName("sectionLabel")
        layout.addWidget(memory_label)
        
        self.memory_list = QListWidget()
        self.memory_list.setObjectName("memoryList")
        self.memory_list.setMaximumHeight(150)
        layout.addWidget(self.memory_list)
        
        # 记忆操作按钮
        mem_btn_layout = QHBoxLayout()
        add_mem_btn = QPushButton("➕")
        add_mem_btn.setToolTip("添加记忆")
        add_mem_btn.clicked.connect(self.add_memory_dialog)
        view_mem_btn = QPushButton("👁")
        view_mem_btn.setToolTip("查看所有记忆")
        view_mem_btn.clicked.connect(self.show_all_memories)
        mem_btn_layout.addWidget(add_mem_btn)
        mem_btn_layout.addWidget(view_mem_btn)
        layout.addLayout(mem_btn_layout)
        
        # 快捷命令
        cmd_label = QLabel("⚡ 快捷命令")
        cmd_label.setObjectName("sectionLabel")
        layout.addWidget(cmd_label)
        
        self.cmd_combo = QComboBox()
        self.cmd_combo.setObjectName("cmdCombo")
        commands = self.db.get_quick_commands()
        for cmd in commands:
            self.cmd_combo.addItem(f"⚡ {cmd['name']}", cmd['command'])
        layout.addWidget(self.cmd_combo)
        
        run_cmd_btn = QPushButton("▶ 运行选中命令")
        run_cmd_btn.clicked.connect(self.run_quick_command)
        layout.addWidget(run_cmd_btn)
        
        return sidebar
    
    def _create_main_area(self):
        """创建右侧主区域"""
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 标签页
        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        
        # Chat 标签页
        self.tabs.addTab(self._create_chat_tab(), "💬 Chat")
        
        # Code Editor 标签页
        self.tabs.addTab(self._create_code_tab(), "📝 代码编辑器")
        
        # Terminal 标签页
        self.tabs.addTab(self._create_terminal_tab(), "⚡ 终端")
        
        # Project 标签页
        self.tabs.addTab(self._create_project_tab(), "📂 项目")
        
        layout.addWidget(self.tabs)
        return main_widget
    
    def _create_chat_tab(self):
        """创建聊天标签页"""
        chat_widget = QWidget()
        layout = QVBoxLayout(chat_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 对话标题
        self.chat_title = QLabel("💬 新对话")
        self.chat_title.setObjectName("chatTitle")
        layout.addWidget(self.chat_title)
        
        # 聊天记录区域
        self.chat_display = QTextEdit()
        self.chat_display.setObjectName("chatDisplay")
        self.chat_display.setReadOnly(True)
        layout.addWidget(self.chat_display, 1)
        
        # 输入区域
        input_widget = QWidget()
        input_layout = QHBoxLayout(input_widget)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        self.chat_input = QTextEdit()
        self.chat_input.setObjectName("chatInput")
        self.chat_input.setPlaceholderText("输入消息... (Ctrl+Enter 发送)")
        self.chat_input.setMaximumHeight(120)
        self.chat_input.installEventFilter(self)
        input_layout.addWidget(self.chat_input)
        
        send_btn = QPushButton("📤\n发送")
        send_btn.setObjectName("sendBtn")
        send_btn.setFixedWidth(80)
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)
        
        layout.addWidget(input_widget)
        
        # 欢迎消息
        self.append_chat_message("assistant", 
            f"👋 欢迎使用 **{APP_NAME}**！\n\n"
            "我是你的 AI 编程伙伴，可以帮你：\n"
            "- 💻 编写、解释、调试代码\n"
            "- 🧠 记住你的编码偏好\n"
            "- ⚡ 执行终端命令\n"
            "- 📂 分析项目结构\n\n"
            "输入 **帮助** 查看完整功能列表！")
        
        return chat_widget
    
    def _create_code_tab(self):
        """创建代码编辑器标签页"""
        code_widget = QWidget()
        layout = QVBoxLayout(code_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 工具栏
        toolbar = QHBoxLayout()
        
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Python", "JavaScript", "Java", "C++", "Go", "Rust", "HTML", "CSS", "SQL"])
        toolbar.addWidget(QLabel("语言:"))
        toolbar.addWidget(self.lang_combo)
        
        toolbar.addStretch()
        
        clear_btn = QPushButton("🗑 清空")
        clear_btn.clicked.connect(lambda: self.code_editor.clear())
        toolbar.addWidget(clear_btn)
        
        save_snippet_btn = QPushButton("💾 保存片段")
        save_snippet_btn.clicked.connect(self.save_code_snippet)
        toolbar.addWidget(save_snippet_btn)
        
        run_btn = QPushButton("▶ 运行")
        run_btn.clicked.connect(self.run_code)
        toolbar.addWidget(run_btn)
        
        layout.addLayout(toolbar)
        
        # 代码编辑器
        self.code_editor = QTextEdit()
        self.code_editor.setObjectName("codeEditor")
        self.code_editor.setFont(QFont("Consolas", 13))
        self.code_editor.setPlaceholderText("# 在这里写代码...\n\nprint('Hello, WorkBuddy!')")
        
        # 代码高亮
        self.code_highlighter = CodeHighlighter(self.code_editor.document(), "python")
        
        # 语言切换时更新高亮
        self.lang_combo.currentTextChanged.connect(self.change_language)
        
        layout.addWidget(self.code_editor, 1)
        
        # 输出区域
        self.code_output = QTextEdit()
        self.code_output.setObjectName("codeOutput")
        self.code_output.setReadOnly(True)
        self.code_output.setMaximumHeight(200)
        self.code_output.setPlaceholderText("运行结果将显示在这里...")
        layout.addWidget(self.code_output)
        
        return code_widget
    
    def _create_terminal_tab(self):
        """创建终端标签页"""
        term_widget = QWidget()
        layout = QVBoxLayout(term_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 终端显示
        self.terminal_display = QTextEdit()
        self.terminal_display.setObjectName("terminalDisplay")
        self.terminal_display.setReadOnly(True)
        self.terminal_display.setFont(QFont("Consolas", 12))
        self.terminal_display.append("WorkBuddy Terminal v1.0")
        self.terminal_display.append("输入命令并点击运行，或使用快捷命令。")
        self.terminal_display.append("-" * 50)
        layout.addWidget(self.terminal_display, 1)
        
        # 命令输入
        cmd_layout = QHBoxLayout()
        self.terminal_input = QLineEdit()
        self.terminal_input.setObjectName("terminalInput")
        self.terminal_input.setPlaceholderText("输入命令...")
        self.terminal_input.returnPressed.connect(self.run_terminal_command)
        cmd_layout.addWidget(self.terminal_input)
        
        run_btn = QPushButton("▶ 运行")
        run_btn.clicked.connect(self.run_terminal_command)
        cmd_layout.addWidget(run_btn)
        
        clear_btn = QPushButton("🗑 清空")
        clear_btn.clicked.connect(self.terminal_display.clear)
        cmd_layout.addWidget(clear_btn)
        
        layout.addLayout(cmd_layout)
        
        return term_widget
    
    def _create_project_tab(self):
        """创建项目标签页"""
        proj_widget = QWidget()
        layout = QVBoxLayout(proj_widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # 项目信息
        info_group = QGroupBox("📂 项目信息")
        info_layout = QVBoxLayout(info_group)
        
        self.project_info_label = QLabel("未打开项目")
        self.project_info_label.setObjectName("projectInfo")
        info_layout.addWidget(self.project_info_label)
        
        layout.addWidget(info_group)
        
        # 文件树
        tree_group = QGroupBox("📁 文件结构")
        tree_layout = QVBoxLayout(tree_group)
        
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("文件")
        self.file_tree.itemDoubleClicked.connect(self.open_file_from_tree)
        tree_layout.addWidget(self.file_tree)
        
        layout.addWidget(tree_group, 1)
        
        # 项目笔记
        notes_group = QGroupBox("📝 项目笔记")
        notes_layout = QVBoxLayout(notes_group)
        
        self.project_notes = QTextEdit()
        self.project_notes.setObjectName("projectNotes")
        self.project_notes.setPlaceholderText("记录项目相关的笔记...")
        self.project_notes.textChanged.connect(self.save_project_notes_auto)
        notes_layout.addWidget(self.project_notes)
        
        layout.addWidget(notes_group)
        
        return proj_widget
    
    # ==================== 事件处理 ====================
    def eventFilter(self, obj, event):
        if obj == self.chat_input and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
                self.send_message()
                return True
        return super().eventFilter(obj, event)
    
    def send_message(self):
        """发送聊天消息"""
        text = self.chat_input.toPlainText().strip()
        if not text:
            return
        
        # 显示用户消息
        self.append_chat_message("user", text)
        self.chat_input.clear()
        
        # 检查特殊命令
        if text in ["查看记忆", "show memories", "记忆列表"]:
            self.show_all_memories()
            return
        elif text.startswith("记住"):
            # 提取记忆
            self._process_memory_command(text)
            return
        
        # 确保有对话
        if not self.current_conversation_id:
            self.current_conversation_id = self.db.create_conversation(
                title=text[:30]
            )
            self.load_conversations()
        
        # 保存用户消息
        self.db.save_message(self.current_conversation_id, "user", text)
        
        # 构建消息列表
        messages = [{"role": "system", "content": self.ai_engine.build_system_prompt()}]
        history = self.db.get_conversation_messages(self.current_conversation_id)
        for msg in history:
            messages.append({"role": msg['role'], "content": msg['content']})
        
        # 显示思考中
        self.append_chat_message("assistant", "🤔 思考中...")
        self.chat_display.repaint()
        
        # 后台处理
        self.chat_worker = ChatWorker(self.ai_engine, messages)
        self.chat_worker.response_ready.connect(lambda r: self.handle_ai_response(r, text))
        self.chat_worker.error_occurred.connect(lambda e: self.append_chat_message("assistant", f"❌ 错误: {e}"))
        self.chat_worker.start()
    
    def handle_ai_response(self, response, user_msg):
        """处理 AI 响应"""
        # 移除"思考中"消息
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        # 简单方式：直接清空最后一行并重写
        self.chat_display.append("")  # 新行
        self.append_chat_message("assistant", response)
        
        # 保存助手消息
        if self.current_conversation_id:
            self.db.save_message(self.current_conversation_id, "assistant", response)
        
        # 检查是否有记忆标记
        self._extract_memory_markers(response)
        
        # 更新对话标题
        if len(user_msg) > 0:
            self.chat_title.setText(f"💬 {user_msg[:30]}")
    
    def _process_memory_command(self, text):
        """处理记忆命令"""
        result = self.ai_engine._memory_response(text)
        self.append_chat_message("assistant", result)
        self.load_memories()
    
    def _extract_memory_markers(self, text):
        """从响应中提取记忆标记"""
        pattern = r'\[REMEMBER:\s*(.+?)=(.+?)\]'
        matches = re.findall(pattern, text)
        for key, value in matches:
            self.db.save_memory(key.strip(), value.strip(), category='auto', importance=2)
        if matches:
            self.load_memories()
    
    def append_chat_message(self, role, content):
        """添加聊天消息到显示区域"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        if role == "user":
            prefix = '<div style="margin: 8px 0; padding: 10px 14px; background: #89b4fa22; border-left: 3px solid #89b4fa; border-radius: 6px;"><b>👤 你</b><br>'
            suffix = '</div>'
        else:
            prefix = '<div style="margin: 8px 0; padding: 10px 14px; background: #a6e3a122; border-left: 3px solid #a6e3a1; border-radius: 6px;"><b>🤖 WorkBuddy</b><br>'
            suffix = '</div>'
        
        # 简单的 markdown 处理
        content = content.replace('\n', '<br>')
        content = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', content)
        content = re.sub(r'`(.+?)`', r'<code style="background:#181825;padding:2px 6px;border-radius:3px;color:#f38ba8;">\1</code>', content)
        
        html = prefix + content + suffix + '<br>'
        self.chat_display.insertHtml(html)
        
        # 滚动到底部
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def new_conversation(self):
        """新建对话"""
        self.current_conversation_id = self.db.create_conversation()
        self.chat_title.setText("💬 新对话")
        self.chat_display.clear()
        self.append_chat_message("assistant", "👋 新对话已开始！有什么我可以帮你的？")
        self.load_conversations()
    
    def load_conversations(self):
        """加载对话列表"""
        self.conversation_list.clear()
        conversations = self.db.get_all_conversations()
        for conv in conversations:
            item = QListWidgetItem(f"💬 {conv['title'][:30]}")
            item.setData(Qt.UserRole, conv['id'])
            # 格式化时间
            updated = conv['updated_at']
            if updated:
                item.setToolTip(f"更新于: {updated}")
            self.conversation_list.addItem(item)
    
    def load_conversation_messages(self, item):
        """加载选中对话的消息"""
        conv_id = item.data(Qt.UserRole)
        self.current_conversation_id = conv_id
        
        # 获取对话标题
        conversations = self.db.get_all_conversations()
        for conv in conversations:
            if conv['id'] == conv_id:
                self.chat_title.setText(f"💬 {conv['title'][:30]}")
                break
        
        # 清空并显示
        self.chat_display.clear()
        messages = self.db.get_conversation_messages(conv_id)
        
        if not messages:
            self.append_chat_message("assistant", "这个对话还没有消息。")
            return
        
        for msg in messages:
            self.append_chat_message(msg['role'], msg['content'])
    
    def load_memories(self):
        """加载记忆列表"""
        self.memory_list.clear()
        memories = self.db.get_all_memories()
        for mem in memories[:10]:  # 只显示前10条
            item = QListWidgetItem(f"🧠 {mem['key'][:20]}")
            item.setData(Qt.UserRole, mem['key'])
            item.setToolTip(f"{mem['key']}: {mem['value']}")
            self.memory_list.addItem(item)
    
    def add_memory_dialog(self):
        """添加记忆对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("添加记忆")
        dialog.setMinimumWidth(400)
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel("键（标识）:"))
        key_input = QLineEdit()
        key_input.setPlaceholderText("如: python_version")
        layout.addWidget(key_input)
        
        layout.addWidget(QLabel("值（内容）:"))
        value_input = QLineEdit()
        value_input.setPlaceholderText("如: 3.11")
        layout.addWidget(value_input)
        
        layout.addWidget(QLabel("分类:"))
        cat_input = QLineEdit()
        cat_input.setText("user_preference")
        layout.addWidget(cat_input)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec_() == QDialog.Accepted:
            key = key_input.text().strip()
            value = value_input.text().strip()
            cat = cat_input.text().strip()
            if key and value:
                self.db.save_memory(key, value, category=cat, importance=3)
                self.load_memories()
                self.status_bar.showMessage(f"✅ 已保存记忆: {key}", 3000)
    
    def show_all_memories(self):
        """显示所有记忆"""
        memories = self.db.get_all_memories()
        if not memories:
            self.append_chat_message("assistant", '🧠 记忆库为空。\n\n说"记住，XXX"来添加记忆！')
            return
        
        msg = "🧠 **记忆库内容：**\n\n"
        for m in memories:
            importance_stars = "⭐" * m['importance']
            msg += f"- **{m['key']}**: {m['value']} `{m['category']}` {importance_stars}\n"
        
        msg += f"\n共 {len(memories)} 条记忆"
        self.append_chat_message("assistant", msg)
    
    def change_language(self, lang):
        """切换代码高亮语言"""
        self.code_highlighter = CodeHighlighter(self.code_editor.document(), lang.lower())
    
    def save_code_snippet(self):
        """保存代码片段"""
        code = self.code_editor.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "警告", "代码编辑器为空！")
            return
        
        title, ok = QInputDialog.getText(self, "保存代码片段", "输入标题:")
        if ok and title:
            lang = self.lang_combo.currentText().lower()
            self.db.save_snippet(title, lang, code, tags=lang)
            self.status_bar.showMessage(f"✅ 已保存代码片段: {title}", 3000)
    
    def save_current_code(self):
        """保存当前代码到文件"""
        code = self.code_editor.toPlainText()
        if not code:
            return
        
        lang_ext = {
            "Python": ".py", "JavaScript": ".js", "Java": ".java",
            "C++": ".cpp", "Go": ".go", "Rust": ".rs",
            "HTML": ".html", "CSS": ".css", "SQL": ".sql"
        }
        ext = lang_ext.get(self.lang_combo.currentText(), ".txt")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存代码", f"code{ext}",
            f"{self.lang_combo.currentText()} Files (*{ext});;All Files (*)"
        )
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)
            self.status_bar.showMessage(f"✅ 已保存到: {file_path}", 3000)
    
    def run_code(self):
        """运行代码"""
        code = self.code_editor.toPlainText().strip()
        if not code:
            return
        
        lang = self.lang_combo.currentText()
        self.code_output.clear()
        self.code_output.append(f"$ 运行 {lang} 代码...")
        
        # 写入临时文件
        ext_map = {"Python": ".py", "JavaScript": ".js", "Java": ".java",
                   "C++": ".cpp", "Go": ".go", "Rust": ".rs"}
        ext = ext_map.get(lang, ".txt")
        
        temp_file = os.path.join(os.path.dirname(__file__), f"temp_code{ext}")
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 执行命令
        cmd_map = {
            "Python": f"python {temp_file}",
            "JavaScript": f"node {temp_file}",
            "Java": f"javac {temp_file} && java temp_code",
            "C++": f"g++ {temp_file} -o temp_code && ./temp_code",
            "Go": f"go run {temp_file}",
            "Rust": f"rustc {temp_file} -o temp_code && ./temp_code"
        }
        cmd = cmd_map.get(lang, "")
        
        if not cmd:
            self.code_output.append("❌ 不支持该语言的运行")
            return
        
        self.command_worker = CommandWorker(cmd, cwd=os.path.dirname(__file__))
        self.command_worker.output_ready.connect(self.code_output.append)
        self.command_worker.finished_signal.connect(
            lambda rc: self.code_output.append(f"\n$ 退出码: {rc}")
        )
        self.command_worker.start()
    
    def run_quick_command(self):
        """运行快捷命令"""
        cmd = self.cmd_combo.currentData()
        if cmd:
            self.terminal_input.setText(cmd)
            self.run_terminal_command()
    
    def run_terminal_command(self):
        """运行终端命令"""
        cmd = self.terminal_input.text().strip()
        if not cmd:
            return
        
        self.terminal_display.append(f"\n$ {cmd}")
        self.terminal_display.repaint()
        
        self.command_worker = CommandWorker(cmd, cwd=self.project_path)
        self.command_worker.output_ready.connect(self.terminal_display.append)
        self.command_worker.finished_signal.connect(
            lambda rc: self.terminal_display.append(f"[退出码: {rc}]")
        )
        self.command_worker.start()
        
        self.terminal_input.clear()
    
    def open_project(self):
        """打开项目文件夹"""
        folder = QFileDialog.getExistingDirectory(self, "选择项目文件夹")
        if folder:
            self.project_path = folder
            project_name = os.path.basename(folder)
            self.project_info_label.setText(
                f"📂 **{project_name}**\n"
                f"路径: {folder}\n"
                f"打开时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # 分析文件结构
            self.analyze_project(folder)
            
            # 保存到数据库
            file_structure = self._get_file_structure_json(folder)
            self.db.save_project_context(folder, project_name, file_structure)
            
            self.status_bar.showMessage(f"📂 已打开项目: {project_name}", 3000)
            
            # 切换到项目标签页
            self.tabs.setCurrentIndex(3)
    
    def analyze_project(self, folder):
        """分析项目结构"""
        self.file_tree.clear()
        
        root_item = QTreeWidgetItem([os.path.basename(folder)])
        root_item.setData(0, Qt.UserRole, folder)
        self.file_tree.addTopLevelItem(root_item)
        
        self._populate_tree(folder, root_item, max_depth=3)
        root_item.setExpanded(True)
    
    def _populate_tree(self, path, parent_item, max_depth=3, current_depth=0):
        """递归填充文件树"""
        if current_depth >= max_depth:
            return
        
        try:
            items = sorted(os.listdir(path))
            for item in items[:50]:  # 限制数量
                if item.startswith('.'):
                    continue
                full_path = os.path.join(path, item)
                tree_item = QTreeWidgetItem([item])
                tree_item.setData(0, Qt.UserRole, full_path)
                
                if os.path.isdir(full_path):
                    tree_item.setText(0, f"📁 {item}")
                    self._populate_tree(full_path, tree_item, max_depth, current_depth + 1)
                else:
                    # 根据扩展名选择图标
                    ext = os.path.splitext(item)[1].lower()
                    icon_map = {
                        '.py': '🐍', '.js': '📜', '.java': '☕', '.cpp': '⚙️',
                        '.go': '🔵', '.rs': '🦀', '.html': '🌐', '.css': '🎨',
                        '.json': '📋', '.md': '📝', '.txt': '📄', '.sql': '🗄️'
                    }
                    tree_item.setText(0, f"{icon_map.get(ext, '📄')} {item}")
                
                parent_item.addChild(tree_item)
        except PermissionError:
            pass
    
    def _get_file_structure_json(self, folder):
        """获取文件结构 JSON"""
        structure = {}
        try:
            for item in sorted(os.listdir(folder))[:30]:
                if item.startswith('.'):
                    continue
                full_path = os.path.join(folder, item)
                if os.path.isdir(full_path):
                    structure[item] = "directory"
                else:
                    structure[item] = os.path.splitext(item)[1]
        except:
            pass
        return json.dumps(structure, ensure_ascii=False)
    
    def open_file_from_tree(self, item):
        """从文件树打开文件"""
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 切换到代码编辑器
                self.tabs.setCurrentIndex(1)
                
                # 设置语言
                ext = os.path.splitext(path)[1].lower()
                ext_to_lang = {
                    '.py': 'Python', '.js': 'JavaScript', '.java': 'Java',
                    '.cpp': 'C++', '.go': 'Go', '.rs': 'Rust',
                    '.html': 'HTML', '.css': 'CSS', '.sql': 'SQL'
                }
                lang = ext_to_lang.get(ext, 'Python')
                self.lang_combo.setCurrentText(lang)
                
                # 加载内容
                self.code_editor.setPlainText(content)
                self.status_bar.showMessage(f"📄 已打开: {path}", 3000)
            except Exception as e:
                QMessageBox.warning(self, "错误", f"无法打开文件: {e}")
    
    def save_project_notes_auto(self):
        """自动保存项目笔记"""
        if self.project_path:
            notes = self.project_notes.toPlainText()
            self.db.save_project_context(
                self.project_path,
                os.path.basename(self.project_path),
                self._get_file_structure_json(self.project_path),
                notes
            )
    
    def toggle_theme(self):
        """切换主题"""
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme()
        self.status_bar.showMessage(f"🎨 已切换到{'浅色' if self.current_theme == 'light' else '深色'}主题", 2000)
    
    def apply_theme(self):
        """应用主题样式"""
        theme = THEMES[self.current_theme]
        
        style = f"""
        QMainWindow {{
            background-color: {theme['bg']};
            color: {theme['fg']};
        }}
        
        QWidget {{
            background-color: {theme['bg']};
            color: {theme['fg']};
        }}
        
        /* 侧边栏 */
        #sidebarTitle {{
            font-size: 16px;
            font-weight: bold;
            color: {theme['accent']};
            padding: 8px;
            border-bottom: 2px solid {theme['accent']};
            margin-bottom: 4px;
        }}
        
        #sectionLabel {{
            font-size: 12px;
            font-weight: bold;
            color: {theme['accent']};
            padding: 4px 0;
            text-transform: uppercase;
        }}
        
        #newChatBtn {{
            background-color: {theme['accent']};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px;
            font-size: 14px;
            font-weight: bold;
        }}
        #newChatBtn:hover {{
            background-color: {theme['accent']}dd;
        }}
        
        /* 列表 */
        QListWidget {{
            background-color: {theme['secondary']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 4px;
        }}
        QListWidget::item {{
            padding: 6px 8px;
            border-radius: 4px;
        }}
        QListWidget::item:hover {{
            background-color: {theme['accent']}22;
        }}
        QListWidget::item:selected {{
            background-color: {theme['accent']}44;
            color: {theme['fg']};
        }}
        
        /* 聊天区域 */
        #chatTitle {{
            font-size: 14px;
            font-weight: bold;
            color: {theme['accent']};
            padding: 4px 0;
        }}
        #chatDisplay {{
            background-color: {theme['code_bg']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 8px;
            font-size: 13px;
        }}
        #chatInput {{
            background-color: {theme['input_bg']};
            border: 2px solid {theme['border']};
            border-radius: 8px;
            padding: 8px;
            font-size: 13px;
        }}
        #chatInput:focus {{
            border-color: {theme['accent']};
        }}
        
        /* 发送按钮 */
        #sendBtn {{
            background-color: {theme['success']};
            color: {theme['bg']};
            border: none;
            border-radius: 8px;
            padding: 10px;
            font-weight: bold;
            font-size: 13px;
        }}
        #sendBtn:hover {{
            background-color: {theme['success']}dd;
        }}
        
        /* 代码编辑器 */
        #codeEditor {{
            background-color: {theme['code_bg']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 8px;
            font-family: Consolas, monospace;
        }}
        #codeOutput {{
            background-color: {theme['input_bg']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 6px;
            font-family: Consolas, monospace;
            font-size: 12px;
        }}
        
        /* 终端 */
        #terminalDisplay {{
            background-color: #0d1117;
            color: #c9d1d9;
            border: 1px solid {theme['border']};
            border-radius: 8px;
            padding: 8px;
            font-family: Consolas, monospace;
        }}
        #terminalInput {{
            background-color: {theme['input_bg']};
            border: 2px solid {theme['border']};
            border-radius: 6px;
            padding: 6px 10px;
            font-family: Consolas, monospace;
        }}
        
        /* 标签页 */
        QTabWidget::pane {{
            border: 1px solid {theme['border']};
            border-radius: 8px;
            background: {theme['bg']};
        }}
        QTabBar::tab {{
            background: {theme['secondary']};
            color: {theme['fg']};
            padding: 8px 16px;
            border-radius: 6px 6px 0 0;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background: {theme['accent']}33;
            color: {theme['accent']};
            font-weight: bold;
        }}
        
        /* 组合框 */
        QComboBox {{
            background-color: {theme['input_bg']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 4px 8px;
        }}
        QComboBox:hover {{
            border-color: {theme['accent']};
        }}
        
        /* 按钮通用 */
        QPushButton {{
            background-color: {theme['secondary']};
            color: {theme['fg']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 6px 12px;
        }}
        QPushButton:hover {{
            background-color: {theme['accent']}22;
            border-color: {theme['accent']};
        }}
        
        /* 分组框 */
        QGroupBox {{
            border: 1px solid {theme['border']};
            border-radius: 8px;
            margin-top: 8px;
            padding-top: 8px;
            font-weight: bold;
        }}
        QGroupBox::title {{
            color: {theme['accent']};
            padding: 0 8px;
        }}
        
        /* 状态栏 */
        QStatusBar {{
            background-color: {theme['secondary']};
            color: {theme['fg']};
            border-top: 1px solid {theme['border']};
        }}
        
        /* 工具栏 */
        QToolBar {{
            background-color: {theme['secondary']};
            border-bottom: 1px solid {theme['border']};
            spacing: 4px;
            padding: 4px;
        }}
        QToolBar QAction {{
            padding: 4px 8px;
            border-radius: 4px;
        }}
        
        /* 树控件 */
        QTreeWidget {{
            background-color: {theme['secondary']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 4px;
        }}
        QTreeWidget::item {{
            padding: 3px;
            border-radius: 3px;
        }}
        QTreeWidget::item:hover {{
            background-color: {theme['accent']}22;
        }}
        QTreeWidget::item:selected {{
            background-color: {theme['accent']}44;
        }}
        
        /* 滚动条 */
        QScrollBar:vertical {{
            background: {theme['secondary']};
            width: 10px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: {theme['border']};
            border-radius: 5px;
            min-height: 20px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {theme['accent']};
        }}
        """
        
        self.setStyleSheet(style)
    
    def open_settings(self):
        """打开设置对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("⚙️ 设置")
        dialog.setMinimumWidth(500)
        layout = QVBoxLayout(dialog)
        
        # API 设置
        api_group = QGroupBox("🔑 LLM API 配置")
        api_layout = QVBoxLayout(api_group)
        
        api_layout.addWidget(QLabel("API URL:"))
        api_url_input = QLineEdit()
        api_url_input.setPlaceholderText("https://api.openai.com/v1/chat/completions")
        api_url_input.setText(self.ai_engine.api_url)
        api_layout.addWidget(api_url_input)
        
        api_layout.addWidget(QLabel("API Key:"))
        api_key_input = QLineEdit()
        api_key_input.setEchoMode(QLineEdit.Password)
        api_key_input.setPlaceholderText("sk-...")
        api_key_input.setText(self.ai_engine.api_key)
        api_layout.addWidget(api_key_input)
        
        api_layout.addWidget(QLabel("模型:"))
        model_input = QLineEdit()
        model_input.setText(self.ai_engine.model)
        model_input.setPlaceholderText("gpt-3.5-turbo")
        api_layout.addWidget(model_input)
        
        layout.addWidget(api_group)
        
        # 记忆管理
        mem_group = QGroupBox("🧠 记忆管理")
        mem_layout = QVBoxLayout(mem_group)
        
        clear_mem_btn = QPushButton("🗑 清除所有记忆")
        clear_mem_btn.clicked.connect(self.clear_all_memories)
        mem_layout.addWidget(clear_mem_btn)
        
        export_mem_btn = QPushButton("📤 导出记忆")
        export_mem_btn.clicked.connect(self.export_memories)
        mem_layout.addWidget(export_mem_btn)
        
        layout.addWidget(mem_group)
        
        # 关于
        about_group = QGroupBox("ℹ️ 关于")
        about_layout = QVBoxLayout(about_group)
        about_layout.addWidget(QLabel(f"{APP_NAME} v{APP_VERSION}"))
        about_layout.addWidget(QLabel("一个带有记忆功能的 AI 编程助手"))
        about_layout.addWidget(QLabel("支持 Python/JS/Java/C++/Go/Rust 等"))
        layout.addWidget(about_group)
        
        # 按钮
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        if dialog.exec_() == QDialog.Accepted:
            self.ai_engine.save_config(
                api_key=api_key_input.text().strip(),
                api_url=api_url_input.text().strip(),
                model=model_input.text().strip()
            )
            if self.ai_engine.api_key:
                self.status_bar.showMessage("✅ API 配置已保存，已切换到在线模式", 3000)
            else:
                self.status_bar.showMessage("⚠️ 使用本地模式（未配置 API）", 3000)
    
    def clear_all_memories(self):
        """清除所有记忆"""
        reply = QMessageBox.question(
            self, "确认", "确定要清除所有记忆吗？此操作不可恢复！",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memories")
            conn.commit()
            conn.close()
            self.load_memories()
            self.status_bar.showMessage("🗑 已清除所有记忆", 3000)
    
    def export_memories(self):
        """导出记忆"""
        memories = self.db.get_all_memories()
        if not memories:
            QMessageBox.information(self, "提示", "没有记忆可导出")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出记忆", "memories.json", "JSON Files (*.json)"
        )
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(memories, f, indent=2, ensure_ascii=False)
            self.status_bar.showMessage(f"📤 已导出到: {file_path}", 3000)
    
    def auto_save(self):
        """自动保存"""
        if self.project_path:
            self.save_project_notes_auto()
    
    def closeEvent(self, event):
        """关闭事件"""
        self.auto_save()
        event.accept()


# ==================== 托盘图标 ====================
class SystemTray:
    """系统托盘支持"""
    
    def __init__(self, app, window):
        self.app = app
        self.window = window
        
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(window)
            self.tray.setIcon(window._create_icon())
            self.tray.setToolTip(APP_NAME)
            
            menu = QMenu()
            show_action = menu.addAction("显示主窗口")
            show_action.triggered.connect(window.show)
            hide_action = menu.addAction("隐藏")
            hide_action.triggered.connect(window.hide)
            menu.addSeparator()
            quit_action = menu.addAction("退出")
            quit_action.triggered.connect(app.quit)
            
            self.tray.setContextMenu(menu)
            self.tray.show()


# ==================== 主入口 ====================
def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    
    # 设置字体
    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    # 托盘
    tray = SystemTray(app, window)
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
