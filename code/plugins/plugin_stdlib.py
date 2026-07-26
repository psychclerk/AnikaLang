import math
import datetime
import random
import os
import sys
import sqlite3
import csv
import base64
import json
import html
import subprocess
import re
import urllib.request
import urllib.error

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction, ReturnException
from core.errors import FMS_Error
from core.utils import _path_to_file_url

class StdLibPlugin(AnikaPlugin):
    def register(self, env, interpreter):
        # ==========================================================================
        # DYNAMIC CODE EVALUATION & TYPE CHECKING
        # ==========================================================================
        def eval_fms(i, a):
            code = str(a[0])
            if len(code.strip()) == 0: return None
            try:
                i.last_result = None
                from core.lexer import Lexer
                from core.parser import Parser
                lexer = Lexer(code)
                parser = Parser(lexer.tokens)
                ast = parser.parse()
                i.execute_block(ast.statements, i.environment)
                if i.last_result is None: return "OK"
                return i.last_result
            except FMS_Error as e: return "ERROR: " + str(e)
            except ReturnException as e: return e.value
            except Exception as e: return "ERROR: " + str(e)

        def eval_fms_silent(i, a):
            result = eval_fms(i, a)
            if isinstance(result, str) and result.startswith("ERROR:"): return None
            return result

        def is_error(i, a):
            val = a[0]
            return isinstance(val, str) and val.startswith("ERROR:")

        def error_message(i, a):
            val = str(a[0])
            if val.startswith("ERROR:"): return val[7:].strip()
            return val

        def list_variables(i, a):
            result = {}
            env_local = i.environment
            while env_local is not None:
                for name, value in env_local.values.items():
                    from core.interpreter import Callable
                    if isinstance(value, Callable): continue
                    if name.startswith("_"): continue
                    if name not in result: result[name] = value
                env_local = env_local.enclosing
            return result

        def type_of(i, a):
            val = a[0]
            if val is None: return "NULL"
            if isinstance(val, bool): return "BOOLEAN"
            if isinstance(val, int): return "INTEGER"
            if isinstance(val, float): return "FLOAT"
            if isinstance(val, str): return "STRING"
            if isinstance(val, list): return "LIST"
            if isinstance(val, dict): return "DICT"
            from core.interpreter import Callable
            if isinstance(val, Callable): return "FUNCTION"
            return type(val).__name__.upper()

        env.define("EVAL_FMS", NativeFunction("EVAL_FMS", 1, eval_fms))
        env.define("EVAL_FMS_SILENT", NativeFunction("EVAL_FMS_SILENT", 1, eval_fms_silent))
        env.define("IS_ERROR", NativeFunction("IS_ERROR", 1, is_error))
        env.define("ERROR_MESSAGE", NativeFunction("ERROR_MESSAGE", 1, error_message))
        env.define("LIST_VARIABLES", NativeFunction("LIST_VARIABLES", 0, list_variables))
        env.define("TYPE_OF", NativeFunction("TYPE_OF", 1, type_of))

        # ==========================================================================
        # REGULAR EXPRESSIONS
        # ==========================================================================
        def regex_match(i, a):
            pattern, text = str(a[0]), str(a[1])
            return bool(re.match(pattern, text))
        def regex_search(i, a):
            pattern, text = str(a[0]), str(a[1])
            match = re.search(pattern, text)
            return match.group(0) if match else ""
        def regex_replace(i, a):
            pattern, text, repl = str(a[0]), str(a[1]), str(a[2])
            return re.sub(pattern, repl, text)
        def regex_findall(i, a):
            pattern, text = str(a[0]), str(a[1])
            return re.findall(pattern, text)

        env.define("REGEX_MATCH", NativeFunction("REGEX_MATCH", 2, regex_match))
        env.define("REGEX_SEARCH", NativeFunction("REGEX_SEARCH", 2, regex_search))
        env.define("REGEX_REPLACE", NativeFunction("REGEX_REPLACE", 3, regex_replace))
        env.define("REGEX_FINDALL", NativeFunction("REGEX_FINDALL", 2, regex_findall))
        
        # ==========================================================================
        # MATH FUNCTIONS
        # ==========================================================================
        env.define("ABS", NativeFunction("ABS", 1, lambda i, a: abs(a[0])))
        env.define("ROUND", NativeFunction("ROUND", 2, lambda i, a: round(a[0], int(a[1]))))
        env.define("RAND", NativeFunction("RAND", 0, lambda i, a: random.random()))

        def safe_pow(i, a):
            try: return math.pow(a[0], a[1])
            except ValueError: return "Error"
        def safe_exp(i, a):
            try: return math.exp(a[0])
            except OverflowError: return "Error"
        def safe_ln(i, a):
            try: return math.log(a[0])
            except ValueError: return "Error"
        def safe_log10(i, a):
            try: return math.log10(a[0])
            except ValueError: return "Error"
        def safe_asin(i, a):
            try: return math.asin(a[0])
            except ValueError: return "Error"
        def safe_acos(i, a):
            try: return math.acos(a[0])
            except ValueError: return "Error"
        def safe_fact(i, a):
            try: return math.factorial(int(a[0]))
            except (ValueError, OverflowError): return "Error"
        def safe_comb(i, a):
            try: return math.comb(int(a[0]), int(a[1]))
            except (ValueError, OverflowError): return "Error"
        def safe_perm(i, a):
            try: return math.perm(int(a[0]), int(a[1]))
            except (ValueError, OverflowError): return "Error"
        def safe_sqrt(i, a):
            try: return math.sqrt(a[0])
            except ValueError: return "Error"

        env.define("POW", NativeFunction("POW", 2, safe_pow))
        env.define("EXP", NativeFunction("EXP", 1, safe_exp))
        env.define("LN", NativeFunction("LN", 1, safe_ln))
        env.define("LOG10", NativeFunction("LOG10", 1, safe_log10))
        env.define("FLOOR", NativeFunction("FLOOR", 1, lambda i, a: math.floor(a[0])))
        env.define("CEIL", NativeFunction("CEIL", 1, lambda i, a: math.ceil(a[0])))
        env.define("PI", NativeFunction("PI", 0, lambda i, a: math.pi))
        env.define("E", NativeFunction("E", 0, lambda i, a: math.e))
        env.define("SIN", NativeFunction("SIN", 1, lambda i, a: math.sin(a[0])))
        env.define("COS", NativeFunction("COS", 1, lambda i, a: math.cos(a[0])))
        env.define("TAN", NativeFunction("TAN", 1, lambda i, a: math.tan(a[0])))
        env.define("ASIN", NativeFunction("ASIN", 1, safe_asin))
        env.define("ACOS", NativeFunction("ACOS", 1, safe_acos))
        env.define("ATAN", NativeFunction("ATAN", 1, lambda i, a: math.atan(a[0])))
        env.define("DEG_TO_RAD", NativeFunction("DEG_TO_RAD", 1, lambda i, a: math.radians(a[0])))
        env.define("RAD_TO_DEG", NativeFunction("RAD_TO_DEG", 1, lambda i, a: math.degrees(a[0])))
        env.define("MIN", NativeFunction("MIN", 2, lambda i, a: min(a[0], a[1])))
        env.define("MAX", NativeFunction("MAX", 2, lambda i, a: max(a[0], a[1])))
        env.define("SUM", NativeFunction("SUM", 1, lambda i, a: sum(a[0]) if isinstance(a[0], list) else 0))
        env.define("AVG", NativeFunction("AVG", 1, lambda i, a: (sum(a[0]) / len(a[0])) if isinstance(a[0], list) and len(a[0]) > 0 else 0))
        env.define("FACT", NativeFunction("FACT", 1, safe_fact))
        env.define("COMB", NativeFunction("COMB", 2, safe_comb))
        env.define("PERM", NativeFunction("PERM", 2, safe_perm))
        env.define("RANDINT", NativeFunction("RANDINT", 2, lambda i, a: random.randint(int(a[0]), int(a[1]))))
        env.define("SQRT", NativeFunction("SQRT", 1, safe_sqrt))

        # ==========================================================================
        # STRING FUNCTIONS
        # ==========================================================================
        env.define("UPPER", NativeFunction("UPPER", 1, lambda i, a: str(a[0]).upper()))
        env.define("LOWER", NativeFunction("LOWER", 1, lambda i, a: str(a[0]).lower()))
        env.define("TRIM", NativeFunction("TRIM", 1, lambda i, a: str(a[0]).strip()))
        
        def len_func(i, a):
            val = a[0]
            if isinstance(val, (list, dict, str)): return len(val)
            return len(str(val))
        
        def str_left(i, a): return str(a[0])[:int(a[1])]
        def str_right(i, a):
            s = str(a[0]); n = int(a[1])
            if n == 0: return ""
            return s[-n:]
        def str_mid(i, a):
            s = str(a[0]); start = int(a[1])
            length = int(a[2]) if len(a) > 2 else len(s) - start
            return s[start:start + length]
        def str_split(i, a): return str(a[0]).split(str(a[1]))
        def str_starts_with(i, a): return str(a[0]).startswith(str(a[1]))
        def str_ends_with(i, a): return str(a[0]).endswith(str(a[1]))
        def str_contains(i, a): return str(a[1]) in str(a[0])
        def str_index_of(i, a):
            try: return str(a[0]).index(str(a[1]))
            except ValueError: return -1
        
        def str_join(i, a):
            delimiter, lst = str(a[0]), a[1]
            if not isinstance(lst, list): raise FMS_Error("JOIN requires a list as second argument", error_type="Runtime Error")
            return delimiter.join(str(x) for x in lst)

        env.define("JOIN", NativeFunction("JOIN", 2, str_join))
        
        def str_rejoin(i, a):
            """REBOL-like rejoin - accepts multiple arguments directly"""
            # Accept either a single list OR multiple arguments
            if len(a) == 1 and isinstance(a[0], list):
                # Single list argument: rejoin(["a", "b", "c"])
                lst = a[0]
            else:
                # Multiple arguments: rejoin("a", "b", "c")
                lst = a
            
            def flatten_and_convert(item):
                if isinstance(item, list):
                    return ''.join(flatten_and_convert(x) for x in item)
                elif item is None:
                    return ""
                else:
                    return str(item)
            
            return ''.join(flatten_and_convert(x) for x in lst)

        # Register with -1 for variable arguments
        env.define("REJOIN", NativeFunction("REJOIN", -1, str_rejoin))

        env.define("LEN", NativeFunction("LEN", 1, len_func))
        env.define("REPLACE", NativeFunction("REPLACE", 3, lambda i, a: str(a[0]).replace(str(a[1]), str(a[2]))))
        env.define("LEFT", NativeFunction("LEFT", 2, str_left))
        env.define("RIGHT", NativeFunction("RIGHT", 2, str_right))
        env.define("MID", NativeFunction("MID", -1, str_mid))
        env.define("SPLIT", NativeFunction("SPLIT", 2, str_split))
        env.define("STARTS_WITH", NativeFunction("STARTS_WITH", 2, str_starts_with))
        env.define("ENDS_WITH", NativeFunction("ENDS_WITH", 2, str_ends_with))
        env.define("CONTAINS", NativeFunction("CONTAINS", 2, str_contains))
        env.define("INDEX_OF", NativeFunction("INDEX_OF", 2, str_index_of))

        # ==========================================================================
        # DATE & TIME FUNCTIONS
        # ==========================================================================
        env.define("NOW", NativeFunction("NOW", 0, lambda i, a: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        env.define("DATE", NativeFunction("DATE", 0, lambda i, a: datetime.date.today().strftime("%Y-%m-%d")))

        def to_indian_date(i, a):
            val = a[0]
            if val is None or val == "" or str(val) == "None": return "-"
            val = str(val)
            try:
                parts = val.split("-")
                if len(parts) == 3: return f"{parts[2]}-{parts[1]}-{parts[0]}"
                return val
            except: return val

        def to_iso_datetime(i, a):
            val = str(a[0])
            if not val or val == "None" or val == "-": return ""
            try:
                dt = datetime.datetime.strptime(val, "%d-%m-%Y %I:%M %p")
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                try:
                    datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                    return val
                except: return val

        def to_indian_datetime(i, a):
            val = str(a[0])
            if not val or val == "None" or val == "-": return "-"
            try:
                dt = datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                return dt.strftime("%d-%m-%Y %I:%M %p")
            except: return val

        def calc_duration(i, a):
            start_str = str(a[0]); end_str = str(a[1])
            if not start_str or not end_str or start_str == "None" or end_str == "None": 
                return "00:00:00"
            try:
                fmt = "%Y-%m-%d %H:%M:%S"
                t1 = datetime.datetime.strptime(start_str, fmt)
                t2 = datetime.datetime.strptime(end_str, fmt)
                
                total_secs = int((t2 - t1).total_seconds())
                if total_secs < 0: 
                    total_secs = 0
                    
                hours = total_secs // 3600
                minutes = (total_secs % 3600) // 60
                seconds = total_secs % 60
                
                return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except: 
                return "00:00:00"
        env.define("CALC_DURATION", NativeFunction("CALC_DURATION", 2, calc_duration))

        env.define("TO_INDIAN_DATE", NativeFunction("TO_INDIAN_DATE", 1, to_indian_date))
        env.define("TO_ISO_DATETIME", NativeFunction("TO_ISO_DATETIME", 1, to_iso_datetime))
        env.define("TO_INDIAN_DATETIME", NativeFunction("TO_INDIAN_DATETIME", 1, to_indian_datetime))
        env.define("CALC_DURATION", NativeFunction("CALC_DURATION", 2, calc_duration))

        # ==========================================================================
        # TYPE CASTING & CONTROL
        # ==========================================================================
        def cast_int(i, a):
            try: return int(float(a[0]))
            except (ValueError, TypeError): return 0
        def cast_float(i, a):
            try: return float(a[0])
            except (ValueError, TypeError): return 0.0
        def iif_func(i, a): return a[1] if i.is_truthy(a[0]) else a[2]

        env.define("INT", NativeFunction("INT", 1, cast_int))
        env.define("FLOAT", NativeFunction("FLOAT", 1, cast_float))
        env.define("STR", NativeFunction("STR", 1, lambda i, a: str(a[0])))
        env.define("IIF", NativeFunction("IIF", 3, iif_func))

        # ==========================================================================
        # DICTIONARY & LIST OPERATIONS
        # ==========================================================================
        def dict_keys(i, a):
            d = a[0]
            if not isinstance(d, dict): raise FMS_Error("DICT_KEYS requires a dictionary", error_type="Runtime Error")
            return list(d.keys())
        def dict_values(i, a):
            d = a[0]
            if not isinstance(d, dict): raise FMS_Error("DICT_VALUES requires a dictionary", error_type="Runtime Error")
            return list(d.values())
        def dict_entries(i, a):
            d = a[0]
            if not isinstance(d, dict): raise FMS_Error("DICT_ENTRIES requires a dictionary", error_type="Runtime Error")
            return [[k, v] for k, v in d.items()]
        def dict_merge(i, a):
            d1, d2 = a[0], a[1]
            if not isinstance(d1, dict) or not isinstance(d2, dict): raise FMS_Error("DICT_MERGE requires two dictionaries", error_type="Runtime Error")
            result = dict(d1); result.update(d2); return result
        def dict_has_key(i, a):
            d, key = a[0], a[1]
            if not isinstance(d, dict): return False
            return key in d
        def dict_set(i, a):
            d, key, value = a[0], a[1], a[2]
            if not isinstance(d, dict): 
                raise FMS_Error("DICT_SET requires a dictionary as first argument", error_type="Runtime Error")
            d[key] = value; return "SUCCESS"
        def dict_remove(i, a):
            d, key = a[0], a[1]
            if not isinstance(d, dict): 
                raise FMS_Error("DICT_REMOVE requires a dictionary as first argument", error_type="Runtime Error")
            if key not in d:
                raise FMS_Error(f"DICT_REMOVE key '{key}' not found in dictionary", error_type="Runtime Error")
            del d[key]
            return "SUCCESS"
        def dict_get(i, a):
            d, key = a[0], a[1]
            if not isinstance(d, dict):
                raise FMS_Error("DICT_GET requires a dictionary as first argument", error_type="Runtime Error")
            return d.get(key, None)

       
        def list_set(i, a):
            lst, idx, value = a[0], int(a[1]), a[2]
            if not isinstance(lst, list): raise FMS_Error("LIST_SET requires a list as first argument", error_type="Runtime Error")
            if idx < 0 or idx >= len(lst): raise FMS_Error(f"LIST_SET index {idx} out of range (length {len(lst)})", error_type="Runtime Error")
            lst[idx] = value; return "SUCCESS"
        def list_append(i, a):
            lst, value = a[0], a[1]
            if not isinstance(lst, list): raise FMS_Error("LIST_APPEND requires a list as first argument", error_type="Runtime Error")
            lst.append(value); return "SUCCESS"
        def list_remove(i, a):
            lst, idx = a[0], int(a[1])
            if not isinstance(lst, list): 
                raise FMS_Error("LIST_REMOVE requires a list as first argument", error_type="Runtime Error")
            if idx < 0 or idx >= len(lst): 
                raise FMS_Error(f"LIST_REMOVE index {idx} out of range (length {len(lst)})", error_type="Runtime Error")
            lst.pop(idx)
            return "SUCCESS"
        def list_contains(i, a):
            lst, value = a[0], a[1]
            if not isinstance(lst, list): 
                raise FMS_Error("LIST_CONTAINS requires a list as first argument", error_type="Runtime Error")
            return value in lst
        
        env.define("DICT_KEYS", NativeFunction("DICT_KEYS", 1, dict_keys))
        env.define("DICT_VALUES", NativeFunction("DICT_VALUES", 1, dict_values))
        env.define("DICT_ENTRIES", NativeFunction("DICT_ENTRIES", 1, dict_entries))
        env.define("DICT_MERGE", NativeFunction("DICT_MERGE", 2, dict_merge))
        env.define("DICT_HAS_KEY", NativeFunction("DICT_HAS_KEY", 2, dict_has_key))
        env.define("DICT_SET", NativeFunction("DICT_SET", 3, dict_set))
        env.define("DICT_REMOVE", NativeFunction("DICT_REMOVE", 2, dict_remove))
        env.define("DICT_GET", NativeFunction("DICT_GET", 2, dict_get))  # <-- New line        
        env.define("LIST_SET", NativeFunction("LIST_SET", 3, list_set))
        env.define("LIST_APPEND", NativeFunction("LIST_APPEND", 2, list_append))
        env.define("LIST_REMOVE", NativeFunction("LIST_REMOVE", 2, list_remove))
        env.define("LIST_CONTAINS", NativeFunction("LIST_CONTAINS", 2, list_contains))

        # ==========================================================================
        # DATABASE (SQLite)
        # ==========================================================================
        env.define("DB_CONNECT", NativeFunction("DB_CONNECT", 1, lambda i, a: sqlite3.connect(str(a[0]))))
        def db_execute(i, a):
            cursor = a[0].cursor(); cursor.execute(str(a[1])); a[0].commit(); return cursor.rowcount
        def db_query(i, a):
            cursor = a[0].cursor(); cursor.execute(str(a[1]))
            cols = [d[0] for d in cursor.description] if cursor.description else []
            return [dict(zip(cols, row)) for row in cursor.fetchall()]
        env.define("DB_EXECUTE", NativeFunction("DB_EXECUTE", 2, db_execute))
        env.define("DB_QUERY", NativeFunction("DB_QUERY", 2, db_query))

        # ==========================================================================
        # FILE I/O & PATHS
        # ==========================================================================
        def file_read(i, a):
            path = str(a[0])
            try:
                with open(path, 'r', encoding='utf-8') as f: return f.read()
            except Exception as e: return "ERROR: " + str(e)
        def file_read_base64(i, a):
            path = str(a[0])
            try:
                with open(path, 'rb') as f: return base64.b64encode(f.read()).decode('utf-8')
            except FileNotFoundError: raise FMS_Error(f"File not found: '{path}'", error_type="File Error")
            except Exception as e: raise FMS_Error(f"Failed to read file as base64: {str(e)}", error_type="File Error")
        def file_write(i, a):
            path, content = str(a[0]), str(a[1])
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'w', encoding='utf-8') as f: f.write(content)
                return "SUCCESS"
            except Exception as e: return "ERROR: " + str(e)
        def file_append(i, a):
            path, content = str(a[0]), str(a[1])
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'a', encoding='utf-8') as f: f.write(content)
                return "SUCCESS"
            except Exception as e: return "ERROR: " + str(e)
        def file_exists(i, a): return os.path.exists(str(a[0]))
        def exec_cmd(i, a):
            try: subprocess.Popen(str(a[0]), shell=True); return "SUCCESS"
            except Exception as e: return "ERROR: " + str(e)
        def file_to_url(i, a):
            path = str(a[0])
            if not os.path.exists(path): raise FMS_Error(f"File not found: {path}", error_type="File Error")
            return _path_to_file_url(path)

        env.define("FILE_READ", NativeFunction("FILE_READ", 1, file_read))
        env.define("FILE_READ_BASE64", NativeFunction("FILE_READ_BASE64", 1, file_read_base64))
        env.define("FILE_WRITE", NativeFunction("FILE_WRITE", 2, file_write))
        env.define("FILE_APPEND", NativeFunction("FILE_APPEND", 2, file_append))
        env.define("FILE_EXISTS", NativeFunction("FILE_EXISTS", 1, file_exists))
        env.define("EXEC", NativeFunction("EXEC", 1, exec_cmd))
        env.define("FILE_TO_URL", NativeFunction("FILE_TO_URL", 1, file_to_url))

        env.define("PATH_JOIN", NativeFunction("PATH_JOIN", -1, lambda i, a: os.path.join(*[str(p) for p in a])))
        env.define("PATH_DIR", NativeFunction("PATH_DIR", 1, lambda i, a: os.path.dirname(str(a[0]))))
        env.define("PATH_FILE", NativeFunction("PATH_FILE", 1, lambda i, a: os.path.basename(str(a[0]))))
        env.define("PATH_EXT", NativeFunction("PATH_EXT", 1, lambda i, a: os.path.splitext(str(a[0]))[1]))
        env.define("PATH_NAME", NativeFunction("PATH_NAME", 1, lambda i, a: os.path.splitext(os.path.basename(str(a[0])))[0]))
        env.define("PATH_CWD", NativeFunction("PATH_CWD", 0, lambda i, a: os.getcwd()))
        env.define("PATH_ABS", NativeFunction("PATH_ABS", 1, lambda i, a: os.path.abspath(str(a[0]))))
        env.define("PATH_NORM", NativeFunction("PATH_NORM", 1, lambda i, a: os.path.normpath(str(a[0]))))
        def path_mkdir(i, a):
            try: os.makedirs(str(a[0]), exist_ok=True); return "SUCCESS"
            except Exception as e: return "ERROR: " + str(e)
        env.define("PATH_MKDIR", NativeFunction("PATH_MKDIR", 1, path_mkdir))
        env.define("PATH_ISDIR", NativeFunction("PATH_ISDIR", 1, lambda i, a: os.path.isdir(str(a[0]))))
        env.define("PATH_ISFILE", NativeFunction("PATH_ISFILE", 1, lambda i, a: os.path.isfile(str(a[0]))))
        def path_list(i, a):
            try: return os.listdir(str(a[0]))
            except Exception: return []
        env.define("PATH_LIST", NativeFunction("PATH_LIST", 1, path_list))
        
        # ==========================================================================
        # ADDITIONAL FILE OPERATIONS
        # ==========================================================================
        def file_delete(i, a):
            path = str(a[0])
            try:
                if os.path.isfile(path):
                    os.remove(path)
                    return "SUCCESS"
                elif os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path) # Deletes directory and all contents
                    return "SUCCESS"
                return "ERROR: Path does not exist"
            except Exception as e:
                return "ERROR: " + str(e)
        def file_rename(i, a):
            old_path, new_path = str(a[0]), str(a[1])
            try:
                os.rename(old_path, new_path); return "SUCCESS"
            except Exception as e: 
                return "ERROR: " + str(e)
        def file_size(i, a):
            path = str(a[0])
            try: return os.path.getsize(path)
            except Exception: return 0

        env.define("FILE_DELETE", NativeFunction("FILE_DELETE", 1, file_delete))
        env.define("FILE_RENAME", NativeFunction("FILE_RENAME", 2, file_rename))
        env.define("FILE_SIZE", NativeFunction("FILE_SIZE", 1, file_size))

        # ==========================================================================
        # CSV OPERATIONS
        # ==========================================================================
        def csv_read(i, a):
            path = str(a[0])
            try:
                with open(path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f)
                    return [dict(row) for row in reader]
            except FileNotFoundError: raise FMS_Error(f"CSV file not found: '{path}'", error_type="File Error")
            except Exception as e: raise FMS_Error(f"Failed to read CSV: {str(e)}", error_type="File Error")
        def csv_write(i, a):
            path, data = str(a[0]), a[1]
            if not isinstance(data, list) or len(data) == 0: raise FMS_Error("CSV_WRITE requires a non-empty list of dictionaries", error_type="Runtime Error")
            try:
                headers = list(data[0].keys())
                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=headers); writer.writeheader(); writer.writerows(data)
                return "SUCCESS"
            except Exception as e: raise FMS_Error(f"Failed to write CSV: {str(e)}", error_type="File Error")
        env.define("CSV_READ", NativeFunction("CSV_READ", 1, csv_read))
        env.define("CSV_WRITE", NativeFunction("CSV_WRITE", 2, csv_write))

        # ==========================================================================
        # SYSTEM & NETWORK
        # ==========================================================================
        def get_interpreter_path(i, a):
            if getattr(sys, 'frozen', False):
                # In --onedir mode, sys.executable points directly to the .exe
                # in the app folder (e.g., dist/AnikaLang/AnikaLang.exe)
                return os.path.abspath(sys.executable)
            else:
                # Development mode: calculate from plugin file location
                root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                entry_script = os.path.basename(sys.argv[0])
                return os.path.join(root_dir, entry_script)
        def http_get(i, a):
            url = str(a[0])
            try:
                req = urllib.request.Request(url, headers={'User-Agent': 'AnikaLang/1.0'})
                with urllib.request.urlopen(req, timeout=30) as response: return response.read().decode('utf-8')
            except urllib.error.URLError as e: raise FMS_Error(f"HTTP GET failed: {str(e)}", error_type="Network Error")
            except Exception as e: raise FMS_Error(f"HTTP GET error: {str(e)}", error_type="Network Error")

        env.define("INTERPRETER_PATH", NativeFunction("INTERPRETER_PATH", 0, get_interpreter_path))
        env.define("HTTP_GET", NativeFunction("HTTP_GET", 1, http_get))

        # ==========================================================================
        # DATA FORMATS (HTML, Base64, JSON)
        # ==========================================================================
        env.define("HTML_ESCAPE", NativeFunction("HTML_ESCAPE", 1, lambda i, a: html.escape(str(a[0]))))
        env.define("BASE64_ENCODE", NativeFunction("BASE64_ENCODE", 1, lambda i, a: base64.b64encode(str(a[0]).encode('utf-8')).decode('utf-8')))
        def b64_decode(i, a):
            try: return base64.b64decode(str(a[0]).encode('utf-8')).decode('utf-8')
            except Exception as e: raise FMS_Error(f"Base64 decode failed: {str(e)}", error_type="Runtime Error")
        def json_parse(i, a):
            try: return json.loads(str(a[0]))
            except Exception as e: raise FMS_Error(f"JSON parse failed: {str(e)}", error_type="Runtime Error")
        def json_stringify(i, a):
            try: return json.dumps(a[0], indent=2)
            except Exception as e: raise FMS_Error(f"JSON stringify failed: {str(e)}", error_type="Runtime Error")

        env.define("BASE64_DECODE", NativeFunction("BASE64_DECODE", 1, b64_decode))
        env.define("JSON_PARSE", NativeFunction("JSON_PARSE", 1, json_parse))
        env.define("JSON_STRINGIFY", NativeFunction("JSON_STRINGIFY", 1, json_stringify))

        # ==========================================================================
        # CLIPBOARD (wxPython)
        # ==========================================================================
        def clipboard_set(i, a):
            try:
                import wx
                if not wx.TheClipboard.IsOpened():
                    wx.TheClipboard.Open()
                    wx.TheClipboard.SetData(wx.TextDataObject(str(a[0])))
                    wx.TheClipboard.Flush()
                    wx.TheClipboard.Close()
                return "SUCCESS"
            except Exception as e: return "ERROR: " + str(e)
        def clipboard_get(i, a):
            try:
                import wx
                if not wx.TheClipboard.IsOpened():
                    wx.TheClipboard.Open()
                    if wx.TheClipboard.IsSupported(wx.DataFormat(wx.DF_TEXT)):
                        data = wx.TextDataObject()
                        wx.TheClipboard.GetData(data)
                        wx.TheClipboard.Close()
                        return data.GetText()
                    wx.TheClipboard.Close()
                return ""
            except Exception: return ""

        env.define("CLIPBOARD_SET", NativeFunction("CLIPBOARD_SET", 1, clipboard_set))
        env.define("CLIPBOARD_GET", NativeFunction("CLIPBOARD_GET", 0, clipboard_get))
        
        # ==========================================================================
        # SYSTEM COMMANDS (EXEC_CAPTURE, CMD_EXISTS)
        # ==========================================================================
        def exec_capture(i, a):
            """Execute command and capture output. Returns [success, output]."""
            cmd = str(a[0])
            try:
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=300, encoding='utf-8', errors='replace'
                )
                output = ""
                if result.stdout: output += result.stdout
                if result.stderr: output += "\n" + result.stderr
                if result.returncode != 0: return [False, output]
                return [True, output]
            except subprocess.TimeoutExpired:
                return [False, "Command timed out after 300 seconds"]
            except Exception as e:
                return [False, str(e)]

        def cmd_exists(i, a):
            """Check if a command is available on the system PATH."""
            cmd = str(a[0])
            try:
                test_cmd = "where " + cmd if os.name == "nt" else "which " + cmd
                result = subprocess.run(test_cmd, shell=True, capture_output=True)
                return result.returncode == 0
            except Exception:
                return False

        env.define("EXEC_CAPTURE", NativeFunction("EXEC_CAPTURE", 1, exec_capture))
        env.define("CMD_EXISTS", NativeFunction("CMD_EXISTS", 1, cmd_exists))

        # ==========================================================================
        # CSV RAW & APPEND
        # ==========================================================================
        def csv_read_raw(i, a):
            """Read CSV file and return list of lists (no headers)"""
            path = str(a[0])
            try:
                with open(path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.reader(f)
                    return [row for row in reader]
            except FileNotFoundError:
                raise FMS_Error(f"CSV file not found: '{path}'", error_type="File Error")
            except Exception as e:
                raise FMS_Error(f"Failed to read CSV: {str(e)}", error_type="File Error")

        def csv_append(i, a):
            """Append a single row (dictionary) to existing CSV file"""
            path = str(a[0])
            row = a[1]
            if not isinstance(row, dict):
                raise FMS_Error("CSV_APPEND requires a dictionary", error_type="Runtime Error")
            try:
                file_exists = os.path.exists(path)
                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                with open(path, 'a', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=list(row.keys()))
                    if not file_exists: writer.writeheader()
                    writer.writerow(row)
                return "SUCCESS"
            except Exception as e:
                raise FMS_Error(f"Failed to append CSV: {str(e)}", error_type="File Error")

        env.define("CSV_READ_RAW", NativeFunction("CSV_READ_RAW", 1, csv_read_raw))
        env.define("CSV_APPEND", NativeFunction("CSV_APPEND", 2, csv_append))