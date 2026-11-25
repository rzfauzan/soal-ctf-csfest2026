import argparse
import sys
from itertools import product
from pathlib import Path
from time import perf_counter

from Crypto.Util.number import inverse
from fpylll import IntegerMatrix, LLL

OUTPUT = Path(__file__).resolve().parents[1] / "public" / "output.txt"
FLAG_LEN = 68
HEAD_LEN = 17
TAIL_LEN = 34
CHUNK_BITS = 8 * HEAD_LEN
TAIL_BITS = 8 * TAIL_LEN
BRUTE_BITS = 11


def trim(poly):
    while len(poly) > 1 and poly[-1] == 0:
        poly.pop()
    return poly


def y_add(a, b, mod):
    size = max(len(a), len(b))
    out = [0] * size
    for i in range(size):
        av = a[i] if i < len(a) else 0
        bv = b[i] if i < len(b) else 0
        out[i] = (av + bv) % mod
    return trim(out)


def y_sub(a, b, mod):
    size = max(len(a), len(b))
    out = [0] * size
    for i in range(size):
        av = a[i] if i < len(a) else 0
        bv = b[i] if i < len(b) else 0
        out[i] = (av - bv) % mod
    return trim(out)


def y_mul(a, b, wrap, deg, mod):
    out = [0] * (len(a) + len(b) - 1)
    for i, av in enumerate(a):
        if av == 0:
            continue
        for j, bv in enumerate(b):
            if bv == 0:
                continue
            out[i + j] += av * bv
            
    for idx in range(len(out) - 1, deg - 1, -1):
        coeff = out[idx] % mod
        if coeff:
            out[idx - deg] += coeff * wrap
            
    return trim([v % mod for v in out[:deg]] or [0])


def is_zero_y(poly):
    return len(poly) == 1 and poly[0] == 0


def x_trim(poly):
    while len(poly) > 1 and is_zero_y(poly[-1]):
        poly.pop()
    return poly


def x_sub(a, b, mod):
    size = max(len(a), len(b))
    out = [[0] for _ in range(size)]
    for i in range(size):
        av = a[i] if i < len(a) else [0]
        bv = b[i] if i < len(b) else [0]
        out[i] = y_sub(av, bv, mod)
    return x_trim(out)


def x_mul(a, b, wrap, deg, mod):
    out = [[0] for _ in range(len(a) + len(b) - 1)]
    for i, av in enumerate(a):
        for j, bv in enumerate(b):
            prod = y_mul(av, bv, wrap, deg, mod)
            out[i + j] = y_add(out[i + j], prod, mod)
    return x_trim(out)


def x_scalar_mul(poly, scalar, wrap, deg, mod):
    return x_trim([y_mul(coeff, scalar, wrap, deg, mod) for coeff in poly])


def x_pow(base, exp, wrap, deg, mod):
    result = [[1]]
    cur = base
    power = exp
    while power:
        if power & 1:
            result = x_mul(result, cur, wrap, deg, mod)
        cur = x_mul(cur, cur, wrap, deg, mod)
        power >>= 1
    return x_trim(result)


def z_mul(a, b, mod):
    out = [0] * (len(a) + len(b) - 1)
    for i, av in enumerate(a):
        if av == 0:
            continue
        for j, bv in enumerate(b):
            if bv == 0:
                continue
            out[i + j] += av * bv
    return trim([v % mod for v in out])


def z_pow(base, exp, mod):
    result = [1]
    cur = base
    power = exp
    while power:
        if power & 1:
            result = z_mul(result, cur, mod)
        cur = z_mul(cur, cur, mod)
        power >>= 1
    return trim(result)


def z_scalar_mul(poly, scalar, mod):
    return trim([(scalar * coeff) % mod for coeff in poly])


def z_sub(a, b, mod):
    size = max(len(a), len(b))
    out = [0] * size
    for i in range(size):
        av = a[i] if i < len(a) else 0
        bv = b[i] if i < len(b) else 0
        out[i] = (av - bv) % mod
    return trim(out)


def gcd_like(first, second, mod):
    p1 = first[:]
    p2 = second[:]
    while len(p2) > 1:
        lc1 = p1[-1]
        lc2 = p2[-1]
        p1 = z_scalar_mul(p1, lc2, mod)
        p2 = z_scalar_mul(p2, lc1, mod)
        shift = len(p1) - len(p2)
        shifted = [0] * shift + p2
        p1 = z_sub(p1, shifted, mod)
        if len(p1) < len(p2):
            p1, p2 = p2, p1
    return p1


def recover_root(poly, mod):
    lead = poly[-1]
    return (-poly[0] * inverse(lead, mod)) % mod


def load_values(path):
    namespace = {}
    exec(path.read_text(), {}, namespace)
    return namespace["N"], namespace["e"], namespace["f_enc"], namespace["l_enc"], namespace["ag_enc"], namespace["flag_enc"]


def build_flag(f, l, ag):
    return int(f).to_bytes(HEAD_LEN, "big") + int(l).to_bytes(HEAD_LEN, "big") + int(ag).to_bytes(TAIL_LEN, "big")


def looks_like_flag(candidate):
    if len(candidate) != FLAG_LEN:
        return False
    if not candidate.startswith(b"CSF{") or not candidate.endswith(b"}"):
        return False
    return all(32 <= ch <= 126 for ch in candidate)


