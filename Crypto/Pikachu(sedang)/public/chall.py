#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass
from pathlib import Path

PUBLIC_PATH = Path(__file__).with_name("output.txt")


@dataclass(frozen=True)
class ChallengeParams:
    code_bits: int
    pbkdf2_rounds: int
    tree_height: int
    salt: bytes

    @property
    def code_space(self) -> int:
        return 1 << self.code_bits

    @property
    def code_bytes_len(self) -> int:
        return (self.code_bits + 7) // 8

    @property
    def leaf_count(self) -> int:
        return 1 << self.tree_height


def load_public(path: Path = PUBLIC_PATH) -> dict[str, object]:
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


def code_to_bytes(code: int, params: ChallengeParams) -> bytes:
    if not 0 <= code < params.code_space:
        raise ValueError("code out of range")
    return code.to_bytes(params.code_bytes_len, "little")


def stretch_code(code: int, params: ChallengeParams) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        code_to_bytes(code, params),
        params.salt,
        params.pbkdf2_rounds,
        dklen=32,
    )


def derive_seeds(stretched: bytes) -> tuple[bytes, bytes]:
    sk_seed = hashlib.sha3_256(b"PikaSPX|sk-seed|" + stretched).digest()
    pub_seed = hashlib.sha3_256(b"PikaSPX|pub-seed|" + stretched).digest()
    return sk_seed, pub_seed


def hash_leaf(sk_seed: bytes, pub_seed: bytes, index: int) -> bytes:
    leaf_secret = hashlib.sha3_256(
        b"PikaSPX|leaf-secret|" + sk_seed + index.to_bytes(2, "little")
    ).digest()
    return hashlib.sha3_256(
        b"PikaSPX|leaf-pk|" + pub_seed + index.to_bytes(2, "little") + leaf_secret
    ).digest()


def merkle_root(leaves: list[bytes]) -> bytes:
    nodes = leaves[:]
    while len(nodes) > 1:
        nodes = [
            hashlib.sha3_256(b"PikaSPX|node|" + nodes[i] + nodes[i + 1]).digest()
            for i in range(0, len(nodes), 2)
        ]
    return nodes[0]


def derive_public_root_from_code(code: int, params: ChallengeParams) -> bytes:
    stretched = stretch_code(code, params)
    sk_seed, pub_seed = derive_seeds(stretched)
    leaves = [hash_leaf(sk_seed, pub_seed, i) for i in range(params.leaf_count)]
    return merkle_root(leaves)


def derive_key_from_code(code: int, params: ChallengeParams, root: bytes | None = None) -> bytes:
    stretched = stretch_code(code, params)
    if root is None:
        root = derive_public_root_from_code(code, params)
    return hashlib.sha3_256(b"PikaSPX|flag-key|" + stretched + root).digest()


def xor_stream(key: bytes, nonce: bytes, data: bytes) -> bytes:
    stream = hashlib.shake_256(key + nonce).digest(len(data))
    return bytes(a ^ b for a, b in zip(data, stream))


def recover_flag_from_code(code: int, path: Path = PUBLIC_PATH) -> str:
    public = load_public(path)
    params = params_from_public(public)
    root = bytes.fromhex(public["root"])
    key = derive_key_from_code(code, params, root)
    flag = xor_stream(key, bytes.fromhex(public["nonce"]), bytes.fromhex(public["ct"]))
    return flag.decode()


if __name__ == "__main__":
    public = load_public()
    params = params_from_public(public)
    print(f"code_bits={params.code_bits}")
    print(f"pbkdf2_rounds={params.pbkdf2_rounds}")
    print(f"tree_height={params.tree_height}")
    print(f"code_space={params.code_space}")
    print("Recompute the published root for every candidate code until it matches.")