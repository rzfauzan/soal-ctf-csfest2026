# PikaSPX - author notes

This is a brute-force challenge with a post-quantum theme.

Design:

1. A toy hash-based signature appliance derives its master seed from a weak 22-bit factory debug code.
2. The factory code is stretched with `PBKDF2-HMAC-SHA256`, then mapped into a small SPHINCS/XMSS-like Merkle tree public root.
3. The flag is encrypted with a stream key derived from the same stretched seed and the public root.
4. Public data contains only the KDF parameters, the public root, and the encrypted flag transcript.

Intended solve:

1. Enumerate every candidate debug code in ascending order.
2. For each candidate, recompute the stretched seed and the Merkle root.
3. Stop when the computed root matches the published `root`.
4. Re-derive the stream key and decrypt the flag.

Calibration:

- `code_bits = 22`
- `pbkdf2_rounds = 1710`
- `debug_code = 0x38769b`

On this machine, the bundled solver benchmarks the candidate rate first and estimates the hit time for the embedded author code. The production instance is tuned so a single-process Python brute run lands near the 30-minute mark.
