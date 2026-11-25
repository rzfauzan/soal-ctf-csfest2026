import json
import hashlib
import re
import multiprocessing
from functools import partial
from tqdm.auto import tqdm
import os

PRIME = 251
FLAG_PATTERN = re.compile(rb"CSF\{[^}]+\}")

def mod_inv(value: int, prime: int = PRIME) -> int:
    value %= prime
    if value == 0:
        raise ZeroDivisionError("element is not invertible modulo prime")
    return pow(value, -1, prime)

def identity(size: int) -> list[list[int]]:
    return [[1 if i == j else 0 for j in range(size)] for i in range(size)]

def mat_copy(matrix: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in matrix]

def mat_mul(a: list[list[int]], b: list[list[int]], prime: int = PRIME) -> list[list[int]]:
    b_t = list(zip(*b))
    return [[sum(x * y for x, y in zip(row_a, col_b)) % prime for col_b in b_t] for row_a in a]

def mat_inv(matrix: list[list[int]], prime: int = PRIME) -> list[list[int]]:
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

def mat_pow(matrix: list[list[int]], exponent: int, prime: int = PRIME) -> list[list[int]]:
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

def change_basis(matrix: list[list[int]], basis: list[list[int]], prime: int = PRIME) -> list[list[int]]:
    return mat_mul(mat_mul(mat_inv(basis, prime), matrix, prime), basis, prime)

def conjugate(matrix: list[list[int]], basis: list[list[int]], prime: int = PRIME) -> list[list[int]]:
    return mat_mul(mat_mul(basis, matrix, prime), mat_inv(basis, prime), prime)

def scale_rows_and_cols(matrix: list[list[int]], left: list[int], right: list[int], prime: int = PRIME) -> list[list[int]]:
    size = len(matrix)
    return [[(left[i] * matrix[i][j] * right[j]) % prime for j in range(size)] for i in range(size)]

def outer_factor_vectors(token_basis: list[list[int]], carrier_basis: list[list[int]], prime: int = PRIME) -> tuple[list[int], list[int]]:
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
                raise ValueError("non-zero carrier cannot map to zero")
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
                    raise ValueError("internal row scale error")
                for col in row_edges[idx]:
                    ratio = (token_basis[idx][col] * mod_inv(carrier_basis[idx][col], prime)) % prime
                    candidate = (ratio * mod_inv(row_scale, prime)) % prime
                    if right[col] is None:
                        right[col] = candidate
                        queue.append(("col", col))
                    elif right[col] != candidate:
                        raise ValueError("inconsistent column scaling")
            else:
                col_scale = right[idx]
                if col_scale is None:
                    raise ValueError("internal column scale error")
                for row in col_edges[idx]:
                    ratio = (token_basis[row][idx] * mod_inv(carrier_basis[row][idx], prime)) % prime
                    candidate = (ratio * mod_inv(col_scale, prime)) % prime
                    if left[row] is None:
                        left[row] = candidate
                        queue.append(("row", row))
                    elif left[row] != candidate:
                        raise ValueError("inconsistent row scaling")

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

def first_nonzero_principal_down(matrix: list[list[int]]) -> int:
    size = len(matrix)
    for index in range(size):
        value = matrix[index][index] % PRIME
        if value != 0:
            return value
    raise ValueError("principal diagonal is all zero")

def first_nonzero_principal_up(matrix: list[list[int]]) -> int:
    size = len(matrix)
    for index in range(size - 1, -1, -1):
        value = matrix[index][index] % PRIME
        if value != 0:
            return value
    raise ValueError("principal diagonal is all zero")

def first_nonzero_secondary_down(matrix: list[list[int]]) -> int:
    size = len(matrix)
    for index in range(size):
        value = matrix[index][size - 1 - index] % PRIME
        if value != 0:
            return value
    raise ValueError("secondary diagonal is all zero")

def first_nonzero_secondary_up(matrix: list[list[int]]) -> int:
    size = len(matrix)
    for index in range(size - 1, -1, -1):
        value = matrix[index][size - 1 - index] % PRIME
        if value != 0:
            return value
    raise ValueError("secondary diagonal is all zero")

def power_parameters(session_key: list[list[int]]) -> tuple[int, int]:
    m_value = (first_nonzero_secondary_up(session_key) * first_nonzero_secondary_down(session_key)) % PRIME
    n_value = (first_nonzero_principal_down(session_key) * first_nonzero_principal_up(session_key)) % PRIME
    if m_value == 0 or n_value == 0:
        raise ValueError("power parameters unexpectedly vanished")
    return m_value, n_value

def setup_common_key(p_matrix: list[list[int]], g_matrix: list[list[int]], a_prime: list[list[int]], b_prime: list[list[int]]) -> tuple[list[list[int]], int, int]:
    g_basis = change_basis(g_matrix, p_matrix, PRIME)
    a_prime_basis = change_basis(a_prime, p_matrix, PRIME)
    b_prime_basis = change_basis(b_prime, p_matrix, PRIME)
    left_scale, right_scale = outer_factor_vectors(a_prime_basis, g_basis, PRIME)
    key_basis = scale_rows_and_cols(b_prime_basis, left_scale, right_scale, PRIME)
    session_key = conjugate(key_basis, p_matrix, PRIME)
    m_value, n_value = power_parameters(session_key)
    return session_key, m_value, n_value

def recursively_update_key(session_key: list[list[int]], m_value: int, n_value: int) -> tuple[list[list[int]], int, int]:
    updated_key = mat_pow(session_key, (m_value * n_value) % PRIME, PRIME)
    next_m, next_n = power_parameters(updated_key)
    return updated_key, next_m, next_n

