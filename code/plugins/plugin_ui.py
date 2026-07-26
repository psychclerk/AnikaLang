import wx
import wx.stc as stc
import wx.grid as gridlib
import wx.html2
import wx.adv
import wx.richtext as richtext
import re
import os
import datetime

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction, Callable
from core.errors import FMS_Error
from core.utils import _path_to_file_url

class UIPlugin(AnikaPlugin):
    def register(self, env, interpreter):
        # ==========================================================================
        # ==========================================================================
        # UI HELPER FUNCTIONS
        # ==========================================================================
        def _parse_pos_args(a, start_idx):
            coords = [None, None, None, None]
            count = len(a) - start_idx
            if count >= 4: coords = [a[start_idx], a[start_idx+1], a[start_idx+2], a[start_idx+3]]
            elif count == 3: coords = [a[start_idx], a[start_idx+1], a[start_idx+2], None]
            elif count == 2: coords = [a[start_idx], a[start_idx+1], None, None]
            return coords

        def _apply_layout(parent, widget, coords):
            x, y, w, h = coords
            if x is not None and y is not None:
                widget.SetPosition(wx.Point(int(x), int(y)))
                if w is not None and h is not None: widget.SetSize(wx.Size(int(w), int(h)))
                elif w is not None: widget.SetSize(wx.Size(int(w), widget.GetBestSize().height))
            else:
                sizer = getattr(parent, '_anika_sizer', None)
                if sizer is not None:
                    sizer.Add(widget, 0, wx.ALL | wx.EXPAND, 5)
                    parent.Layout()
            return widget

        def _to_wx_color(color_str):
            if color_str is None: return None
            s = str(color_str).strip()
            if not s: return None
            try: return wx.Colour(s)
            except: return None

        def _call_anika(i, name, args=None):
            if args is None: args = []
            try:
                fn = i.environment.get(name)
                if isinstance(fn, Callable): return fn.call(i, args)
            except FMS_Error as e:
                wx.MessageBox(str(e), "FMS Error", wx.OK | wx.ICON_ERROR)
            return None

        # ==========================================================================
        # WINDOW & LIFECYCLE
        # ==========================================================================
        def ui_window(i, a):
            if not hasattr(i, 'wx_app') or i.wx_app is None: i.wx_app = wx.App(False)
            title = str(a[0]) if len(a) > 0 else "AnikaLang"
            w = int(a[1]) if len(a) > 1 and a[1] else 800
            h = int(a[2]) if len(a) > 2 and a[2] else 600
            frame = wx.Frame(None, title=title, size=(w, h))
            panel = wx.Panel(frame)
            frame._anika_panel = panel
            frame._anika_sizer = None
            frame_sizer = wx.BoxSizer(wx.VERTICAL)
            frame_sizer.Add(panel, 1, wx.EXPAND)
            frame.SetSizer(frame_sizer)
            frame.Layout()
            i.main_window = frame
            
            def on_close(evt):
                # Close any popup windows first
                for tlw in wx.GetTopLevelWindows():
                    if tlw is not frame:
                        try: tlw.Close()
                        except Exception: pass
                frame.Destroy()
            frame.Bind(wx.EVT_CLOSE, on_close)
            frame.Show()
            return frame

        def ui_popup(i, a):
            parent = getattr(i, 'main_window', None)
            if parent is None: raise FMS_Error("UI_POPUP requires UI_WINDOW first")
            title = str(a[0])
            w = int(a[1]) if len(a) > 1 and a[1] else 500
            h = int(a[2]) if len(a) > 2 and a[2] else 400
            dlg = wx.Frame(parent, title=title, size=(w, h))
            panel = wx.Panel(dlg)
            dlg._anika_panel = panel
            dlg._anika_sizer = None
            dlg_sizer = wx.BoxSizer(wx.VERTICAL)
            dlg_sizer.Add(panel, 1, wx.EXPAND)
            dlg.SetSizer(dlg_sizer)
            dlg.Layout()
            dlg.Show()
            return dlg

        def ui_close(i, a):
            w = a[0]
            if w is None: return None
            try:
                if isinstance(w, wx.Window):
                    top = w.GetTopLevelParent()
                    if top is not None:
                        top.IsBeingDeleted()
                        top.Close()
            except RuntimeError: pass
            except Exception: pass
            return None

        def ui_mainloop(i, a):
            if hasattr(i, 'wx_app') and i.wx_app:
                i.wx_app.SetExitOnFrameDelete(True)   # <-- ADD THIS LINE
                i.wx_app.MainLoop()
            return None

        env.define("UI_WINDOW", NativeFunction("UI_WINDOW", -1, ui_window))
        env.define("UI_POPUP", NativeFunction("UI_POPUP", -1, ui_popup))
        env.define("UI_CLOSE", NativeFunction("UI_CLOSE", 1, ui_close))
        env.define("UI_MAINLOOP", NativeFunction("UI_MAINLOOP", 1, ui_mainloop))

        # ==========================================================================
        # LAYOUT PRIMITIVES
        # ==========================================================================
        def ui_panel(i, a):
            parent = a[0]
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            panel = wx.Panel(target)
            coords = _parse_pos_args(a, 1)
            _apply_layout(target, panel, coords)
            return panel

        def ui_sizer(i, a):
            parent = a[0]
            stype = str(a[1]).upper() if len(a) > 1 else "VERTICAL"
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            if stype == "HORIZONTAL": sizer = wx.BoxSizer(wx.HORIZONTAL)
            elif stype == "GRID":
                cols = int(a[2]) if len(a) > 2 else 2
                sizer = wx.GridSizer(cols, 5, 5)
            elif stype == "FLEX_GRID":
                cols = int(a[2]) if len(a) > 2 else 2
                sizer = wx.FlexGridSizer(cols, 5, 5)
                sizer.AddGrowableCol(0, 1)
            else: sizer = wx.BoxSizer(wx.VERTICAL)
            target.SetSizer(sizer)
            target._anika_sizer = sizer
            return sizer

        def ui_add(i, a):
            sizer, widget = a[0], a[1]
            prop = int(a[2]) if len(a) > 2 and a[2] else 0
            flag_str = str(a[3]).upper() if len(a) > 3 and a[3] else "ALL"
            border = int(a[4]) if len(a) > 4 and a[4] else 5
            flag = 0
            for part in flag_str.replace(",", "|").split("|"):
                part = part.strip()
                if part == "EXPAND": flag |= wx.EXPAND
                elif part == "CENTER": flag |= wx.ALIGN_CENTER
                elif part == "LEFT": flag |= wx.LEFT
                elif part == "RIGHT": flag |= wx.RIGHT
                elif part == "TOP": flag |= wx.TOP
                elif part == "BOTTOM": flag |= wx.BOTTOM
                elif part == "ALL": flag |= wx.ALL
            if not flag: flag = wx.ALL
            if isinstance(sizer, wx.Sizer):
                sizer.Add(widget, prop, flag, border)
                if widget.GetParent(): widget.GetParent().Layout()
            return None

        def ui_pos(i, a):
            widget = a[0]
            x, y = int(a[1]), int(a[2])
            w = int(a[3]) if len(a) > 3 and a[3] else None
            h = int(a[4]) if len(a) > 4 and a[4] else None
            if isinstance(widget, wx.Window):
                widget.SetPosition(wx.Point(x, y))
                if w is not None and h is not None: widget.SetSize(wx.Size(w, h))
            return None

        def ui_refresh(i, a):
            w = a[0]
            if isinstance(w, wx.Window):
                try: w.Refresh(); w.Update()
                except Exception: pass
            return None

        def ui_layout_abs(i, a):
            win = a[0]
            target = win._anika_panel if hasattr(win, '_anika_panel') else win
            if hasattr(target, '_anika_sizer'): target._anika_sizer = None; target.SetSizer(None)
            return None

        def ui_layout_refresh(i, a):
            w = a[0]
            if isinstance(w, wx.Window):
                try: w.Layout(); w.Refresh(); w.Update()
                except Exception: pass
            return None

        def ui_get_pos(i, a):
            w = a[0]
            if isinstance(w, wx.Window): pos = w.GetPosition(); return [pos.x, pos.y]
            return [0, 0]

        def ui_get_size(i, a):
            w = a[0]
            if isinstance(w, wx.Window): sz = w.GetSize(); return [sz.width, sz.height]
            return [0, 0]

        def ui_destroy(i, a):
            w = a[0]
            if isinstance(w, wx.Window): w.Hide(); w.Destroy()
            return None

        def ui_bring_to_front(i, a):
            w = a[0]
            if isinstance(w, wx.Window): w.Raise()
            return None

        def ui_font(i, a):
            w = a[0]
            size = int(a[1]) if len(a) > 1 else 10
            face = str(a[2]) if len(a) > 2 and a[2] else "Segoe UI"
            bold = bool(a[3]) if len(a) > 3 else False
            if isinstance(w, wx.Window):
                weight = wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
                f = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, weight, faceName=face)
                w.SetFont(f); w.Refresh()
            return None

        env.define("UI_PANEL", NativeFunction("UI_PANEL", -1, ui_panel))
        env.define("UI_SIZER", NativeFunction("UI_SIZER", -1, ui_sizer))
        env.define("UI_ADD", NativeFunction("UI_ADD", -1, ui_add))
        env.define("UI_POS", NativeFunction("UI_POS", -1, ui_pos))
        env.define("UI_REFRESH", NativeFunction("UI_REFRESH", 1, ui_refresh))
        env.define("UI_LAYOUT_ABS", NativeFunction("UI_LAYOUT_ABS", 1, ui_layout_abs))
        env.define("UI_LAYOUT_REFRESH", NativeFunction("UI_LAYOUT_REFRESH", 1, ui_layout_refresh))
        env.define("UI_GET_POS", NativeFunction("UI_GET_POS", 1, ui_get_pos))
        env.define("UI_GET_SIZE", NativeFunction("UI_GET_SIZE", 1, ui_get_size))
        env.define("UI_DESTROY", NativeFunction("UI_DESTROY", 1, ui_destroy))
        env.define("UI_BRING_TO_FRONT", NativeFunction("UI_BRING_TO_FRONT", 1, ui_bring_to_front))
        env.define("UI_FONT", NativeFunction("UI_FONT", -1, ui_font))
        
        # ==========================================================================
        # MISSING GENERAL UI FUNCTIONS (Show/Hide, Enable/Disable, Cursor, Tooltip)
        # ==========================================================================
        def ui_show(i, a):
            w = a[0]
            if isinstance(w, wx.Window): w.Show()
            return None

        def ui_hide(i, a):
            w = a[0]
            if isinstance(w, wx.Window): w.Hide()
            return None

        def ui_enable(i, a):
            w = a[0]
            state = bool(a[1]) if len(a) > 1 else True
            if isinstance(w, wx.Window): w.Enable(state)
            return None

        def ui_disable(i, a):
            w = a[0]
            if isinstance(w, wx.Window): w.Enable(False)
            return None

        def ui_cursor(i, a):
            w = a[0]
            cursor_type = str(a[1]).upper() if len(a) > 1 else "ARROW"
            if not isinstance(w, wx.Window): return None
            
            cursor_map = {
                "ARROW": wx.CURSOR_ARROW,
                "WAIT": wx.CURSOR_WAIT,
                "IBEAM": wx.CURSOR_IBEAM,
                "HAND": wx.CURSOR_HAND,
                "CROSS": wx.CURSOR_CROSS,
                "SIZENWSE": wx.CURSOR_SIZENWSE,
                "SIZENESW": wx.CURSOR_SIZENESW
            }
            wx_cursor = cursor_map.get(cursor_type, wx.CURSOR_ARROW)
            w.SetCursor(wx.Cursor(wx_cursor))
            return None

        def ui_tooltip(i, a):
            w, text = a[0], str(a[1])
            if isinstance(w, wx.Window):
                w.SetToolTip(wx.ToolTip(text))
            return None

        # --- Register the new functions ---
        env.define("UI_SHOW", NativeFunction("UI_SHOW", 1, ui_show))
        env.define("UI_HIDE", NativeFunction("UI_HIDE", 1, ui_hide))
        env.define("UI_ENABLE", NativeFunction("UI_ENABLE", -1, ui_enable))
        env.define("UI_DISABLE", NativeFunction("UI_DISABLE", 1, ui_disable))
        env.define("UI_CURSOR", NativeFunction("UI_CURSOR", -1, ui_cursor))
        env.define("UI_TOOLTIP", NativeFunction("UI_TOOLTIP", 2, ui_tooltip))

        # ==========================================================================
        # BASIC WIDGETS
        # ==========================================================================
        def ui_label(i, a):
            parent, text = a[0], str(a[1])
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            lbl = wx.StaticText(target, label=text)
            coords = _parse_pos_args(a, 2); _apply_layout(target, lbl, coords)
            return lbl

        def ui_entry(i, a):
            parent = a[0]
            text = str(a[1]) if len(a) > 1 and a[1] else ""
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            ent = wx.TextCtrl(target, value=text)
            coords = _parse_pos_args(a, 2); _apply_layout(target, ent, coords)
            return ent

        def ui_button(i, a):
            parent, text, action = a[0], str(a[1]), str(a[2])
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            btn = wx.Button(target, label=text)
            def handler(evt): _call_anika(i, action, [])
            btn.Bind(wx.EVT_BUTTON, handler)
            coords = _parse_pos_args(a, 3); _apply_layout(target, btn, coords)
            return btn

        def ui_button_set_state(i, a):
            btn, state = a[0], str(a[1]).upper()
            if isinstance(btn, wx.Button): btn.Enable(state not in ("DISABLED", "FALSE", "0"))
            return None

        def ui_text(i, a):
            parent = a[0]
            text = str(a[1]) if len(a) > 1 and a[1] else ""
            wrap, coord_start = False, 2
            if len(a) > 2:
                third_arg = a[2]
                if isinstance(third_arg, bool): wrap = third_arg; coord_start = 3
                elif isinstance(third_arg, str) and third_arg.upper() in ("TRUE", "FALSE", "YES", "NO", "1", "0"):
                    wrap = third_arg.upper() in ("TRUE", "YES", "1"); coord_start = 3
            style = wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.TE_NOHIDESEL if wrap else wx.TE_MULTILINE | wx.HSCROLL | wx.TE_NOHIDESEL
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            txt = wx.TextCtrl(target, value=text, style=style)
            coords = _parse_pos_args(a, coord_start)
            x, y, w, h = coords
            if wrap and w is not None and h is not None:
                if not hasattr(parent, '_anika_text_sizer'):
                    parent_sizer = wx.BoxSizer(wx.VERTICAL); parent.SetSizer(parent_sizer); parent._anika_text_sizer = parent_sizer
                txt.SetPosition(wx.Point(int(x), int(y))); txt.SetSize(wx.Size(int(w), int(h))); txt.SetMaxSize(wx.Size(int(w), int(h)))
            else: _apply_layout(target, txt, coords)
            return txt

        def ui_text_get(i, a):
            w = a[0]
            if w is None: raise FMS_Error("UI_TEXT_GET received a NULL widget.")
            if isinstance(w, stc.StyledTextCtrl): return w.GetText()
            if isinstance(w, wx.TextCtrl): return w.GetValue()
            return ""

        def ui_text_append(i, a):
            widget, text = a[0], str(a[1])
            if isinstance(widget, wx.TextCtrl): widget.AppendText(text); widget.ShowPosition(widget.GetLastPosition())
            elif hasattr(widget, 'AppendText'): widget.AppendText(text)
            return None

        def ui_text_set(i, a):
            w = a[0]; v = str(a[1]) if len(a) > 1 else ""
            if w is None: raise FMS_Error("UI_TEXT_SET received a NULL widget.")
            if isinstance(w, stc.StyledTextCtrl): w.SetText(v); return None
            if isinstance(w, wx.TextCtrl): w.SetValue(v); return None
            return None

        def ui_text_highlight(i, a): return None

        def ui_text_get_selection(i, a):
            w = a[0]
            if isinstance(w, wx.TextCtrl):
                f, t = w.GetSelection(); return w.GetRange(f, t) if f != t else ""
            if isinstance(w, stc.StyledTextCtrl):
                f, t = w.GetSelection(); return w.GetTextRange(f, t) if f != t else ""
            return ""

        def ui_text_delete_selection(i, a):
            w = a[0]
            if isinstance(w, wx.TextCtrl):
                f, t = w.GetSelection()
                if f != t: w.Remove(f, t)
            elif isinstance(w, stc.StyledTextCtrl):
                f, t = w.GetSelection()
                if f != t: w.Clear()
            return None

        def ui_text_insert_at_cursor(i, a):
            w, text = a[0], str(a[1])
            if isinstance(w, wx.TextCtrl):
                f, t = w.GetSelection()
                if f != t: w.Remove(f, t)
                w.WriteText(text)
            elif isinstance(w, stc.StyledTextCtrl): w.ReplaceSelection(text)
            return None

        def ui_text_select_all(i, a):
            w = a[0]
            if isinstance(w, wx.TextCtrl): w.SetSelection(-1, -1)
            elif isinstance(w, stc.StyledTextCtrl): w.SelectAll()
            return None

        def ui_text_find(i, a):
            w, s = a[0], str(a[1])
            if not s: return ""
            if isinstance(w, wx.TextCtrl):
                text = w.GetValue(); f, t = w.GetSelection(); pos = text.find(s, t)
                if pos == -1: pos = text.find(s)
                if pos != -1: w.SetSelection(pos, pos + len(s)); return str(pos)
            elif isinstance(w, stc.StyledTextCtrl):
                w.SetTargetStart(w.GetCurrentPos()); w.SetTargetEnd(w.GetTextLength()); w.SetSearchFlags(0)
                pos = w.SearchInTarget(s)
                if pos == -1: w.SetTargetStart(0); w.SetTargetEnd(w.GetCurrentPos()); pos = w.SearchInTarget(s)
                if pos != -1: w.SetSelection(pos, pos + len(s)); w.EnsureCaretVisible(); w.SetFocus(); return str(pos)
            return ""

        def ui_text_replace_selected(i, a):
            w, new = a[0], str(a[1])
            if isinstance(w, wx.TextCtrl):
                f, t = w.GetSelection()
                if f != t: w.Remove(f, t); w.WriteText(new); w.SetSelection(f, f + len(new))
            elif isinstance(w, stc.StyledTextCtrl):
                f, t = w.GetSelection()
                if f != t: w.ReplaceSelection(new); w.SetSelection(f, f + len(new))
            return None

        def ui_text_cut(i, a):
            w = a[0]
            if isinstance(w, (wx.TextCtrl, stc.StyledTextCtrl)): w.Cut()
            return None
        def ui_text_copy(i, a):
            w = a[0]
            if isinstance(w, (wx.TextCtrl, stc.StyledTextCtrl)): w.Copy()
            return None
        def ui_text_paste(i, a):
            w = a[0]
            if isinstance(w, (wx.TextCtrl, stc.StyledTextCtrl)): w.Paste()
            return None
        def ui_text_undo(i, a):
            w = a[0]
            if isinstance(w, stc.StyledTextCtrl) and w.CanUndo(): w.Undo()
            elif isinstance(w, wx.TextCtrl) and w.CanUndo(): w.Undo()
            return None
        def ui_text_redo(i, a):
            w = a[0]
            if isinstance(w, stc.StyledTextCtrl) and w.CanRedo(): w.Redo()
            elif isinstance(w, wx.TextCtrl) and w.CanRedo(): w.Redo()
            return None

        env.define("UI_LABEL", NativeFunction("UI_LABEL", -1, ui_label))
        env.define("UI_ENTRY", NativeFunction("UI_ENTRY", -1, ui_entry))
        env.define("UI_BUTTON", NativeFunction("UI_BUTTON", -1, ui_button))
        env.define("UI_BUTTON_SET_STATE", NativeFunction("UI_BUTTON_SET_STATE", 2, ui_button_set_state))
        env.define("UI_TEXT", NativeFunction("UI_TEXT", -1, ui_text))
        env.define("UI_TEXT_GET", NativeFunction("UI_TEXT_GET", 1, ui_text_get))
        env.define("UI_TEXT_APPEND", NativeFunction("UI_TEXT_APPEND", 2, ui_text_append))
        env.define("UI_TEXT_SET", NativeFunction("UI_TEXT_SET", -1, ui_text_set))
        env.define("UI_TEXT_HIGHLIGHT", NativeFunction("UI_TEXT_HIGHLIGHT", -1, ui_text_highlight))
        env.define("UI_TEXT_GET_SELECTION", NativeFunction("UI_TEXT_GET_SELECTION", 1, ui_text_get_selection))
        env.define("UI_TEXT_DELETE_SELECTION", NativeFunction("UI_TEXT_DELETE_SELECTION", 1, ui_text_delete_selection))
        env.define("UI_TEXT_INSERT_AT_CURSOR", NativeFunction("UI_TEXT_INSERT_AT_CURSOR", 2, ui_text_insert_at_cursor))
        env.define("UI_TEXT_SELECT_ALL", NativeFunction("UI_TEXT_SELECT_ALL", 1, ui_text_select_all))
        env.define("UI_TEXT_FIND", NativeFunction("UI_TEXT_FIND", 2, ui_text_find))
        env.define("UI_TEXT_REPLACE_SELECTED", NativeFunction("UI_TEXT_REPLACE_SELECTED", 2, ui_text_replace_selected))
        env.define("UI_TEXT_CUT", NativeFunction("UI_TEXT_CUT", 1, ui_text_cut))
        env.define("UI_TEXT_COPY", NativeFunction("UI_TEXT_COPY", 1, ui_text_copy))
        env.define("UI_TEXT_PASTE", NativeFunction("UI_TEXT_PASTE", 1, ui_text_paste))
        env.define("UI_TEXT_UNDO", NativeFunction("UI_TEXT_UNDO", 1, ui_text_undo))
        env.define("UI_TEXT_REDO", NativeFunction("UI_TEXT_REDO", 1, ui_text_redo))

        # ==========================================================================
        # CASE-INSENSITIVE KEYWORD HELPER
        # ==========================================================================
        def _make_case_insensitive(word_list):
            """Takes a space-separated string of words and returns a string with 
            upper, lower, and capitalized versions for case-insensitive highlighting."""
            words = word_list.split()
            combined = set()
            for w in words:
                combined.add(w.upper())
                combined.add(w.lower())
                combined.add(w.capitalize())
            return " ".join(combined)

        # ==========================================================================
        # CODE EDITOR (Scintilla)
        # ==========================================================================
        def ui_code_editor(i, a):
            parent = a[0]
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            ed = stc.StyledTextCtrl(target, style=wx.BORDER_NONE)
            
            # Base Styles
            ed.StyleSetBackground(stc.STC_STYLE_DEFAULT, wx.Colour(250, 249, 246))
            ed.StyleSetForeground(stc.STC_STYLE_DEFAULT, wx.Colour(45, 45, 45))

            ed.StyleSetBackground(stc.STC_STYLE_LINENUMBER, wx.Colour(242, 241, 238))
            ed.StyleSetForeground(stc.STC_STYLE_LINENUMBER, wx.Colour(130, 130, 130))

            ed.SetCaretForeground(wx.Colour(40, 40, 40))
            ed.SetSelBackground(True, wx.Colour(202, 225, 255))
            ed.StyleClearAll()    
            # --- Lexer Setup ---
            ed.SetLexer(stc.STC_LEX_PYTHON)
            
            # Keyword Set 0: Language Keywords (Blue, Bold)
            # Updated for Phase 1: lowercase, 'def' instead of 'FUNCTION', removed 'SET/TO/THEN/END'
            keywords = "def if else for in while break continue try catch return true false null and or not step include"
            ed.SetKeyWords(0, _make_case_insensitive(keywords))
            
            # Keyword Set 1: Built-in Functions (Purple)
            # Updated for Phase 1: lowercase snake_case
            # Keyword Set 1: Built-in Functions (Purple) - Converted to lowercase for case-insensitive matching
            builtin_functions = (
                "ai_init ai_chat ai_embed ai_list_models rag_init rag_ingest_pdf rag_query rag_get_stats rag_clear "
                "rag_delete_cache rag_ingest_text rag_query_multi db_fts_create db_fts_search db_fts_update "
                "attachment_save attachment_path attachment_delete attachment_list docx_create docx_open docx_save "
                "docx_close docx_add_paragraph docx_add_heading docx_add_bullet docx_add_numbered docx_add_page_break "
                "docx_add_table docx_add_image docx_get_text docx_get_paragraphs docx_replace_text docx_set_header "
                "docx_set_footer docx_set_title docx_set_author docx_get_metadata docx_to_text pptx_create pptx_open "
                "pptx_save pptx_close pptx_add_title_slide pptx_add_slide pptx_add_content_slide pptx_add_text_box "
                "pptx_add_image pptx_add_table pptx_get_slide_count pptx_get_text pptx_get_slides_text "
                "pptx_delete_slide pptx_set_slide_bg pptx_to_pdf pptx_add_notes excel_read excel_write excel_append "
                "excel_sheets xlsx_format_cell xlsx_merge_cells xlsx_set_column_width xlsx_add_formula xlsx_add_chart "
                "xlsx_get_cell xlsx_set_cell xlsx_to_csv csv_to_xlsx graph_line graph_save graph_show graph_close "
                "graph_bar graph_scatter graph_histogram graph_pie graph_box graph_heatmap graph_multi_line "
                "graph_regression_line joplin_export joplin_import translate translate_detect translate_batch "
                "translate_languages translate_to_english tts_speak tts_save tts_save_offline tts_play_file md_to_html "
                "html_to_md markdown_to_html html_to_text export_pdf ml_train_test_split ml_standardize "
                "ml_label_encode ml_knn ml_decision_tree ml_random_forest ml_logistic ml_svm ml_linear_regression "
                "ml_polynomial_regression ml_ridge ml_lasso ml_kmeans ml_dbscan ml_pca ml_predict ml_accuracy "
                "ml_confusion_matrix ml_classification_report ml_r2_score ml_mse ml_mae http_post http_post_headers "
                "http_get_headers email_send email_fetch stats_describe stats_mean stats_median stats_variance "
                "stats_stdev stats_mode stats_percentile stats_quartiles stats_skewness stats_kurtosis stats_frequency "
                "stats_crosstab stats_ttest_1sample stats_ttest_ind stats_ttest_paired stats_anova stats_chisquare "
                "stats_chisquare_indep stats_correlation stats_spearman stats_regression stats_mannwhitney "
                "stats_wilcoxon stats_kruskal stats_zscore stats_clean stats_recode stats_group_by stats_bin "
                "stats_report eval_fms eval_fms_silent is_error error_message list_variables type_of regex_match "
                "regex_search regex_replace regex_findall abs round rand pow exp ln log10 floor ceil pi e sin cos tan "
                "asin acos atan deg_to_rad rad_to_deg min max sum avg fact comb perm randint sqrt upper lower trim "
                "join len replace left right mid split starts_with ends_with contains index_of now date calc_duration "
                "to_indian_date to_iso_datetime to_indian_datetime int float str iif dict_keys dict_values "
                "dict_entries dict_merge dict_has_key dict_set dict_remove list_set list_append list_remove "
                "list_contains db_connect db_execute db_query file_read file_read_base64 file_write file_append "
                "file_exists exec file_to_url path_join path_dir path_file path_ext path_name path_cwd path_abs "
                "path_norm path_mkdir path_isdir path_isfile path_list file_delete file_rename file_size csv_read "
                "csv_write interpreter_path http_get html_escape base64_encode base64_decode json_parse json_stringify "
                "clipboard_set clipboard_get exec_capture cmd_exists csv_read_raw csv_append ui_window ui_popup "
                "ui_close ui_mainloop ui_panel ui_sizer ui_add ui_pos ui_refresh ui_layout_abs ui_layout_refresh "
                "ui_get_pos ui_get_size ui_destroy ui_bring_to_front ui_font ui_show ui_hide ui_enable ui_disable "
                "ui_cursor ui_tooltip ui_label ui_entry ui_button ui_button_set_state ui_text ui_text_get "
                "ui_text_append ui_text_set ui_text_highlight ui_text_get_selection ui_text_delete_selection "
                "ui_text_insert_at_cursor ui_text_select_all ui_text_find ui_text_replace_selected ui_text_cut "
                "ui_text_copy ui_text_paste ui_text_undo ui_text_redo ui_code_editor ui_highlight "
                "ui_editor_get_functions ui_editor_goto_line ui_editor_get_cursor ui_editor_get_line_count "
                "ui_editor_get_line ui_listview ui_listview_insert ui_listview_clear ui_listview_get_selected "
                "ui_listview_autofit ui_listview_refresh ui_listview_set_column_width ui_listbox ui_listbox_insert "
                "ui_listbox_get ui_listbox_clear ui_listbox_refresh ui_listbox_size ui_listbox_get_all "
                "ui_listbox_delete ui_listbox_select ui_tree ui_tree_insert ui_tree_get_selected ui_tree_clear "
                "ui_tree_delete ui_tree_set_text ui_tree_expand ui_htmlview ui_html_set ui_html_clear ui_sheet "
                "ui_sheet_set ui_sheet_get ui_sheet_insert ui_sheet_set_column_width ui_sheet_delete ui_sheet_clear "
                "ui_sheet_headers ui_sheet_cell_set ui_sheet_cell_get ui_sheet_selected ui_sheet_bind ui_sheet_resize "
                "ui_checkbox ui_checkbox_get ui_checkbox_set ui_radio ui_radio_get ui_radio_set ui_combobox "
                "ui_combobox_clear ui_combobox_add ui_combobox_set_items ui_combobox_get_index ui_combobox_set_index "
                "ui_combobox_delete ui_combobox_get_count ui_datepicker ui_tab_remove ui_statusbar ui_statusbar_fields "
                "ui_statusbar_set ui_statusbar_set_widths ui_statusbar_set_border ui_statusbar_set_color "
                "ui_statusbar_get_count ui_statusbar_get_text ui_tabs ui_tab_add ui_tab_get ui_tab_select ui_menu "
                "ui_menu_add ui_menu_item ui_menu_separator ui_menu_check ui_menu_radio ui_set_menu ui_popup_menu "
                "ui_popup_item ui_popup_separator ui_bind_popup ui_get ui_get_client_size ui_set ui_color ui_focus "
                "ui_size ui_bind ui_mouse_pos ui_capture_mouse ui_confirm ui_folder_open ui_alert ui_alert_err "
                "ui_file_open ui_file_save ui_after ui_after_cancel ui_md_editor ui_md_get ui_md_set ui_md_refresh "
                "ui_richtext ui_richtext_get_text ui_richtext_set_text ui_richtext_apply_bold ui_richtext_apply_italic "
                "ui_richtext_apply_underline ui_richtext_set_font ui_richtext_set_font_size ui_richtext_set_text_color "
                "ui_richtext_set_bg_color ui_richtext_set_align ui_richtext_insert_image ui_richtext_line_break "
                "ui_richtext_page_break ui_richtext_undo ui_richtext_redo ui_richtext_cut ui_richtext_copy "
                "ui_richtext_paste ui_richtext_select_all ui_richtext_save ui_richtext_load ui_richtext_word_count "
                "ui_richtext_char_count ui_richtext_find ui_richtext_replace ui_richtext_set_bullet ui_richtext_set_indent "
                "ui_richtext_strikethrough ui_richtext_superscript ui_richtext_subscript ui_richtext_insert_table "
                "ui_richtext_hr ui_richtext_get_selection ui_richtext_has_selection ui_richtext_set_page_color "
                "ui_richtext_print ui_richtext_page_setup ui_richtext_zoom ui_richtext_clear ui_richtext_insert_field "
                "ui_richtext_insert_hyperlink"
            )
            
            # Store the ORIGINAL lowercase built-ins so we can append UDFs to them later
            ed._builtin_functions = builtin_functions
            ed.SetKeyWords(1, _make_case_insensitive(builtin_functions))
            
            # --- COLOR STYLING (Eye-friendly Light Theme) ---

            # 1. Language Keywords
            ed.StyleSetForeground(stc.STC_P_WORD, wx.Colour(44, 92, 170))      # Muted blue
            ed.StyleSetBold(stc.STC_P_WORD, True)

            # 2. Built-in Functions & UDFs
            ed.StyleSetForeground(stc.STC_P_WORD2, wx.Colour(125, 78, 170))    # Soft purple
            ed.StyleSetBold(stc.STC_P_WORD2, False)

            # 2.5 Function Definition Names
            ed.StyleSetForeground(stc.STC_P_DEFNAME, wx.Colour(125, 78, 170))
            ed.StyleSetBold(stc.STC_P_DEFNAME, True)

            # 3. Variables / Identifiers
            ed.StyleSetForeground(stc.STC_P_IDENTIFIER, wx.Colour(166, 107, 38))  # Muted amber

            # 4. Comments
            ed.StyleSetForeground(stc.STC_P_COMMENTLINE, wx.Colour(92, 132, 92))  # Sage green
            ed.StyleSetItalic(stc.STC_P_COMMENTLINE, True)

            # Numbers
            ed.StyleSetForeground(stc.STC_P_NUMBER, wx.Colour(50, 120, 105))      # Teal

            # Strings
            ed.StyleSetForeground(stc.STC_P_STRING, wx.Colour(150, 72, 72))       # Soft brick red

            # Operators
            ed.StyleSetForeground(stc.STC_P_OPERATOR, wx.Colour(90, 90, 90))      # Neutral gray
            ed.StyleSetBold(stc.STC_P_OPERATOR, True)
            
            # --- Margins & Font ---
            # CRITICAL FIX: You must explicitly tell Scintilla to show line numbers in a margin
            ed.SetMarginType(0, stc.STC_MARGIN_NUMBER)
            ed.SetMarginWidth(0, 50)  # Width of the line number column (adjust as needed)
            ed.SetMarginBackground(0, wx.Colour(242, 241, 238)) # Match line number background
            
            # Optional: Add a small folding margin (Margin 1) if you want the [-] icons
            ed.SetMarginType(1, stc.STC_MARGIN_SYMBOL)
            ed.SetMarginWidth(1, 12)
            ed.SetMarginSensitive(1, True)
            
            font = wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Consolas")
            ed.StyleSetFont(stc.STC_STYLE_DEFAULT, font)
            for s in range(33):
                ed.StyleSetFont(s, font)
                           
            # --- Editor Behavior ---
            ed.SetTabWidth(4)
            ed.SetUseTabs(False)
            ed.SetIndent(4)
            ed.SetTabIndents(True)
            ed.SetBackSpaceUnIndents(True)
            ed.SetEOLMode(stc.STC_EOL_LF)
            ed.SetCaretWidth(2)
            ed.SetUndoCollection(True)
            ed.EmptyUndoBuffer()
            
            # --- DYNAMIC HIGHLIGHTING ENGINE ---
            def on_code_change(evt):
                try:
                    text = ed.GetText()
                    
                    # Extract User-Defined Functions: "def my_func"
                    # Updated regex to look for 'def' instead of 'FUNCTION'
                    udfs = re.findall(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)', text, re.MULTILINE | re.IGNORECASE)
                    
                    # Combine built-ins and UDFs for the Purple keyword set
                    user_funcs_str = " ".join(list(set(udfs)))
                    combined_purple = ed._builtin_functions + " " + user_funcs_str
                    
                    # Apply case-insensitive transformation before updating
                    ed.SetKeyWords(1, _make_case_insensitive(combined_purple))
                    
                    # Force Scintilla to re-apply highlighting immediately
                    # ed.Colourise(0, -1)
                    
                except Exception:
                    pass
                evt.Skip() # Important: lets Scintilla continue processing the event
                
            # Bind the live-updater to the text change event
            ed.Bind(stc.EVT_STC_CHANGE, on_code_change) 
            
            
            
            # Layout
            coords = _parse_pos_args(a, 1)
            _apply_layout(target, ed, coords)
            return ed
        env.define("UI_CODE_EDITOR", NativeFunction("UI_CODE_EDITOR", -1, ui_code_editor))

        def ui_highlight(i, a):
            """Force Scintilla to re-apply syntax highlighting to the entire document."""
            ed = a[0]
            if isinstance(ed, stc.StyledTextCtrl):
                ed.Colourise(0, -1)
            return None
            
        def ui_editor_get_functions(i, a):
            ed = a[0]
            if not isinstance(ed, stc.StyledTextCtrl): return []
            text = ed.GetText()
            funcs = []
            
            # Phase 1 Update: Changed regex to look for 'def' instead of 'FUNCTION'
            pat = re.compile(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE)
            
            for idx, line in enumerate(text.split('\n'), 1):
                m = pat.match(line)
                if m: 
                    funcs.append([idx, m.group(1)])
            return funcs
            
        def ui_editor_goto_line(i, a):
            ed, line = a[0], int(a[1])
            if isinstance(ed, stc.StyledTextCtrl): ed.GotoLine(line - 1); ed.EnsureVisible(line - 1)
            return None
            
        def ui_editor_get_cursor(i, a):
            ed = a[0]
            if not isinstance(ed, stc.StyledTextCtrl): return "1:1"
            pos = ed.GetCurrentPos(); line_idx = ed.LineFromPosition(pos)
            col_idx = pos - ed.PositionFromLine(line_idx)
            return f"{line_idx + 1}:{col_idx + 1}"
            
        def ui_editor_get_line_count(i, a):
            ed = a[0]
            if not isinstance(ed, stc.StyledTextCtrl): return "0"
            return str(ed.GetLineCount())
            
        def ui_editor_get_line(i, a):
            ed, line_num = a[0], int(a[1])
            if not isinstance(ed, stc.StyledTextCtrl): return ""
            if line_num < 1 or line_num > ed.GetLineCount(): return ""
            return ed.GetLine(line_num - 1).rstrip('\r\n')

        env.define("UI_CODE_EDITOR", NativeFunction("UI_CODE_EDITOR", -1, ui_code_editor))
        env.define("UI_HIGHLIGHT", NativeFunction("UI_HIGHLIGHT", 1, ui_highlight))
        env.define("UI_EDITOR_GET_FUNCTIONS", NativeFunction("UI_EDITOR_GET_FUNCTIONS", 1, ui_editor_get_functions))
        env.define("UI_EDITOR_GOTO_LINE", NativeFunction("UI_EDITOR_GOTO_LINE", 2, ui_editor_goto_line))
        env.define("UI_EDITOR_GET_CURSOR", NativeFunction("UI_EDITOR_GET_CURSOR", 1, ui_editor_get_cursor))
        env.define("UI_EDITOR_GET_LINE_COUNT", NativeFunction("UI_EDITOR_GET_LINE_COUNT", 1, ui_editor_get_line_count))
        env.define("UI_EDITOR_GET_LINE", NativeFunction("UI_EDITOR_GET_LINE", 2, ui_editor_get_line))

        # ==========================================================================
        # LISTVIEW & LISTBOX
        # ==========================================================================
        def ui_listview(i, a):
            parent = a[0]; cols = a[1] if len(a) > 1 else []
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            lv = wx.ListCtrl(target, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
            for idx, c in enumerate(cols): lv.InsertColumn(idx, str(c).upper(), width=150)
            coords = _parse_pos_args(a, 2); _apply_layout(target, lv, coords)
            return lv
        def ui_listview_insert(i, a):
            lv, row = a[0], a[1]
            if not isinstance(lv, wx.ListCtrl): return None
            values = list(row.values()) if isinstance(row, dict) else (row if isinstance(row, list) else [row])
            if values:
                idx = lv.InsertItem(lv.GetItemCount(), str(values[0]))
                for c in range(1, len(values)): lv.SetItem(idx, c, str(values[c]))
            return None
        def ui_listview_clear(i, a):
            if isinstance(a[0], wx.ListCtrl): a[0].DeleteAllItems()
            return None
        def ui_listview_get_selected(i, a):
            lv = a[0]
            if not isinstance(lv, wx.ListCtrl): return None
            idx = lv.GetFirstSelected()
            if idx == -1: return None
            return [lv.GetItem(idx, c).GetText() for c in range(lv.GetColumnCount())]
        def ui_listview_autofit(i, a):
            lv = a[0]
            if not isinstance(lv, wx.ListCtrl): return None
            for c in range(lv.GetColumnCount()):
                lv.SetColumnWidth(c, wx.LIST_AUTOSIZE)
                if lv.GetColumnWidth(c) < 80: lv.SetColumnWidth(c, 80)
            return "SUCCESS"
        def ui_listview_refresh(i, a):
            if isinstance(a[0], wx.ListCtrl): a[0].Refresh()
            return None
        def ui_listview_set_column_width(i, a):
            lv, col, w = a[0], a[1], int(a[2])
            if not isinstance(lv, wx.ListCtrl): return None
            if isinstance(col, int): lv.SetColumnWidth(col, w)
            else:
                for c in range(lv.GetColumnCount()):
                    if lv.GetColumn(c).GetText() == str(col): lv.SetColumnWidth(c, w); break
            return "SUCCESS"
        def ui_listview_set_selection(i, a):
            lv, idx = a[0], int(a[1])
            if isinstance(lv, wx.ListCtrl):
                # Clear previous selection first
                for i in range(lv.GetItemCount()):
                    if lv.GetItemState(i, wx.LIST_STATE_SELECTED):
                        lv.SetItemState(i, 0, wx.LIST_STATE_SELECTED)
                # Set new selection
                if 0 <= idx < lv.GetItemCount():
                    lv.SetItemState(idx, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)
                    lv.Focus(idx)
                return "SUCCESS"
            return "ERROR: Not a ListCtrl"

        env.define("UI_LISTVIEW_SET_SELECTION", NativeFunction("UI_LISTVIEW_SET_SELECTION", 2, ui_listview_set_selection))

        def ui_listbox(i, a):
            parent = a[0]; target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            lb = wx.ListBox(target, style=wx.LB_SINGLE)
            coords = _parse_pos_args(a, 1); _apply_layout(target, lb, coords)
            return lb
        def ui_listbox_insert(i, a):
            lb, items = a[0], a[1]
            if not isinstance(lb, wx.ListBox): return None
            if isinstance(items, list):
                for it in items: lb.Append(str(it))
            else: lb.Append(str(items))
            return None
        def ui_listbox_get(i, a):
            lb = a[0]
            if isinstance(lb, wx.ListBox):
                s = lb.GetSelection()
                if s != wx.NOT_FOUND: return lb.GetString(s)
            return None
        def ui_listbox_clear(i, a):
            if isinstance(a[0], wx.ListBox): a[0].Clear()
            return None
        def ui_listbox_refresh(i, a): return None
        def ui_listbox_size(i, a):
            if isinstance(a[0], wx.ListBox): return a[0].GetCount()
            return 0
        def ui_listbox_get_all(i, a):
            if isinstance(a[0], wx.ListBox): return list(a[0].GetStrings())
            return []
        def ui_listbox_delete(i, a):
            if isinstance(a[0], wx.ListBox): a[0].Delete(int(a[1])); return "SUCCESS"
        def ui_listbox_select(i, a):
            if isinstance(a[0], wx.ListBox): a[0].SetSelection(int(a[1])); return "SUCCESS"

        env.define("UI_LISTVIEW", NativeFunction("UI_LISTVIEW", -1, ui_listview))
        env.define("UI_LISTVIEW_INSERT", NativeFunction("UI_LISTVIEW_INSERT", 2, ui_listview_insert))
        env.define("UI_LISTVIEW_CLEAR", NativeFunction("UI_LISTVIEW_CLEAR", 1, ui_listview_clear))
        env.define("UI_LISTVIEW_GET_SELECTED", NativeFunction("UI_LISTVIEW_GET_SELECTED", 1, ui_listview_get_selected))
        env.define("UI_LISTVIEW_AUTOFIT", NativeFunction("UI_LISTVIEW_AUTOFIT", 1, ui_listview_autofit))
        env.define("UI_LISTVIEW_REFRESH", NativeFunction("UI_LISTVIEW_REFRESH", 1, ui_listview_refresh))
        env.define("UI_LISTVIEW_SET_COLUMN_WIDTH", NativeFunction("UI_LISTVIEW_SET_COLUMN_WIDTH", 3, ui_listview_set_column_width))
        env.define("UI_LISTBOX", NativeFunction("UI_LISTBOX", -1, ui_listbox))
        env.define("UI_LISTBOX_INSERT", NativeFunction("UI_LISTBOX_INSERT", 2, ui_listbox_insert))
        env.define("UI_LISTBOX_GET", NativeFunction("UI_LISTBOX_GET", 1, ui_listbox_get))
        env.define("UI_LISTBOX_CLEAR", NativeFunction("UI_LISTBOX_CLEAR", 1, ui_listbox_clear))
        env.define("UI_LISTBOX_REFRESH", NativeFunction("UI_LISTBOX_REFRESH", 1, ui_listbox_refresh))
        env.define("UI_LISTBOX_SIZE", NativeFunction("UI_LISTBOX_SIZE", 1, ui_listbox_size))
        env.define("UI_LISTBOX_GET_ALL", NativeFunction("UI_LISTBOX_GET_ALL", 1, ui_listbox_get_all))
        env.define("UI_LISTBOX_DELETE", NativeFunction("UI_LISTBOX_DELETE", 2, ui_listbox_delete))
        env.define("UI_LISTBOX_SELECT", NativeFunction("UI_LISTBOX_SELECT", 2, ui_listbox_select))

        # ==========================================================================
        # TREE & HTML VIEWER
        # ==========================================================================
        def _find_tree_item(tree, item, target_id):
            if not item.IsOk(): return None
            data = tree.GetItemData(item)
            if data and data.get("id") == target_id: return item
            child, cookie = tree.GetFirstChild(item)
            while child.IsOk():
                found = _find_tree_item(tree, child, target_id)
                if found: return found
                child, cookie = tree.GetNextChild(item, cookie)
            return None

        def ui_tree(i, a):
            parent = a[0]; target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            tree = wx.TreeCtrl(target, style=wx.TR_DEFAULT_STYLE | wx.TR_HAS_BUTTONS); tree.AddRoot("Root")
            coords = _parse_pos_args(a, 1); _apply_layout(target, tree, coords)
            return tree
        def ui_tree_insert(i, a):
            tree, parent_id, item_id, text = a[0], str(a[1]) if a[1] else "", str(a[2]), str(a[3])
            if not isinstance(tree, wx.TreeCtrl): return None
            if parent_id == "" or parent_id == "root":
                parent_item = tree.GetRootItem(); new_item = tree.AppendItem(parent_item, text)
            else:
                p = _find_tree_item(tree, tree.GetRootItem(), parent_id)
                new_item = tree.AppendItem(p if p and p.IsOk() else tree.GetRootItem(), text)
            tree.SetItemData(new_item, {"id": item_id, "text": text})
            return item_id
        def ui_tree_get_selected(i, a):
            tree = a[0]
            if isinstance(tree, wx.TreeCtrl):
                item = tree.GetSelection()
                if item.IsOk():
                    data = tree.GetItemData(item)
                    if data: return data.get("id")
            return None
        def ui_tree_clear(i, a):
            if isinstance(a[0], wx.TreeCtrl): a[0].DeleteAllItems(); a[0].AddRoot("Root")
            return None
        def ui_tree_delete(i, a):
            tree, item_id = a[0], str(a[1])
            if isinstance(tree, wx.TreeCtrl):
                item = _find_tree_item(tree, tree.GetRootItem(), item_id)
                if item and item.IsOk(): tree.Delete(item)
            return None
        def ui_tree_set_text(i, a):
            tree, item_id, text = a[0], str(a[1]), str(a[2])
            if isinstance(tree, wx.TreeCtrl):
                item = _find_tree_item(tree, tree.GetRootItem(), item_id)
                if item and item.IsOk():
                    tree.SetItemText(item, text)
                    data = tree.GetItemData(item)
                    if data: data["text"] = text
            return None
        def ui_tree_expand(i, a):
            tree, item_id = a[0], str(a[1])
            expand = bool(a[2]) if len(a) > 2 else True
            if isinstance(tree, wx.TreeCtrl):
                item = _find_tree_item(tree, tree.GetRootItem(), item_id)
                if item and item.IsOk():
                    if expand: tree.Expand(item)
                    else: tree.Collapse(item)
            return None

        def ui_htmlview(i, a):
            parent = a[0]; target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            try: hw = wx.html2.WebView.New(target)
            except Exception as e: raise FMS_Error(f"WebView failed: {e}")
            coords = _parse_pos_args(a, 1); _apply_layout(target, hw, coords)
            return hw
        def ui_html_set(i, a):
            w, html_content = a[0], str(a[1])
            base_url = str(a[2]) if len(a) > 2 and a[2] else ""
            if isinstance(w, wx.html2.WebView):
                if base_url:
                    base_normalized = base_url.replace("\\", "/")
                    if not base_normalized.endswith("/"): base_normalized += "/"
                    w.SetPage(html_content, "file:///" + base_normalized)
                else: w.SetPage(html_content, "")
            return None
        def ui_html_clear(i, a):
            if isinstance(a[0], wx.html2.WebView): a[0].SetPage("", "")
            return None

        env.define("UI_TREE", NativeFunction("UI_TREE", -1, ui_tree))
        env.define("UI_TREE_INSERT", NativeFunction("UI_TREE_INSERT", -1, ui_tree_insert))
        env.define("UI_TREE_GET_SELECTED", NativeFunction("UI_TREE_GET_SELECTED", 1, ui_tree_get_selected))
        env.define("UI_TREE_CLEAR", NativeFunction("UI_TREE_CLEAR", 1, ui_tree_clear))
        env.define("UI_TREE_DELETE", NativeFunction("UI_TREE_DELETE", 2, ui_tree_delete))
        env.define("UI_TREE_SET_TEXT", NativeFunction("UI_TREE_SET_TEXT", 3, ui_tree_set_text))
        env.define("UI_TREE_EXPAND", NativeFunction("UI_TREE_EXPAND", -1, ui_tree_expand))
        env.define("UI_HTMLVIEW", NativeFunction("UI_HTMLVIEW", -1, ui_htmlview))
        env.define("UI_HTML_SET", NativeFunction("UI_HTML_SET", -1, ui_html_set))
        env.define("UI_HTML_CLEAR", NativeFunction("UI_HTML_CLEAR", 1, ui_html_clear))

        # ==========================================================================
        # SPREADSHEET (Grid) - REVISED IMPLEMENTATION
        # ==========================================================================

        # --- Helper Functions ---
        def _grid_bounds_check(grid, row=None, col=None):
            """Validates grid indices to prevent C++ crashes."""
            if not isinstance(grid, gridlib.Grid):
                return False
            if row is not None and (row < 0 or row >= grid.GetNumberRows()):
                return False
            if col is not None and (col < 0 or col >= grid.GetNumberCols()):
                return False
            return True

        def _grid_batch_operation(grid, operation):
            """Execute operation with batch redraw suppression."""
            grid.BeginBatch()
            try:
                result = operation()
            finally:
                grid.EndBatch()
            grid.ForceRefresh()
            return result

        # --- Core Grid Creation ---
        def ui_sheet(i, a):
            """Create a new spreadsheet grid."""
            parent = a[0]
            rows = int(a[1]) if len(a) > 1 and a[1] else 10
            cols = int(a[2]) if len(a) > 2 and a[2] else 5
            
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            grid = gridlib.Grid(target)
            grid.CreateGrid(max(rows, 1), max(cols, 1))
            
            # Styling
            grid.SetDefaultCellFont(wx.Font(10, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, 
                                             wx.FONTWEIGHT_NORMAL, faceName="Consolas"))
            grid.SetLabelBackgroundColour(wx.Colour(74, 144, 222))
            grid.SetLabelTextColour(wx.WHITE)
            grid.SetGridLineColour(wx.Colour(204, 204, 204))
            
            coords = _parse_pos_args(a, 3)
            _apply_layout(target, grid, coords)
            return grid

        # --- Data Operations ---
        def ui_sheet_set(i, a):
            """Set grid data from list of lists or list of dicts."""
            grid, data = a[0], a[1]
            if not isinstance(grid, gridlib.Grid):
                return None
            
            def operation():
                # Parse data format
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    headers = list(data[0].keys())
                    table = [list(r.values()) for r in data]
                    needed_cols = len(headers)
                else:
                    headers = None
                    table = data if isinstance(data, list) else []
                    needed_cols = max((len(row) for row in table), default=0)
                
                # Resize columns (batch)
                current_cols = grid.GetNumberCols()
                if needed_cols > current_cols:
                    grid.AppendCols(needed_cols - current_cols)
                elif needed_cols < current_cols:
                    grid.DeleteCols(needed_cols, current_cols - needed_cols)
                
                # Resize rows (batch)
                needed_rows = len(table)
                current_rows = grid.GetNumberRows()
                if needed_rows > current_rows:
                    grid.AppendRows(needed_rows - current_rows)
                elif needed_rows < current_rows:
                    grid.DeleteRows(needed_rows, current_rows - needed_rows)
                
                # Clear and fill
                grid.ClearGrid()
                if headers:
                    for idx, h in enumerate(headers):
                        grid.SetColLabelValue(idx, str(h))
                
                for r, row in enumerate(table):
                    for c, v in enumerate(row):
                        if c < needed_cols:
                            grid.SetCellValue(r, c, "" if v is None else str(v))
                
                grid.AutoSizeColumns(setAsMin=False)
                return "SUCCESS"
            
            return _grid_batch_operation(grid, operation)

        def ui_sheet_get(i, a):
            """Get all grid data as list of lists."""
            grid = a[0]
            if not isinstance(grid, gridlib.Grid):
                return []
            return [[grid.GetCellValue(r, c) for c in range(grid.GetNumberCols())] 
                    for r in range(grid.GetNumberRows())]

        def ui_sheet_insert(i, a):
            """Insert a row at specified position or append."""
            grid, row = a[0], a[1]
            pos = int(a[2]) if len(a) > 2 else None
            
            if not isinstance(grid, gridlib.Grid):
                return None
            if not isinstance(row, list):
                row = [row]
            
            def operation():
                if pos is None:
                    grid.AppendRows(1)
                    insert_pos = grid.GetNumberRows() - 1
                else:
                    if pos < 0 or pos > grid.GetNumberRows():
                        return None
                    grid.InsertRows(pos, 1)
                    insert_pos = pos
                
                for c, v in enumerate(row):
                    if c < grid.GetNumberCols():
                        grid.SetCellValue(insert_pos, c, "" if v is None else str(v))
                
                return "SUCCESS"
            
            return _grid_batch_operation(grid, operation)

        def ui_sheet_delete(i, a):
            """Delete a row by index."""
            grid, r = a[0], int(a[1])
            if not _grid_bounds_check(grid, row=r):
                return None
            
            grid.DeleteRows(r, 1)
            grid.ForceRefresh()
            return "SUCCESS"

        def ui_sheet_clear(i, a):
            """Clear all cell values."""
            grid = a[0]
            if not isinstance(grid, gridlib.Grid):
                return None
            
            grid.ClearGrid()
            grid.ForceRefresh()
            return "SUCCESS"

        def ui_sheet_headers(i, a):
            """Set column headers."""
            grid, headers = a[0], a[1]
            if not isinstance(grid, gridlib.Grid) or not isinstance(headers, list):
                return None
            
            def operation():
                while grid.GetNumberCols() < len(headers):
                    grid.AppendCols(1)
                for idx, h in enumerate(headers):
                    grid.SetColLabelValue(idx, str(h))
                return "SUCCESS"
            
            return _grid_batch_operation(grid, operation)

        # --- Cell Operations ---
        def ui_sheet_cell_set(i, a):
            """Set a single cell value."""
            grid, r, c, v = a[0], int(a[1]), int(a[2]), a[3]
            if not _grid_bounds_check(grid, r, c):
                return None
            
            grid.SetCellValue(r, c, "" if v is None else str(v))
            grid.ForceRefresh()
            return "SUCCESS"

        def ui_sheet_cell_get(i, a):
            """Get a single cell value."""
            grid, r, c = a[0], int(a[1]), int(a[2])
            if not _grid_bounds_check(grid, r, c):
                return ""
            return grid.GetCellValue(r, c)

        def ui_sheet_cell_style(i, a):
            """Set cell formatting: bg, fg, bold, align, readonly."""
            grid, r, c, style = a[0], int(a[1]), int(a[2]), a[3]
            if not _grid_bounds_check(grid, r, c) or not isinstance(style, dict):
                return None
            
            attr = gridlib.GridCellAttr()
            
            if "bg" in style:
                bg = style["bg"]
                attr.SetBackgroundColour(wx.Colour(*bg) if isinstance(bg, (list, tuple)) else bg)
            
            if "fg" in style:
                fg = style["fg"]
                attr.SetTextColour(wx.Colour(*fg) if isinstance(fg, (list, tuple)) else fg)
            
            if "bold" in style:
                font = grid.GetDefaultCellFont()
                font.SetWeight(wx.FONTWEIGHT_BOLD if style["bold"] else wx.FONTWEIGHT_NORMAL)
                attr.SetFont(font)
            
            if "align" in style:
                h_align = {
                    "left": wx.ALIGN_LEFT,
                    "center": wx.ALIGN_CENTRE,
                    "right": wx.ALIGN_RIGHT
                }
                attr.SetAlignment(h_align.get(style["align"], wx.ALIGN_LEFT), wx.ALIGN_CENTRE)
            
            if "readonly" in style:
                attr.SetReadOnly(style["readonly"])
            
            grid.SetAttr(r, c, attr)
            grid.ForceRefresh()
            return "SUCCESS"

        # --- Grid Configuration ---
        def ui_sheet_set_column_width(i, a):
            """Set column width."""
            grid, col, width = a[0], int(a[1]), int(a[2])
            if not _grid_bounds_check(grid, col=col):
                return None
            
            grid.SetColSize(col, max(width, 1))
            return "SUCCESS"

        def ui_sheet_row_height(i, a):
            """Set row height."""
            grid, row, height = a[0], int(a[1]), int(a[2])
            if not _grid_bounds_check(grid, row=row):
                return None
            
            grid.SetRowSize(row, max(height, 1))
            return "SUCCESS"

        def ui_sheet_resize(i, a):
            """Resize grid to target rows/cols (preserves data from top-left)."""
            grid, tr, tc = a[0], int(a[1]), int(a[2])
            if not isinstance(grid, gridlib.Grid):
                return None
            
            def operation():
                cr, cc = grid.GetNumberRows(), grid.GetNumberCols()
                
                # Resize rows (delete from end to preserve data)
                if tr > cr:
                    grid.AppendRows(tr - cr)
                elif tr < cr:
                    grid.DeleteRows(tr, cr - tr)
                
                # Resize cols (delete from end to preserve data)
                if tc > cc:
                    grid.AppendCols(tc - cc)
                elif tc < cc:
                    grid.DeleteCols(tc, cc - tc)
                
                return "SUCCESS"
            
            return _grid_batch_operation(grid, operation)

        def ui_sheet_autosize(i, a):
            """Auto-fit all columns and rows."""
            grid = a[0]
            if not isinstance(grid, gridlib.Grid):
                return None
            
            grid.AutoSizeColumns(setAsMin=False)
            grid.AutoSizeRows(setAsMin=False)
            grid.ForceRefresh()
            return "SUCCESS"

        def ui_sheet_readonly(i, a):
            """Toggle grid read-only mode."""
            grid, flag = a[0], bool(a[1])
            if not isinstance(grid, gridlib.Grid):
                return None
            
            grid.EnableEditing(not flag)
            return "SUCCESS"

        # --- Selection & Events ---
        def ui_sheet_selected(i, a):
            """Get list of selected cells as [[row, col], ...]."""
            grid = a[0]
            if not isinstance(grid, gridlib.Grid):
                return []
            
            cells = []
            
            # Individual selected cells
            for cell in grid.GetSelectedCells():
                cells.append([cell.GetRow(), cell.GetCol()])
            
            # Selection blocks (ranges)
            try:
                top_lefts = grid.GetSelectionBlockTopLeft()
                bot_rights = grid.GetSelectionBlockBottomRight()
                for idx in range(len(top_lefts)):
                    top = top_lefts[idx]
                    bottom = bot_rights[idx]
                    for row in range(top.GetRow(), bottom.GetRow() + 1):
                        for col in range(top.GetCol(), bottom.GetCol() + 1):
                            if [row, col] not in cells:
                                cells.append([row, col])
            except Exception:
                pass
            
            # Fallback to cursor position
            if not cells:
                row = grid.GetGridCursorRow()
                col = grid.GetGridCursorCol()
                if row >= 0 and col >= 0:
                    cells.append([row, col])
            
            return cells

        def ui_sheet_bind(i, a):
            """Bind event handler: cell_select, edit, label_click, cell_right, cell_dclick, range_select."""
            grid, etype, cb = a[0], str(a[1]).lower(), str(a[2])
            if not isinstance(grid, gridlib.Grid):
                return None
            
            interp = i  # Capture interpreter reference
            
            def handler(evt):
                r = evt.GetRow() if hasattr(evt, 'GetRow') else -1
                c = evt.GetCol() if hasattr(evt, 'GetCol') else -1
                
                if etype == "cell_select":
                    _call_anika(interp, cb, [r, c])
                elif etype == "edit":
                    _call_anika(interp, cb, [r, c, grid.GetCellValue(r, c)])
                elif etype in ["label_click", "cell_right", "cell_dclick", "range_select"]:
                    _call_anika(interp, cb, [r, c])
                else:
                    _call_anika(interp, cb, [r, c])
                
                evt.Skip()  # Allow default processing
            
            event_map = {
                "cell_select":  gridlib.EVT_GRID_CELL_LEFT_CLICK,
                "edit":         gridlib.EVT_GRID_CELL_CHANGED,
                "label_click":  gridlib.EVT_GRID_LABEL_LEFT_CLICK,
                "cell_right":   gridlib.EVT_GRID_CELL_RIGHT_CLICK,
                "cell_dclick":  gridlib.EVT_GRID_CELL_LEFT_DCLICK,
                "range_select": gridlib.EVT_GRID_RANGE_SELECT,
            }
            
            event = event_map.get(etype, gridlib.EVT_GRID_SELECT_CELL)
            grid.Bind(event, handler)
            return "SUCCESS"

        # --- Import/Export ---
        def ui_sheet_export_csv(i, a):
            """Export grid to CSV string."""
            grid = a[0]
            if not isinstance(grid, gridlib.Grid):
                return ""
            
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Headers
            headers = [grid.GetColLabelValue(c) for c in range(grid.GetNumberCols())]
            writer.writerow(headers)
            
            # Data
            for r in range(grid.GetNumberRows()):
                writer.writerow([grid.GetCellValue(r, c) for c in range(grid.GetNumberCols())])
            
            return output.getvalue()

        def ui_sheet_import_csv(i, a):
            """Import CSV string into grid."""
            grid, csv_str = a[0], a[1]
            if not isinstance(grid, gridlib.Grid) or not isinstance(csv_str, str):
                return None
            
            import csv
            import io
            
            reader = csv.reader(io.StringIO(csv_str))
            rows = list(reader)
            
            if not rows:
                return "SUCCESS"
            
            # First row as headers
            ui_sheet_headers(i, [grid, rows[0]])
            
            # Rest as data
            if len(rows) > 1:
                ui_sheet_set(i, [grid, rows[1:]])
            
            return "SUCCESS"

        # ==========================================================================
        # ENVIRONMENT REGISTRATION
        # ==========================================================================
        env.define("UI_SHEET", NativeFunction("UI_SHEET", -1, ui_sheet))
        env.define("UI_SHEET_SET", NativeFunction("UI_SHEET_SET", 2, ui_sheet_set))
        env.define("UI_SHEET_GET", NativeFunction("UI_SHEET_GET", 1, ui_sheet_get))
        env.define("UI_SHEET_INSERT", NativeFunction("UI_SHEET_INSERT", -1, ui_sheet_insert))
        env.define("UI_SHEET_DELETE", NativeFunction("UI_SHEET_DELETE", 2, ui_sheet_delete))
        env.define("UI_SHEET_CLEAR", NativeFunction("UI_SHEET_CLEAR", 1, ui_sheet_clear))
        env.define("UI_SHEET_HEADERS", NativeFunction("UI_SHEET_HEADERS", 2, ui_sheet_headers))
        env.define("UI_SHEET_CELL_SET", NativeFunction("UI_SHEET_CELL_SET", 4, ui_sheet_cell_set))
        env.define("UI_SHEET_CELL_GET", NativeFunction("UI_SHEET_CELL_GET", 3, ui_sheet_cell_get))
        env.define("UI_SHEET_CELL_STYLE", NativeFunction("UI_SHEET_CELL_STYLE", 4, ui_sheet_cell_style))
        env.define("UI_SHEET_SET_COLUMN_WIDTH", NativeFunction("UI_SHEET_SET_COLUMN_WIDTH", 3, ui_sheet_set_column_width))
        env.define("UI_SHEET_ROW_HEIGHT", NativeFunction("UI_SHEET_ROW_HEIGHT", 3, ui_sheet_row_height))
        env.define("UI_SHEET_RESIZE", NativeFunction("UI_SHEET_RESIZE", 3, ui_sheet_resize))
        env.define("UI_SHEET_AUTOSIZE", NativeFunction("UI_SHEET_AUTOSIZE", 1, ui_sheet_autosize))
        env.define("UI_SHEET_READONLY", NativeFunction("UI_SHEET_READONLY", 2, ui_sheet_readonly))
        env.define("UI_SHEET_SELECTED", NativeFunction("UI_SHEET_SELECTED", 1, ui_sheet_selected))
        env.define("UI_SHEET_BIND", NativeFunction("UI_SHEET_BIND", 3, ui_sheet_bind))
        env.define("UI_SHEET_EXPORT_CSV", NativeFunction("UI_SHEET_EXPORT_CSV", 1, ui_sheet_export_csv))
        env.define("UI_SHEET_IMPORT_CSV", NativeFunction("UI_SHEET_IMPORT_CSV", 2, ui_sheet_import_csv))

        # ==========================================================================
        # CONTROLS (Checkbox, Radio, Combobox, Datepicker)
        # ==========================================================================
        def ui_checkbox(i, a):
            parent, text = a[0], str(a[1]); target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            cb = wx.CheckBox(target, label=text); coords = _parse_pos_args(a, 2); _apply_layout(target, cb, coords)
            return cb
        def ui_checkbox_get(i, a):
            if isinstance(a[0], wx.CheckBox): return a[0].GetValue()
            return False
        def ui_checkbox_set(i, a):
            cb, v = a[0], a[1]
            if isinstance(cb, wx.CheckBox):
                if isinstance(v, str): cb.SetValue(v.upper() in ("TRUE","1","YES","ON"))
                else: cb.SetValue(bool(v))
            return None

        def ui_radio(i, a):
            parent, text, value, var = a[0], str(a[1]), str(a[2]), str(a[3])
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            if not hasattr(i, 'radio_vars'): i.radio_vars = {}
            if var not in i.radio_vars: i.radio_vars[var] = {"value": "", "buttons": []}
            style = wx.RB_GROUP if not i.radio_vars[var]["buttons"] else 0
            rb = wx.RadioButton(target, label=text, style=style)
            rb._fms_value = value; rb._fms_var = var
            def handler(evt): i.radio_vars[var]["value"] = value
            rb.Bind(wx.EVT_RADIOBUTTON, handler)
            i.radio_vars[var]["buttons"].append(rb)
            coords = _parse_pos_args(a, 4); _apply_layout(target, rb, coords)
            return rb
        def ui_radio_get(i, a):
            var = str(a[0])
            if hasattr(i, 'radio_vars') and var in i.radio_vars: return i.radio_vars[var]["value"]
            return None
        def ui_radio_set(i, a):
            var, value = str(a[0]), str(a[1])
            if hasattr(i, 'radio_vars') and var in i.radio_vars:
                i.radio_vars[var]["value"] = value
                for btn in i.radio_vars[var]["buttons"]:
                    if btn._fms_value == value: btn.SetValue(True); break
            return None

        def ui_combobox(i, a):
            parent, values = a[0], [str(x) for x in a[1]]; target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            cb = wx.ComboBox(target, choices=values, style=wx.CB_READONLY)
            if values: cb.SetSelection(0)
            coords = _parse_pos_args(a, 2); _apply_layout(target, cb, coords)
            return cb
        def ui_combobox_clear(i, a):
            cb = a[0]
            if isinstance(cb, wx.ComboBox): cb.Clear()
            return None
        def ui_combobox_add(i, a):
            cb, item = a[0], str(a[1])
            if isinstance(cb, wx.ComboBox): cb.Append(item)
            return None
        def ui_combobox_set_items(i, a):
            cb, items = a[0], a[1]
            if isinstance(cb, wx.ComboBox) and isinstance(items, list):
                cb.Clear()
                for item in items: cb.Append(str(item))
                if cb.GetCount() > 0: cb.SetSelection(0)
            return None
        def ui_combobox_get_index(i, a):
            cb = a[0]
            if isinstance(cb, wx.ComboBox): return cb.GetSelection()
            return -1
        def ui_combobox_set_index(i, a):
            cb, idx = a[0], int(a[1])
            if isinstance(cb, wx.ComboBox):
                if 0 <= idx < cb.GetCount(): cb.SetSelection(idx)
            return None
        def ui_combobox_delete(i, a):
            cb, idx = a[0], int(a[1])
            if isinstance(cb, wx.ComboBox):
                if 0 <= idx < cb.GetCount(): cb.Delete(idx)
            return None
        def ui_combobox_get_count(i, a):
            cb = a[0]
            if isinstance(cb, wx.ComboBox): return cb.GetCount()
            return 0

        def ui_datepicker(i, a):
            parent = a[0]; target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            dp = wx.adv.DatePickerCtrl(target, style=wx.adv.DP_SHOWCENTURY | wx.adv.DP_DROPDOWN)
            dp.SetValue(wx.DateTime.Today())
            coords = _parse_pos_args(a, 1); _apply_layout(target, dp, coords)
            return dp

        env.define("UI_CHECKBOX", NativeFunction("UI_CHECKBOX", -1, ui_checkbox))
        env.define("UI_CHECKBOX_GET", NativeFunction("UI_CHECKBOX_GET", 1, ui_checkbox_get))
        env.define("UI_CHECKBOX_SET", NativeFunction("UI_CHECKBOX_SET", 2, ui_checkbox_set))
        env.define("UI_RADIO", NativeFunction("UI_RADIO", -1, ui_radio))
        env.define("UI_RADIO_GET", NativeFunction("UI_RADIO_GET", 1, ui_radio_get))
        env.define("UI_RADIO_SET", NativeFunction("UI_RADIO_SET", 2, ui_radio_set))
        env.define("UI_COMBOBOX", NativeFunction("UI_COMBOBOX", -1, ui_combobox))
        env.define("UI_COMBOBOX_CLEAR", NativeFunction("UI_COMBOBOX_CLEAR", 1, ui_combobox_clear))
        env.define("UI_COMBOBOX_ADD", NativeFunction("UI_COMBOBOX_ADD", 2, ui_combobox_add))
        env.define("UI_COMBOBOX_SET_ITEMS", NativeFunction("UI_COMBOBOX_SET_ITEMS", 2, ui_combobox_set_items))
        env.define("UI_COMBOBOX_GET_INDEX", NativeFunction("UI_COMBOBOX_GET_INDEX", 1, ui_combobox_get_index))
        env.define("UI_COMBOBOX_SET_INDEX", NativeFunction("UI_COMBOBOX_SET_INDEX", 2, ui_combobox_set_index))
        env.define("UI_COMBOBOX_DELETE", NativeFunction("UI_COMBOBOX_DELETE", 2, ui_combobox_delete))
        env.define("UI_COMBOBOX_GET_COUNT", NativeFunction("UI_COMBOBOX_GET_COUNT", 1, ui_combobox_get_count))
        env.define("UI_DATEPICKER", NativeFunction("UI_DATEPICKER", -1, ui_datepicker))

        # ==========================================================================
        # TABS, MENUS, STATUSBAR
        # ==========================================================================
        # ==========================================================================
        # TABS / NOTEBOOK MANAGEMENT - COMPLETE IMPLEMENTATION
        # ==========================================================================

        def ui_tabs(i, a):
            """Create a new Notebook container."""
            parent = a[0]
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            nb = wx.Notebook(target)
            coords = _parse_pos_args(a, 1)
            _apply_layout(target, nb, coords)
            return nb

        def ui_tab_add(i, a):
            """Add a new tab panel and return the panel object."""
            nb, title = a[0], str(a[1])
            if isinstance(nb, wx.Notebook):
                panel = wx.Panel(nb)
                nb.AddPage(panel, title)
                return panel
            return None

        def ui_tab_get_title(i, a):
            """Get the title of a specific tab by index (or selected tab if no index)."""
            nb = a[0]
            idx = int(a[1]) if len(a) > 1 else -1
            
            if isinstance(nb, wx.Notebook):
                # Default to currently selected tab if no index provided
                if idx == -1: 
                    idx = nb.GetSelection()
                    
                if 0 <= idx < nb.GetPageCount():
                    return nb.GetPageText(idx)
            return None

        def ui_tab_set_title(i, a):
            """Update the title of a specific tab by index (or selected tab if no index)."""
            nb = a[0]
            new_title = str(a[1]) if len(a) > 1 else ""
            idx = int(a[2]) if len(a) > 2 else -1
            
            if isinstance(nb, wx.Notebook):
                # Default to currently selected tab if no index provided
                if idx == -1: 
                    idx = nb.GetSelection()
                    
                if 0 <= idx < nb.GetPageCount():
                    nb.SetPageText(idx, new_title)
                    return "SUCCESS"
            return "ERROR: Invalid notebook or index"

        def ui_tab_select(i, a):
            """Select a tab by its integer index."""
            nb = a[0]
            idx = int(a[1]) if len(a) > 1 else 0
            
            if isinstance(nb, wx.Notebook):
                if 0 <= idx < nb.GetPageCount():
                    nb.SetSelection(idx)
                    return "SUCCESS"
            return "ERROR: Invalid index"

        def ui_tab_select_by_name(i, a):
            """Select a tab by matching its title string (legacy support)."""
            nb = a[0]
            title = str(a[1])
            
            if isinstance(nb, wx.Notebook):
                for i in range(nb.GetPageCount()):
                    if nb.GetPageText(i) == title:
                        nb.SetSelection(i)
                        return "SUCCESS"
            return f"ERROR: Tab '{title}' not found"

        def ui_tab_get_index(i, a):
            """Get the integer index of the currently selected tab."""
            nb = a[0]
            if isinstance(nb, wx.Notebook):
                idx = nb.GetSelection()
                if idx != wx.NOT_FOUND:
                    return idx
            return -1

        def ui_tab_count(i, a):
            """Get the total number of open tabs."""
            nb = a[0]
            if isinstance(nb, wx.Notebook):
                return nb.GetPageCount()
            return 0

        def ui_tab_remove(i, a):
            """Remove a tab by index or title. Destroys the underlying panel."""
            nb = a[0]
            target = a[1]
            
            if isinstance(nb, wx.Notebook):
                idx = -1
                
                # Handle both integer index and string title lookup
                if isinstance(target, int):
                    idx = target
                else:
                    title = str(target)
                    for i in range(nb.GetPageCount()):
                        if nb.GetPageText(i) == title:
                            idx = i
                            break
                            
                if 0 <= idx < nb.GetPageCount():
                    nb.DeletePage(idx)
                    return "SUCCESS"
                    
            return "ERROR: Invalid notebook or target"

        def ui_tab_get_panel(i, a):
            """Get the underlying wx.Panel object for a specific tab index."""
            nb = a[0]
            idx = int(a[1]) if len(a) > 1 else -1
            
            if isinstance(nb, wx.Notebook):
                if idx == -1: 
                    idx = nb.GetSelection()
                    
                if 0 <= idx < nb.GetPageCount():
                    return nb.GetPage(idx)
            return None

        # ==========================================================================
        # ENVIRONMENT REGISTRATION
        # ==========================================================================

        env.define("UI_TABS", NativeFunction("UI_TABS", -1, ui_tabs))
        env.define("UI_TAB_ADD", NativeFunction("UI_TAB_ADD", 2, ui_tab_add))
        env.define("UI_TAB_GET_TITLE", NativeFunction("UI_TAB_GET_TITLE", -1, ui_tab_get_title))
        env.define("UI_TAB_SET_TITLE", NativeFunction("UI_TAB_SET_TITLE", -1, ui_tab_set_title))
        env.define("UI_TAB_SELECT", NativeFunction("UI_TAB_SELECT", -1, ui_tab_select))
        env.define("UI_TAB_SELECT_BY_NAME", NativeFunction("UI_TAB_SELECT_BY_NAME", 2, ui_tab_select_by_name))
        env.define("UI_TAB_GET_INDEX", NativeFunction("UI_TAB_GET_INDEX", 1, ui_tab_get_index))
        env.define("UI_TAB_COUNT", NativeFunction("UI_TAB_COUNT", 1, ui_tab_count))
        env.define("UI_TAB_REMOVE", NativeFunction("UI_TAB_REMOVE", 2, ui_tab_remove))
        env.define("UI_TAB_GET_PANEL", NativeFunction("UI_TAB_GET_PANEL", -1, ui_tab_get_panel))

        def ui_menu(i, a): return wx.MenuBar()
        def ui_menu_add(i, a):
            parent, label = a[0], str(a[1])
            if isinstance(parent, wx.MenuBar):
                menu = wx.Menu(); parent.Append(menu, label); return menu
            if isinstance(parent, wx.Menu):
                submenu = wx.Menu(); parent.AppendSubMenu(submenu, label); return submenu
            return None
        def ui_menu_item(i, a):
            menu, label, action = a[0], str(a[1]), str(a[2])
            if isinstance(menu, wx.Menu):
                item = menu.Append(wx.ID_ANY, label); win = getattr(i, 'main_window', None)
                if win:
                    def handler(evt): _call_anika(i, action, [])
                    win.Bind(wx.EVT_MENU, handler, item)
            return None
        def ui_menu_separator(i, a):
            if isinstance(a[0], wx.Menu): a[0].AppendSeparator()
            return None
        def ui_menu_check(i, a):
            menu, label, action = a[0], str(a[1]), str(a[2])
            if isinstance(menu, wx.Menu):
                item = menu.AppendCheckItem(wx.ID_ANY, label); win = getattr(i, 'main_window', None)
                if win:
                    def handler(evt): _call_anika(i, action, [item.IsChecked()])
                    win.Bind(wx.EVT_MENU, handler, item)
                return item
            return None
        def ui_menu_radio(i, a):
            menu, label, value, var = a[0], str(a[1]), str(a[2]), str(a[3])
            action = str(a[4]) if len(a) > 4 else ""
            if not hasattr(i, 'menu_radio_vars'): i.menu_radio_vars = {}
            if var not in i.menu_radio_vars: i.menu_radio_vars[var] = {"items": [], "value": ""}
            if isinstance(menu, wx.Menu):
                item = menu.AppendRadioItem(wx.ID_ANY, label)
                i.menu_radio_vars[var]["items"].append((item, value))
                win = getattr(i, 'main_window', None)
                if win:
                    def handler(evt):
                        i.menu_radio_vars[var]["value"] = value
                        if action: _call_anika(i, action, [value])
                    win.Bind(wx.EVT_MENU, handler, item)
            return None
        def ui_set_menu(i, a):
            win, mb = a[0], a[1]
            if isinstance(win, wx.Frame) and isinstance(mb, wx.MenuBar): win.SetMenuBar(mb)
            return None

        def ui_popup_menu(i, a): return wx.Menu()
        def ui_popup_item(i, a):
            menu, label, action = a[0], str(a[1]), str(a[2])
            if isinstance(menu, wx.Menu):
                item = menu.Append(wx.ID_ANY, label); win = getattr(i, 'main_window', None)
                if win:
                    def handler(evt): _call_anika(i, action, [])
                    win.Bind(wx.EVT_MENU, handler, item)
            return None
        def ui_popup_separator(i, a):
            if isinstance(a[0], wx.Menu): a[0].AppendSeparator()
            return None
        def ui_bind_popup(i, a):
            widget, menu = a[0], a[1]
            if isinstance(widget, wx.Window) and isinstance(menu, wx.Menu):
                def show(evt): widget.PopupMenu(menu, evt.GetPosition())
                widget.Bind(wx.EVT_CONTEXT_MENU, show)
            return None

        # ============================================================================
        # STATUS BAR (Advanced Multi-Field Support)
        # ============================================================================
        
        def ui_statusbar(i, a):
            """Create a simple status bar with one field.
            Args: win, [text]
            """
            win = a[0]
            text = str(a[1]) if len(a) > 1 else ""
            if isinstance(win, wx.Frame):
                sb = win.CreateStatusBar()
                sb.SetStatusText(text)
                return sb
            return None
        env.define("UI_STATUSBAR", NativeFunction("UI_STATUSBAR", -1, ui_statusbar))

        def ui_statusbar_fields(i, a):
            """Create a status bar with multiple sections (fields).
            Args: win, fields_list
            fields_list: List of strings or dicts {"text": "...", "width": 100}
                         width: -1 for proportional, >0 for fixed pixels.
            """
            win = a[0]
            fields = a[1] if len(a) > 1 else []
            if isinstance(win, wx.Frame):
                # Create status bar with N fields
                sb = win.CreateStatusBar(len(fields))
                
                texts = []
                widths = []
                
                for f in fields:
                    if isinstance(f, dict):
                        texts.append(str(f.get("text", "")))
                        widths.append(int(f.get("width", -1)))
                    elif isinstance(f, str):
                        texts.append(f)
                        widths.append(-1) # Default proportional
                    elif isinstance(f, (int, float)):
                        texts.append("")
                        widths.append(int(f))
                        
                for idx, txt in enumerate(texts):
                    sb.SetStatusText(txt, idx)
                    
                # Apply widths
                sb.SetStatusWidths(widths)
                return sb
            return None
        env.define("UI_STATUSBAR_FIELDS", NativeFunction("UI_STATUSBAR_FIELDS", -1, ui_statusbar_fields))

        def ui_statusbar_set(i, a):
            """Set text in a specific status bar field.
            Args: win, text, [field_index]
            """
            win = a[0]
            text = str(a[1]) if len(a) > 1 else ""
            field_idx = int(a[2]) if len(a) > 2 else 0
            
            if isinstance(win, wx.Frame):
                sb = win.GetStatusBar()
                if sb:
                    if 0 <= field_idx < sb.GetFieldsCount():
                        sb.SetStatusText(text, field_idx)
            return None
        env.define("UI_STATUSBAR_SET", NativeFunction("UI_STATUSBAR_SET", -1, ui_statusbar_set))

        def ui_statusbar_set_widths(i, a):
            """Set widths for status bar fields dynamically.
            Args: win, widths_list
            widths_list: List of integers. Negative = proportional, Positive = fixed pixels.
            """
            win = a[0]
            widths = a[1] if len(a) > 1 else []
            if isinstance(win, wx.Frame):
                sb = win.GetStatusBar()
                if sb:
                    w_list = [int(w) for w in widths]
                    # Ensure list length matches field count
                    current_count = sb.GetFieldsCount()
                    if len(w_list) < current_count:
                        w_list.extend([-1] * (current_count - len(w_list)))
                    elif len(w_list) > current_count:
                        w_list = w_list[:current_count]
                    sb.SetStatusWidths(w_list)
            return None
        env.define("UI_STATUSBAR_SET_WIDTHS", NativeFunction("UI_STATUSBAR_SET_WIDTHS", 2, ui_statusbar_set_widths))

        def ui_statusbar_set_border(i, a):
            """Set border style for a specific field.
            Args: win, field_index, style ("NORMAL", "FLAT", "RAISED")
            """
            win = a[0]
            field_idx = int(a[1]) if len(a) > 1 else 0
            style_str = str(a[2]).upper() if len(a) > 2 else "NORMAL"
            
            style_map = {
                "NORMAL": wx.STATUSBAR_NORMAL,
                "FLAT": wx.STATUSBAR_SB_FLAT,
                "RAISED": wx.STATUSBAR_SB_RAISED
            }
            style = style_map.get(style_str, wx.STATUSBAR_NORMAL)
            
            if isinstance(win, wx.Frame):
                sb = win.GetStatusBar()
                if sb:
                    if 0 <= field_idx < sb.GetFieldsCount():
                        # wxPython requires setting styles for ALL fields at once
                        count = sb.GetFieldsCount()
                        styles = [wx.STATUSBAR_NORMAL] * count
                        styles[field_idx] = style
                        sb.SetStatusStyles(styles)
            return None
        env.define("UI_STATUSBAR_SET_BORDER", NativeFunction("UI_STATUSBAR_SET_BORDER", -1, ui_statusbar_set_border))

        def ui_statusbar_set_color(i, a):
            """Set foreground/background colors for the status bar.
            Args: win, [fg_color], [bg_color]
            """
            win = a[0]
            fg = _to_wx_color(a[1]) if len(a) > 1 else None
            bg = _to_wx_color(a[2]) if len(a) > 2 else None
            
            if isinstance(win, wx.Frame):
                sb = win.GetStatusBar()
                if sb:
                    if fg: sb.SetForegroundColour(fg)
                    if bg: sb.SetBackgroundColour(bg)
                    sb.Refresh()
            return None
        env.define("UI_STATUSBAR_SET_COLOR", NativeFunction("UI_STATUSBAR_SET_COLOR", -1, ui_statusbar_set_color))

        def ui_statusbar_get_count(i, a):
            """Get the number of fields in the status bar.
            Args: win
            """
            win = a[0]
            if isinstance(win, wx.Frame):
                sb = win.GetStatusBar()
                if sb: return sb.GetFieldsCount()
            return 0
        env.define("UI_STATUSBAR_GET_COUNT", NativeFunction("UI_STATUSBAR_GET_COUNT", 1, ui_statusbar_get_count))

        def ui_statusbar_get_text(i, a):
            """Get text from a specific status bar field.
            Args: win, [field_index]
            """
            win = a[0]
            field_idx = int(a[1]) if len(a) > 1 else 0
            if isinstance(win, wx.Frame):
                sb = win.GetStatusBar()
                if sb:
                    if 0 <= field_idx < sb.GetFieldsCount():
                        return sb.GetStatusText(field_idx)
            return ""
        env.define("UI_STATUSBAR_GET_TEXT", NativeFunction("UI_STATUSBAR_GET_TEXT", -1, ui_statusbar_get_text))

        env.define("UI_MENU", NativeFunction("UI_MENU", 1, ui_menu))
        env.define("UI_MENU_ADD", NativeFunction("UI_MENU_ADD", 2, ui_menu_add))
        env.define("UI_MENU_ITEM", NativeFunction("UI_MENU_ITEM", 3, ui_menu_item))
        env.define("UI_MENU_SEPARATOR", NativeFunction("UI_MENU_SEPARATOR", 1, ui_menu_separator))
        env.define("UI_MENU_CHECK", NativeFunction("UI_MENU_CHECK", 3, ui_menu_check))
        env.define("UI_MENU_RADIO", NativeFunction("UI_MENU_RADIO", -1, ui_menu_radio))
        env.define("UI_SET_MENU", NativeFunction("UI_SET_MENU", 2, ui_set_menu))
        env.define("UI_POPUP_MENU", NativeFunction("UI_POPUP_MENU", 0, ui_popup_menu))
        env.define("UI_POPUP_ITEM", NativeFunction("UI_POPUP_ITEM", 3, ui_popup_item))
        env.define("UI_POPUP_SEPARATOR", NativeFunction("UI_POPUP_SEPARATOR", 1, ui_popup_separator))
        env.define("UI_BIND_POPUP", NativeFunction("UI_BIND_POPUP", 2, ui_bind_popup))

        # ==========================================================================
        # GENERIC GET/SET/COLOR/SIZE/BIND
        # ==========================================================================
        def ui_get(i, a):
            w = a[0]
            if isinstance(w, wx.TextCtrl): return w.GetValue()
            if isinstance(w, wx.StaticText): return w.GetLabel()
            if isinstance(w, wx.ComboBox): return w.GetValue()
            if isinstance(w, wx.CheckBox): return w.GetValue()
            if isinstance(w, wx.RadioButton): return w.GetValue()
            if isinstance(w, wx.ListBox):
                s = w.GetSelection(); return w.GetString(s) if s != wx.NOT_FOUND else ""
            if isinstance(w, wx.adv.DatePickerCtrl): return w.GetValue().FormatISODate()
            if isinstance(w, stc.StyledTextCtrl): return w.GetText()
            return ""
        def ui_get_client_size(i, a):
            w = a[0]
            if isinstance(w, wx.Frame): cs = w.GetClientSize(); return [cs.GetWidth(), cs.GetHeight()]
            elif isinstance(w, wx.Window): sz = w.GetSize(); return [sz.width, sz.height]
            return [0, 0]
        def ui_set(i, a):
            w, v = a[0], str(a[1])
            if isinstance(w, wx.TextCtrl): w.SetValue(v)
            elif isinstance(w, wx.StaticText): w.SetLabel(v)
            elif isinstance(w, wx.Button): w.SetLabel(v)
            elif isinstance(w, wx.ComboBox): w.SetValue(v)
            elif isinstance(w, wx.CheckBox): w.SetValue(v.upper() in ("TRUE","1","YES","ON"))
            elif isinstance(w, stc.StyledTextCtrl): w.SetText(v)
            return None
        def ui_color(i, a):
            w = a[0]; fg = _to_wx_color(a[1]) if len(a) > 1 else None; bg = _to_wx_color(a[2]) if len(a) > 2 else None
            if isinstance(w, wx.Window):
                if fg: w.SetForegroundColour(fg)
                if bg: w.SetBackgroundColour(bg)
                w.Refresh()
            return None
        def ui_focus(i, a):
            w = a[0]
            if isinstance(w, wx.Window): w.SetFocus()
            return None
        def ui_size(i, a):
            w = a[0]; nw = int(a[1]) if len(a) > 1 and a[1] else None; nh = int(a[2]) if len(a) > 2 and a[2] else None
            if isinstance(w, wx.Window) and (nw or nh):
                cur = w.GetSize(); w.SetSize(wx.Size(nw or cur.width, nh or cur.height))
            return None
        def ui_bind(i, a):
            w = a[0]
            etype = str(a[1]).upper()
            
            # ? FIX: Handle 4-argument calls for KEY_SHORTCUT
            if etype == "KEY_SHORTCUT" and len(a) >= 4:
                shortcut_str = str(a[2])  # "Ctrl+N"
                cb = str(a[3])            # "newFile"
                
                def parse_shortcut(shortcut):
                    parts = shortcut.split('+')
                    key = parts[-1].strip().upper()
                    modifiers = [p.strip().upper() for p in parts[:-1]]
                    
                    key_code = None
                    if len(key) == 1:
                        key_code = ord(key)
                    elif key == 'F1': key_code = wx.WXK_F1
                    elif key == 'F2': key_code = wx.WXK_F2
                    elif key == 'F3': key_code = wx.WXK_F3
                    elif key == 'F4': key_code = wx.WXK_F4
                    elif key == 'F5': key_code = wx.WXK_F5
                    elif key == 'F6': key_code = wx.WXK_F6
                    elif key == 'F7': key_code = wx.WXK_F7
                    elif key == 'F8': key_code = wx.WXK_F8
                    elif key == 'F9': key_code = wx.WXK_F9
                    elif key == 'F10': key_code = wx.WXK_F10
                    elif key == 'F11': key_code = wx.WXK_F11
                    elif key == 'F12': key_code = wx.WXK_F12
                    elif key == 'ENTER': key_code = wx.WXK_RETURN
                    elif key == 'ESC': key_code = wx.WXK_ESCAPE
                    elif key == 'TAB': key_code = wx.WXK_TAB
                    elif key == 'SPACE': key_code = wx.WXK_SPACE
                    elif key == 'DELETE': key_code = wx.WXK_DELETE
                    elif key == 'BACKSPACE': key_code = wx.WXK_BACK
                    
                    ctrl = 'CTRL' in modifiers or 'CONTROL' in modifiers
                    shift = 'SHIFT' in modifiers
                    alt = 'ALT' in modifiers
                    
                    return {'key': key_code, 'ctrl': ctrl, 'shift': shift, 'alt': alt}
                
                def matches_shortcut(evt, shortcut):
                    if shortcut['key'] is None:
                        return False
                    evt_key = evt.GetKeyCode()
                    evt_ctrl = evt.ControlDown()
                    evt_shift = evt.ShiftDown()
                    evt_alt = evt.AltDown()
                    return (evt_key == shortcut['key'] and 
                            evt_ctrl == shortcut['ctrl'] and 
                            evt_shift == shortcut['shift'] and 
                            evt_alt == shortcut['alt'])
                
                shortcut = parse_shortcut(shortcut_str)
                
                def shortcut_handler(evt):
                    if matches_shortcut(evt, shortcut):
                        _call_anika(i, cb, [w])
                        evt.Skip(False)
                    else:
                        evt.Skip()
                
                if isinstance(w, wx.Frame):
                    w.Bind(wx.EVT_CHAR_HOOK, shortcut_handler)
                elif hasattr(w, 'GetParent') and isinstance(w.GetParent(), wx.Frame):
                    w.GetParent().Bind(wx.EVT_CHAR_HOOK, shortcut_handler)
                else:
                    w.Bind(wx.EVT_CHAR_HOOK, shortcut_handler)
                
                return None
            
            # Standard 3-argument handling
            cb = str(a[2])
            
            def handler(evt):
                try:
                    if hasattr(evt, 'GetPosition'): 
                        pos = evt.GetPosition()
                        x, y = pos.x, pos.y
                    else: 
                        x, y = 0, 0
                except Exception: 
                    x, y = 0, 0
                _call_anika(i, cb, [w, x, y])
            
            def handler_simple(evt): 
                _call_anika(i, cb, [w])
            
            if etype == "CLICK":
                if isinstance(w, wx.Button): 
                    w.Bind(wx.EVT_BUTTON, handler_simple)
                else: 
                    w.Bind(wx.EVT_LEFT_UP, handler)
            elif etype == "CHANGE":
                if isinstance(w, wx.TextCtrl): 
                    w.Bind(wx.EVT_TEXT, handler_simple)
                elif isinstance(w, wx.ComboBox): 
                    w.Bind(wx.EVT_TEXT, handler_simple)
                elif isinstance(w, stc.StyledTextCtrl): 
                    w.Bind(stc.EVT_STC_CHANGE, handler_simple)
            elif etype == "CURSOR_MOVE":
                if isinstance(w, stc.StyledTextCtrl): 
                    w.Bind(stc.EVT_STC_UPDATEUI, handler_simple)
                elif isinstance(w, wx.TextCtrl): 
                    w.Bind(wx.EVT_KEY_UP, handler_simple)
            elif etype == "MOUSE_DOWN": 
                w.Bind(wx.EVT_LEFT_DOWN, handler)
            elif etype == "MOUSE_UP": 
                w.Bind(wx.EVT_LEFT_UP, handler)
            elif etype == "MOUSE_MOVE": 
                w.Bind(wx.EVT_MOTION, handler)
            elif etype == "MOUSE_DBLCLICK": 
                w.Bind(wx.EVT_LEFT_DCLICK, handler)
            elif etype == "RIGHT_CLICK": 
                w.Bind(wx.EVT_RIGHT_DOWN, handler)
            elif etype == "SELECT":
                if isinstance(w, wx.ListCtrl): 
                    w.Bind(wx.EVT_LIST_ITEM_SELECTED, handler_simple)
                elif isinstance(w, wx.ListBox): 
                    w.Bind(wx.EVT_LISTBOX, handler_simple)
                elif isinstance(w, wx.TreeCtrl): 
                    w.Bind(wx.EVT_TREE_SEL_CHANGED, handler_simple)
                elif isinstance(w, wx.ComboBox): 
                    w.Bind(wx.EVT_COMBOBOX, handler_simple)
            elif etype == "DOUBLE_CLICK": 
                w.Bind(wx.EVT_LEFT_DCLICK, handler_simple)
            elif etype == "KEY_RELEASE": 
                w.Bind(wx.EVT_KEY_UP, handler_simple)
            elif etype == "KEY_PRESS": 
                w.Bind(wx.EVT_KEY_DOWN, handler_simple)
            elif etype == "FOCUS_IN": 
                w.Bind(wx.EVT_SET_FOCUS, handler_simple)
            elif etype == "FOCUS_OUT": 
                w.Bind(wx.EVT_KILL_FOCUS, handler_simple)
            elif etype == "TAB_CHANGE" and isinstance(w, wx.Notebook): 
                w.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, handler_simple)
            elif etype == "RESIZE":
                def resize_handler(evt):
                    size = evt.GetSize()
                    new_w = size.GetWidth()
                    new_h = size.GetHeight()
                    _call_anika(i, cb, [w, new_w, new_h])
                    evt.Skip()
                w.Bind(wx.EVT_SIZE, resize_handler)
            
            return None
        def ui_mouse_pos(i, a):
            mode = str(a[0]).upper() if len(a) > 0 else "SCREEN"
            if mode == "SCREEN": pos = wx.GetMousePosition(); return [pos.x, pos.y]
            elif mode == "WINDOW" and len(a) > 1:
                win = a[1]
                if isinstance(win, wx.Window): pos = win.ScreenToClient(wx.GetMousePosition()); return [pos.x, pos.y]
            return [0, 0]
        def ui_capture_mouse(i, a):
            w = a[0]; capture = bool(a[1]) if len(a) > 1 else True
            if isinstance(w, wx.Window):
                if capture: w.CaptureMouse()
                else:
                    if w.HasCapture(): w.ReleaseMouse()
            return None

        env.define("UI_GET", NativeFunction("UI_GET", 1, ui_get))
        env.define("UI_GET_CLIENT_SIZE", NativeFunction("UI_GET_CLIENT_SIZE", 1, ui_get_client_size))
        env.define("UI_SET", NativeFunction("UI_SET", 2, ui_set))
        env.define("UI_COLOR", NativeFunction("UI_COLOR", -1, ui_color))
        env.define("UI_FOCUS", NativeFunction("UI_FOCUS", 1, ui_focus))
        env.define("UI_SIZE", NativeFunction("UI_SIZE", -1, ui_size))
        env.define("UI_BIND", NativeFunction("UI_BIND", -1, ui_bind))
        env.define("UI_MOUSE_POS", NativeFunction("UI_MOUSE_POS", -1, ui_mouse_pos))
        env.define("UI_CAPTURE_MOUSE", NativeFunction("UI_CAPTURE_MOUSE", -1, ui_capture_mouse))

        # ==========================================================================
        # ALERTS, FILE DIALOGS, TIMERS
        # ==========================================================================
        def ui_alert(i, a):
            dialog_shown, created_temp_app, app = False, False, None
            try:
                app = wx.GetApp()
                if app is None: app = wx.App(False); created_temp_app = True
                wx.MessageBox(str(a[0]), "Information", wx.OK | wx.ICON_INFORMATION); dialog_shown = True
            except Exception as e: print(f"\n{'='*70}\nINFORMATION\n{'='*70}\n{str(a[0])}\n{'='*70}\n")
            if created_temp_app and app is not None:
                try:
                    has_main_window = any(tlw is not None for tlw in wx.GetTopLevelWindows())
                    if not has_main_window:
                        try: app.ExitMainLoop()
                        except Exception: pass
                except Exception: pass
            return None
        def ui_alert_err(i, a):
            dialog_shown, created_temp_app, app = False, False, None
            try:
                app = wx.GetApp()
                if app is None: app = wx.App(False); created_temp_app = True
                wx.MessageBox(str(a[0]), "Error", wx.OK | wx.ICON_ERROR); dialog_shown = True
            except Exception as e: print(f"\n{'='*70}\nERROR\n{'='*70}\n{str(a[0])}\n{'='*70}\n")
            if created_temp_app and app is not None:
                try:
                    has_main_window = any(tlw is not None for tlw in wx.GetTopLevelWindows())
                    if not has_main_window:
                        try: app.ExitMainLoop()
                        except Exception: pass
                except Exception: pass
            return None
        def ui_confirm(i, a):
            dialog_shown, created_temp_app, app = False, False, None
            msg = str(a[0]) if len(a) > 0 and a[0] is not None else "Are you sure?"
            title = str(a[1]) if len(a) > 1 and a[1] is not None else "Confirm"
            user_confirmed = False
            
            try:
                app = wx.GetApp()
                if app is None: app = wx.App(False); created_temp_app = True
                result = wx.MessageBox(msg, title, wx.YES_NO | wx.ICON_QUESTION)
                if result == wx.YES: user_confirmed = True
                dialog_shown = True
            except Exception as e: print(f"\n{'='*70}\nCONFIRM: {msg}\n{'='*70}\n")
            
            if created_temp_app and app is not None:
                try:
                    has_main_window = any(tlw is not None for tlw in wx.GetTopLevelWindows())
                    if not has_main_window:
                        try: app.ExitMainLoop()
                        except Exception: pass
                except Exception: pass
                
            return user_confirmed

        env.define("UI_CONFIRM", NativeFunction("UI_CONFIRM", -1, ui_confirm))
        def ui_file_open(i, a):
            w = a[0] if a else None; parent = getattr(i, 'main_window', None)
            with wx.FileDialog(parent, "Open File", wildcard="All Files (*.*)|*.*", style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dlg:
                if dlg.ShowModal() == wx.ID_CANCEL: return ""
                path = dlg.GetPath()
                if w is not None:
                    try:
                        with open(path, 'r', encoding='utf-8', errors='replace') as f: content = f.read()
                        if isinstance(w, stc.StyledTextCtrl): w.SetText(content)
                        elif isinstance(w, wx.TextCtrl): w.SetValue(content)
                    except Exception: pass
                return path
        def ui_file_save(i, a):
            w = a[0] if a else None; parent = getattr(i, 'main_window', None)
            with wx.FileDialog(parent, "Save Script", wildcard="FMS (*.fms)|*.fms|All|*.*", style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT, defaultFile="script.fms") as dlg:
                if dlg.ShowModal() == wx.ID_CANCEL: return ""
                path = dlg.GetPath()
                try:
                    content = ""
                    if w is not None:
                        if isinstance(w, stc.StyledTextCtrl): content = w.GetText()
                        elif isinstance(w, wx.TextCtrl): content = w.GetValue()
                    with open(path, 'w', encoding='utf-8') as f: f.write(content)
                    return path
                except Exception as e: return "ERROR: " + str(e)
                
        def ui_folder_open(i, a):
            parent = getattr(i, 'main_window', None)
            title = str(a[0]) if len(a) > 0 and a[0] else "Select Folder"
            default_path = str(a[1]) if len(a) > 1 and a[1] else ""
            
            with wx.DirDialog(parent, title, default_path, wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dlg:
                if dlg.ShowModal() == wx.ID_CANCEL:
                    return ""
                return dlg.GetPath()
                
        env.define("UI_FOLDER_OPEN", NativeFunction("UI_FOLDER_OPEN", -1, ui_folder_open))

        def ui_after(i, a):
            delay, cb = int(a[0]), str(a[1]); win = getattr(i, 'main_window', None)
            if win is None: raise FMS_Error("UI_AFTER requires UI_WINDOW")
            timer = wx.Timer(win)
            def on_timer(evt): _call_anika(i, cb, []); timer.Stop()
            win.Bind(wx.EVT_TIMER, on_timer, timer); timer.Start(delay, oneShot=True)
            return id(timer)
        def ui_after_cancel(i, a): return None

        env.define("UI_ALERT", NativeFunction("UI_ALERT", 1, ui_alert))
        env.define("UI_ALERT_ERR", NativeFunction("UI_ALERT_ERR", 1, ui_alert_err))
        env.define("UI_FILE_OPEN", NativeFunction("UI_FILE_OPEN", -1, ui_file_open))
        env.define("UI_FILE_SAVE", NativeFunction("UI_FILE_SAVE", -1, ui_file_save))
        env.define("UI_AFTER", NativeFunction("UI_AFTER", 2, ui_after))
        env.define("UI_AFTER_CANCEL", NativeFunction("UI_AFTER_CANCEL", 1, ui_after_cancel))

        # ==========================================================================
        # MARKDOWN EDITOR
        # ==========================================================================
        def ui_md_editor(i, a):
            parent = a[0]; target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            panel = wx.Panel(target); sizer = wx.BoxSizer(wx.HORIZONTAL); panel.SetSizer(sizer)
            src = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_NOHIDESEL)
            preview = wx.html2.WebView.New(panel)
            sizer.Add(src, 1, wx.EXPAND | wx.ALL, 5); sizer.Add(preview, 1, wx.EXPAND | wx.ALL, 5)
            panel._md_source = src; panel._md_preview = preview
            def on_change(evt):
                try:
                    import markdown
                    html = markdown.markdown(src.GetValue(), extensions=['fenced_code','tables','toc'])
                    preview.SetPage(html, "")
                except: pass
            src.Bind(wx.EVT_TEXT, on_change)
            coords = _parse_pos_args(a, 1); _apply_layout(target, panel, coords)
            return panel
        def ui_md_get(i, a):
            ed = a[0]
            if hasattr(ed, '_md_source'): return ed._md_source.GetValue()
            return ""
        def ui_md_set(i, a):
            ed, content = a[0], str(a[1])
            if hasattr(ed, '_md_source'): ed._md_source.SetValue(content)
            return None
        def ui_md_refresh(i, a):
            ed = a[0]
            if hasattr(ed, '_md_source') and hasattr(ed, '_md_preview'):
                try:
                    import markdown
                    html = markdown.markdown(ed._md_source.GetValue(), extensions=['fenced_code','tables','toc'])
                    ed._md_preview.SetPage(html, "")
                except: pass
            return None

        env.define("UI_MD_EDITOR", NativeFunction("UI_MD_EDITOR", -1, ui_md_editor))
        env.define("UI_MD_GET", NativeFunction("UI_MD_GET", 1, ui_md_get))
        env.define("UI_MD_SET", NativeFunction("UI_MD_SET", 2, ui_md_set))
        env.define("UI_MD_REFRESH", NativeFunction("UI_MD_REFRESH", 1, ui_md_refresh))


        # ==========================================================================
        # RICH TEXT EDITOR (AbiWord-like word processor core)
        # ==========================================================================

        def _get_selection_range(rt):
            """Get selection range as (start, end) tuple."""
            try:
                sel = rt.GetSelection()
                if isinstance(sel, tuple) and len(sel) == 2:
                    return sel[0], sel[1]
            except Exception:
                pass
            return 0, 0

        def _apply_char_attr(rt, attr):
            """Apply character attributes (color, font) to selection or default."""
            try:
                start, end = _get_selection_range(rt)
                if start != end:
                    rt.SetStyle(start, end, attr)
                else:
                    rt.SetDefaultStyle(attr)
                rt.Refresh()
            except Exception:
                pass

        def _apply_para_attr(rt, attr):
            """Apply paragraph attributes (alignment, bullets) to current paragraph."""
            try:
                start, end = _get_selection_range(rt)
                if start != end:
                    rt.SetStyle(start, end, attr)
                else:
                    caret = rt.GetInsertionPoint()
                    rt.SetParagraphStyle(caret, attr)
                rt.Refresh()
            except Exception:
                pass

        # --- CORE ---
        def ui_richtext(i, a):
            parent = a[0]
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            rt = richtext.RichTextCtrl(target, style=wx.VSCROLL | wx.NO_BORDER)
            rt.SetFont(wx.Font(11, wx.FONTFAMILY_ROMAN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName="Calibri"))
            rt.SetMargins(wx.Point(72, 72))
            coords = _parse_pos_args(a, 1)
            _apply_layout(target, rt, coords)
            return rt

        def ui_richtext_clear(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): rt.Clear()
            return None

        # --- TEXT MANIPULATION (ADDED) ---
        def ui_richtext_get_text(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): return rt.GetValue()
            return ""

        def ui_richtext_set_text(i, a):
            rt = a[0]
            text = str(a[1]) if len(a) > 1 else ""
            if isinstance(rt, richtext.RichTextCtrl): rt.SetValue(text)
            return None

        def ui_richtext_get_selection(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): return rt.GetStringSelection()
            return ""

        def ui_richtext_has_selection(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): return rt.HasSelection()
            return False

        # --- FORMATTING ---
        def ui_richtext_apply_bold(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                try: rt.ApplyBoldToSelection()
                except: pass
            return None

        def ui_richtext_apply_italic(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                try: rt.ApplyItalicToSelection()
                except: pass
            return None

        def ui_richtext_apply_underline(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                try: rt.ApplyUnderlineToSelection()
                except: pass
            return None

        def ui_richtext_set_font(i, a):
            rt = a[0]
            font_name = str(a[1]) if len(a) > 1 else "Calibri"
            if isinstance(rt, richtext.RichTextCtrl):
                attr = richtext.RichTextAttr()
                attr.SetFontFaceName(font_name)
                _apply_char_attr(rt, attr)
            return None

        def ui_richtext_set_font_size(i, a):
            rt = a[0]
            size = int(a[1]) if len(a) > 1 else 11
            if isinstance(rt, richtext.RichTextCtrl):
                attr = richtext.RichTextAttr()
                f = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
                attr.SetFontPointSize(f.GetPointSize())
                _apply_char_attr(rt, attr)
            return None

        def ui_richtext_set_text_color(i, a):
            rt = a[0]
            color_str = str(a[1]).lstrip('#') if len(a) > 1 else "000000"
            if isinstance(rt, richtext.RichTextCtrl):
                try:
                    r = int(color_str[0:2], 16)
                    g = int(color_str[2:4], 16)
                    b = int(color_str[4:6], 16)
                    attr = richtext.RichTextAttr()
                    attr.SetTextColour(wx.Colour(r, g, b))
                    _apply_char_attr(rt, attr)
                except: pass
            return None

        def ui_richtext_set_bg_color(i, a):
            rt = a[0]
            color_str = str(a[1]).lstrip('#') if len(a) > 1 else "FFFFFF"
            if isinstance(rt, richtext.RichTextCtrl):
                try:
                    r = int(color_str[0:2], 16)
                    g = int(color_str[2:4], 16)
                    b = int(color_str[4:6], 16)
                    attr = richtext.RichTextAttr()
                    attr.SetBackgroundColour(wx.Colour(r, g, b))
                    _apply_char_attr(rt, attr)
                except: pass
            return None

        def ui_richtext_set_alignment(i, a):
            rt = a[0]
            align = str(a[1]).upper() if len(a) > 1 else "LEFT"
            if isinstance(rt, richtext.RichTextCtrl):
                align_map = {"LEFT": wx.TEXT_ALIGNMENT_LEFT, "CENTER": wx.TEXT_ALIGNMENT_CENTRE, "RIGHT": wx.TEXT_ALIGNMENT_RIGHT, "JUSTIFY": wx.TEXT_ALIGNMENT_JUSTIFIED}
                wx_align = align_map.get(align, wx.TEXT_ALIGNMENT_LEFT)
                try:
                    attr = richtext.RichTextAttr()
                    attr.SetAlignment(wx_align)
                    _apply_para_attr(rt, attr)
                except: pass
            return None

        def ui_richtext_set_strikethrough(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                # FIXED: Use TextEffects instead of modifying font object directly
                attr = richtext.RichTextAttr()
                attr.SetTextEffects(richtext.RICHTEXT_EFFECT_STRIKETHROUGH)
                flags = richtext.RichTextAttrFlags()
                flags.SetTextEffects(True)
                attr.SetFlags(flags)
                _apply_char_attr(rt, attr)
            return None

        def ui_richtext_set_superscript(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                attr = richtext.RichTextAttr()
                attr.SetTextEffects(richtext.RICHTEXT_EFFECT_SUPERSCRIPT)
                flags = richtext.RichTextAttrFlags()
                flags.SetTextEffects(True)
                attr.SetFlags(flags)
                _apply_char_attr(rt, attr)
            return None

        def ui_richtext_set_subscript(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                attr = richtext.RichTextAttr()
                attr.SetTextEffects(richtext.RICHTEXT_EFFECT_SUBSCRIPT)
                flags = richtext.RichTextAttrFlags()
                flags.SetTextEffects(True)
                attr.SetFlags(flags)
                _apply_char_attr(rt, attr)
            return None

        def ui_richtext_set_bullet(i, a):
            rt = a[0]
            style = str(a[1]).lower() if len(a) > 1 else "bullet"
            if isinstance(rt, richtext.RichTextCtrl):
                try:
                    attr = richtext.RichTextAttr()
                    if style == "bullet":
                        attr.SetBulletStyle(wx.TEXT_ATTR_BULLET_STYLE_SYMBOL)
                        attr.SetBulletText("-")
                        attr.SetBulletFontName("Symbol")
                    else:
                        attr.SetBulletStyle(wx.TEXT_ATTR_BULLET_STYLE_ARABIC)
                        attr.SetBulletText("1")
                    _apply_para_attr(rt, attr)
                except:
                    rt.WriteText("- " if style == "bullet" else "1. ")
            return None

        def ui_richtext_set_indent(i, a): # ADDED
            rt = a[0]
            indent_px = int(a[1]) if len(a) > 1 else 20
            if isinstance(rt, richtext.RichTextCtrl):
                attr = richtext.RichTextAttr()
                attr.SetLeftIndent(indent_px, 0)
                _apply_para_attr(rt, attr)
            return None

        # --- INSERT OPERATIONS ---
        def ui_richtext_insert_image(i, a):
            rt = a[0]
            img_path = str(a[1])
            width = int(a[2]) if len(a) > 2 and a[2] else 0
            height = int(a[3]) if len(a) > 3 and a[3] else 0
            if isinstance(rt, richtext.RichTextCtrl):
                try:
                    img = wx.Image(img_path, wx.BITMAP_TYPE_ANY)
                    if not img.IsOk(): raise FMS_Error("Failed to load image: " + img_path, error_type="File Error")
                    if width > 0 and height > 0: img = img.Scale(width, height, wx.IMAGE_QUALITY_HIGH)
                    elif width > 0:
                        ratio = img.GetHeight() / img.GetWidth()
                        img = img.Scale(width, int(width * ratio), wx.IMAGE_QUALITY_HIGH)
                    bmp = wx.Bitmap(img)
                    rt.WriteImage(bmp)
                    return "SUCCESS"
                except FMS_Error: raise
                except Exception as e: raise FMS_Error("Failed to insert image: " + str(e), error_type="Runtime Error")
            return None

        def ui_richtext_insert_table(i, a):
            rt = a[0]
            rows = int(a[1]) if len(a) > 1 else 3
            cols = int(a[2]) if len(a) > 2 else 3
            if isinstance(rt, richtext.RichTextCtrl):
                try:
                    # Fallback to tab-separated text for stability, as HTML tables often crash RichTextCtrl
                    for r in range(rows):
                        for c in range(cols):
                            rt.WriteText("Cell")
                            if c < cols - 1: rt.WriteText("\t")
                        if r < rows - 1: rt.WriteText("\n")
                    return "SUCCESS"
                except Exception as e:
                    return "ERROR: " + str(e)
            return "ERROR: Not a richtext control"

        def ui_richtext_insert_hyperlink(i, a):
            rt = a[0]
            url = str(a[1])
            display = str(a[2]) if len(a) > 2 and a[2] else url
            if isinstance(rt, richtext.RichTextCtrl):
                try:
                    attr = richtext.RichTextAttr()
                    attr.SetTextColour(wx.Colour(0, 0, 255))
                    attr.SetFontUnderlined(True)
                    rt.BeginStyle(attr)
                    rt.WriteText(display)
                    rt.EndStyle()
                    return "SUCCESS"
                except Exception as e: return "ERROR: " + str(e)
            return "ERROR: Not a richtext control"

        def ui_richtext_insert_field(i, a):
            rt = a[0]
            field_type = str(a[1]).lower() if len(a) > 1 else "date"
            if isinstance(rt, richtext.RichTextCtrl):
                now = datetime.datetime.now()
                if field_type == "date": rt.WriteText(now.strftime("%Y-%m-%d"))
                elif field_type == "time": rt.WriteText(now.strftime("%H:%M:%S"))
                elif field_type == "datetime": rt.WriteText(now.strftime("%Y-%m-%d %H:%M:%S"))
                elif field_type == "page": rt.WriteText("[Page]")
                else: rt.WriteText("[" + field_type + "]")
            return None

        def ui_richtext_hr(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                rt.WriteText("\n")
                attr = richtext.RichTextAttr()
                attr.SetBorderPen(wx.Pen(wx.Colour(128, 128, 128), 1, wx.PENSTYLE_SOLID))
                rt.BeginParagraphSpacing(10, 10)
                rt.WriteText("-" * 80)
                rt.EndParagraphSpacing()
                rt.WriteText("\n")
            return None

        def ui_richtext_line_break(i, a): # ADDED
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): rt.WriteText("\n")
            return None

        def ui_richtext_page_break(i, a): # ADDED
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): rt.WriteText("\f") # Form feed character
            return None

        # --- EDIT OPERATIONS ---
        def ui_richtext_undo(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl) and rt.CanUndo(): rt.Undo()
            return None

        def ui_richtext_redo(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl) and rt.CanRedo(): rt.Redo()
            return None

        def ui_richtext_cut(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): rt.Cut()
            return None

        def ui_richtext_copy(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): rt.Copy()
            return None

        def ui_richtext_paste(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): rt.Paste()
            return None

        def ui_richtext_select_all(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): rt.SelectAll()
            return None

        # --- FILE OPERATIONS ---
        def ui_richtext_save(i, a):
            rt = a[0]
            path = str(a[1])
            fmt = str(a[2]).lower() if len(a) > 2 and a[2] else ""
            if not isinstance(rt, richtext.RichTextCtrl): return "ERROR: Not a richtext control"
            try:
                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                ext = os.path.splitext(path)[1].lower()
                if fmt == "" or fmt == "auto":
                    if ext == ".rtf": fmt = "rtf"
                    elif ext in [".html", ".htm"]: fmt = "html"
                    else: fmt = "txt"
                if fmt == "txt":
                    with open(path, 'w', encoding='utf-8') as f: f.write(rt.GetValue())
                    return "SUCCESS"
                handler = richtext.RichTextBuffer.FindHandlerByType(richtext.RICHTEXT_FILE_TYPE_RTF if fmt == "rtf" else richtext.RICHTEXT_FILE_TYPE_HTML)
                if handler is None: return "ERROR: No handler found"
                stream = wx.FileOutputStream(path)
                if stream.IsOk(): rt.GetBuffer().SaveStream(stream, handler); stream.Close(); return "SUCCESS"
                return "ERROR: Could not open file"
            except Exception as e: return "ERROR: " + str(e)

        def ui_richtext_load(i, a):
            rt = a[0]
            path = str(a[1])
            fmt = str(a[2]).lower() if len(a) > 2 and a[2] else ""
            if not isinstance(rt, richtext.RichTextCtrl): return "ERROR: Not a richtext control"
            try:
                if not os.path.exists(path): return "ERROR: File not found"
                ext = os.path.splitext(path)[1].lower()
                if fmt == "" or fmt == "auto":
                    if ext == ".rtf": fmt = "rtf"
                    elif ext in [".html", ".htm"]: fmt = "html"
                    else: fmt = "txt"
                if fmt == "txt":
                    with open(path, 'r', encoding='utf-8') as f: rt.SetValue(f.read())
                    return "SUCCESS"
                handler = richtext.RichTextBuffer.FindHandlerByType(richtext.RICHTEXT_FILE_TYPE_RTF if fmt == "rtf" else richtext.RICHTEXT_FILE_TYPE_HTML)
                if handler is None: return "ERROR: No handler found"
                stream = wx.FileInputStream(path)
                if stream.IsOk(): rt.GetBuffer().LoadStream(stream, handler); stream.Close(); rt.Refresh(); return "SUCCESS"
                return "ERROR: Could not open file"
            except Exception as e: return "ERROR: " + str(e)

        # --- STATISTICS ---
        def ui_richtext_word_count(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                text = rt.GetValue().strip()
                return len(text.split()) if text else 0
            return 0

        def ui_richtext_char_count(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl): return len(rt.GetValue())
            return 0

        # --- FIND & REPLACE ---
        def ui_richtext_find(i, a):
            rt = a[0]
            search = str(a[1])
            from_cursor = bool(a[2]) if len(a) > 2 else True
            if not isinstance(rt, richtext.RichTextCtrl) or not search: return -1
            try:
                text = rt.GetValue()
                pos = rt.GetInsertionPoint() if from_cursor else 0
                idx = text.find(search, pos)
                if idx == -1: idx = text.find(search)
                if idx >= 0: rt.SetSelection(idx, idx + len(search)); rt.ShowPosition(idx); return idx
                return -1
            except: return -1

        def ui_richtext_replace(i, a):
            rt = a[0]
            search = str(a[1])
            replace = str(a[2])
            replace_all = bool(a[3]) if len(a) > 3 else False
            if not isinstance(rt, richtext.RichTextCtrl) or not search: return 0
            try:
                if replace_all:
                    text = rt.GetValue()
                    count = text.count(search)
                    if count > 0: rt.SetValue(text.replace(search, replace))
                    return count
                else:
                    start, end = _get_selection_range(rt)
                    if start != end:
                        selected = rt.GetValue()[start:end]
                        if selected == search: rt.DeleteSelection(); rt.WriteText(replace); return 1
                    pos = ui_richtext_find(i, [rt, search, True])
                    if pos >= 0: rt.DeleteSelection(); rt.WriteText(replace); return 1
                    return 0
            except: return 0

        # --- VIEW & PRINT ---
        def ui_richtext_zoom(i, a):
            rt = a[0]
            zoom = int(a[1]) if len(a) > 1 else 100
            if isinstance(rt, richtext.RichTextCtrl):
                zoom = max(50, min(400, zoom))
                try: rt.GetBuffer().SetScale(zoom / 100.0); rt.Refresh()
                except: pass
            return None

        def ui_richtext_print(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                try:
                    data = wx.PrintData()
                    data.SetPrintMode(wx.PRINT_MODE_PRINTER)
                    pdd = wx.PrintDialogData(data)
                    rtp = richtext.RichTextPrinting()
                    rtp.Print(rt.GetBuffer())
                    return "SUCCESS"
                except Exception as e: return "ERROR: " + str(e)
            return "ERROR: Not a richtext control"

        def ui_richtext_page_setup(i, a):
            rt = a[0]
            if isinstance(rt, richtext.RichTextCtrl):
                try:
                    dlg = wx.PageSetupDialog(None, wx.PageSetupDialogData())
                    res = "SUCCESS" if dlg.ShowModal() == wx.ID_OK else "CANCELLED"
                    dlg.Destroy()
                    return res
                except Exception as e: return "ERROR: " + str(e)
            return "ERROR: Not a richtext control"

        # --- REGISTRATION ---
        env.define("UI_RICHTEXT", NativeFunction("UI_RICHTEXT", -1, ui_richtext))
        env.define("UI_RICHTEXT_CLEAR", NativeFunction("UI_RICHTEXT_CLEAR", 1, ui_richtext_clear))

        # Text Manipulation (NEW)
        env.define("UI_RICHTEXT_GET_TEXT", NativeFunction("UI_RICHTEXT_GET_TEXT", 1, ui_richtext_get_text))
        env.define("UI_RICHTEXT_SET_TEXT", NativeFunction("UI_RICHTEXT_SET_TEXT", 2, ui_richtext_set_text))
        env.define("UI_RICHTEXT_GET_SELECTION", NativeFunction("UI_RICHTEXT_GET_SELECTION", 1, ui_richtext_get_selection))
        env.define("UI_RICHTEXT_HAS_SELECTION", NativeFunction("UI_RICHTEXT_HAS_SELECTION", 1, ui_richtext_has_selection))

        # Formatting
        env.define("UI_RICHTEXT_APPLY_BOLD", NativeFunction("UI_RICHTEXT_APPLY_BOLD", 1, ui_richtext_apply_bold))
        env.define("UI_RICHTEXT_APPLY_ITALIC", NativeFunction("UI_RICHTEXT_APPLY_ITALIC", 1, ui_richtext_apply_italic))
        env.define("UI_RICHTEXT_APPLY_UNDERLINE", NativeFunction("UI_RICHTEXT_APPLY_UNDERLINE", 1, ui_richtext_apply_underline))
        env.define("UI_RICHTEXT_SET_FONT", NativeFunction("UI_RICHTEXT_SET_FONT", -1, ui_richtext_set_font))
        env.define("UI_RICHTEXT_SET_FONT_SIZE", NativeFunction("UI_RICHTEXT_SET_FONT_SIZE", -1, ui_richtext_set_font_size))
        env.define("UI_RICHTEXT_SET_TEXT_COLOR", NativeFunction("UI_RICHTEXT_SET_TEXT_COLOR", -1, ui_richtext_set_text_color))
        env.define("UI_RICHTEXT_SET_BG_COLOR", NativeFunction("UI_RICHTEXT_SET_BG_COLOR", -1, ui_richtext_set_bg_color))
        env.define("UI_RICHTEXT_SET_ALIGN", NativeFunction("UI_RICHTEXT_SET_ALIGN", -1, ui_richtext_set_alignment))
        env.define("UI_RICHTEXT_STRIKETHROUGH", NativeFunction("UI_RICHTEXT_STRIKETHROUGH", 1, ui_richtext_set_strikethrough))
        env.define("UI_RICHTEXT_SUPERSCRIPT", NativeFunction("UI_RICHTEXT_SUPERSCRIPT", 1, ui_richtext_set_superscript))
        env.define("UI_RICHTEXT_SUBSCRIPT", NativeFunction("UI_RICHTEXT_SUBSCRIPT", 1, ui_richtext_set_subscript))
        env.define("UI_RICHTEXT_SET_BULLET", NativeFunction("UI_RICHTEXT_SET_BULLET", -1, ui_richtext_set_bullet))
        env.define("UI_RICHTEXT_SET_INDENT", NativeFunction("UI_RICHTEXT_SET_INDENT", -1, ui_richtext_set_indent)) # NEW

        # Insert Operations
        env.define("UI_RICHTEXT_INSERT_IMAGE", NativeFunction("UI_RICHTEXT_INSERT_IMAGE", -1, ui_richtext_insert_image))
        env.define("UI_RICHTEXT_INSERT_TABLE", NativeFunction("UI_RICHTEXT_INSERT_TABLE", -1, ui_richtext_insert_table))
        env.define("UI_RICHTEXT_HR", NativeFunction("UI_RICHTEXT_HR", 1, ui_richtext_hr))
        env.define("UI_RICHTEXT_INSERT_HYPERLINK", NativeFunction("UI_RICHTEXT_INSERT_HYPERLINK", -1, ui_richtext_insert_hyperlink))
        env.define("UI_RICHTEXT_INSERT_FIELD", NativeFunction("UI_RICHTEXT_INSERT_FIELD", -1, ui_richtext_insert_field))
        env.define("UI_RICHTEXT_LINE_BREAK", NativeFunction("UI_RICHTEXT_LINE_BREAK", 1, ui_richtext_line_break)) # NEW
        env.define("UI_RICHTEXT_PAGE_BREAK", NativeFunction("UI_RICHTEXT_PAGE_BREAK", 1, ui_richtext_page_break)) # NEW

        # Edit Operations
        env.define("UI_RICHTEXT_UNDO", NativeFunction("UI_RICHTEXT_UNDO", 1, ui_richtext_undo))
        env.define("UI_RICHTEXT_REDO", NativeFunction("UI_RICHTEXT_REDO", 1, ui_richtext_redo))
        env.define("UI_RICHTEXT_CUT", NativeFunction("UI_RICHTEXT_CUT", 1, ui_richtext_cut))
        env.define("UI_RICHTEXT_COPY", NativeFunction("UI_RICHTEXT_COPY", 1, ui_richtext_copy))
        env.define("UI_RICHTEXT_PASTE", NativeFunction("UI_RICHTEXT_PASTE", 1, ui_richtext_paste))
        env.define("UI_RICHTEXT_SELECT_ALL", NativeFunction("UI_RICHTEXT_SELECT_ALL", 1, ui_richtext_select_all))

        # File Operations
        env.define("UI_RICHTEXT_SAVE", NativeFunction("UI_RICHTEXT_SAVE", -1, ui_richtext_save))
        env.define("UI_RICHTEXT_LOAD", NativeFunction("UI_RICHTEXT_LOAD", -1, ui_richtext_load))

        # Statistics
        env.define("UI_RICHTEXT_WORD_COUNT", NativeFunction("UI_RICHTEXT_WORD_COUNT", 1, ui_richtext_word_count))
        env.define("UI_RICHTEXT_CHAR_COUNT", NativeFunction("UI_RICHTEXT_CHAR_COUNT", 1, ui_richtext_char_count))

        # Find & Replace
        env.define("UI_RICHTEXT_FIND", NativeFunction("UI_RICHTEXT_FIND", -1, ui_richtext_find))
        env.define("UI_RICHTEXT_REPLACE", NativeFunction("UI_RICHTEXT_REPLACE", -1, ui_richtext_replace))

        # View & Print
        env.define("UI_RICHTEXT_ZOOM", NativeFunction("UI_RICHTEXT_ZOOM", -1, ui_richtext_zoom))
        env.define("UI_RICHTEXT_PRINT", NativeFunction("UI_RICHTEXT_PRINT", 1, ui_richtext_print))
        env.define("UI_RICHTEXT_PAGE_SETUP", NativeFunction("UI_RICHTEXT_PAGE_SETUP", 1, ui_richtext_page_setup))
        
        # ------------------------------------------------------------------
        # CLOSE-TIME RACE GUARD (AnikaLang 1.2 robustness patch)
        # When a window closes, wx destroys child widgets instantly, but pending
        # events (resize / button / text / timer) can still fire and call UI
        # accessors on those dead C++ objects -> RuntimeError. Wrap every UI
        # accessor so a deleted widget silently returns a safe default instead
        # of crashing the whole app. FMS_Error (e.g. NULL widget) still raises.
        # ------------------------------------------------------------------
        _SAFE_DEFAULTS = {
            "UI_TEXT_GET": "", "UI_GET": "", "UI_TEXT_GET_SELECTION": "",
            "UI_GET_POS": [0, 0], "UI_GET_SIZE": [0, 0], "UI_GET_CLIENT_SIZE": [0, 0],
            "UI_EDITOR_GET_CURSOR": "1:1", "UI_EDITOR_GET_LINE_COUNT": "0",
            "UI_EDITOR_GET_LINE": "", "UI_EDITOR_GET_FUNCTIONS": [],
            "UI_LISTVIEW_GET_SELECTED": None, "UI_LISTBOX_GET": None,
            "UI_CHECKBOX_GET": False, "UI_RADIO_GET": None,
            "UI_COMBOBOX_GET_INDEX": -1, "UI_COMBOBOX_GET_COUNT": 0,
            "UI_TAB_GET_INDEX": -1, "UI_TAB_COUNT": 0, "UI_TAB_GET_TITLE": None,
            "UI_TAB_GET_PANEL": None,
            "UI_STATUSBAR_GET_COUNT": 0, "UI_STATUSBAR_GET_TEXT": "",
            "UI_MD_GET": "", "UI_RICHTEXT_GET_TEXT": "",
            "UI_RICHTEXT_GET_SELECTION": "", "UI_RICHTEXT_HAS_SELECTION": False,
            "UI_RICHTEXT_WORD_COUNT": 0, "UI_RICHTEXT_CHAR_COUNT": 0,
            "UI_RICHTEXT_FIND": -1, "UI_RICHTEXT_REPLACE": 0,
        }
        _SAFE_MUTATORS = {
            "UI_TEXT_SET", "UI_TEXT_APPEND", "UI_SET", "UI_COLOR", "UI_FONT",
            "UI_REFRESH", "UI_POS", "UI_SIZE", "UI_FOCUS", "UI_HIGHLIGHT",
            "UI_SHOW", "UI_HIDE", "UI_ENABLE", "UI_DISABLE", "UI_BRING_TO_FRONT",
            "UI_LAYOUT_REFRESH", "UI_BUTTON_SET_STATE",
            "UI_LISTVIEW_CLEAR", "UI_LISTVIEW_INSERT", "UI_LISTVIEW_AUTOFIT",
            "UI_LISTVIEW_REFRESH", "UI_LISTVIEW_SET_COLUMN_WIDTH", "UI_LISTVIEW_SET_SELECTION",
            "UI_LISTBOX_CLEAR", "UI_LISTBOX_INSERT", "UI_LISTBOX_SELECT",
            "UI_TREE_INSERT", "UI_TREE_CLEAR", "UI_TREE_DELETE", "UI_TREE_SET_TEXT", "UI_TREE_EXPAND",
            "UI_HTML_SET", "UI_HTML_CLEAR",
            "UI_SHEET_SET", "UI_SHEET_GET", "UI_SHEET_INSERT", "UI_SHEET_DELETE", "UI_SHEET_CLEAR",
            "UI_SHEET_HEADERS", "UI_SHEET_CELL_SET", "UI_SHEET_CELL_GET", "UI_SHEET_CELL_STYLE",
            "UI_SHEET_SET_COLUMN_WIDTH", "UI_SHEET_ROW_HEIGHT", "UI_SHEET_RESIZE",
            "UI_SHEET_AUTOSIZE", "UI_SHEET_READONLY", "UI_SHEET_SELECTED", "UI_SHEET_BIND",
            "UI_CHECKBOX_SET", "UI_RADIO_SET", "UI_COMBOBOX_CLEAR", "UI_COMBOBOX_ADD",
            "UI_COMBOBOX_SET_ITEMS", "UI_COMBOBOX_SET_INDEX", "UI_COMBOBOX_DELETE",
            "UI_TAB_ADD", "UI_TAB_SET_TITLE", "UI_TAB_SELECT", "UI_TAB_SELECT_BY_NAME", "UI_TAB_REMOVE",
            "UI_RICHTEXT_CLEAR", "UI_RICHTEXT_SET_TEXT", "UI_RICHTEXT_APPLY_BOLD",
            "UI_RICHTEXT_APPLY_ITALIC", "UI_RICHTEXT_APPLY_UNDERLINE", "UI_RICHTEXT_SET_FONT",
            "UI_RICHTEXT_SET_FONT_SIZE", "UI_RICHTEXT_SET_TEXT_COLOR", "UI_RICHTEXT_SET_BG_COLOR",
            "UI_RICHTEXT_SET_ALIGN", "UI_RICHTEXT_SET_BULLET", "UI_RICHTEXT_SET_INDENT",
            "UI_RICHTEXT_SET_STRIKETHROUGH", "UI_RICHTEXT_SUPERSCRIPT", "UI_RICHTEXT_SUBSCRIPT",
            "UI_RICHTEXT_INSERT_IMAGE", "UI_RICHTEXT_INSERT_TABLE", "UI_RICHTEXT_HR",
            "UI_RICHTEXT_INSERT_HYPERLINK", "UI_RICHTEXT_INSERT_FIELD", "UI_RICHTEXT_LINE_BREAK",
            "UI_RICHTEXT_PAGE_BREAK", "UI_RICHTEXT_UNDO", "UI_RICHTEXT_REDO", "UI_RICHTEXT_CUT",
            "UI_RICHTEXT_COPY", "UI_RICHTEXT_PASTE", "UI_RICHTEXT_SELECT_ALL", "UI_RICHTEXT_SAVE",
            "UI_RICHTEXT_LOAD", "UI_RICHTEXT_ZOOM", "UI_RICHTEXT_PRINT", "UI_RICHTEXT_PAGE_SETUP",
            "UI_MD_SET", "UI_MD_REFRESH",
        }
        _SAFE_NAMES = set(_SAFE_DEFAULTS) | _SAFE_MUTATORS
        for _nm in list(env.values.keys()):
            if _nm in _SAFE_NAMES and isinstance(env.values[_nm], NativeFunction):
                _orig = env.values[_nm]
                _dflt = _SAFE_DEFAULTS.get(_nm, None)
                def _make_guard(o, d):
                    def _guarded(i, a, _o=o, _d=d):
                        try:
                            return _o.func(i, a)
                        except RuntimeError:
                            return _d      # dead wx widget -> safe default
                    return NativeFunction(o.name, o._arity, _guarded)
                env.values[_nm] = _make_guard(_orig, _dflt)