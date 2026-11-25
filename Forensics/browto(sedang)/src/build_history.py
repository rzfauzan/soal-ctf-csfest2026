#!/usr/bin/env python3
import base64
import hashlib
import os
import sqlite3
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "History"
PAYLOAD_B64 = ROOT / "src" / "payload_image.b64"
PAYLOAD_STORAGE_KEY = 31337

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

CHROME_EPOCH = datetime(1601, 1, 1, tzinfo=timezone.utc)


def chrome_time(dt: datetime) -> int:
    return int((dt - CHROME_EPOCH).total_seconds() * 1_000_000)


def force_low_byte(value: int, byte: int) -> int:
    return value + ((byte - value) % 256)


def xnor(data: bytes, key: bytes) -> bytes:
    return bytes((~(byte ^ key[index % len(key)])) & 0xFF for index, byte in enumerate(data))


def chunk(text: str, size: int) -> list[str]:
    return [text[index : index + size] for index in range(0, len(text), size)]


def load_payload_b64() -> tuple[str, bytes]:
    if not PAYLOAD_B64.exists():
        raise FileNotFoundError(f"missing payload file: {PAYLOAD_B64.relative_to(ROOT)}")

    payload_b64 = "".join(PAYLOAD_B64.read_text().split())
    payload = base64.b64decode(payload_b64, validate=True)
    if not payload.startswith(PNG_MAGIC):
        raise ValueError("payload_image.b64 does not decode to a PNG")
    return payload_b64, payload


def scalar(db: sqlite3.Connection, query: str, params: tuple = ()) -> str:
    return str(db.execute(query, params).fetchone()[0])


def derive_key1(db: sqlite3.Connection) -> bytes:
    return db.execute("SELECT hash FROM downloads WHERE id = 1").fetchone()[0]


def derive_key2(db: sqlite3.Connection, stage1_row_count: int) -> bytes:
    material = "|".join(
        [
            scalar(db, "SELECT value FROM meta WHERE key = 'date_created'"),
            scalar(db, "SELECT start_time FROM downloads WHERE id = 1"),
            str(stage1_row_count),
        ]
    ).encode()
    return hashlib.sha256(material).digest()


def derive_key3(db: sqlite3.Connection) -> bytes:
    guid, etag = db.execute("SELECT guid, etag FROM downloads WHERE id = 1").fetchone()
    chain_tail = scalar(
        db,
        """
        SELECT url
        FROM downloads_url_chains
        WHERE id = 1
        ORDER BY chain_index DESC
        LIMIT 1
        """,
    )
    return hashlib.sha256(f"{guid}|{etag}|{chain_tail}".encode()).digest()


