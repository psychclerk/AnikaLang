import urllib.request
import urllib.error
import smtplib
import imaplib
import email
import html
from email.message import EmailMessage
from email.header import decode_header, make_header

from .base_plugin import AnikaPlugin
from core.interpreter import NativeFunction
from core.errors import FMS_Error

class NetworkPlugin(AnikaPlugin):
    def register(self, env, interpreter):
        # ==========================================================================
        # HTTP POST & CUSTOM HEADERS
        # ==========================================================================
        def http_post(i, a):
            url = str(a[0]); data = str(a[1])
            content_type = str(a[2]) if len(a) > 2 else "application/json"
            try:
                req = urllib.request.Request(url, data=data.encode('utf-8'),
                    headers={'Content-Type': content_type, 'User-Agent': 'AnikaLang/1.0'}, method='POST')
                with urllib.request.urlopen(req, timeout=180) as response: return response.read().decode('utf-8')
            except urllib.error.URLError as e: raise FMS_Error(f"HTTP POST failed: {str(e)}", error_type="Network Error")
            except Exception as e: raise FMS_Error(f"HTTP POST error: {str(e)}", error_type="Network Error")

        def http_post_headers(i, a):
            url = str(a[0]); data = str(a[1])
            custom_headers = a[2] if len(a) > 2 else {}
            headers = {'User-Agent': 'AnikaLang/1.0', 'Content-Type': 'application/json'}
            if isinstance(custom_headers, dict):
                for k, v in custom_headers.items(): headers[str(k)] = str(v)
            try:
                req = urllib.request.Request(url, data=data.encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=180) as response: return response.read().decode('utf-8')
            except urllib.error.HTTPError as e: return "ERROR: " + str(e.code) + " - " + e.read().decode('utf-8')
            except Exception as e: raise FMS_Error(f"HTTP POST HEADERS failed: {str(e)}", error_type="Network Error")

        def http_get_headers(i, a):
            url = str(a[0]); custom_headers = a[1] if len(a) > 1 else {}
            headers = {'User-Agent': 'AnikaLang/1.0', 'Accept': 'application/json'}
            if isinstance(custom_headers, dict):
                for k, v in custom_headers.items(): headers[str(k)] = str(v)
            try:
                req = urllib.request.Request(url, headers=headers, method='GET')
                with urllib.request.urlopen(req, timeout=180) as response: return response.read().decode('utf-8')
            except urllib.error.HTTPError as e: return "ERROR: " + str(e.code) + " - " + e.read().decode('utf-8', errors='replace')
            except urllib.error.URLError as e: raise FMS_Error(f"HTTP GET HEADERS failed: {str(e)}", error_type="Network Error")
            except Exception as e: raise FMS_Error(f"HTTP GET HEADERS error: {str(e)}", error_type="Network Error")

        env.define("HTTP_POST", NativeFunction("HTTP_POST", -1, http_post))
        env.define("HTTP_POST_HEADERS", NativeFunction("HTTP_POST_HEADERS", -1, http_post_headers))
        env.define("HTTP_GET_HEADERS", NativeFunction("HTTP_GET_HEADERS", -1, http_get_headers))

        # ==========================================================================
        # EMAIL (SMTP & IMAP)
        # ==========================================================================
        def email_send(i, a):
            host = str(a[0]); port = int(a[1]); username = str(a[2]); password = str(a[3])
            from_addr = str(a[4]); to_addr = str(a[5]); subject = str(a[6]); body_html = str(a[7])
            try:
                msg = EmailMessage(); msg['Subject'] = subject; msg['From'] = from_addr; msg['To'] = to_addr
                msg.set_content(body_html, subtype='html')
                if port == 465: server = smtplib.SMTP_SSL(host, port, timeout=15)
                else:
                    server = smtplib.SMTP(host, port, timeout=15); server.starttls()
                server.login(username, password); server.send_message(msg); server.quit()
                return "SUCCESS"
            except smtplib.SMTPAuthenticationError:
                raise FMS_Error("SMTP Authentication failed. Ensure you are using an 'App Password'.", error_type="Network Error")
            except Exception as e: raise FMS_Error(f"Failed to send email: {str(e)}", error_type="Network Error")

        def email_fetch(i, a):
            host = str(a[0]); port = int(a[1]); username = str(a[2]); password = str(a[3])
            folder = str(a[4]) if len(a) > 4 else "INBOX"; limit = int(a[5]) if len(a) > 5 else 20
            try:
                mail = imaplib.IMAP4_SSL(host, port); mail.login(username, password); mail.select(folder)
                status, messages = mail.search(None, "ALL")
                if status != "OK": raise FMS_Error("Failed to search emails on server.", error_type="Network Error")
                email_ids = messages[0].split()
                latest_ids = email_ids[-limit:] if len(email_ids) >= limit else email_ids
                latest_ids.reverse(); result_list = []
                for e_id in latest_ids:
                    status, data = mail.fetch(e_id, "(RFC822)")
                    if status != "OK": continue
                    raw_email = data[0][1]; msg = email.message_from_bytes(raw_email)
                    def decode_header_safe(header_val):
                        if not header_val: return ""
                        try: return str(make_header(decode_header(header_val)))
                        except: return str(header_val)
                    subject = decode_header_safe(msg['Subject']); from_addr = decode_header_safe(msg['From'])
                    date_str = msg['Date'] if msg['Date'] else "Unknown"
                    body_html = ""; body_text = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition", ""))
                            if "attachment" not in content_disposition:
                                try:
                                    payload = part.get_payload(decode=True)
                                    if payload:
                                        text_payload = payload.decode('utf-8', errors='ignore')
                                        if content_type == "text/html": body_html = text_payload
                                        elif content_type == "text/plain" and not body_text: body_text = text_payload
                                except: pass
                    else:
                        try:
                            payload = msg.get_payload(decode=True)
                            if payload:
                                text_payload = payload.decode('utf-8', errors='ignore')
                                if msg.get_content_type() == "text/html": body_html = text_payload
                                else: body_text = text_payload
                        except: pass
                    if not body_html and body_text:
                        safe_text = html.escape(body_text)
                        body_html = f"<html><body><pre style='font-family: sans-serif; white-space: pre-wrap;'>{safe_text}</pre></body></html>"
                    result_list.append({"id": e_id.decode('utf-8'), "from": from_addr, "subject": subject,
                                        "date": date_str, "body_html": body_html, "body_text": body_text})
                mail.logout(); return result_list
            except imaplib.IMAP4.error as e: raise FMS_Error(f"IMAP Server Error: {str(e)}", error_type="Network Error")
            except Exception as e: raise FMS_Error(f"Failed to fetch emails: {str(e)}", error_type="Network Error")

        env.define("EMAIL_SEND", NativeFunction("EMAIL_SEND", 8, email_send))
        env.define("EMAIL_FETCH", NativeFunction("EMAIL_FETCH", -1, email_fetch))