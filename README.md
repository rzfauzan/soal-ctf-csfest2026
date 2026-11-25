# 🛡️ CSF CTF 2026 - Master Handbook & Kunci Jawaban (Khusus PJ / Panitia)

> **DOKUMEN RAHASIA PANITIA & JURI CTF**  
> Seluruh flag resmi telah distandarisasi ke format: `CSF{...}`.  
> Semua 15 soal telah siap di direktori: `C:\Users\yaanz\.gemini\antigravity\scratch\csf-ctf-challenges\`

---

## 📊 Master Table: 15 Soal, Flag, & Port

| No | Kategori | Tingkat | Nama Soal | Flag Resmi (`CSF{...}`) | Akses / File Peserta | Intended Solution / Celah |
| :-: | :---: | :---: | :--- | :--- | :--- | :--- |
| 1 | **Web** | Mudah | **Stars** | `CSF{i_l0v3_a_milli0n_0f_th3_st4rs_sh1n1ng}` | `http://<ip-server>:8001` | Reverse proxy header injection (`X-Stars-Identity`). |
| 2 | **Web** | Mudah | **LEVI** | `CSF{tr4v3rs1ng_thr0ugh_d1r3ct0ry_l3v1_bypass}` | `http://<ip-server>:8002` | Path traversal PHP bypass filter `str_replace` dengan `....//`. |
| 3 | **Web** | Sedang | **Open Sesame** | `CSF{opeeeeeen_plsss5s_opennnnnn_ses4mee3e}` | `http://<ip-server>:8003` | Memory line limit exploit pada custom HTTP parser. |
| 4 | **Web** | Sedang | **Kucing LKS Jinja** | `CSF{m30w_sst1_kuc1ng_j1nja2_3xpl01t3d}` | `http://<ip-server>:8004` | Jinja2 SSTI dengan bypass filter kata kunci terlarang. |
| 5 | **Web** | Sulit | **Itechno Store** | `CSF{woooowwww_th3_st0r3_1s_gr34t!_h0w_tF_u_H4ck_tHe_sYstEm_br0?!}` | `http://<ip-server>:8005` | Pre-auth session bridge abuse + cPanel CRLF header injection. |
| 6 | **Crypto** | Mudah | **Too Easy** | `CSF{ini_soal_kripto_paling_gampang}` | `chall.py` | Caesar / Shift cipher posisi index dengan charset printable. |
| 7 | **Crypto** | Mudah | **Baby RSA** | `CSF{the_fl4g_length_1s_68_byt3s_s0_1ts_v3ry_easy_t0_s0lv3_1t_r1ght!}` | `output.txt`, `chall.py` | RSA linear relation algebra + brute-force small prime bits. |
| 8 | **Crypto** | Sedang | **Not Too Hard** | `CSF{now_you_understand_that_ch1n3se_rem41nder_1s_us3d_yup?????}` | `chall.py` | Chinese Remainder Theorem (CRT) dengan 5 modul coprime. |
| 9 | **Crypto** | Sedang | **Pikachu** | `CSF{p1k4Chu_l00ks_ador4ble_4nd_i_L0VE_pik4chu}` | `output.txt`, `chall.py` | Post-quantum hash-based signature brute-force 22-bit debug code. |
| 10 | **Crypto** | Sulit | **IHateMath** | `CSF{3l_G4m4R_Ciph3r_1s_g00d_4nd_1_l0ve_1t}` | `output.json`, paper PDF | Non-commutative group / Matrix conjugate Diffie-Hellman & LWE. |
| 11 | **Forensic**| Mudah | **Very Baby Easy** | `CSF{my_extension_is_wrong}` | `archive.zip` | File masquerading: ubah ekstensi dari `.zip` ke `.jpg`/buka header. |
| 12 | **Forensic**| Mudah | **Zippo** | `CSF{z1pp0_m4st3r_unz1p_4ll_l4y3rs_67}` | `challenge.zip` | 67-layer nested zip extraction automation script. |
| 13 | **Forensic**| Sedang | **browto** | `CSF{s4b4r_4d4_yg_m3r4nt4u3}` | `browto.zip` | SQLite Chromium `History` triage (XNOR decryption keyword/metadata). |
| 14 | **Forensic**| Sedang | **Bank Flag** | `CSF{C4rv1ng_Dokum3nt4si_F0ren}` | `disk.img` | FAT32 Disk carving: gabungkan `header.bin` + `chunk.bin` + `eof.bin` jadi PDF. |
| 15 | **Forensic**| Sulit | **tingtingtungtungting**| `CSF{pingpingpungpungping_pingpingpungpungping_haaaaaaaaaacchiiiiiimiiiiiiiii_2026}` | `hachimiiiiii.zip` | Multi-layer audio steganography (LSB samples + XOR metadata chunks). |

