from __future__ import annotations

import hashlib
from dataclasses import dataclass

DEFAULT_CODE_BITS = 22
DEFAULT_PBKDF2_ROUNDS = 1710
DEFAULT_TREE_HEIGHT = 4
DEFAULT_SALT = b"PikaSPX|factory-salt|v2"
NONCE_LEN = 16


@dataclass(frozen=True)
class ChallengeParams:
    code_bits: int = DEFAULT_CODE_BITS
    pbkdf2_rounds: int = DEFAULT_PBKDF2_ROUNDS
    tree_height: int = DEFAULT_TREE_HEIGHT
    salt: bytes = DEFAULT_SALT

    @property
    def code_space(self) -> int:
        return 1 << self.code_bits

    @property
    def code_bytes_len(self) -> int:
        return (self.code_bits + 7) // 8

    @property
    def leaf_count(self) -> int:
        return 1 << self.tree_height


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


def derive_public_root(code: int, params: ChallengeParams) -> bytes:
    stretched = stretch_code(code, params)
    sk_seed, pub_seed = derive_seeds(stretched)
    leaves = [hash_leaf(sk_seed, pub_seed, i) for i in range(params.leaf_count)]
    return merkle_root(leaves)


def derive_key(code: int, params: ChallengeParams, root: bytes | None = None) -> bytes:
    stretched = stretch_code(code, params)
    if root is None:
        root = derive_public_root(code, params)
    return hashlib.sha3_256(b"PikaSPX|flag-key|" + stretched + root).digest()


def xor_stream(key: bytes, nonce: bytes, data: bytes) -> bytes:
    stream = hashlib.shake_256(key + nonce).digest(len(data))
    return bytes(a ^ b for a, b in zip(data, stream))


def encrypt_flag(flag: str, code: int, params: ChallengeParams, nonce: bytes) -> tuple[bytes, bytes]:
    root = derive_public_root(code, params)
    key = derive_key(code, params, root)
    ct = xor_stream(key, nonce, flag.encode())
    return root, ct


def build_public_lines(
    params: ChallengeParams,
    root: bytes,
    nonce: bytes,
    ct: bytes,
) -> list[str]:
    return [
        f"code_bits = {params.code_bits}",
        f"pbkdf2_rounds = {params.pbkdf2_rounds}",
        f"tree_height = {params.tree_height}",
        f"salt = '{params.salt.hex()}'",
        f"root = '{root.hex()}'",
        f"nonce = '{nonce.hex()}'",
        f"ct = '{ct.hex()}'",
    ]
