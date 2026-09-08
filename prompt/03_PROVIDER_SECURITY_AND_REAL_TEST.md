# P0 — PROVIDER SECURITY + REAL TEST

A credential was previously exposed in tool output.

Before any network request:
1. rotate/revoke old credential
2. store new credential only in OS secret store
3. never echo raw key
4. never log Authorization header
5. never commit secret
6. never display full key

Until rotation:
`CONFIGURED_UNVERIFIED`, never `CONNECTED`.

Provider Manager must allow user-managed:
- name
- provider type
- base URL
- API key
- model ID
- test
- sync models
- disconnect

9Router is one provider, not a hard-coded singleton.

Real test:
send one tiny nonce request and verify exact response.

States:
- UNCONFIGURED
- CONFIGURED_UNVERIFIED
- TESTING
- CONNECTED
- AUTH_ERROR
- RATE_LIMITED
- NO_CREDIT
- OFFLINE
- MODEL_ERROR

Model sync must be real if endpoint supports it.
Otherwise allow manual canonical model ID.

PASS only when:
- real network request succeeds
- real model identified
- redaction tests pass
