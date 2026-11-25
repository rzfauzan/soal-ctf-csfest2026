import base64
import binascii
import hashlib
import html
import os
import re
import secrets
import time
from pathlib import Path

from flask import Flask, Response, jsonify, make_response, redirect, render_template, request, url_for


FLAG = os.environ.get(
    "FLAG",
    "C5FEST26{woooowwww_th3_st0r3_1s_gr34t!_h0w_tF_u_H4ck_tHe_sYstEm_br0?!}",
)
SESSION_DIR = Path(os.environ.get("SESSION_DIR", "/tmp/itechno-store-sessions"))
COOKIE_NAME = "whostmgrsession"
CPANEL_VERSION = "11.114.0-itechno.2605"
STORE_BATCH = "JKT-2605-R4C3"
STORE_REQUIRED = {
    "store.acl": "ledger:read,settlement:write",
    "store.market": "ID-JKT",
    "store.mfa": "device-bound",
}

SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{24,80}$")
SESSION_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
TOKEN_RE = re.compile(r"^\d{10}$")

PRODUCTS = [
    {
        "slug": "nano-router",
        "name": "Nano Router C7",
        "category": "Network",
        "price": "Rp 1.290.000",
        "accent": "#0f766e",
        "summary": "Router lab kecil dengan serial console dan profile VLAN siap pakai.",
    },
    {
        "slug": "rfid-starter",
        "name": "RFID Starter Shelf",
        "category": "Access",
        "price": "Rp 840.000",
        "accent": "#b45309",
        "summary": "Bundle reader, kartu test, dan panel inventori untuk demo gudang.",
    },
    {
        "slug": "edge-camera",
        "name": "Edge Camera Kit",
        "category": "Vision",
        "price": "Rp 2.450.000",
        "accent": "#2563eb",
        "summary": "Kamera edge compact untuk quality check dan monitoring rak toko.",
    },
    {
        "slug": "stock-terminal",
        "name": "Stock Terminal X2",
        "category": "POS",
        "price": "Rp 3.100.000",
        "accent": "#7c3aed",
        "summary": "Terminal kasir dan stok dengan mode offline untuk event besar.",
    },
]

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("APP_SECRET", secrets.token_hex(32))
SESSION_DIR.mkdir(parents=True, exist_ok=True)


def clean_value(value: str, limit: int = 160) -> str:
    return value.replace("\r", " ").replace("\n", " ").strip()[:limit]


def session_path(session_id: str) -> Path:
    if not SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("invalid session id")
    return SESSION_DIR / f"{session_id}.session"


def parse_cookie_session_id() -> str | None:
    raw = request.cookies.get(COOKIE_NAME) or request.cookies.get("cpsession")
    if not raw:
        return None
    session_id = raw.split("%2c", 1)[0].split(",", 1)[0]
    if not SESSION_ID_RE.fullmatch(session_id):
        return None
    return session_id


def write_session(session_id: str, values: dict[str, str]) -> None:
    lines = [f"{key}={value}" for key, value in values.items()]
    session_path(session_id).write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_session_record(session_id: str, record: str) -> None:
    with session_path(session_id).open("a", encoding="utf-8") as handle:
        handle.write(record)


def read_session(session_id: str) -> dict[str, str]:
    path = session_path(session_id)
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.rstrip("\r")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if SESSION_KEY_RE.fullmatch(key):
            values[key] = value.strip()
    return values


def create_preauth_session(username: str) -> tuple[str, str]:
    session_id = secrets.token_urlsafe(28)
    nonce = secrets.token_urlsafe(10)
    write_session(
        session_id,
        {
            "created_at": str(int(time.time())),
            "session_kind": "preauth",
            "user": "nobody",
            "hasroot": "0",
            "tfa_verified": "0",
            "cp_security_token": "/cpsess0000000000",
            "failed_login_user": clean_value(username, 48),
            "theme": "jupiter-store",
            "session_canary": hashlib.sha1(f"{session_id}:itechno".encode()).hexdigest(),
        },
    )
    return session_id, f"{session_id}%2c{nonce}"


