import os
import html
import io
import sys
import logging
import requests
import threading
import base64
import zlib
import random
import string
import re
from http.server WASimport HTTPServer, B:aseHTTPRequestHandler
import urllib.parseENCRYPT
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from decoder import full_decode

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8869261992:AAHOuwldQWWLlrQ69gXVtulzlisMhP3rxkQ"  # Ekhane apnar Bot Token boshan

WAITING_FOR_DECODE    = 1
WAITING_FOR_SOURCE    = 2
WAITING_FOR_ENCRYPT   = 3
WAITING_FOR_PY_DECODE = 4
WAITING_FOR_PY_ENCRYPT = 5
WAITING_FOR_JS_ENCRYPT = 6
WAITING_FOR_PHP_DECODE = 7

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🌐 SOURCE CODE"),     KeyboardButton("🔒 HTML DECODER")],
        [KeyboardButton("🐍 PYTHON DECODER"),  KeyboardButton("🔐 PYTHON OBFUSCATE")],
        [KeyboardButton("🔒 HTML OBFUSCATE"),    KeyboardButton("🕷️ PHP DECODER")],
        [KeyboardButton("👤 USER INFO"),       KeyboardButton("🔏 JS OBFUSCATE ")],
        [KeyboardButton("ℹ️ BOT INFO"),        KeyboardButton("👨‍💻 DEVELOPER INFO")],
    ],
    resize_keyboard=True,
)

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── helpers ──────────────────────────────────────────────────────────────────

def _buf(content: str, filename: str) -> io.BytesIO:
    buf = io.BytesIO(content.encode("utf-8"))
    buf.name = filename
    return buf

async def _send_file(update: Update, content: str, filename: str, caption: str):
    buf = _buf(content, filename)
    await update.message.reply_document(
        document=buf,
        filename=filename,
        caption=caption[:1020],
        reply_markup=MAIN_MENU,
    )

