# Browto Writeup

1. Pastikan artefak adalah SQLite database Chromium History.

   ```bash
   file History
   sqlite3 History '.tables'
   ```

2. Ambil query yang diketik user secara manual. Query dengan pola `cache freshness bucket` berisi base32 dari ciphertext, bukan plaintext.

   ```sql
   SELECT term
   FROM keyword_search_terms
   WHERE term LIKE 'cache freshness bucket %'
   ORDER BY term;
   ```

   Ambil token terakhir dari setiap baris, gabungkan, lalu base32 decode. Decrypt hasilnya dengan XNOR memakai key dari BLOB `downloads.hash`:

   ```sql
   SELECT hex(hash)
   FROM downloads
   WHERE id = 1;
   ```

   Hasilnya berisi instruksi untuk layer berikutnya.

3. Ikuti instruksi layer pertama: ambil low byte `visit_time` dari visit ke `cdn-cache.local`, urut berdasarkan `visits.id`. Bytes ini masih ciphertext XNOR.

   ```sql
   SELECT visits.visit_time
   FROM visits
   JOIN urls ON urls.id = visits.url
   WHERE urls.url LIKE 'https://cdn-cache.local/%'
   ORDER BY visits.id;
   ```

   Untuk tiap nilai, ambil `visit_time & 255`. Decrypt dengan XNOR memakai:

   ```text
   sha256(meta.date_created|downloads.start_time|stage1_row_count)
   ```

   Hasilnya berisi `storage_key`, lokasi BLOB layer ketiga, dan instruksi key layer ketiga.

4. Ambil BLOB dari `typed_url_sync_metadata`.

   ```sql
   SELECT value
   FROM typed_url_sync_metadata
   WHERE storage_key = 31337;
   ```

   Bentuk key ketiga:

   ```text
   sha256(download.guid|download.etag|download.chain_tail)
   ```

   XNOR BLOB dengan key tersebut, lalu `zlib` decompress. Hasilnya adalah base64 PNG.

5. Pada versi final, hasil layer ketiga bukan potongan flag teks. Hasilnya adalah base64 PNG. Decode base64 tersebut menjadi file gambar.