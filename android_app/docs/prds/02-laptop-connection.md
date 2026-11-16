# OOTD-02 — Laptop connection and pairing

Version 1.0 · 20 October 2026 · Owner: Mobile/Backend · Status: proposed.

## 1. Overview and scope

Objective: connect an Android phone to the intended laptop service on the same Wi-Fi and recover when the address changes. Personas: owner setting up the app and returning owner after laptop sleep. Pain: typing addresses, untrusted hosts and confusing network errors.

In scope: manual address entry, QR bootstrap, server identity verification, readiness and reconnection. Out: public internet exposure, router port forwarding, cloud hosting, Wi-Fi configuration and database access from the phone.

Verified: F5 is FastAPI but no dedicated pairing/health API was found in its route source. All contracts here are proposed. Pairing recognizes a laptop; it does not log into a user account.

## 2. Functional requirements and acceptance criteria

| Requirement | Acceptance criterion |
|---|---|
| FR1 Discover intended service | QR or manual setup records HTTPS origin and stable `server_id`; invalid scheme/host/port is rejected before account credentials are sent. |
| FR2 Verify server identity | Scanned bootstrap fingerprint must match the certificate; manual flow compares a fingerprint displayed on the laptop. Changed certificate/server ID requires re-verification. |
| FR3 Report readiness | API ready/AI warming/AI unavailable are distinct. Users may browse while AI is warming. Database unavailable reports service unavailable. |
| FR4 Reconnect safely | Same server at a new verified address retains account selection; different server clears server-bound sessions and caches. |
| FR5 Recover within bounded waits | Connection attempt times out after 5s; UI offers retry and specific Wi-Fi/laptop/firewall guidance without automatic infinite polling. |
| FR6 Expose only required service | PostgreSQL stays laptop-local; HTTPS API access is limited to the intended private network; logs contain no bootstrap secret. |

## 3. Flow

Laptop startup creates stable identity/certificate and displays a bootstrap QR containing origin, server UUID and public certificate fingerprint. No account token/password is embedded. Phone scans or enters the same fields, verifies the server, requests health, stores the pair and proceeds to login.

```mermaid
sequenceDiagram
  participant O as Owner
  participant P as Phone
  participant L as Laptop HTTPS service
  O->>P: Scan laptop QR or enter address/fingerprint
  P->>L: TLS handshake with expected identity
  L-->>P: Certificate
  P->>P: Verify fingerprint and server binding
  P->>L: GET /api/v1/health
  L-->>P: server_id, API and AI readiness
  P->>P: Persist paired server
  P-->>O: Connected; continue to login
```

## 4. Frontend

Light F5 cards and sage primary action. Fields: address, optional port, verification fingerprint; QR camera permission is separate from garment capture. Hide advanced details until needed. Camera denial always leaves manual setup available.

States: unpaired, scanning, validating, connected, AI warming, offline, untrusted, incompatible version. Save only verified origin and identity in local settings; auth tokens use separate secure storage. Prevent double-tap connection requests; cancel an old attempt when input changes. Android back stops scanning and cancels pending health requests.

No private payload or credentials to a speculative address. Reject `http`, user-info URLs, paths/query strings and redirect-to-other-host responses for authenticated traffic. Development HTTP can only be a separately labelled test build with synthetic accounts; it is not the release default.

## 5. Backend and proposed API

`GET /api/v1/health`: no auth/body; `Accept: application/json`. Fixed-size allowlisted response; rate limit proposed 60/minute per network client. Implementation checks DB connectivity with a short timeout and cached worker readiness; it must not trigger inference or model downloads per request.

```http
GET /api/v1/health
Accept: application/json

200 OK
{"server_id":"10000000-0000-4000-8000-000000000001","api_version":"1","status":"ready","ai_status":"warming"}
```

Failure:

```json
{"error":{"code":"SERVER_NOT_READY","message":"Laptop service is starting.","retryable":true},"request_id":"r-20"}
```

Return `503` for DB/service unavailable and `Retry-After: 5`; `429` for excess probes. A TLS mismatch is a client connection error, not an HTTP status. Unsupported `api_version` blocks protected requests. Network timeout has client code `SERVER_UNREACHABLE`.

No remote “change server certificate,” unauthenticated pairing-write API, or remote server shutdown route is introduced. Bootstrap display is laptop-local. The proposed certificate strategy is a laptop-specific trust anchor/fingerprint configured in the app's networking layer; normal expiry/hostname checks remain. Validate that chosen Flutter libraries support this before declaring setup ready.

