import sys
import os
import datetime
import traceback
import ctypes

# ==============================================================================
# DPI AWARENESS (Windows)
# ==============================================================================
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ==============================================================================
# LOGGING UTILITIES
# ==============================================================================
def _get_log_path():
    """Get path for error log file."""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "anika_errors.log")

def log_error(error_type, message, source_file=None, traceback_str=None, include_chain=None):
    """Append an error entry to the log file with full context."""
    try:
        log_path = _get_log_path()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write(f"[{timestamp}] {error_type}\n")
            if source_file:
                f.write(f"[FILE] {source_file}\n")
            if include_chain:
                f.write("[INCLUDE CHAIN]\n")
                for i, file in enumerate(include_chain, 1):
                    f.write(f"   {i}. {file}\n")
            f.write("-" * 70 + "\n")
            f.write(f"{message}\n")
            if traceback_str:
                f.write("-" * 70 + "\n")
                f.write("PYTHON TRACEBACK:\n")
                f.write(traceback_str)
                f.write("\n")
            f.write("=" * 70 + "\n")
    except Exception:
        # Silently fail if logging fails (e.g., permission denied), 
        # but don't crash the app.
        pass

# ==============================================================================
# UI & CONSOLE ERROR DISPLAY
# ==============================================================================
def show_error_dialog(title, message, source_file=None, traceback_str=None):
    """
    Show error in UI dialog with copyable text box AND log to file.
    Falls back to console printing if wxPython is unavailable or fails.
    """
    # 1. Log the error first
    log_error(title, message, source_file=source_file, traceback_str=traceback_str)

    # 2. Build the full message for display/copying
    full_msg = str(message)
    if source_file:
        full_msg = f"File: {source_file}\n{full_msg}"
    if traceback_str:
        full_msg = full_msg + "\n--- Python Traceback ---\n" + traceback_str

    dialog_shown = False
    created_temp_app = False
    app = None

    try:
        import wx

        class ErrorDialog(wx.Dialog):
            def __init__(self, parent, title, display_message):
                super().__init__(parent, title=title,
                                 style=wx.DEFAULT_DIALOG_STYLE | wx.STAY_ON_TOP | wx.RESIZE_BORDER)
                self.display_message = display_message

                main_sizer = wx.BoxSizer(wx.VERTICAL)

                # Header with icon
                header_sizer = wx.BoxSizer(wx.HORIZONTAL)
                error_icon = wx.StaticBitmap(self, bitmap=wx.ArtProvider.GetBitmap(wx.ART_ERROR, wx.ART_MESSAGE_BOX))
                header_label = wx.StaticText(self, label="An error occurred:")
                header_label.SetFont(wx.Font(wx.FontInfo(11).Bold()))
                header_sizer.Add(error_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                header_sizer.Add(header_label, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
                main_sizer.Add(header_sizer, 0, wx.LEFT | wx.TOP | wx.RIGHT, 10)

                # Copyable text box (shows the FULL message including traceback)
                self.text_ctrl = wx.TextCtrl(
                    self,
                    value=display_message,
                    style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH | wx.TE_DONTWRAP
                )
                self.text_ctrl.SetMinSize(wx.Size(600, 250))
                self.text_ctrl.SetFont(wx.Font(9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
                main_sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 10)

                # Buttons
                button_sizer = self.CreateButtonSizer(wx.NO_DEFAULT)
                self.copy_btn = wx.Button(self, label="Copy to Clipboard")
                self.copy_btn.Bind(wx.EVT_BUTTON, self.on_copy)
                self.ok_btn = wx.Button(self, id=wx.ID_OK, label="OK")
                self.ok_btn.SetDefault()
                button_sizer.AddStretchSpacer()
                button_sizer.Add(self.copy_btn, 0, wx.RIGHT, 5)
                button_sizer.Add(self.ok_btn, 0)
                main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

                self.SetSizerAndFit(main_sizer)
                self.CentreOnScreen()

                # Select all text for easy copying
                self.text_ctrl.SetSelection(-1, -1)
                self.text_ctrl.SetFocus()

            def on_copy(self, event):
                if wx.TheClipboard.Open():
                    wx.TheClipboard.SetData(wx.TextDataObject(self.display_message))
                    wx.TheClipboard.Close()
                    self.copy_btn.SetLabel("Copied!")
                    wx.CallLater(1500, self._reset_copy_label)
                event.Skip()

            def _reset_copy_label(self):
                if self.copy_btn:
                    self.copy_btn.SetLabel("Copy to Clipboard")

        app = wx.GetApp()
        if app is None:
            app = wx.App(False)
            created_temp_app = True

        dlg = ErrorDialog(None, title, full_msg)
        dlg.ShowModal()
        dlg.Destroy()
        dialog_shown = True

    except Exception as e:
        print(f"[AnikaLang] Dialog creation failed: {e}")

    # Clean up temporary app if we created one and there are no other windows
    if created_temp_app and app is not None:
        try:
            import wx
            has_main_window = any(tlw is not None for tlw in wx.GetTopLevelWindows())
            if not has_main_window:
                try:
                    app.ExitMainLoop()
                except Exception:
                    pass
        except Exception:
            pass

    # Fallback to console if dialog failed to show
    if not dialog_shown:
        print(f"\n{'='*70}")
        print(f"ERROR: {title}")
        print(f"{'='*70}")
        print(full_msg)  # <-- FIXED: Print the full message, not just the base message
        print(f"{'='*70}\n")

# ==============================================================================
# CUSTOM EXCEPTION CLASS
# ==============================================================================
class FMS_Error(Exception):
    """Custom exception for AnikaLang with rich formatting support."""
    
    def __init__(self, message, line=None, col=None, error_type="Runtime Error",
                 source_line=None, source_file=None):
        self.message = str(message)
        self.line = line
        self.col = col
        self.error_type = error_type
        self.source_line = source_line
        self.source_file = source_file
        
        # Format immediately so str(e) returns the rich version
        self.formatted_msg = self._format_message()
        super().__init__(self.formatted_msg)

    def _format_message(self):
        loc = ""
        if self.source_file:
            loc += f" in '{self.source_file}'"
        if self.line is not None:
            loc += f" at line {self.line}"
        if self.col is not None:
            loc += f", col {self.col}"
        
        error_str = f"[{self.error_type}]{loc}:\n{self.message}"
        
        if self.source_line:
            # Clean the source line of trailing whitespace/newlines for clean display
            clean_line = self.source_line.rstrip('\n\r')
            error_str += f"\n--> {clean_line}"
            
            # Add pointer caret (^) under the specific column
            if self.col is not None and self.col > 0:
                # Ensure pointer doesn't exceed line length
                pointer_col = min(self.col - 1, len(clean_line))
                pointer = " " * pointer_col + "^"
                error_str += f"\n{pointer}"
                
        return error_str

    def __str__(self):
        return self.formatted_msg