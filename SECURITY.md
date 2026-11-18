# Security

Caramelo acts on behalf of older adults, so the safety rules below are enforced in code
(`app/services/secure_session.py`) and are covered by tests. They do not depend on the LLM.

| Rule | Enforcement |
| --- | --- |
| Consent before any login, submit or payment click | `SENSITIVE_ACTION` gate, `consent_request` message |
| Passwords and captchas are entered only by the user | Credential handover; the agent never fills `type=password` |
| Keystrokes are not logged or sent to the model | Forwarded straight to the page in `_receive` |
| No banking sites in the secure session | `BLOCKED_HOST_FRAGMENTS` |
| Nothing persists after a session | Browser destroyed in `finally` |
| Risk events are anonymous | Only kind, score and coarse region are stored; TTL index expires them |

## Known limitations

- The demo has no authentication or rate limiting. Do not expose it publicly as is.
- The link scanner fetches arbitrary URLs. In production it must run in an isolated
  network segment that cannot reach internal services (SSRF).
- Frames of the live view travel over the WebSocket; production requires TLS (`wss`).

## Reporting a vulnerability

Open a private security advisory on this repository. Please do not file public issues for vulnerabilities.