async def _download_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document
    if doc is None:
        return None
    allowed = {".php", ".html", ".htm", ".txt", ".js", ".py"}
    ext = os.path.splitext(doc.file_name or "")[1].lower()
    if ext not in allowed and doc.mime_type not in (
        "text/plain", "text/html", "application/x-php",
        "application/octet-stream", "application/php",
        "text/x-python", "application/x-python"
    ):
        return None
    tg_file = await context.bot.get_file(doc.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    buf.seek(0)
    raw = buf.read()
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")

def _rand_var(length=6):
    return '_0x' + ''.join(random.choices('0123456789abcdef', k=length))


# ── Strong HTML Encrypt ───────────────────────────────────────────────────────

def mask_scripts(html_code):
    def process_script(match):
        script_tag = match.group(1)
        script_content = match.group(2)
        script_end = match.group(3)
        if 'src=' in script_tag.lower() or not script_content.strip():
            return match.group(0)
        b64_script = base64.b64encode(script_content.encode('utf-8')).decode('utf-8')
        obfuscated_js = f"eval(decodeURIComponent(escape(atob('{b64_script}'))));"
        return f"{script_tag}\n{obfuscated_js}\n{script_end}"
    return re.sub(r'(<script[^>]*>)(.*?)(</script>)', process_script, html_code, flags=re.IGNORECASE | re.DOTALL)

def rc4_crypt_bytes(data, key):
    S = list(range(256))
    j = 0
    out = bytearray()
    for i in range(256):
        j = (j + S[i] + key[i % len(key)]) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    for char in data:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(char ^ S[(S[i] + S[j]) % 256])
    return out

def _strong_html_encrypt(content: str) -> str:
    html_code = mask_scripts(content)
    b64_bytes = base64.b64encode(urllib.parse.quote(html_code).encode('utf-8'))
    rc4_key = "".join(random.choices(string.ascii_letters + string.digits, k=16))
    rc4_key_bytes = rc4_key.encode('utf-8')
    rc4_cipher = rc4_crypt_bytes(b64_bytes, rc4_key_bytes)
    hex_cipher = rc4_cipher.hex()
    arr = [ord(c) for c in hex_cipher]
    arr_str = ",".join(map(str, arr))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    comment_inner = f"""
╔══════════════════════════════════════════════════════════╗
║  🔒 PROTECTED HTML - DO NOT MODIFY THIS HEADER 🔒         ║
║══════════════════════════════════════════════════════════║
║  Obfuscated By: @TRADER_SAIF_BOT                   ║
║  TG Channel : @TRADING_BY_SAIF                              ║
║  Timestamp: {timestamp}                          ║
║  Signature: SAIF PROTECTOR [TOKEN: {rc4_key}]             ║
║══════════════════════════════════════════════════════════║
║  ⚠️ WARNING: Removing or modifying this credit header    ║
║  will cause this page to stop working permanently!       ║
╚══════════════════════════════════════════════════════════╝"""

    header_comment = f"<!--{comment_inner}\n-->"
    expected_stripped = re.sub(r'\s+', '', comment_inner)

    decoder_js = f"""
    document.addEventListener('contextmenu', event => event.preventDefault());
    document.onkeydown = function(e) {{
        if(e.keyCode == 123) {{ return false; }}
        if(e.ctrlKey && e.shiftKey && e.keyCode == 'I'.charCodeAt(0)) {{ return false; }}
        if(e.ctrlKey && e.shiftKey && e.keyCode == 'C'.charCodeAt(0)) {{ return false; }}
        if(e.ctrlKey && e.shiftKey && e.keyCode == 'J'.charCodeAt(0)) {{ return false; }}
        if(e.ctrlKey && e.keyCode == 'U'.charCodeAt(0)) {{ return false; }}
    }};
    setInterval(function(){{ debugger; }}, 50);
    console.clear();
    
    var _safe = false;
    var _k = "";
    var _iter = document.createTreeWalker(document, 128, null, false);
    var _node;
    var _expected = "{expected_stripped}";
    
    while ((_node = _iter.nextNode())) {{
        var _val = _node.nodeValue;
        if (_val.indexOf('PROTECTED HTML') !== -1) {{
            var _actual = _val.replace(/\s+/g, '');
            if (_actual === _expected) {{
                var _idx = _val.indexOf('[TOKEN: ');
                if (_idx !== -1) {{
                    _k = _val.substring(_idx + 8, _idx + 24);
                    _safe = true;
                    break;
                }}
            }}
        }}
    }}
    
    if (!_safe || _k.length !== 16) {{
        document.write('<h1 style="color:red;text-align:center;margin-top:50px;font-family:sans-serif;background:#000;padding:30px;border-radius:10px;">🚨 CRASH: TAMPER DETECTED!<br><br><span style="color:#fff;font-size:16px;">The credit header was modified or deleted. Decryption Key has been destroyed.</span></h1>');
        while(true) {{ debugger; }}
        return;
    }}

    function _R(k, s) {{
        var _s=[], j=0, x, res='';
        for (var i=0; i<256; i++) _s[i]=i;
        for (i=0; i<256; i++) {{
            j=(j+_s[i]+k.charCodeAt(i%k.length))%256;
            x=_s[i]; _s[i]=_s[j]; _s[j]=x;
        }}
        i=0; j=0;
        for (var y=0; y<s.length; y++) {{
            i=(i+1)%256;
            j=(j+_s[i])%256;
            x=_s[i]; _s[i]=_s[j]; _s[j]=x;
            res += String.fromCharCode(s.charCodeAt(y)^_s[(_s[i]+_s[j])%256]);
        }}
        return res;
    }}

    var _A = [{arr_str}];
    var _h = '';
    for(var i=0; i<_A.length; i++) _h += String.fromCharCode(_A[i]);
    var _c = '';
    for(var i=0; i<_h.length; i+=2) {{
        _c += String.fromCharCode(parseInt(_h.substr(i, 2), 16));
    }}
    var _b = _R(_k, _c);
    
    try {{
        var _final = decodeURIComponent(atob(_b));
        document.open();
        document.write(_final);
        document.close();
    }} catch(e) {{
        document.write('<h1 style="color:red;text-align:center;margin-top:50px;background:#000;padding:30px;">🚨 FATAL ERROR: INVALID KEY! HTML CORRUPTED.</h1>');
    }}
    """

    encoded_decoder_js = base64.b64encode(decoder_js.encode('utf-8')).decode('utf-8')
    chunk_size = len(encoded_decoder_js) // 2
    part1 = encoded_decoder_js[:chunk_size]
    part2 = encoded_decoder_js[chunk_size:]

    final_html = f"""{header_comment}
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="author" id="tdx_author" content="@TRADER_SAIF">
<script>
    document.addEventListener("contextmenu", function(e){{ e.preventDefault(); }}, false);
</script>
</head>
<body oncontextmenu="return false;" onkeydown="return false;" onmousedown="return false;">
<script>
(function(){{
    var _p1 = '{part1}';
    var _p2 = '{part2}';
    var _combined = _p1 + _p2;
    var _payload = decodeURIComponent(escape(atob(_combined)));
    var _init = new Function(_payload);
    _init();
}})();
</script>
<noscript><h2>⚠️ Please enable JavaScript to view this secure page.</h2></noscript>
</body>
</html>"""
    return final_html

# ── Python Encrypt ────────────────────────────────────────────────────────────

def _python_encrypt(code: str) -> str:
    compressed = zlib.compress(code.encode('utf-8'), level=9)
    b64_1 = base64.b64encode(compressed).decode()
    b64_2 = base64.b64encode(b64_1.encode()).decode()

    v1 = '_' + ''.join(random.choices('O0', k=8))
    v2 = '_' + ''.join(random.choices('O0', k=8))
    v3 = '_' + ''.join(random.choices('O0', k=8))
    v4 = '_' + ''.join(random.choices('O0', k=8))

    return (
        f"import base64 as {v1},zlib as {v2}\n"
        f"{v3}='{b64_2}'\n"
        f"{v4}={v2}.decompress({v1}.b64decode({v1}.b64decode({v3}).decode()))\n"
        f"exec({v4})"
    )


# ── Python Decoder ────────────────────────────────────────────────────────────

def _python_decode(code: str) -> tuple:
    current = code
    methods = []

    for _ in range(20):
        changed = False

        # exec(zlib.decompress(base64.b64decode(base64.b64decode('...'))))
        m = re.search(
            r"zlib[.\w]*decompress\s*\([^)]*b64decode\s*\([^)]*b64decode\s*\(\s*['\"]([A-Za-z0-9+/=]+)['\"]\s*\)",
            current, re.DOTALL
        )
        if m:
            try:
                inner = base64.b64decode(base64.b64decode(m.group(1)).decode()).decode('utf-8', errors='replace')
                decompressed = zlib.decompress(base64.b64decode(inner)).decode('utf-8', errors='replace')
                current = decompressed
                methods.append("Python zlib+base64 double-layer")
                changed = True
                continue
            except Exception:
                pass

        # exec(zlib.decompress(base64.b64decode('...')))
        m = re.search(
            r"(?:zlib[.\w]*decompress|decompress)\s*\(\s*(?:base64[.\w]*b64decode|b64decode)\s*\(\s*['\"]([A-Za-z0-9+/=\n]+)['\"]\s*\)\s*\)",
            current, re.DOTALL
        )
        if m:
            try:
                raw = zlib.decompress(base64.b64decode(m.group(1).replace('\n', '')))
                current = raw.decode('utf-8', errors='replace')
                methods.append("Python zlib.decompress(base64.b64decode(...))")
                changed = True
                continue
            except Exception:
                pass

        # exec(base64.b64decode('...'))
        m = re.search(
            r"exec\s*\(\s*(?:base64[.\w]*b64decode|b64decode)\s*\(\s*['\"]([A-Za-z0-9+/=\n]+)['\"]\s*\)\s*\)",
            current
        )
        if m:
            try:
                decoded = base64.b64decode(m.group(1).replace('\n', '')).decode('utf-8', errors='replace')
                current = decoded
                methods.append("Python exec(base64.b64decode(...))")
                changed = True
                continue
            except Exception:
                pass

        # compile + marshal
        m = re.search(r"marshal\.loads\s*\(\s*(?:zlib[.\w]*decompress\s*\()?\s*(?:base64[.\w]*b64decode\s*\()?\s*['\"]([A-Za-z0-9+/=]+)['\"]", current)
        if m:
            try:
                import marshal
                raw = base64.b64decode(m.group(1))
                try:
                    raw = zlib.decompress(raw)
                except Exception:
                    pass
                code_obj = marshal.loads(raw)
                import dis
                out = io.StringIO()
                sys.stdout = out
                dis.dis(code_obj)
                sys.stdout = sys.__stdout__
                current = out.getvalue()
                methods.append("Python marshal.loads bytecode disassembly")
                changed = True
                continue
            except Exception:
                sys.stdout = sys.__stdout__

        # Plain base64 string that looks like Python
        m = re.search(r"['\"]([A-Za-z0-9+/]{60,}={0,2})['\"]", current)
        if m:
            try:
                decoded = base64.b64decode(m.group(1)).decode('utf-8', errors='replace')
                if any(kw in decoded for kw in ['import ', 'def ', 'class ', 'print(', 'exec(', '=', '__']):
                    current = decoded
                    methods.append("Python base64 string")
                    changed = True
                    continue
            except Exception:
                pass

        if not changed:
            break

    if not methods:
        methods.append("কোনো Python obfuscation পাওয়া যায়নি (plain code)")

    return current, methods


# ── JS Encrypt ────────────────────────────────────────────────────────────────

def _js_encrypt(code: str) -> str:
    key = random.randint(10, 126)
    xored = [str(ord(c) ^ key) for c in code]
    chunks = [xored[i:i+30] for i in range(0, len(xored), 30)]
    arr_parts = '[' + '],['.join(','.join(c) for c in chunks) + ']'

    v1 = _rand_var(5)
    v2 = _rand_var(6)
    v3 = _rand_var(5)
    v4 = _rand_var(4)
    v5 = _rand_var(6)
    v6 = _rand_var(5)

    return (
        f"var {v1}=[{arr_parts}].flat(),"
        f"{v2}={key},"
        f"{v3}='';"
        f"for(var {v4}=0;{v4}<{v1}.length;{v4}++){{"
        f"{v3}+=String.fromCharCode({v1}[{v4}]^{v2});"
        f"}}"
        f"var {v5}=Function;"
        f"new {v5}({v3})();"
    )


# ── PHP Decoder (URL crawler) ─────────────────────────────────────────────────

def _crawl_php_links(base_url: str) -> list:
    php_links = set()
    try:
        resp = requests.get(base_url, headers=FETCH_HEADERS, timeout=20)
        soup = BeautifulSoup(resp.content, 'html.parser')
        base_domain = urlparse(base_url).netloc

        for tag in soup.find_all(True):
            for attr in ['href', 'src', 'action', 'data-src']:
                val = tag.get(attr, '') or ''
                if '.php' in val.lower():
                    full = urljoin(base_url, val.split('?')[0])
                    if urlparse(full).netloc == base_domain:
                        php_links.add(full)

        for m in re.findall(r'["\']([^"\']*\.php(?:\?[^"\']*)?)["\']', resp.text):
            full = urljoin(base_url, m.split('?')[0])
            if urlparse(full).netloc == base_domain:
                php_links.add(full)

    except Exception:
        pass

    if '.php' in base_url:
        php_links.add(base_url.split('?')[0])

    return list(php_links)[:15]


# ── /start ────────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = (
        f"✨ 👾 TRADER SAIF BOT ✨\n\n"
        f"স্বাগতম {user.full_name} 👋\n\n"
        f"নিচের বাতামগুলো থেকে টুল সিলেক্ট করুন:"
    )
    photo_path = os.path.join(os.path.dirname(__file__), "welcome.jpg")
    if os.path.exists(photo_path):
        with open(photo_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo, caption=welcome_text, reply_markup=MAIN_MENU
            )
    else:
        await update.message.reply_text(welcome_text, reply_markup=MAIN_MENU)