---

## 🚀 Panduan Deployment Kategori Web (Docker)

Semua 5 soal Web telah diintegrasikan ke dalam satu file **Master Docker Compose** di:
`C:\Users\yaanz\.gemini\antigravity\scratch\csf-ctf-challenges\Web\docker-compose.yml`

### Cara Menjalankan Semua Soal Web Sekaligus:
Di terminal server/VPS lomba Anda, jalankan:
```bash
cd Web
docker compose up -d --build
```

### Verifikasi Uptime & Healthcheck:
```bash
# Periksa status container
docker compose ps

# Test respon masing-masing soal dari terminal
curl -I http://localhost:8001  # Stars
curl -I http://localhost:8002  # LEVI
curl -I http://localhost:8003  # Open Sesame
curl -I http://localhost:8004  # Kucing LKS Jinja
curl -I http://localhost:8005  # Itechno Store
```

### Resource Requirements (Estimasi):
* **RAM Rekomendasi:** 2 GB – 4 GB (semua container sangat ringan karena berbasis Alpine/Python/PHP standard).
* **CPU:** 1-2 vCPU cukup untuk melayani 30–100 tim secara bersamaan.

---

## 💡 Kebijakan Rilis Hint (Jika Peserta Buntu)

Jika setelah 2–3 jam lomba berjalan belum ada peserta yang memecahkan soal tertentu (*first blood*), PJ dapat merilis hint resmi berikut:

### Kategori Web:
* **Stars:** *"Perhatikan bagaimana header dikirim dari reverse proxy frontend ke backend internal."*
* **LEVI:** *"Filter PHP hanya menghapus '../' satu kali secara rekursif atau langsung diganti kosong?"*
* **Open Sesame:** *"Berapa batasan panjang line header yang diizinkan oleh parser sebelum buffer memory mulai bocor?"*
* **Kucing LKS Jinja:** *"Jinja2 tidak hanya bisa mengakses variabel biasa, eksplorasi MRO (Method Resolution Order) dan `__subclasses__()`."*
* **Itechno Store:** *"Fitur login kompatibilitas lama menerima request CRLF injection pada header Authorization."*

### Kategori Cryptography:
* **Too Easy:** *"Coba perhatikan pola pergeseran huruf: apakah pergeserannya statis atau bertambah seiring posisi index karakter?"*
* **Baby RSA:** *"Ada relasi linier antara f, l, dan ag. Perhatikan bit twist kecil pada prime RSA yang bisa di-brute force."*
* **Not Too Hard:** *"5 buah bilangan prima besar yang saling koprima dan operasi sisa bagi modulo... Teorema sisa apa dari Tiongkok yang cocok?"*
* **Pikachu:** *"Debug code bawaan pabrik hanya memiliki panjang 22 bit. Brute-force PBKDF2 sangat feasible dalam hitungan menit."*
* **IHateMath:** *"Basis P sudah diberikan pada parameter publik. Gunakan perpindahan basis ke P untuk mengubah perkalian matriks menjadi perkalian diagonal."*

### Kategori Digital Forensics:
* **Very Baby Easy:** *"Apakah Anda yakin file tersebut benar-benar sebuah arsip ZIP? Coba cek magic bytes atau buka dengan file viewer."*
* **Zippo:** *"Jangan uncompress 67 layer secara manual. Gunakan script Python dengan library `zipfile` dan filter kata kuncinya."*
* **browto:** *"Artefak SQLite History Chromium menyimpan banyak hal: periksa tabel `keyword_search_terms`, `visits`, dan `downloads`."*
* **Bank Flag:** *"File dokumen PDF terpecah menjadi 3 bagian di direktori Users. Coba gabungkan kembali ketiga fragmen tersebut sesuai urutannya."*
* **tingtingtungtungting:** *"Periksa bit paling tidak signifikan (LSB) pada audio dan periksa pula metadata ID3/RIFF INFO chunk untuk menemukan XOR key."*

---

## ⚙️ Skema Scoring Dinamis di CTFd
* **Initial Points:** `500`
* **Minimum Points:** `100`
* **Decay Rate:** `15` solves (poin akan menurun bertahap dari 500 ke 100 saat soal diselesaikan oleh 1 sampai 15 tim).
* Ini memastikan soal yang sulit tetap bernilai tinggi, sedangkan soal yang mudah nilainya otomatis turun secara adil.