def update_public_matrices(session_key: list[list[int]], m_value: int, n_value: int, p_matrix: list[list[int]], g_matrix: list[list[int]]) -> tuple[list[list[int]], list[list[int]]]:
    left = mat_pow(session_key, m_value, PRIME)
    right = mat_pow(session_key, n_value, PRIME)
    next_p = mat_mul(mat_mul(left, p_matrix, PRIME), right, PRIME)
    next_g = mat_mul(mat_mul(left, g_matrix, PRIME), right, PRIME)
    return next_p, next_g

def matrix_to_bytes(matrix: list[list[int]]) -> bytes:
    return bytes(value for row in matrix for value in row)

def extract_flag_from_matrix(message: list[list[int]]) -> str:
    match = FLAG_PATTERN.search(matrix_to_bytes(message))
    if not match:
        raise ValueError("flag marker not found in recovered message")
    return match.group().decode("ascii")

def code_to_bytes(code: int, code_bits: int) -> bytes:
    if not 0 <= code < (1 << code_bits):
        raise ValueError("code out of range")
    return code.to_bytes((code_bits + 7) // 8, "little")

def derive_bruteforce_stream(code: int, code_bits: int, pbkdf2_rounds: int, salt: bytes, nonce: bytes, out_len: int) -> list[int]:
    stretched = hashlib.pbkdf2_hmac("sha256", code_to_bytes(code, code_bits), salt, pbkdf2_rounds, dklen=32)
    raw = hashlib.shake_256(b"IHateMath|journal-brute|" + stretched + nonce).digest(out_len)
    return [value % PRIME for value in raw]

def decrypt_flag_blob(message: list[list[int]], code: int, code_bits: int, pbkdf2_rounds: int, salt: bytes) -> str:
    blob = list(matrix_to_bytes(message))
    nonce = bytes(blob[:16])
    ciphertext = blob[16:]
    stream = derive_bruteforce_stream(code, code_bits, pbkdf2_rounds, salt, nonce, len(ciphertext))
    plaintext = bytes((c - s) % PRIME for c, s in zip(ciphertext, stream))
    return extract_flag_from_matrix([list(plaintext)])

def _attempt_decrypt_wrapper(candidate: int, message: list[list[int]], code_bits: int, pbkdf2_rounds: int, salt: bytes) -> str | None:
    try:
        return decrypt_flag_blob(message, candidate, code_bits, pbkdf2_rounds, salt)
    except ValueError:
        return None

def recover_message_matrix(p_matrix: list[list[int]], g_matrix: list[list[int]], b_prime: list[list[int]], y1: list[list[int]], y2: list[list[int]]) -> str:
    g_basis = change_basis(g_matrix, p_matrix, PRIME)
    b_prime_basis = change_basis(b_prime, p_matrix, PRIME)
    y1_basis = change_basis(y1, p_matrix, PRIME)
    left_j, right_j = outer_factor_vectors(y1_basis, g_basis, PRIME)
    mask_basis = scale_rows_and_cols(b_prime_basis, left_j, right_j, PRIME)
    mask = conjugate(mask_basis, p_matrix, PRIME)
    return mat_mul(y2, mat_inv(mask, PRIME), PRIME)

def solve_public(public: dict[str, object]) -> str:
    print("[*] Mengekstrak dan memulihkan matriks pesan...")
    current_p = public["setup"]["P"]
    current_g = public["setup"]["G"]
    current_b_prime = public["setup"]["B_prime"]
    current_key, current_m, current_n = setup_common_key(current_p, current_g, public["setup"]["A_prime"], current_b_prime)

    for session in public["sessions"]:
        current_key, current_m, current_n = recursively_update_key(current_key, current_m, current_n)
        current_p, current_g = update_public_matrices(current_key, current_m, current_n, current_p, current_g)
        current_b_prime = session["B_prime"]

    message = recover_message_matrix(current_p, current_g, current_b_prime, public["cipher"]["y1"], public["cipher"]["y2"])
    
    brute = public["bruteforce"]
    code_bits = brute["code_bits"]
    pbkdf2_rounds = brute["pbkdf2_rounds"]
    salt = bytes.fromhex(brute["salt"])
    
    total_candidates = 1 << code_bits
    cores = multiprocessing.cpu_count()
    print(f"[*] Menjalankan fase Bruteforce dengan {cores} CPU cores untuk {total_candidates} kemungkinan...")
    
    worker_func = partial(_attempt_decrypt_wrapper, message=message, code_bits=code_bits, pbkdf2_rounds=pbkdf2_rounds, salt=salt)
    
    with multiprocessing.Pool(processes=cores) as pool:
        for result in tqdm(pool.imap_unordered(worker_func, range(total_candidates), chunksize=500), total=total_candidates, desc="Bruteforcing"):
            if result is not None:
                pool.terminate()
                return result

    raise ValueError("Bruteforce search exhausted without finding the flag")

def main() -> None:
    target_file = 'dist/output.json' if os.path.exists('dist/output.json') else ('public/output.json' if os.path.exists('public/output.json') else 'output.json')
    
    if not os.path.exists(target_file):
        print(f"[-] ERROR: File '{target_file}' tidak ditemukan.")
        return

    print(f"[+] Membaca file '{target_file}'...")
    with open(target_file, 'r', encoding="utf-8") as f:
        public = json.loads(f.read())
        
    flag = solve_public(public)
    print("\n========================================")
    print(f"FLAG Found:\n{flag}")
    print("========================================")

if __name__ == "__main__":
    main()