# ── HTML Decode ───────────────────────────────────────────────────────────────

async def html_decode_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 *HTML DECODE — MULTI-LAYER*\n\n"
        "তিনটি উপায়ে পাঠাতে পারো:\n\n"
        "1️⃣ *URL* দাও → পেজের SOURCE নিয়ে DECODE করব\n"
        "2️⃣ *FILE ATTACH* করো → `.php` `.html` `.txt` `.js` file\n"
        "3️⃣ *CODE PASTE* করো → সরাসরি code লিখে পাঠাও\n\n"
        "বাতিল করতে /cancel",
        parse_mode="Markdown",
    )
    return WAITING_FOR_DECODE


async def _run_decode(update: Update, raw: str, source_label: str):
    decoded, methods = full_decode(raw)
    methods_text = "\n".join(f"  • {m}" for m in methods)
    changed = decoded != raw
    if not changed:
        caption = f"⚠️ *DECODE করা যায়নি*\n\n🔍 Tried:\n{methods_text}"
    else:
        caption = f"✅ *DECODE সম্পন্ন!*\n\n🔍 Applied:\n{methods_text}"
    await _send_file(update, decoded, "saif_bot_decoded.html", caption)


async def html_decode_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.document:
        content = await _download_file(update, context)
        if content is None:
            await msg.reply_text("❌ শুধু `.php` `.html` `.txt` `.js` file পাঠাও।", reply_markup=MAIN_MENU)
            return ConversationHandler.END
        status = await msg.reply_text("⚙️ Decode করছি...")
        await _run_decode(update, content, "file")
        await status.delete()
        return ConversationHandler.END

    text = (msg.text or "").strip()
    if not text:
        await msg.reply_text("❌ কিছু পাঠাও।", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    if text.startswith("http://") or text.startswith("https://"):
        status = await msg.reply_text("⏳ URL থেকে source নিচ্ছি...")
        try:
            resp = requests.get(text, headers=FETCH_HEADERS, timeout=20)
            resp.raise_for_status()
            raw = resp.content.decode("utf-8", errors="replace")
        except Exception as e:
            await status.edit_text(f"❌ ত্রুটি: {e}")
            await msg.reply_text("Menu:", reply_markup=MAIN_MENU)
            return ConversationHandler.END
        await status.edit_text("⚙️ DECODE করছি...")
        await _run_decode(update, raw, "url")
        await status.delete()
    else:
        status = await msg.reply_text("⚙️ DECODE করছি...")
        await _run_decode(update, text, "text")
        await status.delete()

    return ConversationHandler.END


# ── Source Code ───────────────────────────────────────────────────────────────

async def source_code_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌐 *SOURCE CODE VIEWER*\n\n"
        "যেকোনো WEBSITE-এর URL পাঠাও।\n\n"
        "বাতিল করতে /cancel",
        parse_mode="Markdown",
    )
    return WAITING_FOR_SOURCE


