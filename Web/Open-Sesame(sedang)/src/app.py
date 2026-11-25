#!/usr/bin/env python3
import base64
import hashlib
import html
import json
import os
import random
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


FLAG = os.getenv("FLAG", "ITECHNO26{opeeeeeen_plssssss_opennnnnn_ses4meeeeeee}")
PORT = int(os.getenv("PORT", "8080"))
LEAK_THRESHOLD = 23900
MAX_HOST_LINE = 65000
TOKEN_SUFFIX = "45525d5f4f58455e445a4a42"


def make_token(label: str) -> str:
    return hashlib.sha256(f"open-sesame::{label}".encode()).hexdigest()[:41] + TOKEN_SUFFIX


def short_mac(value: str) -> str:
    return hashlib.sha256(f"nsppe::{value}".encode()).hexdigest()[:10]


GUEST_TOKEN = make_token("market-door")
AUDITOR_TOKEN = make_token("receiver-trace")
ADMIN_TOKEN = make_token("forty-thieves")
DOOR_PHRASE = base64.urlsafe_b64encode(
    hashlib.sha256(f"iftah::{ADMIN_TOKEN}".encode()).digest()
).decode().rstrip("=")[:26]

SESSIONS = {
    GUEST_TOKEN: {"user": "ali_baba", "role": "merchant", "realm": "public"},
    AUDITOR_TOKEN: {"user": "morgiana", "role": "auditor", "realm": "ops"},
    ADMIN_TOKEN: {"user": "sesame_root", "role": "root", "realm": "vault"},
}


def token_fragments(token: str):
    sizes = [7, 13, 6, 11, 5, 9, 14]
    pos = 0
    parts = []
    for size in sizes:
        parts.append(token[pos : pos + size])
        pos += size
    return parts


def phrase_fragments(phrase: str):
    return [phrase[:8], phrase[8:17], phrase[17:]]


def decoy_token(i: int) -> str:
    digest = hashlib.sha256(f"decoy-cookie::{i}".encode()).hexdigest()
    return digest[:41] + TOKEN_SUFFIX


def pad_noise(rng: random.Random, size: int) -> bytes:
    alphabet = b"0123456789abcdef./:=_- "
    return bytes(rng.choice(alphabet) for _ in range(size))


def build_heap() -> bytes:
    rng = random.Random(0x51E5A4E)
    chunks = []

    chunks.append(b"HTTP/1.1 200 OK\r\nServer: Citrix ADC nshttpd/13.1\r\n")
    chunks.append(
        f"aaa.session.restore NSC_AAAC={GUEST_TOKEN}; user=ali_baba; role=merchant; "
        f"mac={short_mac(GUEST_TOKEN)}\x00\n".encode()
    )
    chunks.append(b"cache-note: repeated 65-byte lowercase hex values are not always sessions\x00\n")
    for i in range(12):
        chunks.append(f"dead-session[{i:02d}] NSC_AAAC={decoy_token(i)} state=expired\x00\n".encode())
        chunks.append(pad_noise(rng, rng.randint(120, 260)) + b"\n")

    chunks.append(
        f"receiver.audit cookie={AUDITOR_TOKEN}; user=morgiana; role=auditor; "
        f"mac={short_mac(AUDITOR_TOKEN)}\x00\n".encode()
    )
    chunks.append(pad_noise(rng, 1800) + b"\n")
    chunks.append(
        b"ns.conf.rollback: /cvpn/http/sesame-admin.local/open-sesame requires "
        b"NSC_AAAC(root) and header X-Open-Sesame\x00\n"
    )

    admin_parts = token_fragments(ADMIN_TOKEN)
    phrase_parts = phrase_fragments(DOOR_PHRASE)
    admin_order = [4, 0, 6, 2, 5, 1, 3]
    phrase_order = [2, 0, 1]

    for i in range(24):
        chunks.append(f"lb-vserver-noise[{i:02d}] ".encode() + pad_noise(rng, rng.randint(260, 520)) + b"\n")
        if i in (3, 7, 12, 17, 21, 23):
            chunks.append(f"orphan-cookie[{i:02d}] {decoy_token(100 + i)}\x00\n".encode())
        if i < len(admin_order):
            idx = admin_order[i]
            frag = admin_parts[idx]
            chunks.append(
                f"aaa.admin.token.fragment[{idx}/7]={frag}; checksum={short_mac(frag)}; "
                f"restore=concat-by-index\x00\n".encode()
            )
        if i < len(phrase_order):
            idx = phrase_order[i]
            frag = phrase_parts[idx]
            chunks.append(
                f"door.phrase.fragment[{idx}/3]={frag}; checksum={short_mac(frag)}; "
                f"header=X-Open-Sesame\x00\n".encode()
            )

    chunks.append(
        b"panic: stale aaad trace ended before secure erase; operator note says "
        b"'Open Sesame' was a theme, not the phrase\x00\n"
    )
    chunks.append(pad_noise(rng, 6000))
    return b"".join(chunks)


