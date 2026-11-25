from __future__ import annotations

import re
import hashlib
import random

from src.ihatemath_common import (
    DIM,
    PRIME,
    Matrix,
    Vector,
    change_basis,
    conjugate,
    diag_matrix,
    mat_inv,
    mat_mul,
    mat_pow,
    matrix_to_bytes,
    outer_factor_vectors,
    random_distinct_nonzero,
    random_invertible_matrix,
    scale_rows_and_cols,
)

DEFAULT_DIM = DIM
DEFAULT_RECURSIVE_SESSIONS = 8
DEFAULT_CODE_BITS = 23
DEFAULT_PBKDF2_ROUNDS = 2500
DEFAULT_SALT = bytes.fromhex("49484154454d4154487c6a6f75726e616c7c62727574657c7631")
FLAG_PATTERN = re.compile(rb"CSF\{[^}]+\}")


def diag_powers(values: Vector, exponent: int) -> Vector:
    return [pow(value, exponent, PRIME) for value in values]


def build_commuting_private(p_matrix: Matrix, diagonal_values: Vector) -> Matrix:
    return conjugate(diag_matrix(diagonal_values), p_matrix, PRIME)


def mat_mul_chain(*matrices: Matrix) -> Matrix:
    result = matrices[0]
    for matrix in matrices[1:]:
        result = mat_mul(result, matrix, PRIME)
    return result


def first_nonzero_principal_down(matrix: Matrix) -> int:
    size = len(matrix)
    for index in range(size):
        value = matrix[index][index] % PRIME
        if value != 0:
            return value
    raise ValueError("principal diagonal is all zero")


def first_nonzero_principal_up(matrix: Matrix) -> int:
    size = len(matrix)
    for index in range(size - 1, -1, -1):
        value = matrix[index][index] % PRIME
        if value != 0:
            return value
    raise ValueError("principal diagonal is all zero")


def first_nonzero_secondary_down(matrix: Matrix) -> int:
    size = len(matrix)
    for index in range(size):
        value = matrix[index][size - 1 - index] % PRIME
        if value != 0:
            return value
    raise ValueError("secondary diagonal is all zero")


def first_nonzero_secondary_up(matrix: Matrix) -> int:
    size = len(matrix)
    for index in range(size - 1, -1, -1):
        value = matrix[index][size - 1 - index] % PRIME
        if value != 0:
            return value
    raise ValueError("secondary diagonal is all zero")


def power_parameters(session_key: Matrix) -> tuple[int, int]:
    m_value = (first_nonzero_secondary_up(session_key) * first_nonzero_secondary_down(session_key)) % PRIME
    n_value = (first_nonzero_principal_down(session_key) * first_nonzero_principal_up(session_key)) % PRIME
    if m_value == 0 or n_value == 0:
        raise ValueError("power parameters unexpectedly vanished")
    return m_value, n_value


def setup_common_key(p_matrix: Matrix, g_matrix: Matrix, a_prime: Matrix, b_prime: Matrix) -> tuple[Matrix, int, int]:
    g_basis = change_basis(g_matrix, p_matrix, PRIME)
    a_prime_basis = change_basis(a_prime, p_matrix, PRIME)
    b_prime_basis = change_basis(b_prime, p_matrix, PRIME)
    left_scale, right_scale = outer_factor_vectors(a_prime_basis, g_basis, PRIME)
    key_basis = scale_rows_and_cols(b_prime_basis, left_scale, right_scale, PRIME)
    session_key = conjugate(key_basis, p_matrix, PRIME)
    m_value, n_value = power_parameters(session_key)
    return session_key, m_value, n_value


def recursively_update_key(session_key: Matrix, m_value: int, n_value: int) -> tuple[Matrix, int, int]:
    updated_key = mat_pow(session_key, (m_value * n_value) % PRIME, PRIME)
    next_m, next_n = power_parameters(updated_key)
    return updated_key, next_m, next_n


