# Echo Cert Signing Keys — Runbook

## TL;DR

- Echo signs certs with ed25519 (32-byte seed)
- Public key is **embedded in `echo-verify`** at release time
- Private key lives in **Fly secrets** / **AWS Secrets Manager** — never in repo

## Generate a new key pair

```bash
python -c "
from nacl.signing import SigningKey
import base64
sk = SigningKey.generate()
print('key_id  :', 'echo-cert-' + __import__('datetime').date.today().strftime('%Y-q%m')[:-1] +
      str(((__import__('datetime').date.today().month - 1) // 3) + 1))
print('seed    :', base64.b64encode(bytes(sk)).decode())
print('public  :', base64.b64encode(bytes(sk.verify_key)).decode())
"
```

## Deploy the private key

```bash
fly secrets set \
  CERT_SIGNING_KEY_INLINE='<base64 seed>' \
  CERT_SIGNING_KEY_ID='echo-cert-2026-q2' \
  -a echo-api
```

## Publish the new public key

1. Edit `packages/verify-cert-python/echo_verify/keys.py`:

   ```python
   EMBEDDED_KEYS = (
       PublicKey(
           key_id="echo-cert-2026-q2",
           public_key_b64="<your new public key b64>",
           valid_from_ts=<unix ts of activation>,
           valid_until_ts=<unix ts of retirement, ~6 months later>,
           purpose="cert-issuance",
       ),
       # ... older keys retained for verifying old certs ...
   )
   ```

2. Edit `packages/verify-cert-js/src/keys.ts` with the same key.

3. Add a golden vector test (sign a known payload with the new key, verify both
   libraries agree).

4. Bump versions: `0.4.3 → 0.4.4`.

5. Release:
   ```bash
   cd packages/verify-cert-python && python -m build && twine upload dist/*
   cd packages/verify-cert-js && npm version 0.4.4 && npm publish
   ```

## Rotation policy

- **Cadence**: quarterly (90 days)
- **Overlap**: new key is published 30 days before old key stops signing
- **Retention**: old keys remain in the registry **forever** — verifying old
  certs must always work
- **Compromise response**: see `COMPROMISE_RUNBOOK.md`

## Compromise checklist

If a signing key is suspected compromised:

1. [ ] **Stop using the key immediately** (clear the Fly secret)
2. [ ] Generate + deploy a new key
3. [ ] **Mark the old key as compromised** in `keys.py`:
   ```python
   PublicKey(
       key_id="echo-cert-...",
       compromised_at_ts=<unix ts>,
       ...
   )
   ```
4. [ ] Publish a notice on `status.echo.ai`
5. [ ] Re-issue affected certs with the new key
6. [ ] Update `verify-cert` to refuse signatures with `compromised_at` set
7. [ ] Post-mortem within 7 days

## Never do these

- ❌ Commit a signing key to git
- ❌ Store a signing key in `.env`
- ❌ Use the same key across environments (dev/staging/prod)
- ❌ Use the dev key (`echo-cert-dev`) in production
- ❌ Delete a public key from `keys.py` (only mark expired/compromised)