def deny_with_legacy_basic_auth() -> Response:
    auth_header = request.headers.get("Authorization", "")
    session_id = parse_cookie_session_id()
    decoded = ""

    if auth_header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth_header.split(None, 1)[1], validate=True).decode(
                "utf-8", "replace"
            )
        except (binascii.Error, UnicodeDecodeError):
            decoded = ""

    if ":" in decoded:
        username, secret_material = decoded.split(":", 1)
    else:
        username, secret_material = decoded[:64], ""

    if session_id:
        append_session_record(
            session_id,
            "\n".join(
                [
                    f"last_auth_failure={int(time.time())}",
                    f"failed_auth_user={clean_value(username, 64)}",
                    f"failed_auth_material={secret_material}",
                    "auth_module=StoreBasicBridge",
                    "denied_path=/",
                    "",
                ]
            ),
        )

    body = """<!doctype html>
<title>401 Access Denied</title>
<h1>401 Access Denied</h1>
<p>do_token_denied: invalid security token for cpsrvd compatibility bridge.</p>
"""
    response = make_response(body, 401)
    response.headers["WWW-Authenticate"] = 'Basic realm="Itechno Store WHM"'
    response.headers["X-cPanel-Error"] = "do_token_denied"
    return response


def root_context(token: str, require_store: bool = False):
    if not TOKEN_RE.fullmatch(token):
        return None, json_error("invalid cpsess token", 404)

    session_id = parse_cookie_session_id()
    if not session_id:
        return None, redirect(url_for("legacy_login"))

    data = read_session(session_id)
    token_path = f"/cpsess{token}"
    fresh = False
    try:
        fresh = abs(int(time.time()) - int(data.get("successful_internal_auth_with_timestamp", "0"))) <= 240
    except ValueError:
        fresh = False

    checks = {
        "user": data.get("user") == "root",
        "hasroot": data.get("hasroot") == "1",
        "tfa_verified": data.get("tfa_verified") == "1",
        "cp_security_token": data.get("cp_security_token") == token_path,
        "successful_internal_auth_with_timestamp": fresh,
    }
    missing = [name for name, ok in checks.items() if not ok]
    if missing:
        return None, json_error(
            "not authenticated to WHM",
            403,
            details={"missing": missing, "handler": "whostmgrd::authz"},
        )

    if require_store:
        store_missing = [
            f"{key}={value}" for key, value in STORE_REQUIRED.items() if data.get(key) != value
        ]
        if store_missing:
            return None, json_error(
                "root session lacks Itechno Store settlement badges",
                403,
                details={"missing_badges": store_missing},
            )

    return {"session_id": session_id, "data": data, "token_path": token_path}, None


def ledger_nonce(session_id: str, batch: str) -> str:
    return hashlib.sha256(f"{session_id}:{batch}:settlement".encode()).hexdigest()[:20]


def json_error(message: str, status: int = 400, details: dict | None = None) -> Response:
    payload = {"metadata": {"result": 0, "reason": message}, "error": message}
    if details:
        payload["details"] = details
    return jsonify(payload), status


@app.after_request
def panel_headers(response: Response) -> Response:
    response.headers.setdefault("X-Itechno-Node", "storefront-jkt-02")
    response.headers.setdefault("X-Panel-Compatibility", f"cpsrvd/{CPANEL_VERSION}")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response


@app.route("/")
def index():
    if request.headers.get("Authorization"):
        return deny_with_legacy_basic_auth()
    return render_template("index.html", products=PRODUCTS)


@app.route("/product/<slug>")
def product(slug: str):
    selected = next((product for product in PRODUCTS if product["slug"] == slug), None)
    if not selected:
        return render_template("not_found.html"), 404
    return render_template("product.html", product=selected, products=PRODUCTS)


@app.route("/login", methods=["GET", "POST"])
def customer_login():
    if request.method == "POST":
        response = make_response(render_template("login.html", failed=True))
        response.set_cookie("store_session", secrets.token_urlsafe(24), httponly=True, samesite="Lax")
        return response, 403
    return render_template("login.html", failed=False)


@app.route("/admin")
def fake_admin():
    return render_template("admin.html"), 403


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").lower()
    results = [
        product
        for product in PRODUCTS
        if query in product["name"].lower() or query in product["category"].lower()
    ][:5]
    return jsonify({"ok": True, "query": query, "results": results})


@app.route("/robots.txt")
def robots():
    return Response(
        "\n".join(
            [
                "User-agent: *",
                "Disallow: /cpsess*/",
                "Disallow: /json-api/",
                "Disallow: /whm/",
                "Disallow: /admin",
                "",
            ]
        ),
        mimetype="text/plain",
    )


