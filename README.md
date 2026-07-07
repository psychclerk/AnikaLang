# AnikaLang wxPython Edition

**A powerful, dynamically-typed scripting language with a massive standard library, native GUI framework, Machine Learning, RAG, and Office Document manipulation capabilities.**

![Version](https://img.shields.io/badge/version-1.1-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Functions](https://img.shields.io/badge/functions-470+-purple)

---

## 🌟 Overview

AnikaLang is a custom scripting language designed for rapid application development, data analysis, and desktop GUI creation. It features a clean, BASIC-like syntax combined with the power of Python's ecosystem. The v1.1 release introduces a fully modular **Plugin Architecture**, ensuring fast startup times and lazy-loading of heavy dependencies like NumPy, SciPy, and wxPython.

## ✨ Key Features

- **🧠 Custom Engine**: Lexer, Parser, AST, and Tree-walking Interpreter.
- **🔌 Plugin Architecture**: 13 modular plugins. Heavy dependencies are lazy-loaded only when needed.
- **🪟 Native GUI (wxPython)**: 100+ UI functions to build desktop apps (Windows, Layouts, Widgets, Code Editors, Rich Text, Grids).
- **🤖 AI & RAG**: Universal OpenAI-compatible client, PDF ingestion, intelligent chunking, and FAISS vector search.
- **📊 Data Science**: 30 Statistical functions, 22 Machine Learning models (scikit-learn), and 12 Matplotlib graph types.
- **📄 Office Automation**: Full manipulation of Word (DOCX), PowerPoint (PPTX), and Excel (XLSX/CSV) files.
- **🌐 Network & Media**: HTTP requests, SMTP/IMAP Email, Markdown/HTML conversion, and PDF export.
- **🗣️ Translation & TTS**: Google Translate integration and offline/online Text-to-Speech.
- **⚡ Compiler**: Transpile AnikaLang scripts directly to executable Python code.

---

## 📥 Download & Installation

A fully compiled standalone Windows executable is available in the **GitHub Releases / Assets**.

Because of the extensive feature set (wxPython, ML, RAG, Office Docs), the compiled package is large and has been split into **3 parts** to bypass GitHub's file size limits:

- `AnikaLangv1_1.7z.001`
- `AnikaLangv1_1.7z.002`
- `AnikaLangv1_1.7z.003`

### Installation Steps:
1. Download all three `.7z.*` files from the **Releases** section of this repository.
2. Place all three files in the exact same folder on your computer.
3. Download and install [7-Zip](https://www.7-zip.org/) if you haven't already.
4. Right-click on `AnikaLangv1_1.7z.001` and select **Extract Here** (7-Zip will automatically detect and combine the `.002` and `.003` parts).
5. Open the extracted folder. You will find a small `AnikaLang.exe` and an `_internal` folder containing all dependencies.
6. Double-click `AnikaLang.exe` to launch the IDE or select a script to run.

**No Python installation required!** Everything you need is bundled inside.

---

## 🚀 Usage

### 1. Launch the IDE
Double-click `AnikaLang.exe` or run it from the command line without arguments to open the built-in Professional IDE:
```bash
AnikaLang.exe
```

### 2. Run a Script Directly
Pass a `.fms` script file as an argument:
```bash
AnikaLang.exe path/to/your_script.fms
```

### 3. Compile to Python
Transpile your `.fms` script into a standalone `.py` file:
```bash
AnikaLang.exe --compile path/to/your_script.fms

COMPILER IS BROKEN
```

---

## 📂 Sample Projects

The `projects/` folder contains **23 fully functional sample applications** demonstrating the power of AnikaLang. You can run any of these by navigating to their folder and executing their main `.fms` file via the IDE or CLI.

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
| `ML`            | Machine learning tools                       |
| `notepad`       | Plain text editor                            |
| `rag`           | Retrieval-Augmented Generation application   |
| `REPL`          | Interactive REPL (Read-Eval-Print Loop)      |
| `stats`         | Statistics / data analysis                   |
| `tests`         | Test suite or testing application            |
| `timer`         | Timer / stopwatch                            |
| `timesheet`     | Timesheet tracker                            |
| `tts`           | Text-to-speech                               |
| `tutor`         | Tutoring / learning application              |

---

## 🏗️ Internal Architecture

The codebase is cleanly separated into a core engine and a plugin system:

```text
anika_lang/
├── main.py                 # CLI Entry point & execution runner
├── core/                   # Lexer, Parser, AST, Interpreter, Compiler
│   ├── errors.py
│   ├── lexer.py
│   ├── parser.py
│   ├── interpreter.py
│   └── plugin_manager.py
├── plugins/                # 13 Modular Plugins (Lazy-loaded)
│   ├── plugin_stdlib.py    # Math, String, Date, File, CSV, JSON
│   ├── plugin_ui.py        # wxPython GUI (100+ functions)
│   ├── plugin_stats.py     # Statistical Analysis
│   ├── plugin_ml.py        # Machine Learning (scikit-learn)
│   ├── plugin_graphs.py    # Matplotlib Graphing
│   ├── plugin_ai_rag.py    # AI API, RAG, FAISS, PDF processing
│   ├── plugin_docs.py      # DOCX & PPTX manipulation
│   ├── plugin_excel.py     # XLSX & CSV operations
│   └── ...
├── projects/               # 23 Sample Applications
└── docs/                   # HTML API Documentation
```

### Adding a New Plugin
Creating new functionality is incredibly easy. Simply create a new file in the `plugins/` directory (e.g., `plugin_myfeature.py`), inherit from `AnikaPlugin`, and implement the `register` method. The `PluginManager` will automatically discover and load it on the next run!

---

## 📖 Documentation

Complete API reference for all **470+ functions** and **40 categories** is available in the `docs/` folder.

- **Interactive HTML Docs**: Open `docs/documentation.html` in your browser. It features a dark theme, real-time search, and collapsible categories.
- **In-IDE Help**: Use the Help menu in the built-in IDE to open the documentation directly in your default browser.

---

## 📜 License

This project is licensed under the APACHE License. See the [LICENSE](LICENSE) file for details.

---

*Built with ❤️ using Python and wxPython.*

