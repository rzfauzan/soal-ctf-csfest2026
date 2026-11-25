#!/usr/bin/env python3
import base64
import hashlib
import re
import sqlite3
import sys
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = ROOT / "public" / "History"
DEFAULT_OUTPUT = ROOT / "solution" / "recovered_flag.png"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def xnor(data: bytes, key: bytes) -> bytes:
    return bytes((~(byte ^ key[index % len(key)])) & 0xFF for index, byte in enumerate(data))


def b32decode_unpadded(text: str) -> bytes:
    return base64.b32decode(text + ("=" * ((8 - len(text) % 8) % 8)))


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


def solve(history_path: Path, output_path: Path = DEFAULT_OUTPUT) -> Path:
    db = sqlite3.connect(history_path)
    try:
        terms = [
            row[0]
            for row in db.execute(
                """
                SELECT term
                FROM keyword_search_terms
                WHERE term LIKE 'cache freshness bucket %'
                ORDER BY term
                """
            )
        ]
        if not terms:
            raise ValueError("stage 1 shards not found")

        b32 = "".join(term.rsplit(" ", 1)[1] for term in terms)
        stage1_cipher = b32decode_unpadded(b32)
        stage1 = xnor(stage1_cipher, derive_key1(db)).decode()

        low_bytes = [
            row[0] & 0xFF
            for row in db.execute(
                """
                SELECT visits.visit_time
                FROM visits
                JOIN urls ON urls.id = visits.url
                WHERE urls.url LIKE 'https://cdn-cache.local/%'
                ORDER BY visits.id
                """
            )
        ]
        stage2 = xnor(bytes(low_bytes), derive_key2(db, len(terms))).decode()

        storage_key = int(re.search(r"storage_key=(\d+)", stage2).group(1))
        blob = db.execute(
            "SELECT value FROM typed_url_sync_metadata WHERE storage_key = ?",
            (storage_key,),
        ).fetchone()[0]
        payload_b64 = zlib.decompress(xnor(blob, derive_key3(db))).decode()
        png = base64.b64decode(payload_b64, validate=True)
        if not png.startswith(PNG_MAGIC):
            raise ValueError("decoded payload is not a PNG")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(png)
        digest = hashlib.sha256(png).hexdigest()
        expected_digest = db.execute(
            "SELECT value FROM meta WHERE key = 'payload_png_sha256'"
        ).fetchone()

        print(f"[stage1] {stage1}")
        print(f"[stage2] {stage2}")
        print(f"[stage3] recovered base64 PNG: {len(payload_b64)} chars")
        print(f"[png] wrote {output_path}")
        print(f"[png] sha256 {digest}")
        if expected_digest:
            print(f"[png] expected {expected_digest[0]}")
        return output_path
    finally:
        db.close()


def main() -> None:
    history_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_HISTORY
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT
    solve(history_path, output_path)


if __name__ == "__main__":
    main()
