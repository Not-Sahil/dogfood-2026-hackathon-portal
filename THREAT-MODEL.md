# Threat Model

This document records the implemented controls and the remaining limitations.

| Threat | Control | Limitation |
|---|---|---|
| Judge collusion / peer-score exposure | Judge-specific score route; organizer/admin-only peer access | Compromised organizer/admin credentials remain privileged |
| Sybil community voting | Authenticated participant votes; one vote per participant/project | No real-world identity verification |
| Ballot stuffing | Per-event vote allowance and short-window address rate limit | IP-based rate limiting is not a substitute for identity proof |
| Duplicate ballot replay | Unique DB constraint on event/voter/project | Prevents duplicates for the same account, not account creation abuse |
| Submission duplication | Repository/title fingerprint scan | Fingerprints are signals for organizer review, not proof of plagiarism |
| Submission scraping | Public gallery exposes submitted-project metadata | Public galleries are intentionally browsable |
| Deadline gaming | Submission deadline is enforced in backend event logic | Server clock is the trusted source |
| Webhook tampering | HMAC-SHA256 signature | Endpoint operator must protect its secret |
| Judge-record forgery | Ed25519 signatures plus public verification key | Private signing key must remain local and protected |
