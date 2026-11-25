#!/usr/bin/env python3
import base64
import hashlib
import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "9000"))
FRONTEND_NAME = os.environ.get("FRONTEND_NAME", "STAR-FE-01")
BACKEND_FQDN = "STAR-MBX-01.stars.internal"
FLAG = os.environ.get("FLAG", "ITECHNO26{i_l0v3_a_milli0n_0f_th3_st4rs}")
STAR_SECRET = os.environ.get("STAR_SECRET", "local-dev-secret").encode()

ADMIN_SID = "S-1-5-21-1942260526-2720607261-2114161939-500"
RAW_IDENTITY = "STARS\\Aurora Nebula"
EXPORT_TARGET = "/powershell/galaxy?vault=andromeda"

USERS = {
    "orion@stars.local": {
        "display": "Orion Starwatch",
        "legacy": "/o=Stars/ou=Exchange Administrative Group/cn=Recipients/cn=orion",
        "sid": "S-1-5-21-1942260526-2720607261-2114161939-1107",
        "role": "Observer",
        "hint": "The director's portrait was brighter than Orion's.",
    },
    "lyra@stars.local": {
        "display": "Lyra Nightdesk",
        "legacy": "/o=Stars/ou=Exchange Administrative Group/cn=Recipients/cn=lyra",
        "sid": "S-1-5-21-1942260526-2720607261-2114161939-1110",
        "role": "Helpdesk",
        "hint": "Lyra keeps decoy constellations for noisy scans.",
    },
    "aurora@stars.local": {
        "display": "Aurora Director",
        "legacy": "/o=Stars/ou=Exchange Administrative Group/cn=Recipients/cn=aurora",
        "sid": ADMIN_SID,
        "role": "Organization Management",
        "hint": "Aurora signs the final star catalog.",
    },
}

SESSIONS = {}


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


def b64(data):
    if isinstance(data, str):
        data = data.encode()
    return base64.b64encode(data).decode()


def xml_escape(value):
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def token(label, sid):
    digest = hmac.new(STAR_SECRET, f"{label}:{sid}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")[:26]


def expected_ticket(canary):
    msg = f"{RAW_IDENTITY.lower()}:500".encode()
    return hmac.new(canary.encode(), msg, hashlib.sha256).hexdigest()[:24]