def update_public_matrices(
    session_key: Matrix,
    m_value: int,
    n_value: int,
    p_matrix: Matrix,
    g_matrix: Matrix,
) -> tuple[Matrix, Matrix]:
    left = mat_pow(session_key, m_value, PRIME)
    right = mat_pow(session_key, n_value, PRIME)
    next_p = mat_mul_chain(left, p_matrix, right)
    next_g = mat_mul_chain(left, g_matrix, right)
    return next_p, next_g


def build_setup_tokens(
    p_matrix: Matrix,
    g_matrix: Matrix,
    diag_a: Vector,
    diag_b: Vector,
    k1: int,
    k2: int,
    r1: int,
    r2: int,
) -> tuple[Matrix, Matrix, Matrix, Matrix, Matrix, int, int]:
    a_matrix = build_commuting_private(p_matrix, diag_a)
    b_matrix = build_commuting_private(p_matrix, diag_b)
    a_prime = mat_mul_chain(mat_pow(a_matrix, k1, PRIME), g_matrix, mat_pow(a_matrix, k2, PRIME))
    b_prime = mat_mul_chain(mat_pow(b_matrix, r1, PRIME), g_matrix, mat_pow(b_matrix, r2, PRIME))
    session_key, m_value, n_value = setup_common_key(p_matrix, g_matrix, a_prime, b_prime)
    return a_matrix, b_matrix, a_prime, b_prime, session_key, m_value, n_value


def build_session_tokens(
    p_matrix: Matrix,
    g_matrix: Matrix,
    diag_a: Vector,
    diag_b: Vector,
    m_value: int,
    n_value: int,
) -> tuple[Matrix, Matrix, Matrix, Matrix]:
    a_matrix = build_commuting_private(p_matrix, diag_a)
    b_matrix = build_commuting_private(p_matrix, diag_b)
    a_prime = mat_mul_chain(mat_pow(a_matrix, m_value, PRIME), g_matrix, mat_pow(a_matrix, n_value, PRIME))
    b_prime = mat_mul_chain(mat_pow(b_matrix, m_value, PRIME), g_matrix, mat_pow(b_matrix, n_value, PRIME))
    return a_matrix, b_matrix, a_prime, b_prime


def encode_flag_matrix(flag: str, rng: random.Random, dim: int = DEFAULT_DIM) -> Matrix:
    payload = flag.encode("ascii")
    if len(payload) > dim * dim:
        raise ValueError("flag is too long for the message matrix")
    while True:
        pad = bytes(rng.randrange(PRIME) for _ in range(dim * dim - len(payload)))
        blob = payload + pad
        matrix = [list(blob[row * dim : (row + 1) * dim]) for row in range(dim)]
        try:
            mat_inv(matrix, PRIME)
            return matrix
        except ValueError:
            continue


