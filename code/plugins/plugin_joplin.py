import os
import tarfile
import tempfile
import shutil

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class JoplinPlugin(AnikaPlugin):
    def register(self, env, interpreter):
        def joplin_export(i, a):
            notes = a[0]; output_path = str(a[1])
            try:
                if not isinstance(notes, list): raise FMS_Error("notes_list must be a list", error_type="Runtime Error")
                temp_dir = tempfile.mkdtemp(prefix="joplin_export_")
                try:
                    for idx, note in enumerate(notes):
                        note_id = note.get("id", f"note_{idx}"); title = note.get("title", f"Note {idx}")
                        body = note.get("body", "")
                        metadata = f"---\nid: {note_id}\ntitle: {title}\ncreated_time: {note.get('created_time', '')}\nupdated_time: {note.get('updated_time', '')}\n---\n"
                        with open(os.path.join(temp_dir, f"{note_id}.md"), 'w', encoding='utf-8') as f: f.write(metadata + body)
                    with tarfile.open(output_path, "w:gz") as tar:
                        for filename in os.listdir(temp_dir): tar.add(os.path.join(temp_dir, filename), arcname=filename)
                    return "SUCCESS"
                finally: shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e: raise FMS_Error(f"Joplin export failed: {str(e)}", error_type="Runtime Error")

        def joplin_import(i, a):
            jex_path = str(a[0])
            try:
                if not os.path.exists(jex_path): raise FMS_Error(f"File not found: {jex_path}", error_type="Runtime Error")
                notes = []; temp_dir = tempfile.mkdtemp(prefix="joplin_import_")
                try:
                    with tarfile.open(jex_path, "r:gz") as tar: tar.extractall(temp_dir)
                    for filename in os.listdir(temp_dir):
                        if filename.endswith(".md"):
                            with open(os.path.join(temp_dir, filename), 'r', encoding='utf-8') as f: content = f.read()
                            note = {"id": filename[:-3], "title": "", "body": content}
                            if content.startswith("---"):
                                parts = content.split("---", 2)
                                if len(parts) >= 3:
                                    note["body"] = parts[2].strip()
                                    for line in parts[1].strip().split("\n"):
                                        if ":" in line:
                                            key, val = line.split(":", 1); note[key.strip()] = val.strip()
                            notes.append(note)
                    return notes
                finally: shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e: raise FMS_Error(f"Joplin import failed: {str(e)}", error_type="Runtime Error")

        env.define("JOPLIN_EXPORT", NativeFunction("JOPLIN_EXPORT", 2, joplin_export))
        env.define("JOPLIN_IMPORT", NativeFunction("JOPLIN_IMPORT", 1, joplin_import))