class BackendHandler(BaseHTTPRequestHandler):
    server_version = "Microsoft-HTTPAPI/2.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args))

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def do_HEAD(self):
        self.dispatch(head_only=True)

    def dispatch(self, head_only=False):
        path = urlsplit(self.path).path
        if path == "/healthz":
            self.respond(200, "ok\n", head_only=head_only)
            return

        if self.headers.get("X-From-Frontend") != FRONTEND_NAME:
            self.respond(403, "Backend accepts requests only from the Exchange frontend.\n", head_only=head_only)
            return

        if path == "/":
            self.backend_fingerprint(head_only=head_only)
            return
        if path == "/autodiscover/autodiscover.xml":
            self.autodiscover(head_only=head_only)
            return
        if path == "/EWS/Exchange.asmx":
            self.ews(head_only=head_only)
            return
        if path == "/mapi/emsmdb":
            self.mapi(head_only=head_only)
            return
        if path == "/ecp/proxyLogon.ecp":
            self.proxy_logon(head_only=head_only)
            return
        if path == "/ecp/DDI/DDIService.svc/GetObject":
            self.ddi_get_object(head_only=head_only)
            return
        if path == "/ecp/StarChart/Export.svc":
            self.star_export(head_only=head_only)
            return
        if path == "/powershell/galaxy":
            self.respond(403, "The galaxy vault requires an ECP export worker.\n", head_only=head_only)
            return

        self.respond(404, "The mailbox star route does not exist.\n", head_only=head_only)

    def read_body(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return b""
        return self.rfile.read(min(length, 1024 * 1024))

    def backend_fingerprint(self, head_only=False):
        self.respond(
            200,
            "STAR-MBX-01 ready\n",
            headers={
                "X-FEServer": "STAR-MBX-01",
                "X-CalculatedBETarget": BACKEND_FQDN,
                "X-DiagInfo": "StarsMailbox/15.2.986.5",
            },
            head_only=head_only,
        )

    def autodiscover(self, head_only=False):
        body = self.read_body().decode("utf-8", "ignore")
        if "responseschema/2006a" not in body:
            self.respond(600, autodiscover_error("InvalidRequest", "schema mismatch"), "text/xml", head_only=head_only)
            return

        match = re.search(r"<(?:[A-Za-z0-9_]+:)?EMailAddress>([^<]+)", body, re.I)
        email = match.group(1).strip().lower() if match else ""
        user = USERS.get(email)
        if not user:
            self.respond(404, autodiscover_error("MailboxNotFound", "unknown star mailbox"), "text/xml", head_only=head_only)
            return

        self.respond(200, autodiscover_ok(email, user), "text/xml; charset=utf-8", head_only=head_only)

    def ews(self, head_only=False):
        body = self.read_body().decode("utf-8", "ignore")
        match = re.search(r"<(?:[A-Za-z0-9_]+:)?Email>([^<]+)", body, re.I)
        email = match.group(1).strip().lower() if match else ""
        user = USERS.get(email)
        if not user:
            self.respond(200, soap_fault("ErrorNonExistentMailbox", "The star has no mailbox."), "text/xml", head_only=head_only)
            return

        if email == "orion@stars.local":
            ppm = """P3
# director-mailbox: aurora@stars.local
# route-after-sid: /ecp/proxyLogon.ecp
# note: ProxyLogon wants the director SID, not Orion's SID.
2 2
255
9 14 29 247 200 75 9 14 29 247 200 75
"""
        elif email == "aurora@stars.local":
            ppm = """P3
# Aurora signs StarVirtualDirectory exports.
# The final ticket is derived from the ECP canary.
1 1
255
247 200 75
"""
        else:
            ppm = """P3
# decoy-photo: no privileged stars here.
1 1
255
8 13 24
"""

        response = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <GetUserPhotoResponse xmlns="http://schemas.microsoft.com/exchange/services/2006/messages">
      <ResponseCode>NoError</ResponseCode>
      <ContentType>image/x-portable-pixmap</ContentType>
      <PictureData>{b64(ppm)}</PictureData>
    </GetUserPhotoResponse>
  </s:Body>
</s:Envelope>
"""
        self.respond(200, response, "text/xml; charset=utf-8", head_only=head_only)

    def mapi(self, head_only=False):
        text = self.read_body().decode("latin-1", "ignore")
        found = None
        for email, user in USERS.items():
            if user["legacy"] in text:
                found = (email, user)
                break
        if not found:
            self.respond(400, "EcDoConnectEx failed: missing LegacyDN in MAPI payload.\n", head_only=head_only)
            return

        email, user = found
        body = (
            "MDBSTATUS=0\n"
            f"Mailbox={email}\n"
            f"DisplayName={user['display']}\n"
            f"Role={user['role']}\n"
            f"UserSid={user['sid']}\n"
            f"MasterAccountSid={user['sid']}\n"
            "AuxiliaryBuffer=stars-mapi-rpc-http\n"
        )
        self.respond(
            200,
            body,
            "application/mapi-http",
            headers={"X-RequestType": "Connect", "X-CalculatedBETarget": BACKEND_FQDN},
            head_only=head_only,
        )

    def proxy_logon(self, head_only=False):
        body = self.read_body().decode("utf-8", "ignore")
        match = re.search(r"<s>([^<]+)</s>", body, re.I)
        sid = match.group(1).strip() if match else ""
        if sid != ADMIN_SID:
            self.respond(403, "ProxyLogon rejected: this SID does not own the director star.\n", head_only=head_only)
            return

        session = token("session", sid)
        canary = token("canary", sid)
        SESSIONS[session] = {"sid": sid, "canary": canary, "user": "aurora@stars.local"}

        response = b"ProxyLogon complete. Follow the ECP canary.\n"
        self.send_response(241, "ProxyLogon Complete")
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(response)))
        self.send_header("X-CalculatedBETarget", BACKEND_FQDN)
        self.send_header("Set-Cookie", f"ASP.NET_SessionId={session}; path=/ecp; HttpOnly; SameSite=Lax")
        self.send_header("Set-Cookie", f"msExchEcpCanary={canary}; path=/ecp; HttpOnly; SameSite=Lax")
        self.end_headers()
        if not head_only and self.command != "HEAD":
            self.wfile.write(response)

    def require_ecp(self):
        cookies = parse_cookies(self.headers.get("Cookie"))
        session_id = cookies.get("ASP.NET_SessionId", "")
        cookie_canary = cookies.get("msExchEcpCanary", "")
        session = SESSIONS.get(session_id)
        if not session:
            return None, "missing or expired ECP session"

        query = parse_qs(urlsplit(self.path).query)
        supplied_canary = (
            query.get("msExchEcpCanary", [""])[0]
            or self.headers.get("msExchEcpCanary", "")
            or self.headers.get("X-OWA-CANARY", "")
            or cookie_canary
        )
        if supplied_canary != session["canary"]:
            return None, "bad ECP canary"
        return session, ""

    def ddi_get_object(self, head_only=False):
        session, error = self.require_ecp()
        if not session:
            self.respond(440, f"ECP authentication failed: {error}\n", head_only=head_only)
            return

        query = parse_qs(urlsplit(self.path).query)
        schema = query.get("schema", [""])[0]
        if not schema and self.command == "POST":
            try:
                payload = json.loads(self.read_body().decode("utf-8", "ignore") or "{}")
            except json.JSONDecodeError:
                payload = {}
            schema = payload.get("schema", "")

        if schema != "StarVirtualDirectory":
            body = {
                "d": {
                    "AvailableSchemas": [
                        "Mailbox",
                        "OABVirtualDirectory",
                        "StarVirtualDirectory",
                        "TransportRule",
                    ],
                    "Hint": "Only one schema knows where the Aurora catalog is exported.",
                }
            }
            self.respond_json(200, body, head_only=head_only)
            return

        body = {
            "d": {
                "Output": [
                    {
                        "Identity": {"RawIdentity": RAW_IDENTITY},
                        "Properties": {
                            "Name": "Aurora Nebula",
                            "Server": BACKEND_FQDN,
                            "ExternalUrl": "https://stars.invalid/owa/aurora",
                            "ExportTarget": EXPORT_TARGET,
                            "SidRid": "500",
                            "TicketHint": "hex(hmac_sha256(canary, lower(RawIdentity) + ':500'))[0:24]",
                        },
                    }
                ],
                "CanaryBinding": "msExchEcpCanary",
                "Next": "/ecp/StarChart/Export.svc",
            }
        }
        self.respond_json(200, body, head_only=head_only)

    def star_export(self, head_only=False):
        session, error = self.require_ecp()
        if not session:
            self.respond(440, f"ECP authentication failed: {error}\n", head_only=head_only)
            return

        try:
            payload = json.loads(self.read_body().decode("utf-8", "ignore") or "{}")
        except json.JSONDecodeError:
            payload = {}

        query = parse_qs(urlsplit(self.path).query)
        target = payload.get("target") or query.get("target", [""])[0]
        supplied_ticket = self.headers.get("X-Star-Ticket", "")
        correct_ticket = expected_ticket(session["canary"])

        if target != EXPORT_TARGET:
            self.respond(400, "Export worker can only open the Andromeda galaxy vault.\n", head_only=head_only)
            return
        if not hmac.compare_digest(supplied_ticket, correct_ticket):
            self.respond(403, "Bad star ticket.\n", head_only=head_only)
            return

        body = {
            "catalog": "Aurora Nebula",
            "status": "exported",
            "flag": FLAG,
        }
        self.respond_json(200, body, head_only=head_only)

    def respond_json(self, status, obj, headers=None, head_only=False):
        body = json.dumps(obj, separators=(",", ":")).encode()
        self.respond(status, body, "application/json", headers=headers, head_only=head_only)

    def respond(self, status, body, content_type="text/plain", headers=None, head_only=False):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-CalculatedBETarget", BACKEND_FQDN)
        self.send_header("X-FEServer", "STAR-MBX-01")
        self.send_header("X-OWA-Version", "15.2.986.5")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if not head_only and self.command != "HEAD":
            self.wfile.write(body)


def autodiscover_ok(email, user):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/responseschema/2006">
  <Response xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a">
    <User>
      <DisplayName>{xml_escape(user['display'])}</DisplayName>
      <LegacyDN>{xml_escape(user['legacy'])}</LegacyDN>
      <AutoDiscoverSMTPAddress>{xml_escape(email)}</AutoDiscoverSMTPAddress>
    </User>
    <Account>
      <AccountType>email</AccountType>
      <Action>settings</Action>
      <MicrosoftOnline>False</MicrosoftOnline>
      <PublicFolderServer>PF-STARS-01; {xml_escape(user['hint'])}</PublicFolderServer>
      <Server>{BACKEND_FQDN}</Server>
      <AD>STAR-AD-01.stars.internal</AD>
      <ServerExclusiveConnect>off</ServerExclusiveConnect>
      <AuthPackage>Ntlm</AuthPackage>
      <CertPrincipalName>msstd:stars.invalid</CertPrincipalName>
      <OWAUrl AuthenticationMethod="Fba">https://mail.stars.invalid/owa/</OWAUrl>
      <OOFUrl>https://{BACKEND_FQDN}/EWS/Exchange.asmx</OOFUrl>
    </Account>
  </Response>
</Autodiscover>
"""


def autodiscover_error(code, message):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<Autodiscover>
  <Response>
    <Error Time="00:00:00" Id="0">
      <ErrorCode>{xml_escape(code)}</ErrorCode>
      <Message>{xml_escape(message)}</Message>
    </Error>
  </Response>
</Autodiscover>
"""


def soap_fault(code, message):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">
  <s:Body>
    <s:Fault>
      <faultcode>{xml_escape(code)}</faultcode>
      <faultstring>{xml_escape(message)}</faultstring>
    </s:Fault>
  </s:Body>
</s:Envelope>
"""


def main():
    server = ThreadingHTTPServer(("0.0.0.0", BACKEND_PORT), BackendHandler)
    print(f"Stars backend listening on 0.0.0.0:{BACKEND_PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