HEAP = build_heap()


def page(title: str, body: str) -> bytes:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #111417;
      --panel: #181d21;
      --text: #edf2f4;
      --muted: #9db1bd;
      --line: #34414a;
      --accent: #d6a74f;
      --bad: #d96c62;
      --ok: #69c58a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background:
        linear-gradient(180deg, rgba(17,20,23,.88), rgba(17,20,23,.98)),
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='320' height='180' viewBox='0 0 320 180'%3E%3Crect width='320' height='180' fill='%23232b30'/%3E%3Cpath d='M20 150C82 91 105 28 160 28s78 63 140 122' fill='none' stroke='%23d6a74f' stroke-width='6' opacity='.24'/%3E%3Cpath d='M0 172h320' stroke='%235b6d76' stroke-width='10' opacity='.35'/%3E%3C/svg%3E");
      background-size: cover, 640px 360px;
    }}
    main {{
      width: min(980px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 48px 0;
    }}
    header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0; font-size: clamp(2rem, 5vw, 4rem); letter-spacing: 0; }}
    h2 {{ margin: 0 0 12px; font-size: 1.35rem; }}
    p {{ color: var(--muted); line-height: 1.65; }}
    code, pre {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: .95rem;
    }}
    pre {{
      overflow-x: auto;
      padding: 16px;
      border: 1px solid var(--line);
      background: #0d1012;
    }}
    .panel {{
      margin-top: 24px;
      padding: 20px;
      border: 1px solid var(--line);
      background: color-mix(in srgb, var(--panel) 88%, transparent);
      border-radius: 8px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: .88rem;
      white-space: nowrap;
    }}
    a {{ color: var(--accent); }}
    .bad {{ color: var(--bad); }}
    .ok {{ color: var(--ok); }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Open Sesame</h1>
      <span class="pill">ADC Gateway 13.1 build 49.15</span>
    </header>
    {body}
  </main>
</body>
</html>""".encode()


class OpenSesameHandler(BaseHTTPRequestHandler):
    server_version = "CitrixADC/13.1"
    sys_version = ""

    def log_message(self, fmt, *args):
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args), flush=True)

    def send_body(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, data):
        self.send_body(status, json.dumps(data, separators=(",", ":")).encode(), "application/json")

    def read_request_body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return b""
        return self.rfile.read(min(length, 65536))

    def cookie_session(self):
        cookie_header = self.headers.get("Cookie", "")
        jar = SimpleCookie()
        try:
            jar.load(cookie_header)
        except Exception:
            return None, None
        token = jar["NSC_AAAC"].value if "NSC_AAAC" in jar else ""
        return token, SESSIONS.get(token)

    def do_GET(self):
        self.route()

    def do_POST(self):
        self.read_request_body()
        self.route()

    def route(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self.home()
        if path == "/oauth/idp/.well-known/openid-configuration":
            return self.oidc_configuration()
        if path == "/logon/LogonPoint/Authentication/GetUserName":
            return self.get_username()
        if path in ("/vpn/index.html", "/vpn/portal"):
            return self.portal()
        if path == "/vpn/portal/bookmarks":
            return self.bookmarks()
        if path == "/cvpn/http/sesame-admin.local/open-sesame":
            return self.open_sesame(parsed.query)
        if path == "/healthz":
            return self.send_body(200, b"ok\n", "text/plain")
        return self.send_body(404, b"Not found\n", "text/plain")

    def home(self):
        body = """
    <section class="panel">
      <h2>Gateway Login</h2>
      <p>This appliance proxies the merchant market and its clientless bookmarks.
      The authentication plane still exposes an OpenID discovery document for legacy receivers.</p>
      <pre>GET /oauth/idp/.well-known/openid-configuration</pre>
      <p>External notes mention CVE-2023-4966, but the visible symptom depends on how much of the
      virtual host buffer the receiver asks nshttpd to normalize.</p>
    </section>
    <section class="panel">
      <h2>Status</h2>
      <p><span class="ok">online</span> AAA virtual server: <code>sesame-gw.local</code></p>
    </section>
"""
        self.send_body(200, page("Open Sesame", body))

    def oidc_configuration(self):
        issuer = f"https://{self.headers.get('Host', 'sesame-gw.local')}/oauth/idp"
        document = {
            "issuer": issuer[:256],
            "authorization_endpoint": issuer[:256] + "/authorize",
            "jwks_uri": issuer[:256] + "/certs",
            "response_types_supported": ["code"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
        }
        clean = json.dumps(document, separators=(",", ":")).encode()
        host = self.headers.get("Host", "")

        if len(host) <= LEAK_THRESHOLD:
            return self.send_body(200, clean, "application/json")

        if len(host) > MAX_HOST_LINE:
            return self.send_body(431, b"Request Header Fields Too Large\n", "text/plain")

        leak_len = min(len(host) - LEAK_THRESHOLD, len(HEAP))
        body = clean + b"\n" + (b"\x00" * 16) + HEAP[:leak_len]
        return self.send_body(200, body, "application/json")

    def get_username(self):
        token, session = self.cookie_session()
        if not session:
            return self.send_body(403, b"", "text/plain")
        if session["role"] == "auditor":
            return self.send_body(200, f"{session['user']}\nlegacy-receiver=true".encode(), "text/plain")
        return self.send_body(200, session["user"].encode(), "text/plain")

    def portal(self):
        token, session = self.cookie_session()
        if not session:
            return self.send_body(401, page("Login Required", """
    <section class="panel">
      <h2 class="bad">Authentication Required</h2>
      <p>Missing or invalid <code>NSC_AAAC</code> session.</p>
    </section>
"""))

        escaped_user = html.escape(session["user"])
        escaped_role = html.escape(session["role"])
        body = f"""
    <section class="panel">
      <h2>Session</h2>
      <p>Welcome <code>{escaped_user}</code>. Authorization role: <code>{escaped_role}</code>.</p>
      <p><a href="/vpn/portal/bookmarks">Open clientless bookmarks</a></p>
    </section>
"""
        self.send_body(200, page("Open Sesame Portal", body))

    def bookmarks(self):
        token, session = self.cookie_session()
        if not session:
            return self.send_body(401, b"login required\n", "text/plain")
        rows = [
            ("Market ledger", "/cvpn/http/market.local/ledger", "available"),
            ("Receiver trace", "/cvpn/http/ops.local/receiver-trace", "archived"),
        ]
        if session["role"] == "root":
            rows.append(("Sesame vault", "/cvpn/http/sesame-admin.local/open-sesame", "restricted"))

        lines = ["<section class=\"panel\"><h2>Bookmarks</h2>"]
        for name, href, status in rows:
            lines.append(f"<p><a href=\"{href}\">{html.escape(name)}</a> <code>{html.escape(status)}</code></p>")
        lines.append("</section>")
        self.send_body(200, page("Bookmarks", "\n".join(lines)))

    def open_sesame(self, query: str):
        token, session = self.cookie_session()
        if not session:
            return self.send_body(401, b"missing NSC_AAAC\n", "text/plain")
        if session["role"] != "root":
            return self.send_body(403, b"the stone door only trusts root sessions\n", "text/plain")

        supplied = self.headers.get("X-Open-Sesame", "")
        if not supplied:
            supplied = parse_qs(query).get("phrase", [""])[0]
        if supplied != DOOR_PHRASE:
            return self.send_body(403, b"root accepted, door phrase rejected\n", "text/plain")

        body = f"flag={FLAG}\n"
        self.send_body(200, body.encode(), "text/plain")


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), OpenSesameHandler)
    print(f"Open Sesame challenge listening on 0.0.0.0:{PORT}", flush=True)
    print(f"heap={len(HEAP)} bytes leak_threshold={LEAK_THRESHOLD}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