def code_to_bytes(code: int, code_bits: int) -> bytes:
    if not 0 <= code < (1 << code_bits):
        raise ValueError("code out of range")
    return code.to_bytes((code_bits + 7) // 8, "little")


def derive_bruteforce_stream(
    code: int,
    code_bits: int,
    pbkdf2_rounds: int,
    salt: bytes,
    nonce: bytes,
    out_len: int,
) -> list[int]:
    stretched = hashlib.pbkdf2_hmac(
        "sha256",
        code_to_bytes(code, code_bits),
        salt,
        pbkdf2_rounds,
        dklen=32,
    )
    raw = hashlib.shake_256(b"IHateMath|journal-brute|" + stretched + nonce).digest(out_len)
    return [value % PRIME for value in raw]


def encrypt_flag_blob(
    flag: str,
    rng: random.Random,
    code: int,
    code_bits: int,
    pbkdf2_rounds: int,
    salt: bytes,
    dim: int,
) -> Matrix:
    plaintext = list(flag.encode("ascii"))
    slots = dim * dim
    if len(plaintext) > slots - 16:
        raise ValueError("flag is too long for the brute-force blob layout")
    while True:
        nonce_values = [rng.randrange(PRIME) for _ in range(16)]
        nonce = bytes(nonce_values)
        stream = derive_bruteforce_stream(code, code_bits, pbkdf2_rounds, salt, nonce, len(plaintext))
        ciphertext = [(p + s) % PRIME for p, s in zip(plaintext, stream)]
        blob = nonce_values + ciphertext + [0] * (slots - 16 - len(ciphertext))
        matrix = [blob[row * dim : (row + 1) * dim] for row in range(dim)]
        try:
            mat_inv(matrix, PRIME)
            return matrix
        except ValueError:
            continue


def extract_flag_from_matrix(message: Matrix) -> str:
    match = FLAG_PATTERN.search(matrix_to_bytes(message))
    if not match:
        raise ValueError("flag marker not found in the recovered message matrix")
    return match.group().decode("ascii")


def decrypt_flag_blob(
    message: Matrix,
    code: int,
    code_bits: int,
    pbkdf2_rounds: int,
    salt: bytes,
) -> str:
    blob = list(matrix_to_bytes(message))
    nonce = bytes(blob[:16])
    ciphertext = blob[16:]
    stream = derive_bruteforce_stream(code, code_bits, pbkdf2_rounds, salt, nonce, len(ciphertext))
    plaintext = bytes((c - s) % PRIME for c, s in zip(ciphertext, stream))
    return extract_flag_from_matrix([list(plaintext)])


def decrypt_message_matrix(y2: Matrix, mask: Matrix) -> Matrix:
    return mat_mul(y2, mat_inv(mask, PRIME), PRIME)


def recover_message_matrix(p_matrix: Matrix, g_matrix: Matrix, b_prime: Matrix, y1: Matrix, y2: Matrix) -> Matrix:
    g_basis = change_basis(g_matrix, p_matrix, PRIME)
    b_prime_basis = change_basis(b_prime, p_matrix, PRIME)
    y1_basis = change_basis(y1, p_matrix, PRIME)
    left_j, right_j = outer_factor_vectors(y1_basis, g_basis, PRIME)
    mask_basis = scale_rows_and_cols(b_prime_basis, left_j, right_j, PRIME)
    mask = conjugate(mask_basis, p_matrix, PRIME)
    return decrypt_message_matrix(y2, mask)


def build_instance(
    flag: str,
    seed: int,
    *,
    dim: int = DEFAULT_DIM,
    recursive_sessions: int = DEFAULT_RECURSIVE_SESSIONS,
    code_bits: int = DEFAULT_CODE_BITS,
    pbkdf2_rounds: int = DEFAULT_PBKDF2_ROUNDS,
    salt: bytes = DEFAULT_SALT,
) -> dict[str, object]:
    if dim != DEFAULT_DIM:
        raise ValueError("the journal protocol instance is fixed to GL(8, F_251)")

    rng = random.Random(seed)

    p_matrix = random_invertible_matrix(rng, dim, PRIME)
    g_basis = random_invertible_matrix(rng, dim, PRIME, dense_nonzero=True)
    g_matrix = conjugate(g_basis, p_matrix, PRIME)

    diag_a = random_distinct_nonzero(rng, dim, PRIME)
    diag_b = random_distinct_nonzero(rng, dim, PRIME)
    k1 = rng.randrange(1, PRIME)
    k2 = rng.randrange(1, PRIME)
    r1 = rng.randrange(1, PRIME)
    r2 = rng.randrange(1, PRIME)

    _, _, setup_a_prime, setup_b_prime, session_key, m_value, n_value = build_setup_tokens(
        p_matrix,
        g_matrix,
        diag_a,
        diag_b,
        k1,
        k2,
        r1,
        r2,
    )

    sessions: list[dict[str, object]] = []
    author_sessions: list[dict[str, object]] = []

    current_p = p_matrix
    current_g = g_matrix
    current_key = session_key
    current_m = m_value
    current_n = n_value
    current_b_prime = setup_b_prime

    for round_index in range(recursive_sessions):
        current_key, current_m, current_n = recursively_update_key(current_key, current_m, current_n)
        current_p, current_g = update_public_matrices(current_key, current_m, current_n, current_p, current_g)
        _, _, current_a_prime, current_b_prime = build_session_tokens(
            current_p,
            current_g,
            diag_a,
            diag_b,
            current_m,
            current_n,
        )
        sessions.append(
            {
                "round": round_index + 1,
                "A_prime": current_a_prime,
                "B_prime": current_b_prime,
            }
        )
        author_sessions.append(
            {
                "round": round_index + 1,
                "m": current_m,
                "n": current_n,
                "session_key": current_key,
            }
        )

    brute_code = rng.randrange(1 << code_bits)
    message_matrix = encrypt_flag_blob(flag, rng, brute_code, code_bits, pbkdf2_rounds, salt, dim)
    diag_j = random_distinct_nonzero(rng, dim, PRIME)
    j_matrix = build_commuting_private(current_p, diag_j)
    y1 = mat_mul_chain(mat_pow(j_matrix, current_m, PRIME), current_g, mat_pow(j_matrix, current_n, PRIME))
    mask = mat_mul_chain(mat_pow(j_matrix, current_m, PRIME), current_b_prime, mat_pow(j_matrix, current_n, PRIME))
    y2 = mat_mul(message_matrix, mask, PRIME)

    public = {
        "p": PRIME,
        "d": dim,
        "recursive_sessions": recursive_sessions,
        "bruteforce": {
            "code_bits": code_bits,
            "pbkdf2_rounds": pbkdf2_rounds,
            "salt": salt.hex(),
        },
        "setup": {
            "P": p_matrix,
            "G": g_matrix,
            "A_prime": setup_a_prime,
            "B_prime": setup_b_prime,
        },
        "sessions": sessions,
        "cipher": {
            "y1": y1,
            "y2": y2,
        },
    }

    author = {
        "seed": seed,
        "flag": flag,
        "diag_a": diag_a,
        "diag_b": diag_b,
        "diag_j": diag_j,
        "k1": k1,
        "k2": k2,
        "r1": r1,
        "r2": r2,
        "brute_code": brute_code,
        "setup": {
            "session_key": session_key,
            "m": m_value,
            "n": n_value,
        },
        "sessions": author_sessions,
    }
    return {"public": public, "author": author}


def solve_public(public: dict[str, object], *, brute_code: int | None = None) -> str:
    current_p = public["setup"]["P"]
    current_g = public["setup"]["G"]
    current_b_prime = public["setup"]["B_prime"]
    current_key, current_m, current_n = setup_common_key(
        current_p,
        current_g,
        public["setup"]["A_prime"],
        current_b_prime,
    )

    for session in public["sessions"]:
        current_key, current_m, current_n = recursively_update_key(current_key, current_m, current_n)
        current_p, current_g = update_public_matrices(current_key, current_m, current_n, current_p, current_g)
        current_b_prime = session["B_prime"]

    message = recover_message_matrix(
        current_p,
        current_g,
        current_b_prime,
        public["cipher"]["y1"],
        public["cipher"]["y2"],
    )
    brute = public["bruteforce"]
    code_bits = brute["code_bits"]
    pbkdf2_rounds = brute["pbkdf2_rounds"]
    salt = bytes.fromhex(brute["salt"])
    if brute_code is not None:
        return decrypt_flag_blob(message, brute_code, code_bits, pbkdf2_rounds, salt)
    for candidate in range(1 << code_bits):
        try:
            return decrypt_flag_blob(message, candidate, code_bits, pbkdf2_rounds, salt)
        except ValueError:
            continue
    raise ValueError("bruteforce search exhausted without finding the flag")
