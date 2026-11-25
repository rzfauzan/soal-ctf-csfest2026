from pathlib import Path

from Crypto.Util.number import GCD, bytes_to_long, getPrime

BITS = 11


def load_flag() -> bytes:
    base_dir = Path(__file__).resolve().parent
    candidates = (
        Path.cwd() / "flag",
        base_dir / "flag",
        base_dir.parent / "flag",
        base_dir.parent / "solver" / "flag",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.read_bytes()
    raise FileNotFoundError("flag file not found")


while True:
    p = getPrime(1024)
    q = getPrime(1024)
    e = 0x11
    if GCD((p - 1) * (q - 1), e) == 1:
        break
N = p * q

flag = load_flag()
assert len(flag) == 68

f, l, ag = flag[:17], flag[17:34], flag[34:]
f, l, ag, flag = map(bytes_to_long, (f, l, ag, flag))

twist = ((p ^ q) >> 1) & ((1 << BITS) - 1)
u = 2 * f + l + (7 + twist) * ag
v = f + 3 * l + (11 + 2 * twist) * ag

assert u < N and v < N and ag < N and flag < N

f_enc = pow(u, e, N)
l_enc = pow(v, e, N)
ag_enc = pow(ag, e, N)
flag_enc = pow(flag, e, N)

print(f"{N = }")
print(f"{e = }")
print(f"{f_enc = }")
print(f"{l_enc = }")
print(f"{ag_enc = }")
print(f"{flag_enc = }")