async def source_code_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("❌ সঠিক URL দাও।", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    status = await update.message.reply_text("⏳SOURCE CODEনিচ্ছি...")
    try
        resp = requests.get(text, headers=FETCH_HEADERS, timeout=20)
        resp.raise_for_status()
        source = resp.content.decode("utf-8", errors="replace")
    except Exception as e:
        await status.edit_text(f"❌ ত্রুটি: {e}")
        await update.message.reply_text("Menu:", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    await status.delete()
    await _send_file(update, source, "saif_bot_web_source_code.html", f"✅ *Source Code*\n🔗 {text[:200]}")
    return ConversationHandler.END


# ── HTML Encrypt ──────────────────────────────────────────────────────────────

async def html_encrypt_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔒 *HTML OBFUSCATE — Ultra Strong*\n\n"
        "HTML CODE পাঠাও অথবা FILE ATTACH করো।\n"
        "XOR + BASE64 MULTI-LAYER দিয়ে এমনভাবে OBFUSCATE হবে\n"
        "যে কেউ সহজে DECODE করতে পারবে না।\n\n"
        "বাতিল করতে /cancel",
        parse_mode="Markdown",
    )
    return WAITING_FOR_ENCRYPT


async def html_encrypt_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.document:
        content = await _download_file(update, context)
        if content:
            status = await msg.reply_text("⚙️ OBFUSCATE করছি...")
            encrypted = _strong_html_encrypt(content)
            await status.delete()
            await _send_file(update, encrypted, "saif_bot_obf.html", "✅ *HTML OBFUSCATE সম্পন্ন!*\n🔐 RC4 + ANTI-TAMPER APPLIED")
            return ConversationHandler.END

    text = (msg.text or "").strip()
    if not text:
        await msg.reply_text("❌ কিছু পাঠাও।", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    status = await msg.reply_text("⚙️ OBFUSCATE করছি...")
    encrypted = _strong_html_encrypt(text)
    await status.delete()
    await _send_file(update, encrypted, "encrypted.html", "✅ *HTML OBFUSCATE সম্পন্ন!*\n🔐 RC4 + ANTI-TAMPER APPLIED")
    return ConversationHandler.END


# ── Python Decoder ────────────────────────────────────────────────────────────

async def python_decoder_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🐍 *PYTHON DECODER*\n\n"
        "OBFUSCATE PYTHON CODE পাঠাও অথবা `.py` file attach করো।\n\n"
        "✅ *DECODE করতে পারে:*\n"
        "• exec(base64.b64decode(...))\n"
        "• exec(zlib.decompress(base64.b64decode(...)))\n"
        "• Double base64 layer\n"
        "• marshal.loads bytecode\n"
        "• Variable name obfuscation\n\n"
        "বাতিল করতে /cancel",
        parse_mode="Markdown",
    )
    return WAITING_FOR_PY_DECODE


async def python_decoder_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.document:
        content = await _download_file(update, context)
        if content is None:
            await msg.reply_text("❌ `.py` file পাঠাও।", reply_markup=MAIN_MENU)
            return ConversationHandler.END
    else:
        content = (msg.text or "").strip()
        if not content:
            await msg.reply_text("❌ কিছু পাঠাও।", reply_markup=MAIN_MENU)
            return ConversationHandler.END

    status = await msg.reply_text("⚙️ PYTHON DECODE করছি...")
    decoded, methods = _python_decode(content)
    methods_text = "\n".join(f"  • {m}" for m in methods)
    caption = f"🐍 *PYTHON DECODER*\n\n🔍 Applied:\n{methods_text}"
    await status.delete()
    await _send_file(update, decoded, "decoded.py", caption)
    return ConversationHandler.END


# ── Python Encrypt ────────────────────────────────────────────────────────────

async def python_encrypt_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔐 *PYTHON OBFUSCATE*\n\n"
        "PYTHON CODE পাঠাও অথবা `.py` FILE ATTACH করো।\n"
        "ZLIB+BASE64 DOUBLE-LAYER দিয়ে OBFUSCATE হবে।\n\n"
        "বাতিল করতে /cancel",
        parse_mode="Markdown",
    )
    return WAITING_FOR_PY_ENCRYPT


