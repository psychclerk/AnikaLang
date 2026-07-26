import sys
import os
import traceback

# Ensure the root directory is in sys.path so 'core' and 'plugins' can be imported
# --- PYINSTALLER COMPATIBILITY ---
# When compiled to an exe, files are extracted to a temporary _MEIPASS folder.
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
    
from core.errors import FMS_Error, show_error_dialog
from core.lexer import Lexer
from core.parser import Parser
from core.interpreter import Interpreter
from core.compiler import Compiler
from core.plugin_manager import PluginManager

def run_fms_code(code_text, source_path=None):
    """Lex, parse, load plugins, and interpret AnikaLang code."""
    try:
        lexer = Lexer(code_text)
    except FMS_Error as e:
        if e.source_file is None: e.source_file = source_path
        show_error_dialog("Syntax Error (Lexer)", str(e), source_file=e.source_file)
        raise
    except Exception as e:
        tb = traceback.format_exc()
        msg = f"Unexpected error during tokenization:\n{str(e)}"
        show_error_dialog("Internal Error (Lexer)", msg, source_file=source_path, traceback_str=tb)
        raise FMS_Error(msg, source_file=source_path)

    try:
        parser = Parser(lexer.tokens)
        ast = parser.parse()
    except FMS_Error as e:
        if e.source_file is None: e.source_file = source_path
        show_error_dialog("Syntax Error (Parser)", str(e), source_file=e.source_file)
        raise
    except Exception as e:
        tb = traceback.format_exc()
        msg = f"Unexpected error during parsing:\n{str(e)}"
        show_error_dialog("Internal Error (Parser)", msg, source_file=source_path, traceback_str=tb)
        raise FMS_Error(msg, source_file=source_path)

    # Initialize Interpreter and load all plugins
    interpreter = Interpreter()
    interpreter.set_source(code_text, source_file=source_path)
    
    plugins_dir = os.path.join(BASE_DIR, "plugins")
    plugin_manager = PluginManager(plugins_dir)
    plugin_manager.load_plugins(interpreter.environment, interpreter)
    
    # Execute the AST
    interpreter.interpret(ast)

def change_to_script_dir(script_path):
    """Change the working directory to the script's directory."""
    try:
        abs_path = os.path.abspath(script_path)
        s_dir = os.path.dirname(abs_path)
        if s_dir and os.path.isdir(s_dir):
            os.chdir(s_dir)
            return s_dir
    except Exception as e:
        print(f"Warning: Could not change to script directory: {e}")
    return None

if __name__ == "__main__":
    def handle_fatal_error(message, source_file=None, tb=None):
        show_error_dialog("AnikaLang Startup Error", message, source_file=source_file, traceback_str=tb)
        sys.exit(1)

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        # --- COMPILE MODE ---
        if arg == "--compile" and len(sys.argv) > 2:
            target_file = sys.argv[2]
            if not os.path.exists(target_file):
                handle_fatal_error(f"File not found: '{target_file}'", source_file=target_file)
            
            change_to_script_dir(target_file)
            
            try:
                with open(os.path.basename(target_file), 'r', encoding='utf-8') as f:
                    code_text = f.read()
                lexer = Lexer(code_text)
                parser = Parser(lexer.tokens)
                ast = parser.parse()
                compiler = Compiler()
                python_code = compiler.compile(ast)
                output_file = target_file.replace('.fms', '_compiled.py')
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(python_code)
                print(f"Successfully compiled '{target_file}' to '{output_file}'")
                print("You can now run it directly with: python " + output_file)
            except FMS_Error as e:
                handle_fatal_error(str(e), source_file=target_file)
            except Exception as e:
                tb = traceback.format_exc()
                handle_fatal_error(f"Compilation error: {str(e)}", source_file=target_file, tb=tb)
            sys.exit(0)
            
        # --- HELP MODE ---
        if arg in ("-h", "--help"):
            print("AnikaLang Interpreter (wxPython Edition)")
            print("Usage: python main.py <script.fms>              (Run script)")
            print("       python main.py --compile <script.fms>    (Compile to Python)")
            sys.exit(0)
            
        # --- RUN MODE (File passed as argument) ---
        if not os.path.exists(arg):
            handle_fatal_error(f"File not found: '{arg}'", source_file=os.path.abspath(arg))
            
        change_to_script_dir(arg)
        script_filename = os.path.basename(arg)
        
        try:
            with open(script_filename, 'r', encoding='utf-8') as f:
                code_text = f.read()
            print(f"Running AnikaLang script: {arg}")
            run_fms_code(code_text, source_path=os.path.abspath(arg))
            sys.exit(0)
        except FMS_Error:
            sys.exit(1)
        except UnicodeDecodeError as e:
            handle_fatal_error(f"File encoding error: {str(e)}\nPlease save the file as UTF-8.", source_file=os.path.abspath(arg))
        except PermissionError as e:
            handle_fatal_error(f"Permission denied: {str(e)}\nCheck file permissions.", source_file=os.path.abspath(arg))
        except Exception as e:
            tb = traceback.format_exc()
            handle_fatal_error(f"Error reading file '{arg}':\n{str(e)}", source_file=os.path.abspath(arg), tb=tb)
            
    else:
        # --- RUN MODE (No arguments -> Show File Dialog) ---
        print("No file specified. Opening file selection dialog...")
        try:
            import wx
            app = wx.App(False)
            with wx.FileDialog(None, "Select AnikaLang Script to Run", 
                               wildcard="FMS Scripts (*.fms)|*.fms|All Files|*.*", 
                               style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() == wx.ID_CANCEL:
                    print("No file selected. Exiting.")
                    sys.exit(0)
                file_path = dlg.GetPath()
                
            if file_path:
                change_to_script_dir(file_path)
                script_filename = os.path.basename(file_path)
                try:
                    with open(script_filename, 'r', encoding='utf-8') as f:
                        code_text = f.read()
                    print(f"Running AnikaLang script: {file_path}")
                    run_fms_code(code_text, source_path=os.path.abspath(file_path))
                    sys.exit(0)
                except FMS_Error:
                    sys.exit(1)
                except UnicodeDecodeError as e:
                    handle_fatal_error(f"File encoding error: {str(e)}\nPlease save the file as UTF-8.", source_file=os.path.abspath(file_path))
                except PermissionError as e:
                    handle_fatal_error(f"Permission denied: {str(e)}\nCheck file permissions.", source_file=os.path.abspath(file_path))
                except Exception as e:
                    tb = traceback.format_exc()
                    handle_fatal_error(f"Error reading file '{file_path}':\n{str(e)}", source_file=os.path.abspath(file_path), tb=tb)
            else:
                print("No file selected. Exiting.")
                sys.exit(0)
        except Exception as e:
            tb = traceback.format_exc()
            handle_fatal_error(f"Failed to open file dialog:\n{str(e)}", tb=tb)