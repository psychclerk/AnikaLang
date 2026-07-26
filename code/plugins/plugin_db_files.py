import os
import shutil
import uuid

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class DbFilesPlugin(AnikaPlugin):
    def register(self, env, interpreter):
        # ==========================================================================
        # SQLITE FULL-TEXT SEARCH (FTS5)
        # ==========================================================================
        def db_fts_create(i, a):
            db = a[0]; fts_name = str(a[1]); source_table = str(a[2]); columns = [str(c) for c in a[3:]]
            if not columns: raise FMS_Error("DB_FTS_CREATE requires at least one column", error_type="Runtime Error")
            try:
                cols = ", ".join(columns)
                db.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts_name} USING fts5({cols}, content='{source_table}')")
                db.execute(f"INSERT INTO {fts_name}({cols}) SELECT {cols} FROM {source_table}"); db.commit(); return "SUCCESS"
            except Exception as e: raise FMS_Error(f"FTS create failed: {str(e)}", error_type="Runtime Error")

        def db_fts_search(i, a):
            db = a[0]; fts_name = str(a[1]); query = str(a[2]); limit = int(a[3]) if len(a) > 3 else 100
            try:
                cursor = db.execute(f"SELECT *, rank FROM {fts_name} WHERE {fts_name} MATCH ? ORDER BY rank LIMIT ?", (query, limit))
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]
            except Exception as e: raise FMS_Error(f"FTS search failed: {str(e)}", error_type="Runtime Error")

        def db_fts_update(i, a):
            db = a[0]; fts_name = str(a[1]); rowid = a[2]
            old_vals = a[3] if len(a) > 3 else None; new_vals = a[4] if len(a) > 4 else None
            try:
                if old_vals and isinstance(old_vals, dict):
                    cols = list(old_vals.keys()); vals = [old_vals[c] for c in cols]
                    db.execute(f"INSERT INTO {fts_name}({', '.join(cols)}) VALUES ('delete', {', '.join(['?'] * len(cols))})", vals)
                if new_vals and isinstance(new_vals, dict):
                    cols = list(new_vals.keys()); vals = [new_vals[c] for c in cols]
                    db.execute(f"INSERT INTO {fts_name}({', '.join(cols)}) VALUES ({', '.join(['?'] * len(cols))})", vals)
                db.commit(); return "SUCCESS"
            except Exception as e: raise FMS_Error(f"FTS update failed: {str(e)}", error_type="Runtime Error")

        env.define("DB_FTS_CREATE", NativeFunction("DB_FTS_CREATE", -1, db_fts_create))
        env.define("DB_FTS_SEARCH", NativeFunction("DB_FTS_SEARCH", -1, db_fts_search))
        env.define("DB_FTS_UPDATE", NativeFunction("DB_FTS_UPDATE", -1, db_fts_update))

        # ==========================================================================
        # FILE ATTACHMENTS
        # ==========================================================================
        def attachment_save(i, a):
            source_path = str(a[0]); attach_dir = str(a[1]) if len(a) > 1 else "attachments"
            try:
                if not os.path.exists(attach_dir): os.makedirs(attach_dir, exist_ok=True)
                ext = os.path.splitext(source_path)[1].lower()
                res_id = str(uuid.uuid4()).replace("-", "") + ext
                shutil.copy2(source_path, os.path.join(attach_dir, res_id)); return res_id
            except Exception as e: raise FMS_Error(f"Attachment save failed: {str(e)}", error_type="Runtime Error")

        def attachment_path(i, a):
            res_id = str(a[0]); attach_dir = str(a[1]) if len(a) > 1 else "attachments"
            return os.path.join(attach_dir, res_id)

        def attachment_delete(i, a):
            res_id = str(a[0]); attach_dir = str(a[1]) if len(a) > 1 else "attachments"
            try:
                path = os.path.join(attach_dir, res_id)
                if os.path.exists(path): os.remove(path)
                return "SUCCESS"
            except Exception as e: return f"ERROR: {str(e)}"

        def attachment_list(i, a):
            attach_dir = str(a[0]) if len(a) > 0 else "attachments"
            try:
                if not os.path.exists(attach_dir): return []
                return os.listdir(attach_dir)
            except Exception: return []

        env.define("ATTACHMENT_SAVE", NativeFunction("ATTACHMENT_SAVE", -1, attachment_save))
        env.define("ATTACHMENT_PATH", NativeFunction("ATTACHMENT_PATH", -1, attachment_path))
        env.define("ATTACHMENT_DELETE", NativeFunction("ATTACHMENT_DELETE", -1, attachment_delete))
        env.define("ATTACHMENT_LIST", NativeFunction("ATTACHMENT_LIST", -1, attachment_list))