def recover_ab_for_twist(twist, ratio_u, ratio_v, ratio_flag, e, mod, inv5, alpha, beta, gamma, delta):
    linear = [
        [((gamma + delta * twist) * inv5) % mod, (beta * inv5) % mod],
        [(alpha * inv5) % mod],
    ]
    f1 = x_pow(linear, e, ratio_v, e, mod)
    f1[0][0] = (f1[0][0] - ratio_flag) % mod
    f2 = [[(-ratio_u) % mod]] + [[0] for _ in range(e - 1)] + [[1]]

    while len(f2) > 1:
        lc1 = f1[-1]
        lc2 = f2[-1]
        f1 = x_scalar_mul(f1, lc2, ratio_v, e, mod)
        f2 = x_scalar_mul(f2, lc1, ratio_v, e, mod)
        shift = len(f1) - len(f2)
        shifted = [[0] for _ in range(shift)] + f2
        f1 = x_sub(f1, shifted, mod)
        if len(f1) < len(f2):
            f1, f2 = f2, f1

    g = f2[0]
    f3 = [(-ratio_v) % mod] + [0] * (e - 1) + [1]
    b_poly = gcd_like(g, f3, mod)
    if len(b_poly) != 2:
        return None
    b = recover_root(b_poly, mod)

    linear_x = [((gamma + delta * twist + beta * b) * inv5) % mod, (alpha * inv5) % mod]
    g1 = z_pow(linear_x, e, mod)
    g1[0] = (g1[0] - ratio_flag) % mod
    g2 = [(-ratio_u) % mod] + [0] * (e - 1) + [1]
    a_poly = gcd_like(g1, g2, mod)
    if len(a_poly) != 2:
        return None
    a = recover_root(a_poly, mod)
    return a, b


def candidate_rows(reduced_matrix):
    nrows = len(reduced_matrix)
    for row in reduced_matrix:
        yield tuple(int(value) for value in row)
        
    for i, j, k in product(range(nrows), repeat=3):
        if i == j == k == 0:
            continue
        combo = [0, 0, 0]
        for coeff, row_idx in zip((-1, 1, 2), (i, j, k)):
            row = reduced_matrix[row_idx]
            combo[0] += coeff * int(row[0])
            combo[1] += coeff * int(row[1])
            combo[2] += coeff * int(row[2])
        yield tuple(combo)


def recover_flag_from_ab(a, b, twist, mod, inv5):
    coeff_f = ((3 * a - b - 10 - twist) * inv5) % mod
    coeff_l = ((-a + 2 * b - 15 - 3 * twist) * inv5) % mod

    M = IntegerMatrix.from_matrix([
        [1, coeff_f, coeff_l],
        [0, mod, 0],
        [0, 0, mod],
    ])
    LLL.reduction(M)
    
    reduced = [[M[i, j] for j in range(M.ncols)] for i in range(M.nrows)]

    seen = set()
    for candidate in candidate_rows(reduced):
        ag = abs(candidate[0])
        if ag == 0 or ag in seen or ag.bit_length() > TAIL_BITS:
            continue
        seen.add(ag)
        f = (coeff_f * ag) % mod
        l = (coeff_l * ag) % mod
        if f.bit_length() > CHUNK_BITS or l.bit_length() > CHUNK_BITS:
            continue
        flag = build_flag(f, l, ag)
        if looks_like_flag(flag):
            return flag
    return None


def solve_range(output_path, start, stop, progress):
    N, e, f_enc, l_enc, ag_enc, flag_enc = load_values(output_path)

    ratio_u = f_enc * inverse(ag_enc, N) % N
    ratio_v = l_enc * inverse(ag_enc, N) % N
    ratio_flag = flag_enc * inverse(ag_enc, N) % N
    inv5 = inverse(5, N)
    base_34 = 256 ** 34
    base_51 = 256 ** 51

    alpha = (3 * base_51 - base_34) % N
    beta = (-base_51 + 2 * base_34) % N
    gamma = (-10 * base_51 - 15 * base_34 + 5) % N
    delta = (-base_51 - 3 * base_34) % N

    begin = perf_counter()
    checked = 0

    for twist in range(start, stop):
        recovered = recover_ab_for_twist(twist, ratio_u, ratio_v, ratio_flag, e, N, inv5, alpha, beta, gamma, delta)
        checked += 1

        if progress and checked % progress == 0:
            elapsed = perf_counter() - begin
            rate = elapsed / checked
            print(
                f"[+] checked {checked} twists in {elapsed:.2f}s ({rate:.3f}s each), current twist={twist}",
                file=sys.stderr,
                flush=True,
            )

        if recovered is None:
            continue

        a, b = recovered
        flag = recover_flag_from_ab(a, b, twist, N, inv5)
        if flag is not None:
            return twist, flag, perf_counter() - begin

    return None, None, perf_counter() - begin


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=1 << BRUTE_BITS)
    parser.add_argument("--progress", type=int, default=64)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    progress = 0 if args.quiet else args.progress
    twist, flag, elapsed = solve_range(args.output, args.start, args.stop, progress)
    if flag is None:
        raise ValueError(f"failed to recover the flag in range [{args.start}, {args.stop}) after {elapsed:.2f}s")
    print(flag.decode())
    print(f"[+] twist = {twist}, elapsed = {elapsed:.2f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