async def python_encrypt_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.document:
        content = await _download_file(update, context)
        if content is None:
            await msg.reply_text("❌ `.py` file পাঠাও।", reply_markup=MAIN_MENU)
            return ConversationHandler.END
    else:
        content = (msg.text or "").strip()
        if not content:
            await msg.reply_text("❌ কিছু পাঠাও।", reply_markup=MAIN_MENU)
            return ConversationHandler.END

    status = await msg.reply_text("⚙️ PYTHON OBFUSCATE করছি...")
    encrypted = _python_encrypt(content)
    await status.delete()
    await _send_file(update, encrypted, "saif_bot_obf.py", "✅ *Python Encrypt সম্পন্ন!*\n🔐 zlib+base64 double-layer applied")
    return ConversationHandler.END


# ── JS Encrypt ────────────────────────────────────────────────────────────────

async def js_encrypt_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔏 *JS Encrypt*\n\n"
        "JavaScript code পাঠাও অথবা `.js` file attach করো।\n"
        "XOR + _0x obfuscation দিয়ে encode হবে।\n\n"
        "বাতিল করতে /cancel",
        parse_mode="Markdown",
    )
    return WAITING_FOR_JS_ENCRYPT


async def js_encrypt_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message

    if msg.document:
        content = await _download_file(update, context)
        if content is None:
            await msg.reply_text("❌ `.js` file পাঠাও।", reply_markup=MAIN_MENU)
            return ConversationHandler.END
    else:
        content = (msg.text or "").strip()
        if not content:
            await msg.reply_text("❌ কিছু পাঠাও।", reply_markup=MAIN_MENU)
            return ConversationHandler.END

    status = await msg.reply_text("⚙️ JS encrypt করছি...")
    encrypted = _js_encrypt(content)
    await status.delete()
    await _send_file(update, encrypted, "encrypted.js", "✅ *JS Encrypt সম্পন্ন!*\n🔏 XOR+_0x obfuscation applied")
    return ConversationHandler.END


