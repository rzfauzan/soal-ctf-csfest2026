#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pikaspx_common import ChallengeParams, derive_key, derive_public_root, xor_stream  # noqa: E402

PUBLIC_PATH = ROOT / "dist" / "output.txt"
AUTHOR_PATH = ROOT / "author" / "instance.json"


def load_public(path: Path) -> dict[str, object]:
    ns: dict[str, object] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        key, value = line.split("=", 1)
        ns[key.strip()] = ast.literal_eval(value.strip())
    return ns


def params_from_public(public: dict[str, object]) -> ChallengeParams:
    return ChallengeParams(
        code_bits=int(public["code_bits"]),
        pbkdf2_rounds=int(public["pbkdf2_rounds"]),
        tree_height=int(public["tree_height"]),
        salt=bytes.fromhex(public["salt"]),
    )


def benchmark_rate(params: ChallengeParams, samples: int) -> float:
    start = time.perf_counter()
    acc = 0
    for code in range(samples):
        acc ^= derive_public_root(code, params)[0]
    elapsed = time.perf_counter() - start
    if elapsed == 0:
        raise RuntimeError("benchmark timer resolution failure")
    print(f"benchmark_samples={samples} dummy={acc}")
    return samples / elapsed


def format_duration(seconds: float) -> str:
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {sec}s"
    return f"{minutes}m {sec}s"


def brute_force(public: dict[str, object], params: ChallengeParams, progress_step: int) -> int:
    target_root = bytes.fromhex(public["root"])
    start = time.perf_counter()
    for code in range(params.code_space):
        if code and code % progress_step == 0:
            elapsed = time.perf_counter() - start
            rate = code / elapsed if elapsed else 0.0
            eta = (params.code_space - code) / rate if rate else 0.0
            print(
                f"progress={code}/{params.code_space} rate={rate:.1f} code/s eta={format_duration(eta)}"
            )
        if derive_public_root(code, params) == target_root:
            return code
    raise RuntimeError("brute force exhausted the keyspace")


def decrypt_flag(public: dict[str, object], params: ChallengeParams, code: int) -> bytes:
    root = bytes.fromhex(public["root"])
    key = derive_key(code, params, root)
    return xor_stream(key, bytes.fromhex(public["nonce"]), bytes.fromhex(public["ct"]))


def load_author_code() -> int | None:
    if not AUTHOR_PATH.exists():
        return None
    data = json.loads(AUTHOR_PATH.read_text(encoding="utf-8"))
    return int(data["debug_code"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-only", action="store_true")
    parser.add_argument("--benchmark-samples", type=int, default=4096)
    parser.add_argument("--progress-step", type=int, default=1 << 18)
    args = parser.parse_args()

    public = load_public(PUBLIC_PATH)
    params = params_from_public(public)
    rate = benchmark_rate(params, args.benchmark_samples)
    total_seconds = params.code_space / rate
    print(f"estimated_full_scan={format_duration(total_seconds)} at {rate:.1f} code/s")
    author_code = load_author_code()
    if author_code is not None:
        estimated_hit = author_code / rate
        print(f"estimated_hit_time={format_duration(estimated_hit)} for code=0x{author_code:06x}")
    if args.benchmark_only:
        return

    code = brute_force(public, params, args.progress_step)
    flag = decrypt_flag(public, params, code)
    print(f"debug_code=0x{code:06x}")
    print(flag.decode())


if __name__ == "__main__":
    main()
