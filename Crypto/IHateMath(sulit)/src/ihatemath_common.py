from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from pathlib import Path

PRIME = 251
DIM = 8
DEFAULT_ROUNDS = 6
NONCE_LEN = 16

Matrix = list[list[int]]
Vector = list[int]


@dataclass(frozen=True)
class ChallengeParams:
    prime: int = PRIME
    dim: int = DIM
    rounds: int = DEFAULT_ROUNDS


def mod_inv(value: int, prime: int = PRIME) -> int:
    value %= prime
    if value == 0:
        raise ZeroDivisionError("matrix element is not invertible modulo prime")
    return pow(value, -1, prime)


def identity(size: int) -> Matrix:
    return [[1 if i == j else 0 for j in range(size)] for i in range(size)]


def diag_matrix(values: Vector) -> Matrix:
    size = len(values)
    return [[values[i] if i == j else 0 for j in range(size)] for i in range(size)]


def mat_copy(matrix: Matrix) -> Matrix:
    return [row[:] for row in matrix]


def mat_add(a: Matrix, b: Matrix, prime: int = PRIME) -> Matrix:
    return [[(x + y) % prime for x, y in zip(row_a, row_b)] for row_a, row_b in zip(a, b)]


def mat_sub(a: Matrix, b: Matrix, prime: int = PRIME) -> Matrix:
    return [[(x - y) % prime for x, y in zip(row_a, row_b)] for row_a, row_b in zip(a, b)]


def mat_mul(a: Matrix, b: Matrix, prime: int = PRIME) -> Matrix:
    rows = len(a)
    cols = len(b[0])
    inner = len(b)
    out = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        for k in range(inner):
            if a[i][k] == 0:
                continue
            aik = a[i][k]
            for j in range(cols):
                out[i][j] = (out[i][j] + aik * b[k][j]) % prime
    return out


def mat_vec_mul(matrix: Matrix, vector: Vector, prime: int = PRIME) -> Vector:
    return [sum(matrix[i][j] * vector[j] for j in range(len(vector))) % prime for i in range(len(matrix))]


def mat_inv(matrix: Matrix, prime: int = PRIME) -> Matrix:
    size = len(matrix)
    work = [row[:] + eye for row, eye in zip(matrix, identity(size))]
    pivot_row = 0
    for col in range(size):
        pivot = None
        for row in range(pivot_row, size):
            if work[row][col] % prime != 0:
                pivot = row
                break
        if pivot is None:
            raise ValueError("matrix is singular")
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        scale = mod_inv(work[pivot_row][col], prime)
        work[pivot_row] = [(scale * value) % prime for value in work[pivot_row]]
        for row in range(size):
            if row == pivot_row or work[row][col] == 0:
                continue
            factor = work[row][col]
            work[row] = [
                (value - factor * pivot_value) % prime
                for value, pivot_value in zip(work[row], work[pivot_row])
            ]
        pivot_row += 1
    return [row[size:] for row in work]


def mat_pow(matrix: Matrix, exponent: int, prime: int = PRIME) -> Matrix:
    if exponent < 0:
        return mat_pow(mat_inv(matrix, prime), -exponent, prime)
    result = identity(len(matrix))
    base = mat_copy(matrix)
    power = exponent
    while power:
        if power & 1:
            result = mat_mul(result, base, prime)
        base = mat_mul(base, base, prime)
        power >>= 1
    return result


def conjugate(matrix: Matrix, basis: Matrix, prime: int = PRIME) -> Matrix:
    return mat_mul(mat_mul(basis, matrix, prime), mat_inv(basis, prime), prime)


def change_basis(matrix: Matrix, basis: Matrix, prime: int = PRIME) -> Matrix:
    return mat_mul(mat_mul(mat_inv(basis, prime), matrix, prime), basis, prime)


def columns_to_matrix(columns: list[Vector]) -> Matrix:
    size = len(columns)
    return [[columns[j][i] for j in range(size)] for i in range(size)]