# ── PHP Decoder (URL) ─────────────────────────────────────────────────────────

async def php_decoder_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🕷️ *PHP Decoder*\n\n"
        "Website-এর URL দাও — সেই page-এর সব PHP file খুঁজে বের করব।\n"
        "Obfuscated হলে decode করে দেব।\n\n"
        "উদাহরণ: `https://example.com/index.php`\n\n"
        "বাতিল করতে /cancel",
        parse_mode="Markdown",
    )
    return WAITING_FOR_PHP_DECODE


async def php_decoder_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if not (text.startswith("http://") or text.startswith("https://")):
        await update.message.reply_text("❌ সঠিক URL দাও (http:// বা https:// দিয়ে শুরু)।", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    status = await update.message.reply_text("⏳ Website স্ক্যান করছি — PHP files খুঁজছি...")

    php_links = _crawl_php_links(text)

    if not php_links:
        await status.edit_text("❌ কোনো PHP file পাওয়া যায়নি।")
        await update.message.reply_text("Menu:", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    await status.edit_text(f"⚙️ {len(php_links)}টা PHP file পাওয়া গেছে, download ও decode করছি...")

    results = []
    for php_url in php_links:
        try:
            r = requests.get(php_url, headers=FETCH_HEADERS, timeout=15)
            content = r.content.decode("utf-8", errors="replace")
            decoded, methods = full_decode(content)
            fname = urlparse(php_url).path.split('/')[-1] or 'index.php'
            if not fname.endswith('.php'):
                fname += '.php'
            results.append((fname, decoded, methods, php_url))
        except Exception:
            continue

    await status.delete()

    if not results:
        await update.message.reply_text("❌ PHP file download করা গেল গঠন না।", reply_markup=MAIN_MENU)
        return ConversationHandler.END

    for fname, content, methods, url in results:
        methods_text = "\n".join(f"  • {m}" for m in methods)
        caption = f"🕷️ *PHP Decoder*\n🔗 {url[:150]}\n\n🔍 Applied:\n{methods_text}"
        await _send_file(update, content, fname, caption)

    return ConversationHandler.END


# ── Cancel ────────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ বাতিল করা হয়েছে।", reply_markup=MAIN_MENU)
    return ConversationHandler.END


# ── Static buttons ────────────────────────────────────────────────────────────

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    info = (
        f"👤 *USER INFO*\n\n"
        f"🆔 ID: `{user.id}`\n"
        f"👤 নাম: {user.full_name}\n"
        f"📛 USERNAME: @{user.username or 'নেই'}\n"
        f"🌐 ভাষা: {user.language_code or 'অজানা'}\n"
        f"🤖 BOT: {'হ্যাঁ' if user.is_bot else 'না'}\n"
        f"👑 PREMIUM: {'হ্যাঁ' if getattr(user, 'is_premium', False) else 'না'}"
    )
    await update.message.reply_text(info, parse_mode="Markdown", reply_markup=MAIN_MENU)


async def bot_info_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *BOT INFO*\n\n"
        "🤖 নাম: TRADER SAIF BOT\n"
        "⚙️ *FEATURES:*\n"
        "  • 🔒 HTML DECODE (URL / FILE / TEXT)\n"
        "  • 🌐 SOURCE CODE VIEWER\n"
        "  • 🔒 HTML ENCRYPT (XOR+BASE64 ULTRA STRONG)\n"
        "  • 🐍 Python DECODER\n"
        "  • 🔐 Python ENCRYPT\n"
        "  • 🔏 JS ENCRYPT (_0x OBFUSCATION)\n"
        "  • 🕷️ PHP Decoder (URL CRAWLER)\n"
        "  • 👤 USER INFO\n\n"
        "💬 *Decode করতে পারে:*\n"
        "PHPKodo • PHPCabbo • PHPKobo • Base64\n"
        "gzinflate • str\\_rot13 • HTML entities\n"
        "Hex • URL encoding • JS eval/atob\n"
        "Python exec/zlib/base64 chains",
        parse_mode="Markdown", reply_markup=MAIN_MENU,
    )


async def developer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👨‍💻 *DEVELOPER INFO*\n\n"
        "👤 Name: MD SHAHRIAR SAIF\n"
        "📱 Telegram: @TRADER\\_SAIF\n\n"
        "🤖 THIS BOT CREATED AND DEVELOPED\n"
        "BY MD SHAHRIAR SAIF.\n\n"
        "📩 যেকোনো সমস্যা বা FEATURE REQUEST-এর জন্য\n"
        "TELEGRAM-এ CONTACT করো।",
        parse_mode="Markdown", reply_markup=MAIN_MENU
    )


