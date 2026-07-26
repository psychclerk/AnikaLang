import os
import re
import threading
import subprocess

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class LangVoicePlugin(AnikaPlugin):
    def _get_translator(self):
        try: from deep_translator import GoogleTranslator; return GoogleTranslator
        except ImportError: raise FMS_Error("Translation requires deep-translator. Run: pip install deep-translator", error_type="Import Error")

    def _get_gtts(self):
        try: from gtts import gTTS; return gTTS
        except ImportError: raise FMS_Error("Google TTS requires gTTS. Run: pip install gTTS", error_type="Import Error")

    def register(self, env, interpreter):
        # ==========================================================================
        # TRANSLATION
        # ==========================================================================
        def translate_text(i, a):
            GoogleTranslator = self._get_translator()
            text = str(a[0]); target = str(a[1]).lower() if len(a) > 1 else "en"
            source = str(a[2]).lower() if len(a) > 2 and a[2] else "auto"
            if not text.strip(): return ""
            try: return GoogleTranslator(source=source, target=target).translate(text) or ""
            except Exception as e: raise FMS_Error(f"Translation failed: {str(e)}", error_type="Translation Error")

        def translate_detect(i, a):
            text = str(a[0]).strip()
            if not text: return "unknown"
            if re.search(r'[\u4e00-\u9fff]', text): return "zh-CN"
            if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text): return "ja"
            if re.search(r'[\uac00-\ud7af]', text): return "ko"
            if re.search(r'[\u0600-\u06ff]', text): return "ar"
            if re.search(r'[\u0900-\u097f]', text): return "hi"
            if re.search(r'[\u0400-\u04ff]', text): return "ru"
            return "en"

        def translate_batch(i, a):
            GoogleTranslator = self._get_translator()
            texts = a[0]; target = str(a[1]).lower() if len(a) > 1 else "en"
            source = str(a[2]).lower() if len(a) > 2 and a[2] else "auto"
            if not isinstance(texts, list): raise FMS_Error("TRANSLATE_BATCH requires a list", error_type="Runtime Error")
            try:
                translator = GoogleTranslator(source=source, target=target)
                return [translator.translate(str(t)) or str(t) for t in texts]
            except Exception as e: raise FMS_Error(f"Batch translation failed: {str(e)}", error_type="Translation Error")

        def translate_languages(i, a):
            return [["en", "English"], ["es", "Spanish"], ["fr", "French"], ["de", "German"], ["it", "Italian"],
                    ["pt", "Portuguese"], ["ru", "Russian"], ["ja", "Japanese"], ["ko", "Korean"],
                    ["zh-CN", "Chinese (Simplified)"], ["zh-TW", "Chinese (Traditional)"], ["ar", "Arabic"],
                    ["hi", "Hindi"], ["bn", "Bengali"], ["ur", "Urdu"], ["tr", "Turkish"], ["nl", "Dutch"],
                    ["pl", "Polish"], ["sv", "Swedish"], ["da", "Danish"], ["fi", "Finnish"], ["no", "Norwegian"],
                    ["el", "Greek"], ["he", "Hebrew"], ["th", "Thai"], ["vi", "Vietnamese"], ["id", "Indonesian"],
                    ["ms", "Malay"], ["cs", "Czech"], ["hu", "Hungarian"], ["ro", "Romanian"], ["uk", "Ukrainian"]]

        def translate_to_english(i, a):
            GoogleTranslator = self._get_translator()
            text = str(a[0])
            if not text.strip(): return ""
            try: return GoogleTranslator(source="auto", target="en").translate(text) or ""
            except Exception as e: raise FMS_Error(f"Translation to English failed: {str(e)}", error_type="Translation Error")

        env.define("TRANSLATE", NativeFunction("TRANSLATE", -1, translate_text))
        env.define("TRANSLATE_DETECT", NativeFunction("TRANSLATE_DETECT", 1, translate_detect))
        env.define("TRANSLATE_BATCH", NativeFunction("TRANSLATE_BATCH", -1, translate_batch))
        env.define("TRANSLATE_LANGUAGES", NativeFunction("TRANSLATE_LANGUAGES", 0, translate_languages))
        env.define("TRANSLATE_TO_ENGLISH", NativeFunction("TRANSLATE_TO_ENGLISH", 1, translate_to_english))

        # ==========================================================================
        # TEXT-TO-SPEECH
        # ==========================================================================
        def tts_speak(i, a):
            text = str(a[0]); rate = int(a[1]) if len(a) > 1 and a[1] else 175
            volume = float(a[2]) if len(a) > 2 and a[2] is not None else 1.0
            if not text.strip(): return "SUCCESS"
            def _speak_thread():
                try:
                    import pyttsx3
                    engine = pyttsx3.init(); engine.setProperty('rate', rate)
                    engine.setProperty('volume', max(0.0, min(1.0, volume)))
                    engine.say(text); engine.runAndWait(); engine.stop()
                except Exception as e: print(f"TTS thread error: {e}")
            try: threading.Thread(target=_speak_thread, daemon=True).start(); return "SUCCESS"
            except Exception as e: raise FMS_Error(f"TTS speak failed: {str(e)}", error_type="TTS Error")

        def tts_save(i, a):
            gTTS = self._get_gtts()
            text = str(a[0]); output_path = str(a[1])
            language = str(a[2]).lower() if len(a) > 2 and a[2] else "en"
            slow = bool(a[3]) if len(a) > 3 and a[3] is not None else False
            if not text.strip(): return "ERROR: Empty text"
            try:
                os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
                gTTS(text=text, lang=language, slow=slow).save(output_path); return "SUCCESS"
            except Exception as e: raise FMS_Error(f"TTS save failed: {str(e)}", error_type="TTS Error")

        def tts_save_offline(i, a):
            text = str(a[0]); output_path = str(a[1]); rate = int(a[2]) if len(a) > 2 and a[2] else 175
            if not text.strip(): return "ERROR: Empty text"
            try:
                os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
                import pyttsx3
                engine = pyttsx3.init(); engine.setProperty('rate', rate)
                engine.save_to_file(text, output_path); engine.runAndWait(); engine.stop(); return "SUCCESS"
            except Exception as e: raise FMS_Error(f"TTS save offline failed: {str(e)}", error_type="TTS Error")

        def tts_play_file(i, a):
            file_path = str(a[0])
            if not os.path.exists(file_path): raise FMS_Error(f"Audio file not found: '{file_path}'", error_type="File Error")
            try:
                if os.name == 'nt':
                    subprocess.Popen(['powershell', '-c', f'(New-Object Media.SoundPlayer "{file_path}").PlaySync()'], shell=False)
                else:
                    for player in ['aplay', 'afplay', 'paplay']:
                        try: subprocess.Popen([player, file_path]); return "SUCCESS"
                        except FileNotFoundError: continue
                    raise FMS_Error("No audio player found.", error_type="Runtime Error")
                return "SUCCESS"
            except Exception as e: raise FMS_Error(f"Failed to play audio: {str(e)}", error_type="Runtime Error")

        env.define("TTS_SPEAK", NativeFunction("TTS_SPEAK", -1, tts_speak))
        env.define("TTS_SAVE", NativeFunction("TTS_SAVE", -1, tts_save))
        env.define("TTS_SAVE_OFFLINE", NativeFunction("TTS_SAVE_OFFLINE", -1, tts_save_offline))
        env.define("TTS_PLAY_FILE", NativeFunction("TTS_PLAY_FILE", 1, tts_play_file))