def create_schema(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        PRAGMA page_size = 4096;
        PRAGMA journal_mode = OFF;
        PRAGMA user_version = 82;

        CREATE TABLE meta(
          key LONGVARCHAR NOT NULL UNIQUE PRIMARY KEY,
          value LONGVARCHAR
        );

        CREATE TABLE urls(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          url LONGVARCHAR,
          title LONGVARCHAR,
          visit_count INTEGER DEFAULT 0 NOT NULL,
          typed_count INTEGER DEFAULT 0 NOT NULL,
          last_visit_time INTEGER NOT NULL,
          hidden INTEGER DEFAULT 0 NOT NULL
        );
        CREATE INDEX urls_url_index ON urls(url);

        CREATE TABLE visits(
          id INTEGER PRIMARY KEY,
          url INTEGER NOT NULL,
          visit_time INTEGER NOT NULL,
          from_visit INTEGER,
          transition INTEGER DEFAULT 0 NOT NULL,
          segment_id INTEGER,
          visit_duration INTEGER DEFAULT 0 NOT NULL,
          incremented_omnibox_typed_score BOOLEAN DEFAULT FALSE NOT NULL,
          opener_visit INTEGER,
          originator_cache_guid TEXT,
          originator_visit_id INTEGER,
          originator_from_visit INTEGER,
          originator_opener_visit INTEGER,
          is_known_to_sync BOOLEAN DEFAULT FALSE NOT NULL,
          consider_for_ntp_most_visited BOOLEAN DEFAULT FALSE NOT NULL,
          external_referrer_url TEXT,
          visited_link_id INTEGER,
          app_id TEXT
        );
        CREATE INDEX visits_url_index ON visits(url);
        CREATE INDEX visits_time_index ON visits(visit_time);

        CREATE TABLE visit_source(
          id INTEGER PRIMARY KEY,
          source INTEGER NOT NULL
        );

        CREATE TABLE keyword_search_terms(
          keyword_id INTEGER NOT NULL,
          url_id INTEGER NOT NULL,
          term LONGVARCHAR NOT NULL,
          normalized_term LONGVARCHAR NOT NULL
        );
        CREATE INDEX keyword_search_terms_index1 ON keyword_search_terms(keyword_id, normalized_term);
        CREATE INDEX keyword_search_terms_index2 ON keyword_search_terms(url_id);

        CREATE TABLE downloads(
          id INTEGER PRIMARY KEY,
          guid VARCHAR NOT NULL,
          current_path LONGVARCHAR NOT NULL,
          target_path LONGVARCHAR NOT NULL,
          start_time INTEGER NOT NULL,
          received_bytes INTEGER NOT NULL,
          total_bytes INTEGER NOT NULL,
          state INTEGER NOT NULL,
          danger_type INTEGER NOT NULL,
          interrupt_reason INTEGER NOT NULL,
          hash BLOB NOT NULL,
          end_time INTEGER NOT NULL,
          opened INTEGER NOT NULL,
          last_access_time INTEGER NOT NULL,
          transient INTEGER NOT NULL,
          referrer VARCHAR NOT NULL,
          site_url VARCHAR NOT NULL,
          tab_url VARCHAR NOT NULL,
          tab_referrer_url VARCHAR NOT NULL,
          http_method VARCHAR NOT NULL,
          by_ext_id VARCHAR NOT NULL,
          by_ext_name VARCHAR NOT NULL,
          etag VARCHAR NOT NULL,
          last_modified VARCHAR NOT NULL,
          mime_type VARCHAR NOT NULL,
          original_mime_type VARCHAR NOT NULL
        );

        CREATE TABLE downloads_url_chains(
          id INTEGER NOT NULL,
          chain_index INTEGER NOT NULL,
          url LONGVARCHAR NOT NULL,
          PRIMARY KEY(id, chain_index)
        );

        CREATE TABLE typed_url_sync_metadata(
          storage_key INTEGER PRIMARY KEY NOT NULL,
          value BLOB
        );
        """
    )

    db.executemany(
        "INSERT INTO meta(key, value) VALUES(?, ?)",
        [
            ("version", "82"),
            ("last_compatible_version", "82"),
            ("date_created", "13389331200000000"),
        ],
    )


def add_url(
    db: sqlite3.Connection,
    url: str,
    title: str,
    visit_time: int,
    *,
    hidden: int = 0,
    typed: bool = False,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO urls(url, title, visit_count, typed_count, last_visit_time, hidden)
        VALUES(?, ?, 0, ?, ?, ?)
        """,
        (url, title, 1 if typed else 0, visit_time, hidden),
    )
    return int(cursor.lastrowid)


def add_visit(
    db: sqlite3.Connection,
    url_id: int,
    visit_time: int,
    *,
    transition: int = 0,
    from_visit: int | None = None,
    duration: int = 0,
) -> int:
    cursor = db.execute(
        """
        INSERT INTO visits(
          url, visit_time, from_visit, transition, segment_id, visit_duration,
          incremented_omnibox_typed_score, opener_visit, originator_cache_guid,
          originator_visit_id, originator_from_visit, originator_opener_visit,
          is_known_to_sync, consider_for_ntp_most_visited, external_referrer_url,
          visited_link_id, app_id
        )
        VALUES(?, ?, ?, ?, 0, ?, 0, 0, '', 0, 0, 0, 0, 1, '', 0, '')
        """,
        (url_id, visit_time, from_visit, transition, duration),
    )
    visit_id = int(cursor.lastrowid)
    db.execute(
        """
        UPDATE urls
        SET visit_count = visit_count + 1,
            last_visit_time = CASE WHEN last_visit_time > ? THEN last_visit_time ELSE ? END
        WHERE id = ?
        """,
        (visit_time, visit_time, url_id),
    )
    db.execute("INSERT INTO visit_source(id, source) VALUES(?, 0)", (visit_id,))
    return visit_id


