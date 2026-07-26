# ==============================================================================
# FILE: plugins/plugin_image_audio_video.py
# AnikaLang 1.2 — Image / Audio / Video plugin
# Backends (all lazy): Pillow (IMG_*), pygame (AUDIO_* + audio player),
# ffmpeg/ffprobe (VIDEO_* processing), wx.media (video player widget).
# ==============================================================================
import os
import re
import io
import time
import base64
import shutil
import subprocess
import threading
import wx
from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction, Callable
from core.errors import FMS_Error


# ------------------------------------------------------------------------------
# Module-level helpers (mirror plugin_ui's layout helpers; self-contained here)
# ------------------------------------------------------------------------------
def _parse_pos_args(a, start_idx):
    coords = [None, None, None, None]
    n = len(a) - start_idx
    if n >= 4:   coords = [a[start_idx], a[start_idx+1], a[start_idx+2], a[start_idx+3]]
    elif n == 3: coords = [a[start_idx], a[start_idx+1], a[start_idx+2], None]
    elif n == 2: coords = [a[start_idx], a[start_idx+1], None, None]
    return coords

def _apply_layout(parent, widget, coords):
    x, y, w, h = coords
    if x is not None and y is not None:
        widget.SetPosition(wx.Point(int(x), int(y)))
    if w is not None and h is not None:
        widget.SetSize(wx.Size(int(w), int(h)))
    elif w is not None:
        widget.SetSize(wx.Size(int(w), widget.GetBestSize().height))
    return widget

def _to_wx_color(c):
    if c is None: return None
    s = str(c).strip()
    if not s: return None
    try: return wx.Colour(s)
    except Exception: return None

def _hex(s):
    if s is None: return None
    s = str(s).strip().lstrip('#')
    if len(s) == 3: s = ''.join(ch * 2 for ch in s)
    if len(s) != 6: return None
    try: return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception: return None

def _call_anika(i, name, args=None):
    if args is None: args = []
    try:
        fn = i.environment.get(name)
        if isinstance(fn, Callable):
            return fn.call(i, args)
    except Exception as e:
        try: wx.MessageBox(str(e), "AnikaLang Error", wx.OK | wx.ICON_ERROR)
        except Exception: pass
    return None

def _fmt_time(sec):
    sec = int(max(0, sec))
    return f"{sec // 60}:{sec % 60:02d}"