@app.route("/.well-known/cpanel-dcv")
def cpanel_dcv():
    return Response(
        "\n".join(
            [
                "server=cpsrvd",
                f"version={CPANEL_VERSION}",
                "compat_login=/login/?login_only=1",
                "default_token=/cpsess0000000000",
                "",
            ]
        ),
        mimetype="text/plain",
    )


@app.route("/login/", methods=["GET", "POST"])
def legacy_login():
    if request.method == "POST" and request.args.get("login_only") == "1":
        session_id, cookie_value = create_preauth_session(request.form.get("user", ""))
        response = jsonify(
            {
                "status": 0,
                "message": "The login is invalid.",
                "security_token": "/cpsess0000000000",
                "session": session_id[:8],
            }
        )
        response.set_cookie(COOKIE_NAME, cookie_value, httponly=True, samesite="Lax")
        response.headers["X-cPanel-Login"] = "1"
        return response

    return Response(
        "<h1>Itechno Store Legacy Login</h1><p>Use the storefront identity provider.</p>",
        status=401,
        headers={"WWW-Authenticate": 'Basic realm="Itechno Store WHM"'},
    )


@app.route("/cpsess<token>/scripts2/listaccts")
def list_accounts(token: str):
    ctx, failure = root_context(token)
    if failure:
        return failure

    rows = [
        ("itechno-store.id", "root", "storefront", "ACTIVE"),
        ("ledger.itechno-store.id", "root", "settlement-ledger", "LOCKED"),
        ("cdn.itechno-store.id", "nobody", "static-assets", "ACTIVE"),
    ]
    return render_template("listaccts.html", rows=rows, ctx=ctx)


@app.route("/cpsess<token>/json-api/version")
def api_version(token: str):
    ctx, failure = root_context(token)
    if failure:
        return failure
    return jsonify(
        {
            "metadata": {"result": 1, "command": "version"},
            "data": {"version": CPANEL_VERSION, "build": "store-compat-2605"},
        }
    )


@app.route("/cpsess<token>/json-api/applist")
def api_applist(token: str):
    ctx, failure = root_context(token)
    if failure:
        return failure
    return jsonify(
        {
            "metadata": {"result": 1, "command": "applist"},
            "data": {
                "apis": [
                    "version",
                    "applist",
                    "storefront_config",
                    "store_export_ledger",
                ],
                "note": "Store settlement APIs require root plus session-bound store badges.",
            },
        }
    )


@app.route("/cpsess<token>/json-api/storefront_config")
def api_storefront_config(token: str):
    ctx, failure = root_context(token)
    if failure:
        return failure
    session_id = ctx["session_id"]
    return jsonify(
        {
            "metadata": {"result": 1, "command": "storefront_config"},
            "data": {
                "store": "Itechno Store",
                "region": "ID-JKT",
                "active_batch": STORE_BATCH,
                "nonce_mode": "sha256(<session-id>:<active_batch>:settlement)[:20]",
                "required_session_badges": STORE_REQUIRED,
                "session_hint": f"{session_id[:6]}...{session_id[-4:]}",
            },
        }
    )


@app.route("/cpsess<token>/json-api/store_export_ledger")
def api_store_export_ledger(token: str):
    ctx, failure = root_context(token, require_store=True)
    if failure:
        return failure

    batch = request.args.get("batch", "")
    nonce = request.args.get("nonce", "")
    expected_nonce = ledger_nonce(ctx["session_id"], batch)
    if batch != STORE_BATCH or nonce != expected_nonce:
        return json_error(
            "ledger selector rejected",
            409,
            details={
                "batch": "invalid" if batch != STORE_BATCH else "ok",
                "nonce": "invalid" if nonce != expected_nonce else "ok",
            },
        )

    return jsonify(
        {
            "metadata": {"result": 1, "command": "store_export_ledger"},
            "data": {
                "store": "Itechno Store",
                "batch": STORE_BATCH,
                "exported_by": html.escape(ctx["data"].get("user", "unknown")),
                "flag": FLAG,
            },
        }
    )


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/json-api/"):
        return json_error("api endpoint moved behind cpsess token", 404)
    return render_template("not_found.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
