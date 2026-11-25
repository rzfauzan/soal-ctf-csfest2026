#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ihatemath_common import load_json, save_json  # noqa: E402
from src.ihatemath_protocol import (  # noqa: E402
    DEFAULT_CODE_BITS,
    DEFAULT_DIM,
    DEFAULT_PBKDF2_ROUNDS,
    DEFAULT_RECURSIVE_SESSIONS,
    build_instance,
    solve_public,
)

DIST = ROOT / "dist"
AUTHOR = ROOT / "author"

DEFAULT_FLAG = "CSF{3l_G4m4R_Ciph3r_1s_g00d_4nd_1_l0ve_1t}"
DEFAULT_SEED = 0x49484154454D4154485F4A4F55524E414C


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    return int(value, 0)


def verify_output(path: Path, expected_flag: str, brute_code: int) -> None:
    public = load_json(path)
    recovered = solve_public(public, brute_code=brute_code)
    if recovered != expected_flag:
        raise ValueError("self-check failed while verifying output.json")


def main() -> None:
    flag = os.environ.get("FLAG", DEFAULT_FLAG)
    seed = env_int("IHATEMATH_SEED", DEFAULT_SEED)
    dim = env_int("IHATEMATH_DIM", DEFAULT_DIM)
    rounds = env_int("IHATEMATH_ROUNDS", DEFAULT_RECURSIVE_SESSIONS)
    code_bits = env_int("IHATEMATH_CODE_BITS", DEFAULT_CODE_BITS)
    pbkdf2_rounds = env_int("IHATEMATH_PBKDF2_ROUNDS", DEFAULT_PBKDF2_ROUNDS)

    instance = build_instance(
        flag,
        seed,
        dim=dim,
        recursive_sessions=rounds,
        code_bits=code_bits,
        pbkdf2_rounds=pbkdf2_rounds,
    )

    DIST.mkdir(parents=True, exist_ok=True)
    AUTHOR.mkdir(parents=True, exist_ok=True)

    output_path = DIST / "output.json"
    author_path = AUTHOR / "instance.json"

    save_json(output_path, instance["public"])
    save_json(author_path, instance["author"])
    verify_output(output_path, flag, instance["author"]["brute_code"])
    print(f"wrote {output_path} and {author_path}")


if __name__ == "__main__":
    main()