def normalize_vector(vector: Vector, prime: int = PRIME) -> Vector:
    for value in vector:
        if value % prime != 0:
            scale = mod_inv(value, prime)
            return [(scale * entry) % prime for entry in vector]
    raise ValueError("cannot normalize the zero vector")


def rref(matrix: Matrix, prime: int = PRIME) -> tuple[Matrix, list[int]]:
    work = mat_copy(matrix)
    rows = len(work)
    cols = len(work[0])
    pivots: list[int] = []
    pivot_row = 0
    for col in range(cols):
        pivot = None
        for row in range(pivot_row, rows):
            if work[row][col] % prime != 0:
                pivot = row
                break
        if pivot is None:
            continue
        work[pivot_row], work[pivot] = work[pivot], work[pivot_row]
        scale = mod_inv(work[pivot_row][col], prime)
        work[pivot_row] = [(scale * value) % prime for value in work[pivot_row]]
        for row in range(rows):
            if row == pivot_row or work[row][col] == 0:
                continue
            factor = work[row][col]
            work[row] = [
                (value - factor * pivot_value) % prime
                for value, pivot_value in zip(work[row], work[pivot_row])
            ]
        pivots.append(col)
        pivot_row += 1
        if pivot_row == rows:
            break
    return work, pivots


def nullspace_basis(matrix: Matrix, prime: int = PRIME) -> list[Vector]:
    reduced, pivots = rref(matrix, prime)
    cols = len(matrix[0])
    free_cols = [col for col in range(cols) if col not in pivots]
    basis: list[Vector] = []
    for free in free_cols:
        vector = [0] * cols
        vector[free] = 1
        for row, pivot in enumerate(pivots):
            vector[pivot] = (-reduced[row][free]) % prime
        basis.append(vector)
    return basis


def eigenpairs(matrix: Matrix, prime: int = PRIME) -> list[tuple[int, Vector]]:
    size = len(matrix)
    pairs: list[tuple[int, Vector]] = []
    for eigenvalue in range(prime):
        shifted = [
            [
                (matrix[i][j] - (eigenvalue if i == j else 0)) % prime
                for j in range(size)
            ]
            for i in range(size)
        ]
        kernel = nullspace_basis(shifted, prime)
        if not kernel:
            continue
        if len(kernel) != 1:
            raise ValueError("unexpected repeated eigenvalue during diagonalization")
        pairs.append((eigenvalue, normalize_vector(kernel[0], prime)))
    return pairs


def diag_entries(matrix: Matrix) -> Vector:
    return [matrix[i][i] for i in range(len(matrix))]


def is_diagonal(matrix: Matrix) -> bool:
    size = len(matrix)
    for i in range(size):
        for j in range(size):
            if i != j and matrix[i][j] != 0:
                return False
    return True


def simultaneous_diagonalizer(a: Matrix, b: Matrix, prime: int = PRIME) -> tuple[Matrix, Vector, Vector]:
    pairs: list[tuple[int, int, Vector]] = []
    for eigenvalue_a, vector in eigenpairs(a, prime):
        image = mat_vec_mul(b, vector, prime)
        pivot = next(index for index, value in enumerate(vector) if value != 0)
        eigenvalue_b = (image[pivot] * mod_inv(vector[pivot], prime)) % prime
        if any((image[i] - eigenvalue_b * vector[i]) % prime != 0 for i in range(len(vector))):
            raise ValueError("matrices do not share a common eigenbasis")
        pairs.append((eigenvalue_a, eigenvalue_b, vector))
    pairs.sort(key=lambda item: (item[0], item[1]))
    basis = columns_to_matrix([vector for _, _, vector in pairs])
    diag_a = change_basis(a, basis, prime)
    diag_b = change_basis(b, basis, prime)
    if not is_diagonal(diag_a) or not is_diagonal(diag_b):
        raise ValueError("failed to diagonalize the commuting pair")
    return basis, diag_entries(diag_a), diag_entries(diag_b)


