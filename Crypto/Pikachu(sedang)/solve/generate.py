#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pikaspx_common import (  # noqa: E402
    DEFAULT_CODE_BITS,
    DEFAULT_PBKDF2_ROUNDS,
    DEFAULT_TREE_HEIGHT,
    NONCE_LEN,
    ChallengeParams,
    build_public_lines,
    encrypt_flag,
)

DIST = ROOT / "dist"
AUTHOR = ROOT / "author"

DEFAULT_FLAG = "CSF{p1k4Chu_l00ks_ador4ble_4nd_i_L0VE_pik4chu}"
DEFAULT_DEBUG_CODE = 0x38769B
DEFAULT_NONCE_SEED = 0x50494B415350585F4E4F4E4345


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value, 0)


def build_instance(flag: str) -> dict[str, object]:
    params = ChallengeParams(
        code_bits=env_int("PIKASPX_CODE_BITS", DEFAULT_CODE_BITS),
        pbkdf2_rounds=env_int("PIKASPX_PBKDF2_ROUNDS", DEFAULT_PBKDF2_ROUNDS),
        tree_height=env_int("PIKASPX_TREE_HEIGHT", DEFAULT_TREE_HEIGHT),
        salt=bytes.fromhex(
            os.environ.get("PIKASPX_SALT_HEX", "50696b615350587c666163746f72792d73616c747c7632")
        ),
    )
    debug_code = env_int("PIKASPX_DEBUG_CODE", DEFAULT_DEBUG_CODE)
    if not 0 <= debug_code < params.code_space:
        raise ValueError("debug code is outside the configured code space")
    nonce_rng = random.Random(env_int("PIKASPX_NONCE_SEED", DEFAULT_NONCE_SEED))
    nonce = nonce_rng.randbytes(NONCE_LEN)
    root, ct = encrypt_flag(flag, debug_code, params, nonce)
    return {
        "public": {
            "params": params,
            "root": root,
            "nonce": nonce,
            "ct": ct,
        },
        "author": {
            "debug_code": debug_code,
            "debug_code_hex": f"{debug_code:0{params.code_bytes_len * 2}x}",
            "code_bits": params.code_bits,
            "pbkdf2_rounds": params.pbkdf2_rounds,
            "tree_height": params.tree_height,
            "salt_hex": params.salt.hex(),
            "flag": flag,
            "nonce_hex": nonce.hex(),
        },
    }


def write_public(instance: dict[str, object]) -> None:
    DIST.mkdir(parents=True, exist_ok=True)
    public = instance["public"]
    lines = build_public_lines(
        public["params"],
        public["root"],
        public["nonce"],
        public["ct"],
    )
    (DIST / "output.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_author(instance: dict[str, object]) -> None:
    AUTHOR.mkdir(parents=True, exist_ok=True)
    (AUTHOR / "instance.json").write_text(
        json.dumps(instance["author"], indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    flag = os.environ.get("FLAG", DEFAULT_FLAG)
    instance = build_instance(flag)
    write_public(instance)
    write_author(instance)
    print("wrote dist/output.txt and author/instance.json")


if __name__ == "__main__":
    main()
