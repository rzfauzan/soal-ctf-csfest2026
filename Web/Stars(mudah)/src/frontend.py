#!/usr/bin/env python3
import http.client
import mimetypes
import os
import posixpath
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "static"

FRONTEND_NAME = "STAR-FE-01"
BACKEND_FQDN = "STAR-MBX-01.stars.internal"
BACKEND_HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "9000"))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", "8000"))

BACKEND_ALIASES = {
    "localhost",
    "127.0.0.1",
    "exchange",
    "star-mbx-01",
    "star-mbx-01.stars.internal",
    "star-mbx-01.internal",
}

ALLOWED_PROXY_VERSIONS = {"1", "3", "1942062522"}
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stars Mail</title>
  <link rel="stylesheet" href="/static/main.css">
  <script defer src="/static/sky.js"></script>
</head>
<body>
  <main class="shell">
    <section class="panel hero">
      <div class="brand">
        <span class="mark"></span>
        <span>Stars Mail</span>
      </div>
      <h1>Stars</h1>
      <p class="lead">Private observatory mail for the night crew.</p>
      <a class="button" href="/owa/auth/logon.aspx">Open OWA</a>
    </section>
    <section class="panel status">
      <h2>Relay Status</h2>
      <dl>
        <div><dt>Frontend</dt><dd>STAR-FE-01</dd></div>
        <div><dt>Mailbox</dt><dd>STAR-MBX-01</dd></div>
        <div><dt>Build</dt><dd>15.2.986.5</dd></div>
        <div><dt>Observer Desk</dt><dd data-role="observer">orion at stars dot local</dd></div>
      </dl>
    </section>
  </main>
</body>
</html>
"""


LOGON_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stars OWA</title>
  <link rel="stylesheet" href="/owa/auth/Current/themes/resources/logon.css">
</head>
<body>
  <form class="login" method="post" action="/owa/auth.owa">
    <div class="brand"><span class="mark"></span><span>Stars OWA</span></div>
    <label>Mailbox <input name="username" autocomplete="off"></label>
    <label>Password <input name="password" type="password"></label>
    <button type="submit">Sign in</button>
    <p>Public sign-in is disabled during meteor season.</p>
  </form>
</body>
</html>
"""


LOGON_CSS = """
html, body { min-height: 100%; margin: 0; }
body {
  display: grid;
  place-items: center;
  font-family: Arial, sans-serif;
  color: #eef4ff;
  background:
    radial-gradient(circle at 18% 22%, rgba(255,255,255,.9) 0 1px, transparent 2px),
    radial-gradient(circle at 74% 31%, rgba(255,255,255,.8) 0 1px, transparent 2px),
    radial-gradient(circle at 51% 67%, rgba(255,255,255,.7) 0 1px, transparent 2px),
    linear-gradient(135deg, #071017, #151b2d 56%, #101418);
}
.login {
  width: min(360px, calc(100vw - 32px));
  padding: 28px;
  border: 1px solid rgba(255,255,255,.18);
  border-radius: 8px;
  background: rgba(10, 15, 25, .86);
  box-shadow: 0 24px 80px rgba(0,0,0,.38);
}
.brand { display: flex; gap: 10px; align-items: center; margin-bottom: 22px; font-weight: 700; }
.mark { width: 16px; height: 16px; background: #f7c84b; clip-path: polygon(50% 0,61% 36%,100% 50%,61% 64%,50% 100%,39% 64%,0 50%,39% 36%); }
label { display: grid; gap: 8px; margin: 14px 0; font-size: 13px; color: #c9d5e8; }
input {
  min-height: 38px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,.16);
  background: #101a2a;
  color: #fff;
  padding: 0 10px;
}
button {
  width: 100%;
  min-height: 40px;
  margin-top: 10px;
  border: 0;
  border-radius: 6px;
  background: #f7c84b;
  color: #17202d;
  font-weight: 700;
}
p { margin: 16px 0 0; color: #9caac0; font-size: 13px; }
"""


def parse_cookies(header):
    cookies = {}
    if not header:
        return cookies
    for part in header.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies[name.strip()] = value.strip().strip('"')
    return cookies


def parse_beresource(raw):
    if not raw or any(ord(ch) < 32 for ch in raw):
        raise ValueError("empty or invalid backend cookie")

    raw = unquote(raw.strip().strip('"'))
    version_match = re.search(r"~([0-9]+)$", raw)
    if not version_match:
        raise ValueError("missing Exchange routing version")

    version = version_match.group(1)
    if version not in ALLOWED_PROXY_VERSIONS:
        raise ValueError("unsupported Exchange routing version")

    prefix = raw[: version_match.start()]
    prefix = prefix.split("#", 1)[0].strip()

    if "/" in prefix:
        target, route = prefix.split("/", 1)
        backend_path = "/" + route
    else:
        target, backend_path = prefix, "/"

    if ":" in target:
        host, port = target.rsplit(":", 1)
        if port not in {"80", "443", "444"}:
            raise ValueError("backend port is not routed by this frontend")
        target = host

    target = target.strip().lower().rstrip(".")
    if target not in BACKEND_ALIASES:
        raise ValueError("backend target is not in the accepted Exchange site")

    for suffix in ("?a=", "&a=", "?"):
        if backend_path.endswith(suffix):
            backend_path = backend_path[: -len(suffix)]

    if not backend_path.startswith("/") or "\\" in backend_path:
        raise ValueError("invalid backend path")

    return target, backend_path, version