def add_search(db: sqlite3.Connection, term: str, when: datetime, *, index: int) -> int:
    encoded = term.replace(" ", "+")
    ts = chrome_time(when)
    url_id = add_url(
        db,
        f"https://www.google.com/search?q={encoded}&oq={encoded}&sourceid=chrome&ie=UTF-8",
        f"Search: {term}",
        ts,
        typed=True,
    )
    add_visit(db, url_id, ts, transition=805306368)
    db.execute(
        """
        INSERT INTO keyword_search_terms(keyword_id, url_id, term, normalized_term)
        VALUES(?, ?, ?, ?)
        """,
        (1, url_id, term, term.lower()),
    )
    return url_id


def add_download_decoy(db: sqlite3.Connection, when: datetime) -> None:
    start = chrome_time(when)
    end = chrome_time(when + timedelta(seconds=7))
    db.execute(
        """
        INSERT INTO downloads(
          id, guid, current_path, target_path, start_time, received_bytes,
          total_bytes, state, danger_type, interrupt_reason, hash, end_time,
          opened, last_access_time, transient, referrer, site_url, tab_url,
          tab_referrer_url, http_method, by_ext_id, by_ext_name, etag,
          last_modified, mime_type, original_mime_type
        )
        VALUES(1, ?, ?, ?, ?, ?, ?, 1, 0, 0, ?, ?, 1, ?, 0, ?, ?, ?, '', 'GET', '', '', ?, ?, ?, ?)
        """,
        (
            "0b5c6db1-1a76-4ad0-8a8d-1e1b5cc0ffee",
            "/home/analyst/Downloads/flag.txt",
            "/home/analyst/Downloads/flag.txt",
            start,
            41,
            41,
            hashlib.sha256(b"ITECHNO26{d1suatu kampus di jepang ada jalanan yang di cor sama mahaiswanya sendiri sunggu jenaka tapi ini bukan soal jepang}\n").digest(),
            end,
            end,
            "https://paste.invalid/login",
            "https://paste.invalid/",
            "https://paste.invalid/raw/ITECHNO%7Bstrings_only_finds_decoys%7D",
            '"92818-decoy"',
            "Tue, 28 Apr 2026 04:13:37 GMT",
            "text/plain",
            "text/plain",
        ),
    )
    db.execute(
        """
        INSERT INTO downloads_url_chains(id, chain_index, url)
        VALUES(1, 0, ?), (1, 1, ?)
        """,
        (
            "https://paste.invalid/d/old-incident-note",
            "https://paste.invalid/raw/ITECHNO%7Bstrings_only_finds_decoys%7D",
        ),
    )


