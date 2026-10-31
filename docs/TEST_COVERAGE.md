# Backend workflow coverage audit

Updated October 22, 2026. This is a scenario coverage audit, not a claim of 100%
line/branch coverage or production certification.

Verification result: 281 full regression tests passed (up from 160); the optional
smoke selection has 28 passing cases. One dependency warning remains.

## Running the checks

Full regression suite:

    python -B -m pytest tests -q

Core smoke selection:

    python -B -m pytest tests -m smoke -q

The app server does not need to be running. Tests start an in-process HTTP client.
Each test has an isolated SQLite database and temporary photo directory. Test-only
JWT secrets, admin phones and business defaults are pinned in tests/conftest.py.
The running server's environment and .env file are not changed by a test process.

Unexpected requests/httpx network calls fail the tests. Geocoding, SMS and model
responses are mocked; the HTTP endpoints, role checks, ORM writes, image parsing,
graph routing, deadline logic, ledger hooks and notification hooks are exercised.

## Coverage map

| Area | Scenarios | Principal test files |
| --- | --- | --- |
| OTP and roles | Renter/reviewer signup, existing login, admin allowlist, role spoofing, leading-zero codes, cooldown, resend invalidation, expiry, attempts, replay, production OTP visibility, invalid tokens, self/admin user access | test_auth_flows.py, test_reliability.py |
| Job lifecycle | Create, distance-priced acceptance, visit, photos, submission, notes-only verification, approval, missing evidence, report correction/resubmission, duplicate actions, ownership and expired jobs | test_inspection_workflows.py, test_cleanup.py, test_reliability.py |
| Photos | Real JPEG/PNG/WebP bytes, spoofed/disallowed/empty files, size cap, item cap, owner/phase restrictions, originals retained, authenticated download, replacement-only uploads, rollback cleanup | test_inspection_workflows.py, test_photo_review_workflows.py, test_reliability.py |
| Re-upload clock regression | Equal original/review/replacement timestamps, clock moving backwards, replacement completion, deletion, caps, and admin original/replacement labels | test_photo_review_workflows.py, test_photo_round_migration.py |
| Report AI boundaries | Exact checklist coverage, missing/duplicate/unknown results, confidence/flag validation, actual graph branches, failed verification and retry | test_deadline_and_money_boundaries.py, test_reliability.py, test_inspection_workflows.py |
| Photo review and fees | Rejected-item-only image input, minimum/rounding/cap, exact fee agreement, AI failure with no hold, genuine result acceptance, re-upload, recheck approval/rejection, no pre-human strikes | test_photo_review_workflows.py, test_deadline_and_money_boundaries.py |
| Human decisions and appeals | Both decisions with both fees, winner/loser permissions, one appeal, deadline, uphold, overturn both directions, exact financial reversal, strike reversal, three-strike suspension, probation unsuspend | test_photo_review_workflows.py, test_workflow_api_contracts.py, test_reliability.py |
| Money and ledger | Exact renter/reviewer/platform/escrow amounts, 103.31 INR payout, frozen commission, fee retention/refunds, partial legacy refunds, append-only entries, backfill repeatability, scoped ledger endpoints | test_deadline_and_money_boundaries.py, test_legacy_and_support_workflows.py, test_workflow_api_contracts.py, test_reliability.py |
| Deadlines and scheduler | Unaccepted expiry, submit expiry, initial review silence, AI-result silence, re-upload silence, recheck silence, repeat sweeps, manual trigger/status, exact deadline and one microsecond late | test_deadline_and_money_boundaries.py, test_photo_review_workflows.py, test_inspection_workflows.py, test_reliability.py |
| Legacy disputes | Eligible paid historical job, 30-day window, exact boundary, ownership, duplicate cases, AI recommendation without money movement, retry, human uphold/refund/partial resolution, historical reads | test_legacy_and_support_workflows.py, test_deadline_and_money_boundaries.py |
| Support and reviewer setup | FAQ/status/escalation after authentication, foreign-job denial, modern complaints use photo review, provider failure, profile creation/location ownership | test_legacy_and_support_workflows.py, test_workflow_api_contracts.py |
| Notifications | Job/review/appeal states, admin queues, ownership, unread/read/all-read, pagination, rollback, stale writes, scheduler deduplication | test_notifications.py |
| Frontend APIs and CORS | Renter/reviewer/admin lists, filters, pagination, report access, origin allowlist, validation/HTTP/unexpected errors, OpenAPI error schema | test_frontend_support.py |
| Concurrency | Competing acceptance and payment creation, review/appeal stale writes, OTP reuse, scheduler winning during photo AI with no extra fee | test_reliability.py, test_notifications.py, test_deadline_and_money_boundaries.py |
| Migrations | Reliability, notification and replacement-photo migrations preserve data and can be repeated | test_reliability.py, test_notifications.py, test_photo_round_migration.py |

## Bug found and fixed by the audit

The former replacement-photo rule compared photo.created_at > review.created_at.
Windows clock precision can produce identical timestamps. The full suite initially
passed, but the separate smoke run caught a replacement upload being refused.
A deterministic regression test forced equal timestamps and reproduced the bug.

Photos now have an optional photo_review_id. Original evidence has no case
reference; uploads during re-upload are linked to that case. Completion, upload
caps, deletion permissions and admin round labels use the explicit reference.
Timestamps and original image files are preserved.

Run migrate_photo_rounds.py before deploying the new photo model. It backs up the
database, adds the nullable reference/index, and links existing unambiguous legacy
re-uploads using the previous timestamp rule. Equal-timestamp legacy rows cannot
be inferred reliably and retain their existing original classification. Newly
uploaded replacements are classified explicitly even with equal timestamps.

## What these tests do not establish

- Real model accuracy, real photo authenticity, provider costs or prompt-injection
  resistance. Mock outputs establish business behavior for known verdicts.
- Real SMS delivery, payment transfers, marketplace escrow, KYC or clawbacks.
- PostgreSQL behavior, cloud storage, browser/device workflows, load capacity or
  scheduler coordination across several production workers.
- Every possible concurrency interleaving or every line/branch. Concurrency tests
  cover selected stale-request and rollback cases, rather than a load test.
- Recovery from arbitrary historical database edits or ambiguous legacy photo
  timestamps. No existing photos are deleted by the migration.

The remaining Starlette/AnyIO deprecation warning comes from an installed
dependency and remains visible.