## 6. Data, consistency, security and operations

Proposed local laptop configuration: stable `server_id`, HTTPS identity/certificate and private key; private key stays laptop-only. Phone stores origin, expected certificate identity, `server_id`, API version and last verified time. No pairing table is required for v1.

Concurrent successful attempts use a generation ID so an old response cannot overwrite a new selection. Compare server UUID only after the secure connection is established. API errors must omit LAN IP, filesystem path and software internals.

Health target: p95 ≤300ms warm LAN; probe no more than once/30s while the connection screen is visible, pause in background. Logs: readiness transitions and anonymous request ID; metrics: probe latency, worker readiness age, DB unavailable duration. Alert the laptop operator after 60s DB failure, without sending photos or credentials externally.

[Android network security documentation](https://developer.android.com/privacy-and-security/security-config) describes configurable trust anchors and debug-only trust overrides. Actual Flutter transport behavior must also be tested.

## 7. Analytics

Consented envelope: event UUID/version, UTC time, anonymous or account `distinct_id`, nullable `user_id`, app `session_id`, platform, app version, screen and source. Never send address, certificate fingerprint or QR contents.

| Event | Trigger | Properties with type/example |
|---|---|---|
| `server_connection_started` | Valid setup attempt | `operation_id:uuid`, `method:enum(qr,manual)`, `attempt:int=1` |
| `server_connection_succeeded` | Verified health response | `operation_id:uuid`, `duration_ms:int=220`, `ai_status:enum` |
| `server_connection_failed` | Attempt terminates | `error_code:enum(tls_mismatch,timeout,incompatible,not_ready)`, `retryable:bool` |
| `server_connection_retried` | Explicit retry | `operation_id:uuid`, `attempt:int=2` |
| `server_connection_abandoned` | User leaves active setup | `operation_id:uuid`, `last_step:enum` |

Payload properties example: `{"method":"qr","attempt":1,"duration_ms":220,"ai_status":"ready"}` plus envelope. One terminal outcome per attempt; abandon only on explicit exit. Inferred drop-off is no success within 10 minutes, with timeouts reported separately.

KPI: verified successes / started attempts; p95 connection duration excluding user entry; failures by allowlisted reason. Target ≥95% success on a supported, correctly configured LAN.

## 8. Tests

| ID | Preconditions/scenario | Steps | Expected | Priority/type |
|---|---|---|---|---|
| T01 | Running trusted laptop | Scan QR → connect | Matching server stored; login opens | P0 integration |
| T02 | Camera denied | Open scanner → manual setup | Manual works without camera permission | P1 UI/negative |
| T03 | Wrong certificate | Enter genuine address, wrong fingerprint | No credentials sent; trust error | P0 security |
| T04 | Malicious QR with HTTP/user-info/redirect | Scan each | Rejected or explicit secure verification failure | P0 security/API |
| T05 | Laptop asleep/firewall blocked | Connect; retry after wake | ≤5s failure then recovery | P0 recovery |
| T06 | Same server new IP | Re-pair new verified address | Correct account context retained | P1 regression |
| T07 | Different server same address | Connect | Clear old tokens/caches; require login | P0 security |
| T08 | DB down, AI warming, API incompatible | Stub each health result | Three distinct usable states | P0 API/UI |
| T09 | Rapid address edits/taps | Launch overlapping probes | Only latest attempt persists | P1 concurrency |
| T10 | 100 warm probes; consent toggled | Measure and inspect events | p95 target; throttling; no addresses in events | P1 performance/analytics |

FR1/2→T01–04/07; FR3→T08; FR4→T05–07; FR5→T05/09; FR6→T03/04/10 plus deployment review.

## 9. Implementation and open decisions

Backend: HTTPS bootstrap, persistent identity, health probes, private-network runbook. Mobile: scanner/manual fallback, trust verification, connection state controller. QA: physical phone on target router, certificate rotation and airplane mode. Analytics: per-attempt correlation.

Dependencies: 04 account session boundaries, 19 DB, 20 release network configuration. Blockers before release: supported Android version, actual network access permissions for selected target SDK, certificate bootstrap verified on the phone. Laptop sleep and guest-Wi-Fi client isolation are operational constraints.

## 10. Release readiness

- [ ] Trusted QR/manual connection and changed-identity tests pass.
- [ ] Auth/media never sent over unverified or cleartext release connection.
- [ ] DB port remains private; failure recovery documented.
- [ ] Readiness, event redaction and rate limits verified.
- [ ] Owner can repeat setup without developer tools.