def populate(db: sqlite3.Connection) -> None:
    create_schema(db)
    payload_b64, payload = load_payload_b64()
    payload_digest = hashlib.sha256(payload).hexdigest()

    start = datetime(2026, 4, 18, 8, 12, 0, tzinfo=timezone.utc)
    normal_pages = [
        (
            "https://mail.invalid/inbox",
            "Inbox - Analyst",
            "daily check",
            0,
        ),
        (
            "https://docs.invalid/cases/browser-artifact-notes",
            "Browser Artifact Notes",
            "case notes",
            6,
        ),
        (
            "https://paste.invalid/raw/ITECHNO%7Breadable_history_is_a_decoy%7D",
            "draft flag ITECHNO26{NARO HELM HATI HATI KALO DI PARKIRAN, DISUATU MASA ADA SUATU KAMPUS DI VENEZUELA KETIKA MAHASISWANYA INGIN MENDEMO PEMERINTAHNYA DEMONSTRAN ITU SENDIRI MALAH MALING HELM DI PARKIRAN KAMPUSNYA DENGAN ALASAN NGELINDUNGIN PALA SAMPE SEKARANG BLOM BALIK TUH HELM, UNTUNG AJA BUKAN DI NEGERI INI}",
            "decoy",
            11,
        ),
        (
            "https://developer.chrome.com/docs/",
            "Chrome for Developers",
            "docs",
            18,
        ),
        (
            "https://news.invalid/security/supply-chain",
            "Security News",
            "news",
            24,
        ),
    ]

    last_visit = None
    for url, title, _, minute in normal_pages:
        ts = chrome_time(start + timedelta(minutes=minute))
        url_id = add_url(db, url, title, ts, typed=minute in {0, 6})
        last_visit = add_visit(db, url_id, ts, transition=805306369, from_visit=last_visit)

    add_download_decoy(db, start + timedelta(hours=1, minutes=35))

    add_search(db, "chromium history sqlite visit_time converter", start + timedelta(minutes=31), index=0)
    add_search(db, "how to tell fake flag from browser strings", start + timedelta(minutes=34), index=1)
    add_search(db, "download digest same bit browser artifact checksum", start + timedelta(minutes=37), index=2)
    add_search(db, "timeline low byte entropy looks wrong", start + timedelta(minutes=38), index=3)

    stage1_plain = (
        "S1:history-route\n"
        "NEXT:cdn-cache.local visits ordered by visits.id\n"
        "DATA:visit_time_low_byte\n"
        "LOCK:XNOR\n"
        "K2:sha256(meta.date_created|downloads.start_time|stage1_row_count)"
    )
    stage1_cipher = xnor(stage1_plain.encode(), derive_key1(db))
    stage1_b32 = base64.b32encode(stage1_cipher).decode().rstrip("=")
    for index, piece in enumerate(chunk(stage1_b32, 31)):
        add_search(
            db,
            f"cache freshness bucket {index:02d} {piece}",
            start + timedelta(minutes=40 + index),
            index=index,
        )

    add_search(db, "base64 decode padding error not this time", start + timedelta(minutes=49), index=99)

    stage2_plain = (
        f"S2:metadata-route\n"
        f"NEXT:typed_url_sync_metadata storage_key={PAYLOAD_STORAGE_KEY}\n"
        "DATA:xnor(zlib(base64_png))\n"
        "K3:sha256(download.guid|download.etag|download.chain_tail)\n"
        "OUTPUT:decode_base64_to_png"
    )
    stage1_row_count = len(chunk(stage1_b32, 31))
    stage2_cipher = xnor(stage2_plain.encode(), derive_key2(db, stage1_row_count))
    payload_start = start + timedelta(hours=1, minutes=9)
    for index, byte in enumerate(stage2_cipher):
        nominal = chrome_time(payload_start + timedelta(seconds=index * 9))
        ts = force_low_byte(nominal, byte)
        digest = hashlib.sha1(f"browto-cache-{index}".encode()).hexdigest()[:10]
        url_id = add_url(
            db,
            f"https://cdn-cache.local/pixel/{index:03d}.gif?etag={digest}",
            "cached image",
            ts,
            hidden=1,
        )
        last_visit = add_visit(db, url_id, ts, transition=0, from_visit=last_visit, duration=index % 3)

    blob = xnor(zlib.compress(payload_b64.encode(), level=9), derive_key3(db))
    db.execute(
        "INSERT INTO typed_url_sync_metadata(storage_key, value) VALUES(?, ?)",
        (PAYLOAD_STORAGE_KEY, sqlite3.Binary(blob)),
    )
    db.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?)",
        ("payload_png_sha256", payload_digest),
    )


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    db = sqlite3.connect(OUT)
    try:
        populate(db)
        db.commit()
        db.execute("VACUUM")
    finally:
        db.close()

    os.chmod(OUT, 0o644)
    print(f"wrote: {OUT.relative_to(ROOT)}")
    print(f"payload: {PAYLOAD_B64.relative_to(ROOT)}")
    print(f"png_sha256: {hashlib.sha256(load_payload_b64()[1]).hexdigest()}")


if __name__ == "__main__":
    main()