def scale_rows_and_cols(matrix: Matrix, left: Vector, right: Vector, prime: int = PRIME) -> Matrix:
    size = len(matrix)
    return [
        [(left[i] * matrix[i][j] * right[j]) % prime for j in range(size)]
        for i in range(size)
    ]


def hadamard_mul(a: Matrix, b: Matrix, prime: int = PRIME) -> Matrix:
    return [[(x * y) % prime for x, y in zip(row_a, row_b)] for row_a, row_b in zip(a, b)]


def hadamard_div(a: Matrix, b: Matrix, prime: int = PRIME) -> Matrix:
    return [[(x * mod_inv(y, prime)) % prime for x, y in zip(row_a, row_b)] for row_a, row_b in zip(a, b)]


def outer_factor_vectors(token_basis: Matrix, carrier_basis: Matrix, prime: int = PRIME) -> tuple[Vector, Vector]:
    size = len(token_basis)
    row_edges = [[] for _ in range(size)]
    col_edges = [[] for _ in range(size)]
    for i in range(size):
        for j in range(size):
            carrier = carrier_basis[i][j] % prime
            token = token_basis[i][j] % prime
            if carrier == 0:
                if token != 0:
                    raise ValueError("token and carrier disagree on the zero pattern")
                continue
            if token == 0:
                raise ValueError("non-zero carrier cannot map to a zero token")
            row_edges[i].append(j)
            col_edges[j].append(i)

    left: list[int | None] = [None] * size
    right: list[int | None] = [None] * size

    for start_row in range(size):
        if left[start_row] is not None or not row_edges[start_row]:
            continue
        left[start_row] = 1
        queue: list[tuple[str, int]] = [("row", start_row)]
        while queue:
            kind, idx = queue.pop()
            if kind == "row":
                row_scale = left[idx]
                if row_scale is None:
                    raise ValueError("internal row scale error during factorization")
                for col in row_edges[idx]:
                    ratio = (token_basis[idx][col] * mod_inv(carrier_basis[idx][col], prime)) % prime
                    candidate = (ratio * mod_inv(row_scale, prime)) % prime
                    if right[col] is None:
                        right[col] = candidate
                        queue.append(("col", col))
                    elif right[col] != candidate:
                        raise ValueError("inconsistent column scaling during factorization")
            else:
                col_scale = right[idx]
                if col_scale is None:
                    raise ValueError("internal column scale error during factorization")
                for row in col_edges[idx]:
                    ratio = (token_basis[row][idx] * mod_inv(carrier_basis[row][idx], prime)) % prime
                    candidate = (ratio * mod_inv(col_scale, prime)) % prime
                    if left[row] is None:
                        left[row] = candidate
                        queue.append(("row", row))
                    elif left[row] != candidate:
                        raise ValueError("inconsistent row scaling during factorization")

    left = [value if value is not None else 1 for value in left]
    right = [value if value is not None else 1 for value in right]
    for i in range(size):
        for j in range(size):
            carrier = carrier_basis[i][j] % prime
            token = token_basis[i][j] % prime
            if carrier == 0:
                if token != 0:
                    raise ValueError("token and carrier disagree on the zero pattern")
                continue
            if (left[i] * carrier * right[j]) % prime != token:
                raise ValueError("token ratio is not rank one on the carrier support")
    return left, right


def recover_round_key(
    a: Matrix,
    b: Matrix,
    g: Matrix,
    alice_token: Matrix,
    bob_token: Matrix,
    prime: int = PRIME,
) -> Matrix:
    basis, _, _ = simultaneous_diagonalizer(a, b, prime)
    g_basis = change_basis(g, basis, prime)
    alice_basis = change_basis(alice_token, basis, prime)
    bob_basis = change_basis(bob_token, basis, prime)
    left, right = outer_factor_vectors(alice_basis, g_basis, prime)
    key_basis = scale_rows_and_cols(bob_basis, left, right, prime)
    return conjugate(key_basis, basis, prime)