# ==============================================================================
class ImageAudioVideoPlugin(AnikaPlugin):

    # ---- lazy backends -------------------------------------------------------
    @staticmethod
    def _get_pil():
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps
            return Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, ImageOps
        except ImportError:
            raise FMS_Error("Image functions require Pillow. Run: pip install Pillow",
                            error_type="Import Error")

    @staticmethod
    def _get_pygame():
        try:
            import pygame
        except ImportError:
            raise FMS_Error("Audio playback requires pygame. Run: pip install pygame",
                            error_type="Import Error")
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
        except Exception as e:
            raise FMS_Error("Could not initialize audio mixer: " + str(e),
                            error_type="Runtime Error")
        return pygame

    @staticmethod
    def _get_ffmpeg():
        ff = shutil.which("ffmpeg")
        fp = shutil.which("ffprobe")
        if not ff:
            raise FMS_Error("Video processing requires ffmpeg on your system PATH "
                            "(https://ffmpeg.org).", error_type="Import Error")
        return {"ffmpeg": ff, "ffprobe": fp}

    @staticmethod
    def _get_mediactrl():
        try:
            import wx.media
            return wx.media.MediaCtrl
        except Exception:
            raise FMS_Error("Video playback needs a wxPython build with the media "
                            "module and a system backend (DirectShow / QuickTime / "
                            "GStreamer).", error_type="Import Error")

    # ==========================================================================
    def register(self, env, interpreter):
        plugin = self
        interp = interpreter

        # ---- per-instance handle registries ---------------------------------
        if not hasattr(plugin, "_img_handles"):
            plugin._img_handles = {}
            plugin._img_next = 1
        if not hasattr(plugin, "_audio_handles"):
            plugin._audio_handles = {}
            plugin._audio_next = 1

        def _reg_img(pil_img, path=None):
            h = plugin._img_next
            plugin._img_next += 1
            plugin._img_handles[h] = {"img": pil_img, "path": path}
            return h

        def _get_img(h):
            h = int(h)
            if h not in plugin._img_handles:
                raise FMS_Error(f"Invalid image handle: {h}. Image may be closed.",
                                error_type="Runtime Error")
            return plugin._img_handles[h]

        def _reg_audio(path):
            h = plugin._audio_next
            plugin._audio_next += 1
            plugin._audio_handles[h] = {"path": path, "volume": 1.0, "playing": False,
                                        "offset": 0.0, "start": 0.0, "len": None}
            return h

        def _get_audio(h):
            h = int(h)
            if h not in plugin._audio_handles:
                raise FMS_Error(f"Invalid audio handle: {h}. Audio may be closed.",
                                error_type="Runtime Error")
            return plugin._audio_handles[h]

        # ---- unified audio transport (used by AUDIO_* and the player widget) -
        def _h_len(h):
            rec = _get_audio(h)
            if rec.get("len") is None:
                ln = 0.0
                try:
                    pg = plugin._get_pygame()
                    ln = float(pg.mixer.Sound(rec["path"]).get_length())
                except Exception:
                    ln = 0.0
                rec["len"] = ln
            return rec["len"]

        def _h_cur(h):
            rec = _get_audio(h)
            cur = rec["offset"] + (time.time() - rec["start"] if rec["playing"] else 0.0)
            ln = _h_len(h)
            if ln and cur > ln:
                cur = ln
            return max(0.0, cur)

        def _h_play(h, loops=0):
            pg = plugin._get_pygame()
            rec = _get_audio(h)
            pg.mixer.music.load(rec["path"])
            pg.mixer.music.set_volume(rec["volume"])
            try:
                pg.mixer.music.play(loops=loops, start=rec["offset"])
            except TypeError:
                pg.mixer.music.play(loops=loops)
                try: pg.mixer.music.set_pos(rec["offset"])
                except Exception: pass
            rec["playing"] = True
            rec["start"] = time.time()

        def _h_pause(h):
            rec = _get_audio(h)
            if rec["playing"]:
                rec["offset"] = rec["offset"] + (time.time() - rec["start"])
                rec["playing"] = False
                try: plugin._get_pygame().mixer.music.pause()
                except Exception: pass

        def _h_stop(h):
            rec = _get_audio(h)
            rec["playing"] = False
            rec["offset"] = 0.0
            try: plugin._get_pygame().mixer.music.stop()
            except Exception: pass

        def _h_seek(h, sec):
            rec = _get_audio(h)
            ln = _h_len(h)
            sec = max(0.0, float(sec))
            if ln and sec > ln: sec = ln
            rec["offset"] = sec
            rec["start"] = time.time()
            pg = plugin._get_pygame()
            if rec["playing"]:
                try: pg.mixer.music.play(start=sec)
                except TypeError:
                    pg.mixer.music.rewind()
                    try: pg.mixer.music.set_pos(sec)
                    except Exception: pass
            else:
                try:
                    pg.mixer.music.load(rec["path"])
                    pg.mixer.music.set_volume(rec["volume"])
                    pg.mixer.music.set_pos(sec)
                except Exception: pass

        def _h_setvol(h, v):
            rec = _get_audio(h)
            v = max(0.0, min(1.0, float(v)))
            rec["volume"] = v
            try: plugin._get_pygame().mixer.music.set_volume(v)
            except Exception: pass

        # ==================================================================
        # IMAGE FUNCTIONS (Pillow)
        # ==================================================================
        def img_load(i, a):
            Image, *_ = plugin._get_pil()
            path = str(a[0])
            if not os.path.exists(path):
                raise FMS_Error(f"Image not found: '{path}'", error_type="File Error")
            try:
                im = Image.open(path)
                im.load()
                if im.mode in ("P", "LA", "PA"):
                    im = im.convert("RGBA")
                return _reg_img(im, path)
            except Exception as e:
                raise FMS_Error(f"Failed to load image: {e}", error_type="Image Error")

        def img_save(i, a):
            im = _get_img(a[0])["img"]
            path = str(a[1])
            fmt = str(a[2]).upper() if len(a) > 2 and a[2] else None
            try:
                os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
                out = im
                if (fmt == "JPEG" or path.lower().endswith((".jpg", ".jpeg"))) \
                        and im.mode in ("RGBA", "LA", "P"):
                    out = im.convert("RGB")
                out.save(path, format=fmt) if fmt else out.save(path)
                return "SUCCESS"
            except Exception as e:
                raise FMS_Error(f"Failed to save image: {e}", error_type="Image Error")

        def img_close(i, a):
            h = int(a[0])
            rec = plugin._img_handles.pop(h, None)
            if rec:
                try: rec["img"].close()
                except Exception: pass
            return None

        def img_info(i, a):
            rec = _get_img(a[0])
            im = rec["img"]
            info = {"width": im.width, "height": im.height, "mode": im.mode or "",
                    "format": im.format or "", "path": rec.get("path") or ""}
            if info["path"] and os.path.exists(info["path"]):
                info["size_bytes"] = os.path.getsize(info["path"])
            return info

        def img_size(i, a):
            im = _get_img(a[0])["img"]
            return [im.width, im.height]

        def img_resize(i, a):
            Image, *_ = plugin._get_pil()
            im = _get_img(a[0])["img"]
            return _reg_img(im.resize((max(1, int(a[1])), max(1, int(a[2]))), Image.LANCZOS))

        def img_thumbnail(i, a):
            Image, *_ = plugin._get_pil()
            im = _get_img(a[0])["img"].copy()
            im.thumbnail((max(1, int(a[1])), max(1, int(a[2]))), Image.LANCZOS)
            return _reg_img(im)

        def img_crop(i, a):
            im = _get_img(a[0])["img"]
            x, y, w, h = int(a[1]), int(a[2]), int(a[3]), int(a[4])
            return _reg_img(im.crop((x, y, x + w, y + h)))

        def img_rotate(i, a):
            Image, *_ = plugin._get_pil()
            im = _get_img(a[0])["img"]
            expand = bool(a[2]) if len(a) > 2 else True
            return _reg_img(im.rotate(float(a[1]), resample=Image.BICUBIC, expand=expand))

        def img_flip_h(i, a):
            Image, *_ = plugin._get_pil()
            from PIL import ImageOps as _ops
            return _reg_img(_ops.mirror(_get_img(a[0])["img"]))

        def img_flip_v(i, a):
            from PIL import ImageOps as _ops
            return _reg_img(_ops.flip(_get_img(a[0])["img"]))

        def img_grayscale(i, a):
            from PIL import ImageOps as _ops
            return _reg_img(_ops.grayscale(_get_img(a[0])["img"]).convert("RGBA"))

        def img_blur(i, a):
            from PIL import ImageFilter as _f
            r = float(a[1]) if len(a) > 1 else 2.0
            return _reg_img(_get_img(a[0])["img"].filter(_f.GaussianBlur(radius=r)))

        def img_brightness(i, a):
            from PIL import ImageEnhance as _e
            return _reg_img(_e.Brightness(_get_img(a[0])["img"].convert("RGB")).enhance(float(a[1])))

        def img_contrast(i, a):
            from PIL import ImageEnhance as _e
            return _reg_img(_e.Contrast(_get_img(a[0])["img"].convert("RGB")).enhance(float(a[1])))

        def img_sharpen(i, a):
            from PIL import ImageEnhance as _e
            f = float(a[1]) if len(a) > 1 else 2.0
            return _reg_img(_e.Sharpness(_get_img(a[0])["img"].convert("RGB")).enhance(f))

        def img_composite(i, a):
            base = _get_img(a[0])["img"].convert("RGBA")
            over = _get_img(a[1])["img"].convert("RGBA")
            x = int(a[2]) if len(a) > 2 else 0
            y = int(a[3]) if len(a) > 3 else 0
            out = base.copy()
            out.paste(over, (x, y), over)
            return _reg_img(out)

        def img_draw_text(i, a):
            Image, ImageDraw, ImageFont, *_ = plugin._get_pil()
            im = _get_img(a[0])["img"].convert("RGBA")
            text = str(a[1]); x = int(a[2]); y = int(a[3])
            size = int(a[4]) if len(a) > 4 else 16
            col = _hex(a[5]) if len(a) > 5 else (0, 0, 0)
            if col is None: col = (0, 0, 0)
            draw = ImageDraw.Draw(im)
            try: font = ImageFont.truetype("arial.ttf", size)
            except Exception:
                try: font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
                except Exception: font = ImageFont.load_default()
            draw.text((x, y), text, font=font, fill=col + (255,))
            return _reg_img(im)

        def img_draw_rect(i, a):
            Image, ImageDraw, *_ = plugin._get_pil()
            im = _get_img(a[0])["img"].convert("RGBA")
            x, y, w, h = int(a[1]), int(a[2]), int(a[3]), int(a[4])
            outline = _hex(a[5]) if len(a) > 5 else (0, 0, 0)
            fill = (_hex(a[6]) + (255,)) if len(a) > 6 and a[6] else None
            ImageDraw.Draw(im).rectangle([x, y, x + w, y + h], fill=fill,
                                         outline=outline + (255,) if outline else None, width=2)
            return _reg_img(im)

        def img_to_base64(i, a):
            im = _get_img(a[0])["img"]
            fmt = str(a[1]).upper() if len(a) > 1 and a[1] else "PNG"
            buf = io.BytesIO()
            out = im.convert("RGB") if fmt == "JPEG" and im.mode in ("RGBA", "LA", "P") else im
            out.save(buf, format=fmt)
            return base64.b64encode(buf.getvalue()).decode('utf-8')

        def img_from_base64(i, a):
            Image, *_ = plugin._get_pil()
            try:
                raw = base64.b64decode(str(a[0]))
                return _reg_img(Image.open(io.BytesIO(raw)).convert("RGBA"))
            except Exception as e:
                raise FMS_Error(f"Base64 image decode failed: {e}", error_type="Image Error")

        def img_convert(i, a):
            Image, *_ = plugin._get_pil()
            src, dst = str(a[0]), str(a[1])
            fmt = str(a[2]).upper() if len(a) > 2 and a[2] else None
            if not os.path.exists(src):
                raise FMS_Error(f"Image not found: '{src}'", error_type="File Error")
            try:
                os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
                with Image.open(src) as im:
                    out = im
                    if (fmt == "JPEG" or dst.lower().endswith((".jpg", ".jpeg"))) \
                            and im.mode in ("RGBA", "LA", "P"):
                        out = im.convert("RGB")
                    out.save(dst, format=fmt) if fmt else out.save(dst)
                return "SUCCESS"
            except Exception as e:
                raise FMS_Error(f"Image convert failed: {e}", error_type="Image Error")

        # ==================================================================
        # AUDIO FUNCTIONS (pygame)
        # ==================================================================
        def audio_load(i, a):
            path = str(a[0])
            if not os.path.exists(path):
                raise FMS_Error(f"Audio file not found: '{path}'", error_type="File Error")
            return _reg_audio(path)

        def audio_play(i, a):
            loops = int(a[1]) if len(a) > 1 else 0
            _h_play(a[0], loops)
            return "SUCCESS"

        def audio_pause(i, a):
            _h_pause(a[0]); return None

        def audio_resume(i, a):
            _h_play(a[0]); return None

        def audio_stop(i, a):
            _h_stop(a[0]); return None

        def audio_stop_all(i, a):
            for h in list(plugin._audio_handles.keys()):
                _h_stop(h)
            return "SUCCESS"

        def audio_set_volume(i, a):
            _h_setvol(a[0], a[1]); return None

        def audio_get_volume(i, a):
            return _get_audio(a[0])["volume"]

        def audio_is_playing(i, a):
            return bool(_get_audio(a[0])["playing"])

        def audio_get_pos(i, a):
            return _h_cur(a[0])

        def audio_set_pos(i, a):
            _h_seek(a[0], a[1]); return "SUCCESS"

        def audio_get_length(i, a):
            return _h_len(a[0])

        def audio_info(i, a):
            path = str(a[0])
            if not os.path.exists(path):
                raise FMS_Error(f"Audio file not found: '{path}'", error_type="File Error")
            info = {"path": path, "format": os.path.splitext(path)[1].lower().lstrip('.'),
                    "size_bytes": os.path.getsize(path), "duration": 0.0}
            try:
                pg = plugin._get_pygame()
                info["duration"] = float(pg.mixer.Sound(path).get_length())
            except Exception:
                pass
            return info

        def audio_close(i, a):
            h = int(a[0])
            if h in plugin._audio_handles:
                _h_stop(h)
                del plugin._audio_handles[h]
            return None

        def sfx_play(i, a):
            path = str(a[0])
            vol = max(0.0, min(1.0, float(a[1]))) if len(a) > 1 else 1.0
            if not os.path.exists(path):
                raise FMS_Error(f"Audio file not found: '{path}'", error_type="File Error")
            try:
                pg = plugin._get_pygame()
                snd = pg.mixer.Sound(path)
                snd.set_volume(vol)
                snd.play()
                return "SUCCESS"
            except Exception:
                if os.name == 'nt':
                    try:
                        import winsound
                        winsound.PlaySound(path, winsound.SND_FILENAME |
                                           winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                        return "SUCCESS"
                    except Exception as e:
                        raise FMS_Error(f"SFX play failed: {e}", error_type="Audio Error")
                raise FMS_Error("SFX playback needs pygame (pip install pygame).",
                                error_type="Import Error")

        # ==================================================================
        # VIDEO FUNCTIONS (ffmpeg / ffprobe)
        # ==================================================================
        def video_info(i, a):
            path = str(a[0])
            if not os.path.exists(path):
                raise FMS_Error(f"Video file not found: '{path}'", error_type="File Error")
            tools = plugin._get_ffmpeg()
            info = {"path": path, "size_bytes": os.path.getsize(path),
                    "duration": 0.0, "width": 0, "height": 0, "format": ""}
            if tools["ffprobe"]:
                try:
                    r = subprocess.run([tools["ffprobe"], "-v", "error",
                        "-select_streams", "v:0",
                        "-show_entries", "stream=width,height:format=duration,format_name",
                        "-of", "default=noprint_wrappers=1", path],
                        capture_output=True, text=True, timeout=30)
                    out = r.stdout
                    m = re.search(r"width=(\d+)", out)
                    if m: info["width"] = int(m.group(1))
                    m = re.search(r"height=(\d+)", out)
                    if m: info["height"] = int(m.group(1))
                    m = re.search(r"duration=([0-9.]+)", out)
                    if m: info["duration"] = float(m.group(1))
                    m = re.search(r"format_name=(.+)", out)
                    if m: info["format"] = m.group(1).strip()
                    if info["duration"] == 0.0:
                        r2 = subprocess.run([tools["ffprobe"], "-v", "error",
                            "-show_entries", "format=duration",
                            "-of", "default=noprint_wrappers=1:nokey=1", path],
                            capture_output=True, text=True, timeout=30)
                        try: info["duration"] = float(r2.stdout.strip())
                        except Exception: pass
                    return info
                except Exception:
                    pass
            try:
                r = subprocess.run([tools["ffmpeg"], "-i", path],
                                   capture_output=True, text=True, timeout=30)
                err = r.stderr
                m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", err)
                if m:
                    info["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                m = re.search(r"(\d{2,5})x(\d{2,5})", err)
                if m:
                    info["width"] = int(m.group(1)); info["height"] = int(m.group(2))
            except Exception:
                pass
            return info

        def video_extract_frame(i, a):
            path, sec, out = str(a[0]), float(a[1]), str(a[2])
            tools = plugin._get_ffmpeg()
            os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
            subprocess.run([tools["ffmpeg"], "-y", "-ss", str(sec), "-i", path,
                            "-frames:v", "1", "-q:v", "2", out],
                           capture_output=True, timeout=120)
            return "SUCCESS" if os.path.exists(out) else "ERROR: frame extraction failed"

        def video_thumbnail(i, a):
            path, out = str(a[0]), str(a[1])
            sec = float(a[2]) if len(a) > 2 else 0.0
            return video_extract_frame(i, [path, sec, out])

        def video_convert(i, a):
            src, dst = str(a[0]), str(a[1])
            tools = plugin._get_ffmpeg()
            os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
            r = subprocess.run([tools["ffmpeg"], "-y", "-i", src, dst],
                               capture_output=True, text=True, timeout=1800)
            return "SUCCESS" if r.returncode == 0 else "ERROR: " + r.stderr[-500:]

        def video_trim(i, a):
            src, dst, start, end = str(a[0]), str(a[1]), float(a[2]), float(a[3])
            tools = plugin._get_ffmpeg()
            os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
            r = subprocess.run([tools["ffmpeg"], "-y", "-ss", str(start), "-to", str(end),
                                "-i", src, "-c", "copy", dst],
                               capture_output=True, text=True, timeout=1800)
            return "SUCCESS" if r.returncode == 0 else "ERROR: " + r.stderr[-500:]

        def video_extract_audio(i, a):
            src, dst = str(a[0]), str(a[1])
            tools = plugin._get_ffmpeg()
            os.makedirs(os.path.dirname(dst) or '.', exist_ok=True)
            r = subprocess.run([tools["ffmpeg"], "-y", "-i", src, "-vn", dst],
                               capture_output=True, text=True, timeout=1800)
            return "SUCCESS" if r.returncode == 0 else "ERROR: " + r.stderr[-500:]

        # ==================================================================
        # UI: IMAGE VIEW widget
        # ==================================================================
        def _pil_to_wximage(pil_img):
            buf = io.BytesIO()
            pil_img.convert("RGBA").save(buf, format="PNG")
            buf.seek(0)
            return wx.Image(buf)

        def _iv_fit(panel):
            """Scale the stored image to fit the panel and center the bitmap.
            No sizer is used, so there is no EXPAND/alignment conflict and the
            image is genuinely centered within the panel."""
            img = getattr(panel, "_iv_img", None)
            sb = getattr(panel, "_iv_sb", None)
            if img is None or sb is None:
                return
            pw = panel.GetClientSize().GetWidth()
            ph = panel.GetClientSize().GetHeight()
            if pw <= 0 or ph <= 0:
                return
            iw = img.GetWidth()
            ih = img.GetHeight()
            if iw <= 0 or ih <= 0:
                return
            zoom = getattr(panel, "_iv_zoom", 1.0)
            scale = min(pw / iw, ph / ih) * zoom
            nw = max(1, int(iw * scale))
            nh = max(1, int(ih * scale))
            sb.SetBitmap(wx.Bitmap(img.Scale(nw, nh, wx.IMAGE_QUALITY_HIGH)))
            # Size the bitmap control to the scaled image, then center it in the panel
            sb.SetSize(wx.Size(nw, nh))
            sb.SetPosition(wx.Point((pw - nw) // 2, (ph - nh) // 2))
            if not sb.IsShown():
                sb.Show()

        def ui_image_view(i, a):
            parent = a[0]
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            panel = wx.Panel(target)
            panel._iv_img = None
            panel._iv_zoom = 1.0
            sb = wx.StaticBitmap(panel)
            panel._iv_sb = sb
            # NOTE: deliberately NO sizer here. The StaticBitmap is positioned
            # manually by _iv_fit, which both centers the image correctly and
            # avoids the wx "wxEXPAND overrides alignment flags" assertion.
            def _on_size(evt):
                _iv_fit(panel)
                evt.Skip()
            panel.Bind(wx.EVT_SIZE, _on_size)
            if len(a) > 1 and a[1]:
                try:
                    panel._iv_img = wx.Image(str(a[1]), wx.BITMAP_TYPE_ANY)
                except Exception:
                    panel._iv_img = None
            coords = _parse_pos_args(a, 2)
            _apply_layout(target, panel, coords)
            _iv_fit(panel)
            return panel

        def ui_image_view_set(i, a):
            panel, path = a[0], str(a[1])
            if not os.path.exists(path):
                raise FMS_Error(f"Image not found: '{path}'", error_type="File Error")
            panel._iv_img = wx.Image(path, wx.BITMAP_TYPE_ANY)
            panel._iv_zoom = 1.0
            _iv_fit(panel)
            return None

        def ui_image_view_set_handle(i, a):
            panel = a[0]
            rec = _get_img(a[1])
            panel._iv_img = _pil_to_wximage(rec["img"])
            panel._iv_zoom = 1.0
            _iv_fit(panel)
            return None

        def ui_image_view_fit(i, a):
            a[0]._iv_zoom = 1.0
            _iv_fit(a[0])
            return None

        def ui_image_view_zoom(i, a):
            a[0]._iv_zoom = max(0.1, float(a[1]))
            _iv_fit(a[0])
            return None

        def ui_image_view_clear(i, a):
            a[0]._iv_img = None
            a[0]._iv_zoom = 1.0
            try: a[0]._iv_sb.SetBitmap(wx.Bitmap())
            except Exception: pass
            return None

        # ==================================================================
        # UI: AUDIO PLAYER widget
        # ==================================================================
        def ui_audio_player(i, a):
            parent = a[0]
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            plugin._get_pygame()  # raises if unavailable
            panel = wx.Panel(target)
            panel._ap_h = None
            s = wx.BoxSizer(wx.VERTICAL)
            panel.SetSizer(s)

            title = wx.StaticText(panel, label="No audio loaded")
            title.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
                                  wx.FONTWEIGHT_BOLD))
            s.Add(title, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)

            seek = wx.Slider(panel, value=0, minValue=0, maxValue=1000,
                             style=wx.SL_HORIZONTAL)
            s.Add(seek, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)

            time_lbl = wx.StaticText(panel, label="0:00 / 0:00")
            time_lbl.SetFont(wx.Font(8, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                                     wx.FONTWEIGHT_NORMAL))
            s.Add(time_lbl, 0, wx.LEFT | wx.RIGHT, 8)

            row = wx.BoxSizer(wx.HORIZONTAL)
            b_play = wx.Button(panel, label="▶")
            b_pause = wx.Button(panel, label="❚❚")
            b_stop = wx.Button(panel, label="■")
            row.Add(b_play, 0, wx.RIGHT, 4)
            row.Add(b_pause, 0, wx.RIGHT, 4)
            row.Add(b_stop, 0, wx.RIGHT, 12)
            row.Add(wx.StaticText(panel, label="Vol"), 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            vol = wx.Slider(panel, value=100, minValue=0, maxValue=100,
                            style=wx.SL_HORIZONTAL, size=(110, -1))
            row.Add(vol, 1, wx.ALIGN_CENTER_VERTICAL)
            s.Add(row, 0, wx.EXPAND | wx.ALL, 6)

            def load_path(path):
                if not os.path.exists(path):
                    raise FMS_Error(f"Audio file not found: '{path}'",
                                    error_type="File Error")
                panel._ap_h = _reg_audio(path)
                title.SetLabel(os.path.basename(path))
                seek.SetValue(0)
                time_lbl.SetLabel(f"0:00 / {_fmt_time(_h_len(panel._ap_h))}")

            panel._ap_load = load_path

            def on_play(evt):
                if panel._ap_h is None: return
                _h_play(panel._ap_h)
            def on_pause(evt):
                if panel._ap_h is None: return
                _h_pause(panel._ap_h)
            def on_stop(evt):
                if panel._ap_h is None: return
                _h_stop(panel._ap_h)
                seek.SetValue(0)
                time_lbl.SetLabel(f"0:00 / {_fmt_time(_h_len(panel._ap_h))}")
            def on_vol(evt):
                if panel._ap_h is None: return
                _h_setvol(panel._ap_h, vol.GetValue() / 100.0)
            def on_seek(evt):
                if panel._ap_h is None: return
                ln = _h_len(panel._ap_h)
                if ln <= 0: return
                _h_seek(panel._ap_h, (seek.GetValue() / 1000.0) * ln)

            b_play.Bind(wx.EVT_BUTTON, on_play)
            b_pause.Bind(wx.EVT_BUTTON, on_pause)
            b_stop.Bind(wx.EVT_BUTTON, on_stop)
            vol.Bind(wx.EVT_SLIDER, on_vol)
            seek.Bind(wx.EVT_SLIDER, on_seek)

            timer = wx.Timer(panel)
            def on_tick(evt):
                if panel._ap_h is None: return
                rec = _get_audio(panel._ap_h)
                if not rec["playing"]: return
                cur = _h_cur(panel._ap_h)
                ln = _h_len(panel._ap_h)
                if ln > 0:
                    seek.SetValue(int(min(1.0, cur / ln) * 1000))
                time_lbl.SetLabel(f"{_fmt_time(cur)} / {_fmt_time(ln)}")
            timer.Bind(wx.EVT_TIMER, on_tick)
            timer.Start(250)
            panel._ap_timer = timer

            def on_destroy(evt):
                try: timer.Stop()
                except Exception: pass
                evt.Skip()
            panel.Bind(wx.EVT_WINDOW_DESTROY, on_destroy)

            if len(a) > 1 and a[1]:
                load_path(str(a[1]))
            coords = _parse_pos_args(a, 2)
            _apply_layout(target, panel, coords)
            return panel

        def ui_audio_player_load(i, a):
            if hasattr(a[0], "_ap_load"): a[0]._ap_load(str(a[1]))
            return None

        def ui_audio_player_play(i, a):
            if getattr(a[0], "_ap_h", None) is not None: _h_play(a[0]._ap_h)
            return None

        def ui_audio_player_pause(i, a):
            if getattr(a[0], "_ap_h", None) is not None: _h_pause(a[0]._ap_h)
            return None

        def ui_audio_player_stop(i, a):
            if getattr(a[0], "_ap_h", None) is not None: _h_stop(a[0]._ap_h)
            return None

        # ==================================================================
        # UI: VIDEO PLAYER widget (wx.media.MediaCtrl)
        # ==================================================================
        def ui_video_player(i, a):
            parent = a[0]
            target = parent._anika_panel if hasattr(parent, '_anika_panel') else parent
            MediaCtrl = plugin._get_mediactrl()
            panel = wx.Panel(target)
            s = wx.BoxSizer(wx.VERTICAL)
            panel.SetSizer(s)
            try:
                mc = MediaCtrl(panel)
            except Exception as e:
                raise FMS_Error("Could not create video player: " + str(e),
                                error_type="Runtime Error")
            panel._vp_mc = mc
            s.Add(mc, 1, wx.EXPAND)

            row = wx.BoxSizer(wx.HORIZONTAL)
            b_play = wx.Button(panel, label="▶")
            b_pause = wx.Button(panel, label="❚❚")
            b_stop = wx.Button(panel, label="■")
            row.Add(b_play, 0, wx.RIGHT, 4)
            row.Add(b_pause, 0, wx.RIGHT, 4)
            row.Add(b_stop, 0, wx.RIGHT, 12)
            seek = wx.Slider(panel, value=0, minValue=0, maxValue=1000,
                             style=wx.SL_HORIZONTAL, size=(220, -1))
            row.Add(seek, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
            time_lbl = wx.StaticText(panel, label="0:00 / 0:00")
            time_lbl.SetFont(wx.Font(8, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL,
                                     wx.FONTWEIGHT_NORMAL))
            row.Add(time_lbl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
            row.Add(wx.StaticText(panel, label="Vol"), 0,
                    wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
            vol = wx.Slider(panel, value=100, minValue=0, maxValue=100,
                            style=wx.SL_HORIZONTAL, size=(90, -1))
            row.Add(vol, 0, wx.ALIGN_CENTER_VERTICAL)
            s.Add(row, 0, wx.EXPAND | wx.ALL, 6)

            panel._vp_seeking = False

            def on_play(evt):
                try: mc.Play()
                except Exception: pass
            def on_pause(evt):
                try: mc.Pause()
                except Exception: pass
            def on_stop(evt):
                try:
                    mc.Stop(); seek.SetValue(0)
                    time_lbl.SetLabel(f"0:00 / {_fmt_time(mc.Length() / 1000.0)}")
                except Exception: pass
            def on_vol(evt):
                try: mc.SetVolume(vol.GetValue() / 100.0)
                except Exception: pass
            def on_seek(evt):
                if panel._vp_seeking: return
                ln = mc.Length()
                if ln <= 0: return
                panel._vp_seeking = True
                try: mc.Seek(int((seek.GetValue() / 1000.0) * ln))
                except Exception: pass
                panel._vp_seeking = False

            b_play.Bind(wx.EVT_BUTTON, on_play)
            b_pause.Bind(wx.EVT_BUTTON, on_pause)
            b_stop.Bind(wx.EVT_BUTTON, on_stop)
            vol.Bind(wx.EVT_SLIDER, on_vol)
            seek.Bind(wx.EVT_SLIDER, on_seek)

            timer = wx.Timer(panel)
            def on_tick(evt):
                if panel._vp_seeking: return
                try:
                    pos = mc.GetPosition(); ln = mc.Length()
                except Exception:
                    return
                if ln > 0:
                    seek.SetValue(int(min(1.0, pos / ln) * 1000))
                time_lbl.SetLabel(f"{_fmt_time(pos / 1000.0)} / {_fmt_time(ln / 1000.0)}")
            timer.Bind(wx.EVT_TIMER, on_tick)
            timer.Start(250)
            panel._vp_timer = timer

            def on_destroy(evt):
                try: timer.Stop()
                except Exception: pass
                evt.Skip()
            panel.Bind(wx.EVT_WINDOW_DESTROY, on_destroy)

            if len(a) > 1 and a[1]:
                try: mc.Load(str(a[1]))
                except Exception as e:
                    raise FMS_Error("Video load failed: " + str(e),
                                    error_type="Runtime Error")
            coords = _parse_pos_args(a, 2)
            _apply_layout(target, panel, coords)
            return panel

        def ui_video_player_load(i, a):
            mc = getattr(a[0], "_vp_mc", None)
            if mc is None: return None
            path = str(a[1])
            if not os.path.exists(path):
                raise FMS_Error(f"Video file not found: '{path}'", error_type="File Error")
            if not mc.Load(path):
                raise FMS_Error("Video load failed (unsupported format or backend).",
                                error_type="Runtime Error")
            return "SUCCESS"

        def ui_video_player_play(i, a):
            mc = getattr(a[0], "_vp_mc", None)
            if mc: 
                try: mc.Play()
                except Exception: pass
            return None

        def ui_video_player_pause(i, a):
            mc = getattr(a[0], "_vp_mc", None)
            if mc:
                try: mc.Pause()
                except Exception: pass
            return None

        def ui_video_player_stop(i, a):
            mc = getattr(a[0], "_vp_mc", None)
            if mc:
                try: mc.Stop()
                except Exception: pass
            return None

        # ==================================================================
        # REGISTRATION
        # ==================================================================
        # Image
        env.define("IMG_LOAD",        NativeFunction("IMG_LOAD", 1, img_load))
        env.define("IMG_SAVE",        NativeFunction("IMG_SAVE", -1, img_save))
        env.define("IMG_CLOSE",       NativeFunction("IMG_CLOSE", 1, img_close))
        env.define("IMG_INFO",        NativeFunction("IMG_INFO", 1, img_info))
        env.define("IMG_SIZE",        NativeFunction("IMG_SIZE", 1, img_size))
        env.define("IMG_RESIZE",      NativeFunction("IMG_RESIZE", 3, img_resize))
        env.define("IMG_THUMBNAIL",   NativeFunction("IMG_THUMBNAIL", 3, img_thumbnail))
        env.define("IMG_CROP",        NativeFunction("IMG_CROP", 5, img_crop))
        env.define("IMG_ROTATE",      NativeFunction("IMG_ROTATE", -1, img_rotate))
        env.define("IMG_FLIP_H",      NativeFunction("IMG_FLIP_H", 1, img_flip_h))
        env.define("IMG_FLIP_V",      NativeFunction("IMG_FLIP_V", 1, img_flip_v))
        env.define("IMG_GRAYSCALE",   NativeFunction("IMG_GRAYSCALE", 1, img_grayscale))
        env.define("IMG_BLUR",        NativeFunction("IMG_BLUR", -1, img_blur))
        env.define("IMG_BRIGHTNESS",  NativeFunction("IMG_BRIGHTNESS", 2, img_brightness))
        env.define("IMG_CONTRAST",    NativeFunction("IMG_CONTRAST", 2, img_contrast))
        env.define("IMG_SHARPEN",     NativeFunction("IMG_SHARPEN", -1, img_sharpen))
        env.define("IMG_COMPOSITE",   NativeFunction("IMG_COMPOSITE", -1, img_composite))
        env.define("IMG_DRAW_TEXT",   NativeFunction("IMG_DRAW_TEXT", -1, img_draw_text))
        env.define("IMG_DRAW_RECT",   NativeFunction("IMG_DRAW_RECT", -1, img_draw_rect))
        env.define("IMG_TO_BASE64",   NativeFunction("IMG_TO_BASE64", -1, img_to_base64))
        env.define("IMG_FROM_BASE64", NativeFunction("IMG_FROM_BASE64", 1, img_from_base64))
        env.define("IMG_CONVERT",     NativeFunction("IMG_CONVERT", -1, img_convert))
        # Audio
        env.define("AUDIO_LOAD",       NativeFunction("AUDIO_LOAD", 1, audio_load))
        env.define("AUDIO_PLAY",       NativeFunction("AUDIO_PLAY", -1, audio_play))
        env.define("AUDIO_PAUSE",      NativeFunction("AUDIO_PAUSE", 1, audio_pause))
        env.define("AUDIO_RESUME",     NativeFunction("AUDIO_RESUME", 1, audio_resume))
        env.define("AUDIO_STOP",       NativeFunction("AUDIO_STOP", 1, audio_stop))
        env.define("AUDIO_STOP_ALL",   NativeFunction("AUDIO_STOP_ALL", 0, audio_stop_all))
        env.define("AUDIO_SET_VOLUME", NativeFunction("AUDIO_SET_VOLUME", 2, audio_set_volume))
        env.define("AUDIO_GET_VOLUME", NativeFunction("AUDIO_GET_VOLUME", 1, audio_get_volume))
        env.define("AUDIO_IS_PLAYING", NativeFunction("AUDIO_IS_PLAYING", 1, audio_is_playing))
        env.define("AUDIO_GET_POS",    NativeFunction("AUDIO_GET_POS", 1, audio_get_pos))
        env.define("AUDIO_SET_POS",    NativeFunction("AUDIO_SET_POS", 2, audio_set_pos))
        env.define("AUDIO_GET_LENGTH", NativeFunction("AUDIO_GET_LENGTH", 1, audio_get_length))
        env.define("AUDIO_INFO",       NativeFunction("AUDIO_INFO", 1, audio_info))
        env.define("AUDIO_CLOSE",      NativeFunction("AUDIO_CLOSE", 1, audio_close))
        env.define("SFX_PLAY",         NativeFunction("SFX_PLAY", -1, sfx_play))
        # Video
        env.define("VIDEO_INFO",          NativeFunction("VIDEO_INFO", 1, video_info))
        env.define("VIDEO_EXTRACT_FRAME", NativeFunction("VIDEO_EXTRACT_FRAME", 3, video_extract_frame))
        env.define("VIDEO_THUMBNAIL",     NativeFunction("VIDEO_THUMBNAIL", -1, video_thumbnail))
        env.define("VIDEO_CONVERT",       NativeFunction("VIDEO_CONVERT", -1, video_convert))
        env.define("VIDEO_TRIM",          NativeFunction("VIDEO_TRIM", 4, video_trim))
        env.define("VIDEO_EXTRACT_AUDIO", NativeFunction("VIDEO_EXTRACT_AUDIO", 2, video_extract_audio))
        # UI widgets
        env.define("UI_IMAGE_VIEW",            NativeFunction("UI_IMAGE_VIEW", -1, ui_image_view))
        env.define("UI_IMAGE_VIEW_SET",        NativeFunction("UI_IMAGE_VIEW_SET", 2, ui_image_view_set))
        env.define("UI_IMAGE_VIEW_SET_HANDLE", NativeFunction("UI_IMAGE_VIEW_SET_HANDLE", 2, ui_image_view_set_handle))
        env.define("UI_IMAGE_VIEW_FIT",        NativeFunction("UI_IMAGE_VIEW_FIT", 1, ui_image_view_fit))
        env.define("UI_IMAGE_VIEW_ZOOM",       NativeFunction("UI_IMAGE_VIEW_ZOOM", 2, ui_image_view_zoom))
        env.define("UI_IMAGE_VIEW_CLEAR",      NativeFunction("UI_IMAGE_VIEW_CLEAR", 1, ui_image_view_clear))
        env.define("UI_AUDIO_PLAYER",       NativeFunction("UI_AUDIO_PLAYER", -1, ui_audio_player))
        env.define("UI_AUDIO_PLAYER_LOAD",  NativeFunction("UI_AUDIO_PLAYER_LOAD", 2, ui_audio_player_load))
        env.define("UI_AUDIO_PLAYER_PLAY",  NativeFunction("UI_AUDIO_PLAYER_PLAY", 1, ui_audio_player_play))
        env.define("UI_AUDIO_PLAYER_PAUSE", NativeFunction("UI_AUDIO_PLAYER_PAUSE", 1, ui_audio_player_pause))
        env.define("UI_AUDIO_PLAYER_STOP",  NativeFunction("UI_AUDIO_PLAYER_STOP", 1, ui_audio_player_stop))
        env.define("UI_VIDEO_PLAYER",       NativeFunction("UI_VIDEO_PLAYER", -1, ui_video_player))
        env.define("UI_VIDEO_PLAYER_LOAD",  NativeFunction("UI_VIDEO_PLAYER_LOAD", 2, ui_video_player_load))
        env.define("UI_VIDEO_PLAYER_PLAY",  NativeFunction("UI_VIDEO_PLAYER_PLAY", 1, ui_video_player_play))
        env.define("UI_VIDEO_PLAYER_PAUSE", NativeFunction("UI_VIDEO_PLAYER_PAUSE", 1, ui_video_player_pause))
        env.define("UI_VIDEO_PLAYER_STOP",  NativeFunction("UI_VIDEO_PLAYER_STOP", 1, ui_video_player_stop))