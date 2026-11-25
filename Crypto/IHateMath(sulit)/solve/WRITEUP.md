# Intended Solve

Public setup:

- `P`
- `G`
- `A' = A^k1 G A^k2`
- `B' = B^r1 G B^r2`

Karena `A = P D_A P^{-1}` dan `B = P D_B P^{-1}`, basis `P` justru sudah diberikan ke pemain. Jadi langkah pertama bukan diagonalization, tetapi pindah ke basis `P`:

- `G* = P^{-1} G P`
- `A'* = P^{-1} A' P = D_A^k1 G* D_A^k2`
- `B'* = P^{-1} B' P = D_B^r1 G* D_B^r2`

Dari `A'* / G*` factor mask kiri-kanan, lalu pasang mask itu ke `B'*` untuk recover first common key:

- `K = A^k1 B' A^k2 = B^r1 A' B^r2`

Berikutnya hitung:

- `m = K_{d,1↗} . K_{1,d↙}`
- `n = K_{1,1↘} . K_{d,d↖}`

Lalu replay protokol baru sesudah setup, persis seperti jurnal:

1. `K <- K^(m.n)`
2. hitung `m, n` baru dari `K`
3. `P <- K^m P K^n`
4. `G <- K^m G K^n`
5. dari `P` baru, bentuk `A = P D_A P^{-1}` dan `B = P D_B P^{-1}`
6. baca transcript publik `A' = A^m G A^n` dan `B' = B^m G B^n`
7. ulangi sampai sesi terakhir

Untuk cipher akhir:

- `y1 = J^m G J^n`
- `y2 = H (J^m B' J^n)`

Factor `y1 / G` di basis `P` untuk recover mask `J^m` dan `J^n`, bentuk `J^m B' J^n`, lalu hitung:

- `H = y2 (J^m B' J^n)^(-1)`

Di versi ini, `H` bukan flag langsung. `H` adalah blob 64-byte:

- `nonce[16] || ct[48]`

dengan semua byte diperlakukan sebagai elemen `F_251`. Setelah `H` pulih:

1. Ambil 16 byte pertama sebagai `nonce`.
2. Ambil 48 byte sisanya sebagai ciphertext aditif modulo `251`.
3. Brute-force `code` 23-bit.
4. Untuk tiap kandidat, hitung:
   - `stretched = PBKDF2-HMAC-SHA256(code_le, salt, 2500, 32)`
   - `stream = SHAKE256("IHateMath|journal-brute|" || stretched || nonce)`
   - stream dibatasi ke `F_251` dengan `byte mod 251`
   - `pt_i = (ct_i - stream_i) mod 251`
5. Cari plaintext yang memuat pola `ITECHNO26{...}`.