def ssrf_surface(path):
    route = urlsplit(path).path
    if route == "/owa/auth/Current/themes/resources/logon.css":
        return True
    if route == "/owa/auth/favicon.ico":
        return True
    if route == "/ecp/favicon.ico":
        return True
    if route.startswith("/ecp/") and re.fullmatch(r"/ecp/[A-Za-z0-9_.-]{2,24}", route):
        return True
    return False


def authenticated_backend_surface(path):
    route = urlsplit(path).path
    return route.startswith("/ecp/DDI/DDIService.svc/") or route.startswith("/ecp/StarChart/")


class FrontendHandler(BaseHTTPRequestHandler):
    server_version = "Microsoft-IIS/10.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def do_GET(self):
        self.handle_method()

    def do_POST(self):
        self.handle_method()

    def do_HEAD(self):
        self.handle_method(head_only=True)

    def handle_method(self, head_only=False):
        cookies = parse_cookies(self.headers.get("Cookie"))
        route_cookie = cookies.get("X-BEResource") or cookies.get("X-AnonResource-Backend")

        if route_cookie and ssrf_surface(self.path):
            self.handle_ssrf(route_cookie, head_only=head_only)
            return

        if authenticated_backend_surface(self.path):
            self.proxy_to_backend(self.command, self.path, target_hint=BACKEND_FQDN, head_only=head_only)
            return

        self.handle_public(head_only=head_only)

    def read_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(min(length, 1024 * 1024))

    def handle_ssrf(self, route_cookie, head_only=False):
        try:
            target, backend_path, version = parse_beresource(route_cookie)
        except ValueError as exc:
            self.respond(441, f"Routing Error: {exc}\n", content_type="text/plain")
            return

        self.proxy_to_backend(
            self.command,
            backend_path,
            target_hint=target,
            routing_version=version,
            head_only=head_only,
        )

    def proxy_to_backend(self, method, backend_path, target_hint, routing_version="direct", head_only=False):
        body = b"" if method in {"GET", "HEAD"} else self.read_body()
        headers = {
            "Host": BACKEND_FQDN,
            "X-From-Frontend": FRONTEND_NAME,
            "X-Frontend-Site": "Stars",
            "X-Backend-Target": target_hint,
            "X-Exchange-Routing-Version": routing_version,
            "X-Original-URL": self.path,
            "User-Agent": self.headers.get("User-Agent", "StarsFrontEnd/15.2"),
        }

        for name in (
            "Content-Type",
            "Cookie",
            "SOAPAction",
            "X-Star-Ticket",
            "X-OWA-CANARY",
            "msExchEcpCanary",
        ):
            value = self.headers.get(name)
            if value:
                headers[name] = value

        if body:
            headers["Content-Length"] = str(len(body))

        try:
            conn = http.client.HTTPConnection(BACKEND_HOST, BACKEND_PORT, timeout=5)
            conn.request(method, backend_path, body=body, headers=headers)
            resp = conn.getresponse()
            data = resp.read()
        except OSError:
            self.respond(503, "Mailbox backend unavailable\n", content_type="text/plain")
            return
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self.send_response(resp.status, resp.reason)
        self.send_header("X-FEServer", FRONTEND_NAME)
        for name, value in resp.getheaders():
            if name.lower() in HOP_BY_HOP:
                continue
            self.send_header(name, value)
        self.end_headers()
        if not head_only and method != "HEAD":
            self.wfile.write(data)

    def handle_public(self, head_only=False):
        path = urlsplit(self.path).path
        if path == "/":
            self.respond(200, INDEX_HTML, "text/html; charset=utf-8", head_only=head_only)
            return
        if path == "/owa/auth/logon.aspx":
            self.respond(200, LOGON_HTML, "text/html; charset=utf-8", head_only=head_only)
            return
        if path == "/owa/auth/Current/themes/resources/logon.css":
            self.respond(200, LOGON_CSS, "text/css; charset=utf-8", head_only=head_only)
            return
        if path == "/ecp/favicon.ico":
            self.respond(200, b"STARICO", "image/x-icon", head_only=head_only)
            return
        if path.startswith("/static/"):
            self.serve_static(path, head_only=head_only)
            return
        if path == "/owa/auth.owa":
            self.respond(403, "The stars are not aligned for password login.\n", "text/plain", head_only=head_only)
            return
        self.respond(404, "Not found\n", "text/plain", head_only=head_only)

    def serve_static(self, path, head_only=False):
        normalized = posixpath.normpath(unquote(path)).lstrip("/")
        full_path = (ROOT / normalized).resolve()
        if not str(full_path).startswith(str(STATIC_ROOT.resolve())) or not full_path.is_file():
            self.respond(404, "Not found\n", "text/plain", head_only=head_only)
            return
        content_type = mimetypes.guess_type(str(full_path))[0] or "application/octet-stream"
        data = full_path.read_bytes()
        self.respond(200, data, content_type, head_only=head_only)

    def respond(self, status, body, content_type="text/plain", head_only=False):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-FEServer", FRONTEND_NAME)
        self.send_header("X-OWA-Version", "15.2.986.5")
        self.end_headers()
        if not head_only and self.command != "HEAD":
            self.wfile.write(body)


def main():
    server = ThreadingHTTPServer(("0.0.0.0", FRONTEND_PORT), FrontendHandler)
    print(f"Stars frontend listening on 0.0.0.0:{FRONTEND_PORT}, backend={BACKEND_HOST}:{BACKEND_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
