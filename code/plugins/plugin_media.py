import re
import html as html_module

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class MediaPlugin(AnikaPlugin):
    def register(self, env, interpreter):
        # ==========================================================================
        # MARKDOWN & HTML CONVERSION
        # ==========================================================================
        def md_to_html(i, a):
            md_text = str(a[0]) if a[0] is not None else ""
            try:
                import markdown
                return markdown.markdown(md_text, extensions=['fenced_code', 'tables', 'toc', 'nl2br', 'sane_lists'])
            except ImportError:
                html_out = html_module.escape(md_text)
                html_out = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_out, flags=re.MULTILINE)
                html_out = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_out, flags=re.MULTILINE)
                html_out = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_out, flags=re.MULTILINE)
                html_out = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_out)
                html_out = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_out)
                html_out = re.sub(r'`(.+?)`', r'<code>\1</code>', html_out)
                html_out = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html_out, flags=re.MULTILINE)
                html_out = html_out.replace('\n', '</p><p>')
                return '<p>' + html_out + '</p>'
            except Exception as e:
                return f"<p style='color:red'>Markdown conversion error: {str(e)}</p><pre>{md_text}</pre>"

        def html_to_md(i, a):
            html_text = str(a[0]) if a[0] is not None else ""
            if len(html_text.strip()) == 0: return ""
            try:
                import markdownify
                md = markdownify.markdownify(html_text, heading_style="ATX", bullets="-", strip=['img'],
                    convert=['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'em', 'i', 'a', 'code', 'pre',
                             'ul', 'ol', 'li', 'blockquote', 'br', 'hr', 'table', 'tr', 'th', 'td', 'img'])
                return re.sub(r'\n{3,}', '\n\n', md).strip()
            except ImportError:
                pass
            # Fallback regex converter
            md = html_text
            md = re.sub(r'<!--.*?-->', '', md, flags=re.DOTALL)
            md = re.sub(r'<style.*?>.*?</style>', '', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<script.*?>.*?</script>', '', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n# \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\n#### \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h5[^>]*>(.*?)</h5>', r'\n##### \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<h6[^>]*>(.*?)</h6>', r'\n###### \1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<(strong|b)[^>]*>(.*?)</\1>', r'**\2**', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<(em|i)[^>]*>(.*?)</\1>', r'*\2*', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<code[^>]*>(.*?)</code>', lambda m: '`' + m.group(1).strip() + '`' if '\n' not in m.group(1) else m.group(0), md, flags=re.DOTALL | re.IGNORECASE)
            def convert_pre(match):
                inner = match.group(1)
                lang_match = re.search(r'class=["\'].*?language-(\w+)', inner, re.IGNORECASE)
                lang = lang_match.group(1) if lang_match else ""
                code = re.sub(r'</?code[^>]*>', '', inner, flags=re.IGNORECASE)
                code = code.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
                return '\n```' + lang + '\n' + code.strip() + '\n```\n'
            md = re.sub(r'<pre[^>]*>(.*?)</pre>', convert_pre, md, flags=re.DOTALL | re.IGNORECASE)
            def convert_link(match): return '[' + (match.group(2) or "").strip() + '](' + (match.group(1) or "") + ')'
            md = re.sub(r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', convert_link, md, flags=re.DOTALL | re.IGNORECASE)
            def convert_img(match):
                src = match.group(1) or ""; alt_match = re.search(r'alt=["\']([^"\']*)["\']', match.group(0), re.IGNORECASE)
                return '![' + (alt_match.group(1) if alt_match else "") + '](' + src + ')'
            md = re.sub(r'<img[^>]*src=["\']([^"\']*)["\'][^>]*/?>', convert_img, md, flags=re.IGNORECASE)
            def convert_blockquote(match):
                content = re.sub(r'</?p[^>]*>', '', match.group(1).strip(), flags=re.IGNORECASE)
                return '\n' + '\n'.join('> ' + line.strip() for line in content.split('\n') if line.strip()) + '\n'
            md = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', convert_blockquote, md, flags=re.DOTALL | re.IGNORECASE)
            def convert_ul(match):
                items = re.findall(r'<li[^>]*>(.*?)</li>', match.group(1), flags=re.DOTALL | re.IGNORECASE)
                return '\n' + '\n'.join('- ' + re.sub(r'\s+', ' ', re.sub(r'</?p[^>]*>', '', item, flags=re.IGNORECASE)).strip() for item in items) + '\n'
            md = re.sub(r'<ul[^>]*>(.*?)</ul>', convert_ul, md, flags=re.DOTALL | re.IGNORECASE)
            def convert_ol(match):
                items = re.findall(r'<li[^>]*>(.*?)</li>', match.group(1), flags=re.DOTALL | re.IGNORECASE)
                return '\n' + '\n'.join(str(idx) + '. ' + re.sub(r'\s+', ' ', re.sub(r'</?p[^>]*>', '', item, flags=re.IGNORECASE)).strip() for idx, item in enumerate(items, 1)) + '\n'
            md = re.sub(r'<ol[^>]*>(.*?)</ol>', convert_ol, md, flags=re.DOTALL | re.IGNORECASE)
            def convert_table(match):
                rows = re.findall(r'<tr[^>]*>(.*?)</tr>', match.group(0), flags=re.DOTALL | re.IGNORECASE)
                if not rows: return ''
                md_rows = [[re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', c)).strip() for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row, flags=re.DOTALL | re.IGNORECASE)] for row in rows]
                if not md_rows: return ''
                result = '\n| ' + ' | '.join(md_rows[0]) + ' |\n| ' + ' | '.join(['---'] * len(md_rows[0])) + ' |\n'
                for row in md_rows[1:]:
                    while len(row) < len(md_rows[0]): row.append('')
                    result += '| ' + ' | '.join(row[:len(md_rows[0])]) + ' |\n'
                return result + '\n'
            md = re.sub(r'<table[^>]*>.*?</table>', convert_table, md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<br\s*/?>', '\n', md, flags=re.IGNORECASE)
            md = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', md, flags=re.DOTALL | re.IGNORECASE)
            md = re.sub(r'<hr\s*/?>', '\n---\n', md, flags=re.IGNORECASE)
            md = md.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"').replace('&nbsp;', ' ').replace('&#39;', "'")
            md = re.sub(r'<[^>]+>', '', md)
            md = re.sub(r'[ \t]+\n', '\n', md); md = re.sub(r'\n{3,}', '\n\n', md)
            return md.strip()

        def markdown_to_html(i, a):
            text = str(a[0]); extensions = ['fenced_code', 'tables', 'toc', 'nl2br']
            if len(a) > 1 and a[1]: extensions = [e.strip() for e in str(a[1]).split(',')]
            try:
                import markdown; return markdown.markdown(text, extensions=extensions)
            except ImportError: raise FMS_Error("Missing dependency: 'markdown'. Run: pip install markdown", error_type="Import Error")
            except Exception as e: raise FMS_Error(f"Markdown conversion failed: {str(e)}", error_type="Runtime Error")

        def html_to_text(i, a):
            html_str = str(a[0])
            try:
                from html.parser import HTMLParser
                class TextExtractor(HTMLParser):
                    def __init__(self): super().__init__(); self.result = []
                    def handle_data(self, data): self.result.append(data)
                parser = TextExtractor(); parser.feed(html_str); return ''.join(parser.result)
            except Exception: return html_str

        def export_pdf(i, a):
            html_content = str(a[0]); output_path = str(a[1])
            try:
                import weasyprint; weasyprint.HTML(string=html_content).write_pdf(output_path); return "SUCCESS"
            except ImportError: pass
            except Exception as e: return f"ERROR: weasyprint failed: {str(e)}"
            try:
                import pdfkit; pdfkit.from_string(html_content, output_path); return "SUCCESS"
            except ImportError: pass
            except Exception as e: return f"ERROR: pdfkit failed: {str(e)}"
            try:
                with open(output_path, 'w', encoding='utf-8') as f: f.write(html_content)
                return "WARNING: Saved as HTML (install weasyprint for real PDF)"
            except Exception as e: return f"ERROR: {str(e)}"

        env.define("MD_TO_HTML", NativeFunction("MD_TO_HTML", 1, md_to_html))
        env.define("HTML_TO_MD", NativeFunction("HTML_TO_MD", 1, html_to_md))
        env.define("MARKDOWN_TO_HTML", NativeFunction("MARKDOWN_TO_HTML", -1, markdown_to_html))
        env.define("HTML_TO_TEXT", NativeFunction("HTML_TO_TEXT", 1, html_to_text))
        env.define("EXPORT_PDF", NativeFunction("EXPORT_PDF", 2, export_pdf))