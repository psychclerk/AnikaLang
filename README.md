# AnikaLang wxPython Edition

**A powerful, dynamically-typed scripting language with a massive standard library, native GUI framework, Machine Learning, RAG, and Office Document manipulation capabilities.**

![Version](https://img.shields.io/badge/version-1.2-blue)
![Python](https://img.shields.io/badge/python-3.12+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Functions](https://img.shields.io/badge/functions-470+-purple)

---

## 🌟 Overview

AnikaLang is a custom scripting language designed for rapid application development, data analysis, and desktop GUI creation. Version 1.2 introduces a **modernized syntax** with curly-brace blocks, `def` functions, and `=` assignment — while retaining the full power of Python's ecosystem through a modular **Plugin Architecture** with lazy-loading of heavy dependencies like NumPy, SciPy, and wxPython.

---

## 🆕 What's New in v1.2

### Modern Syntax Overhaul

AnikaLang 1.2 replaces the legacy BASIC-style syntax with a clean, C-family syntax:

| Concept | v1.1 (Legacy) | v1.2 (Current) |
|---------|---------------|----------------|
| Assignment | `SET x TO 10` | `x = 10` |
| Function | `FUNCTION name() ... END FUNCTION` | `def name() { ... }` |
| If/Else | `IF cond THEN ... ELSE ... END IF` | `if cond { ... } else { ... }` |
| While | `WHILE cond THEN ... END WHILE` | `while cond { ... }` |
| For (list) | `FOR x IN list THEN ... END FOR` | `for x in list { ... }` |
| For (range) | `FOR i IN [1..10] STEP 2 THEN ... END FOR` | `for i in 1..10 step 2 { ... }` |
| Try/Catch | `TRY ... CATCH err THEN ... END TRY` | `try { ... } catch err { ... }` |
| String concat | `"a" & "b" & "c"` | `rejoin("a", "b", "c")` or `"a" + "b"` |
| Booleans | `TRUE` / `FALSE` / `NULL` | `true` / `false` / `null` |
| Module import | *(not available)* | `include "module.fms"` |

### Additional v1.2 Features

- **`rejoin()`** — REBOL-style multi-argument string concatenation
- **`include`** — Load and execute external `.fms` modules
- **`eval_fms()`** — Dynamic code evaluation at runtime
- **`ui_code_editor`** — Scintilla-based code editor with live syntax highlighting
- **`ui_richtext`** — Full word-processor widget (bold, italic, tables, images, find/replace, print)
- **`ui_sheet`** — Spreadsheet grid with cell styling, events, and CSV import/export
- **`ui_tabs`** — Tabbed notebook with add/remove/select by name or index
- **`ui_statusbar`** — Multi-field status bar with per-field colors and borders
- **`ui_tree`** — Hierarchical tree control with expand/collapse
- **`ui_htmlview`** — Embedded web browser (Chromium via wx.html2)
- **`ui_md_editor`** — Side-by-side Markdown editor with live preview
- **`ui_after` / `ui_after_cancel`** — One-shot timers for delayed actions
- **`ui_bind`** — Universal event binding (click, change, select, resize, key press, etc.)
- **`ui_popup_menu`** — Right-click context menus
- **`ui_datepicker`** — Calendar date selection widget
- **DB FTS5** — SQLite full-text search with ranking
- **Joplin I/O** — Import/export Joplin `.jex` archives
- **Case-insensitive keywords** — `def`, `DEF`, and `Def` all work

---

## ✨ Key Features

- **🧠 Custom Engine**: Lexer, Parser, AST, and Tree-walking Interpreter with rich error reporting.
- **🔌 Plugin Architecture**: 13 modular plugins. Heavy dependencies are lazy-loaded only when needed.
- **🪟 Native GUI (wxPython)**: 150+ UI functions to build desktop apps (Windows, Layouts, Widgets, Code Editors, Rich Text, Grids, Trees, Tabs, Menus).
- **🤖 AI & RAG**: Universal OpenAI-compatible client, PDF ingestion, intelligent chunking, and FAISS vector search.
- **📊 Data Science**: 30 Statistical functions, 22 Machine Learning models (scikit-learn), and 12 Matplotlib graph types.
- **📄 Office Automation**: Full manipulation of Word (DOCX), PowerPoint (PPTX), and Excel (XLSX/CSV) files.
- **🌐 Network & Media**: HTTP requests, SMTP/IMAP Email, Markdown/HTML conversion, and PDF export.
- **🗣️ Translation & TTS**: Google Translate integration and offline/online Text-to-Speech.
- **🗄️ Database**: SQLite with full-text search (FTS5), file attachments, and CSV operations.
- **⚡ Compiler**: Transpile AnikaLang scripts directly to executable Python code.

---

## 📥 Download & Installation

AnikaLang 1.2 is now open sourced and can be downloaded as code. 

### Installation Steps:
1. Download the code.zip from the repo.
2. extract in a folder of your choice.
3. Download and install Python 3.12.
4. Run pip install requirements.txt.
5. Run python main.py path/to/your_script.fms 

---

### Compile to Python
Transpile your `.fms` script into a standalone `.py` file:
```bash
Python main.py --compile path/to/your_script.fms
```

> ⚠️ **Note:** The compiler is currently under active development and may not support all v1.2 syntax features.

---

## 📝 Quick Syntax Reference

### Hello World (GUI)
```anikalang
win = ui_window("Hello World", 400, 300)
lbl = ui_label(win, "Hello, AnikaLang 1.2!", 100, 130, 200, 30)
ui_font(lbl, 14, "Segoe UI", true)
ui_mainloop(win)
```

### Variables & Types
```anikalang
name = "Alice"
age = 30
height = 5.7
active = true
nothing = null

# Type checking
t = type_of(age)          # "INTEGER"

# Conversion
num = int("42")           # 42
pi_str = str(3.14159)     # "3.14159"
price = float("19.99")    # 19.99
```

### Strings
```anikalang
# Concatenation (two ways)
greeting = "Hello, " + name + "!"
message = rejoin("Score: ", str(score), " / ", str(total))

# Operations
upper("hello")            # "HELLO"
lower("HELLO")            # "hello"
len("hello")              # 5
mid("hello", 1, 3)        # "ell"
replace("hello", "l", "r") # "herro"
trim("  padded  ")        # "padded"
split("a,b,c", ",")       # ["a", "b", "c"]
```

### Control Flow
```anikalang
# If / Else (no ELSE IF — nest instead)
if score >= 90 {
    grade = "A"
} else {
    if score >= 80 {
        grade = "B"
    } else {
        grade = "C"
    }
}

# While loop
count = 1
while count <= 10 {
    total = total + count
    count = count + 1
}

# For loop (list)
fruits = ["apple", "banana", "cherry"]
for fruit in fruits {
    ui_alert(fruit)
}

# For loop (range with step)
for i in 0..100 step 10 {
    ui_alert(str(i))
}

# Break & Continue
for i in 1..100 {
    if i > 5 { break }
    if i == 3 { continue }
}
```

### Functions
```anikalang
def greet(name) {
    return rejoin("Hello, ", name, "!")
}

def factorial(n) {
    if n <= 1 { return 1 }
    return n * factorial(n - 1)
}

message = greet("Alice")   # "Hello, Alice!"
result = factorial(5)      # 120
```

### Error Handling
```anikalang
try {
    result = 10 / 0
} catch err {
    ui_alert(rejoin("Error: ", err))
}
```

### Lists & Dictionaries
```anikalang
# Lists
nums = [10, 20, 30, 40, 50]
first = nums[0]                    # 10
list_append(nums, 60)
list_set(nums, 0, 100)

# Dictionaries
person = {
    "name": "Alice",
    "age": 30,
    "city": "NYC"
}
name = person["name"]              # "Alice"
name = person.name                 # Same thing (dot access)
dict_set(person, "email", "a@b.com")
dict_has_key(person, "email")      # true
```

### GUI Counter App
```anikalang
count = 0
display = null

def increment() {
    count = count + 1
    ui_set(display, rejoin("Count: ", str(count)))
}

def reset() {
    count = 0
    ui_set(display, "Count: 0")
}

win = ui_window("Counter App", 300, 200)
display = ui_label(win, "Count: 0", 100, 30, 100, 30)
ui_font(display, 16, "Segoe UI", true)

btn_inc = ui_button(win, "Increment", "increment", 50, 90, 90, 35)
ui_color(btn_inc, "white", "#27ae60")

btn_reset = ui_button(win, "Reset", "reset", 160, 90, 90, 35)
ui_color(btn_reset, "white", "#e74c3c")

ui_mainloop(win)
```

### Modules
```anikalang
# Load an external module
include "utils.fms"

# Use functions defined in the module
result = my_utility_function(42)
```

---

## 📂 Sample Projects

The `projects/` folder contains **fully functional sample applications** demonstrating the power of AnikaLang. You can run any of these by navigating to their folder and executing their main `.fms` file via the IDE or CLI.

| Folder          | App/Module Description                       |
| --------------- | -------------------------------------------- |
| `blog`          | Blog editor / publishing app                 |
| `calc`          | Calculator                                   |
| `contacts`      | Contacts manager                             |
| `counter`       | Counter / tally app                          |
| `csv`           | CSV viewer/editor                            |
| `document`      | Document editor                              |
| `emr`           | Electronic Medical Record (EMR)              |
| `filemanager`   | File manager                                 |
| `form_designer` | Form designer / GUI builder                  |
| `game_theory`   | Game theory tools or simulations             |
| `ide`           | Integrated Development Environment           |
| `logbook`       | Logbook / journal                            |
| `markdown`      | Markdown editor                              |
| `rag`           | Retrieval-Augmented Generation application   |
| `REPL`          | Interactive REPL (Read-Eval-Print Loop)      |
| `stats`         | Statistics / data analysis (mock up)         |
| `tests`         | Test suite or testing application            |
| `timer`         | Timer / stopwatch                            |
| `timesheet`     | Timesheet tracker                            |
| `tts`           | Text-to-speech                               |
| `tutor`         | Interactive tutorial / learning application  |

---

## 🏗️ Internal Architecture

The codebase is cleanly separated into a core engine and a plugin system:

```text
anikalang_v1_2/
├── main.py                 # CLI Entry point & execution runner
├── core/                   # Lexer, Parser, AST, Interpreter, Compiler
│   ├── __init__.py
│   ├── ast_nodes.py        # 20 AST node types
│   ├── errors.py           # Rich error formatting & logging
│   ├── lexer.py            # Tokenizer (v1.2 keywords)
│   ├── parser.py           # Recursive-descent parser
│   ├── interpreter.py      # Tree-walking interpreter
│   ├── compiler.py         # AnikaLang → Python transpiler
│   ├── plugin_manager.py   # Auto-discovery & loading
│   └── utils.py            # Shared utilities (doc handles, paths)
├── plugins/                # 13 Modular Plugins (Lazy-loaded)
│   ├── base_plugin.py      # AnikaPlugin base class
│   ├── plugin_stdlib.py    # Math, String, Date, File, CSV, JSON, Regex, Clipboard
│   ├── plugin_ui.py        # wxPython GUI (150+ functions)
│   ├── plugin_stats.py     # Statistical Analysis (30 functions)
│   ├── plugin_ml.py        # Machine Learning (22 models, scikit-learn)
│   ├── plugin_graphs.py    # Matplotlib Graphing (12 chart types)
│   ├── plugin_ai_rag.py    # AI API, RAG, FAISS, PDF processing
│   ├── plugin_docs.py      # DOCX & PPTX manipulation
│   ├── plugin_excel.py     # XLSX & CSV operations
│   ├── plugin_db_files.py  # SQLite FTS5 & file attachments
│   ├── plugin_network.py   # HTTP, SMTP/IMAP Email
│   ├── plugin_media.py     # Markdown/HTML conversion, PDF export
│   ├── plugin_lang_voice.py # Translation & Text-to-Speech
│   └── plugin_joplin.py    # Joplin import/export
├── projects/               # 23 Sample Applications
└── docs/                   # HTML API Documentation
```

### Adding a New Plugin
Creating new functionality is incredibly easy. Simply create a new file in the `plugins/` directory (e.g., `plugin_myfeature.py`), inherit from `AnikaPlugin`, and implement the `register` method. The `PluginManager` will automatically discover and load it on the next run!

```python
# plugins/plugin_myfeature.py
from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction

class MyFeaturePlugin(AnikaPlugin):
    def register(self, env, interpreter):
        def my_function(i, a):
            return "Hello from my plugin!"

        env.define("MY_FUNCTION", NativeFunction("MY_FUNCTION", 0, my_function))
```

---

## 📖 Documentation

Complete API reference for all **470+ functions** and **40 categories** is available in the `docs/` folder.

- **Interactive HTML Docs**: Open `docs/documentation.html` in your browser. It features a dark theme, real-time search, and collapsible categories.
- **Beginner Tutorial**: Open `docs/tutorial.html` for a 15-lesson interactive guide from "Hello World" to building complete desktop apps.
- **In-IDE Help**: Use the Help menu in the built-in IDE to open the documentation directly in your default browser.

---

## 🔧 Dependencies (for development)

If running from source (not the compiled exe):

```bash
pip install wxPython          # GUI framework (required)
pip install numpy             # Math/ML (optional, lazy-loaded)
pip install scipy             # Advanced stats (optional, lazy-loaded)
pip install scikit-learn      # Machine learning (optional, lazy-loaded)
pip install matplotlib        # Graphing (optional, lazy-loaded)
pip install python-docx       # Word documents (optional, lazy-loaded)
pip install python-pptx       # PowerPoint (optional, lazy-loaded)
pip install openpyxl          # Excel (optional, lazy-loaded)
pip install faiss-cpu         # Vector search (optional, lazy-loaded)
pip install PyPDF2            # PDF processing (optional, lazy-loaded)
pip install deep-translator   # Translation (optional, lazy-loaded)
pip install gTTS              # Google TTS (optional, lazy-loaded)
pip install pyttsx3           # Offline TTS (optional, lazy-loaded)
pip install markdown          # Markdown conversion (optional, lazy-loaded)
pip install markdownify       # HTML to Markdown (optional, lazy-loaded)
```

All optional dependencies are **lazy-loaded** — the interpreter starts instantly and only imports a library when you first call a function that needs it.

---

## 📜 License

This project is licensed under the Apache License. See the [LICENSE](LICENSE) file for details.

---

*Built with ❤️ using Python and wxPython.*