def session_update_power(session_key: Matrix, prime: int = PRIME) -> int:
    raw = (
        session_key[-1][0] * session_key[0][-1]
        + session_key[0][0] * session_key[-1][-1]
    ) % prime
    return raw if raw != 0 else 1


def advance_state(a: Matrix, b: Matrix, g: Matrix, session_key: Matrix, prime: int = PRIME) -> tuple[Matrix, Matrix, Matrix]:
    power = session_update_power(session_key, prime)
    conjugator = mat_pow(session_key, power, prime)
    inverse_conjugator = mat_inv(conjugator, prime)
    next_a = mat_mul(mat_mul(conjugator, a, prime), inverse_conjugator, prime)
    next_b = mat_mul(mat_mul(conjugator, b, prime), inverse_conjugator, prime)
    next_g = mat_mul(mat_mul(conjugator, g, prime), inverse_conjugator, prime)
    return next_a, next_b, next_g


def recover_final_mask(
    a: Matrix,
    b: Matrix,
    g: Matrix,
    bob_token: Matrix,
    capsule: Matrix,
    prime: int = PRIME,
) -> Matrix:
    basis, _, _ = simultaneous_diagonalizer(a, b, prime)
    g_basis = change_basis(g, basis, prime)
    bob_basis = change_basis(bob_token, basis, prime)
    capsule_basis = change_basis(capsule, basis, prime)
    left, right = outer_factor_vectors(capsule_basis, g_basis, prime)
    mask_basis = scale_rows_and_cols(bob_basis, left, right, prime)
    return conjugate(mask_basis, basis, prime)


def recover_mixed_product(
    a: Matrix,
    b: Matrix,
    g: Matrix,
    left_token: Matrix,
    right_token: Matrix,
    prime: int = PRIME,
) -> Matrix:
    basis, _, _ = simultaneous_diagonalizer(a, b, prime)
    g_basis = change_basis(g, basis, prime)
    left_basis = change_basis(left_token, basis, prime)
    right_basis = change_basis(right_token, basis, prime)
    if any(g_basis[i][j] == 0 for i in range(len(g_basis)) for j in range(len(g_basis))):
        raise ValueError("carrier matrix contains a zero entry and cannot be divided entrywise")
    product_basis = hadamard_div(hadamard_mul(left_basis, right_basis, prime), g_basis, prime)
    return conjugate(product_basis, basis, prime)


def matrix_to_bytes(matrix: Matrix) -> bytes:
    return bytes(value for row in matrix for value in row)


def xor_stream(data: bytes, mask: Matrix, nonce: bytes) -> bytes:
    seed = hashlib.sha3_256(b"IHateMath|mask|" + matrix_to_bytes(mask) + nonce).digest()
    stream = hashlib.shake_256(b"IHateMath|stream|" + seed + nonce).digest(len(data))
    return bytes(a ^ b for a, b in zip(data, stream))


def random_distinct_nonzero(rng: random.Random, count: int, prime: int = PRIME) -> Vector:
    values = list(range(1, prime))
    rng.shuffle(values)
    return values[:count]


def random_invertible_matrix(
    rng: random.Random,
    size: int,
    prime: int = PRIME,
    *,
    dense_nonzero: bool = False,
) -> Matrix:
    while True:
        matrix = [
            [
                rng.randrange(1, prime) if dense_nonzero else rng.randrange(prime)
                for _ in range(size)
            ]
            for _ in range(size)
        ]
        try:
            mat_inv(matrix, prime)
            return matrix
        except ValueError:
            continue


def matrix_to_hex_rows(matrix: Matrix) -> list[str]:
    return [" ".join(f"{value:02x}" for value in row) for row in matrix]


def matrix_from_hex_rows(rows: list[str]) -> Matrix:
    return [[int(part, 16) for part in row.split()] for row in rows]


def save_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))