# ── Health Check Server ───────────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):
        pass


def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info("Health server running on port %d", port)
    server.serve_forever()


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    decode_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔒 HTML Decode$"), html_decode_ask)],
        states={
            WAITING_FOR_DECODE: [
                MessageHandler(filters.Document.ALL, html_decode_process),
                MessageHandler(filters.TEXT & ~filters.COMMAND, html_decode_process),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    source_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🌐 Source Code$"), source_code_ask)],
        states={
            WAITING_FOR_SOURCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, source_code_process),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    encrypt_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔒 HTML Encrypt$"), html_encrypt_ask)],
        states={
            WAITING_FOR_ENCRYPT: [
                MessageHandler(filters.Document.ALL, html_encrypt_process),
                MessageHandler(filters.TEXT & ~filters.COMMAND, html_encrypt_process),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    py_decode_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🐍 Python Decoder$"), python_decoder_ask)],
        states={
            WAITING_FOR_PY_DECODE: [
                MessageHandler(filters.Document.ALL, python_decoder_process),
                MessageHandler(filters.TEXT & ~filters.COMMAND, python_decoder_process),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    py_encrypt_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔐 Python Encrypt$"), python_encrypt_ask)],
        states={
            WAITING_FOR_PY_ENCRYPT: [
                MessageHandler(filters.Document.ALL, python_encrypt_process),
                MessageHandler(filters.TEXT & ~filters.COMMAND, python_encrypt_process),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    js_encrypt_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔏 JS Encrypt$"), js_encrypt_ask)],
        states={
            WAITING_FOR_JS_ENCRYPT: [
                MessageHandler(filters.Document.ALL, js_encrypt_process),
                MessageHandler(filters.TEXT & ~filters.COMMAND, js_encrypt_process),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    php_decode_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🕷️ PHP Decoder$"), php_decoder_ask)],
        states={
            WAITING_FOR_PHP_DECODE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, php_decoder_process),
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(decode_conv)
    app.add_handler(source_conv)
    app.add_handler(encrypt_conv)
    app.add_handler(py_decode_conv)
    app.add_handler(py_encrypt_conv)
    app.add_handler(js_encrypt_conv)
    app.add_handler(php_decode_conv)

    app.add_handler(MessageHandler(filters.Regex("^👤 User Info$"),       user_info))
    app.add_handler(MessageHandler(filters.Regex("^ℹ️ Bot Info$"),        bot_info_cmd))
    app.add_handler(MessageHandler(filters.Regex("^👨‍💻 Developer Info$"),  developer_info))

    logger.info("✅ Bot চালু হয়েছে...")
    print("✅ Bot চালু হয়েছে...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
