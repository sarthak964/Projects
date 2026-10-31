# TruStay reliability fixes

Updated October 20, 2026. No new marketplace functionality was added.

## Changes in this pass

- Added database version checks to reject stale job, payment, report, photo-review,
  appeal, rating and ledger writes. Reviewer profile and OTP updates also use
  versions. Conflicting requests roll back and return HTTP 409; SQLite lock
  contention returns a retryable HTTP 503.
- Kept job acceptance and payment creation in one transaction. A competing
  acceptance cannot overwrite the winner or leave a second payment/ledger hold.
- Centralized payment checks. Approval, deadlines and admin decisions require a
  real payment with the expected status and amount before changing the outcome.
- Replaced binary-float money conversion and commission calculation with Decimal
  rounding into integer paise. Rejected negative/non-finite fees and refunds,
  required exact fee confirmation, and bounded partial refunds by the payment.
- Made ledger rows append-only through ORM writes; corrections use reversals.
  Direct database SQL remains outside these application safeguards.
- Restricted legacy disputes to paid jobs without photo-review records. Historical
  cases remain readable. Legacy AI now recommends an outcome and escalates to a
  human instead of moving money based on its own confidence.
- Retained the earlier fixes blocking direct legacy payment release, validating
  exact AI checklist coverage, rejecting invalid job checklists, and returning
  retryable verification errors without saving partial results.
- Added AI confidence bounds and rejected contradictory passed/unaddressed flags.
- Updated jobs_completed on payment completion and reversal. The migration
  repairs existing counts using currently paid jobs.
- Saved ratings and reviewer averages together, so a failed update cannot leave
  half a rating transaction committed.
- Checked authorization before deadline side effects and before support AI calls.
  Updated support facts to match photo review and human dispute decisions.
- Prevented failed photo uploads from leaving new files behind, and prevented
  failed photo deletions from removing existing evidence.
- Required valid JWT subjects and expiry claims, and rejected incomplete reviewer
  home locations before distance calculations.
- Replaced deprecated datetime.utcnow calls with a shared UTC helper that keeps
  the existing naive-UTC SQLite timestamp format.
- Preserved 9000000006 as an admin, as requested.

## Database and backups

Run migrate_reliability.py before deploying the matching models. It adds version_id
to jobs, reviewer_profiles and otp_codes, backs up the SQLite database first, and
is safe to run again. Existing payments and ledger history are retained.

Deployment also saves copies of replaced source files under _backups.

## Verification

The isolated regression suite covers HTTP authorization/errors, job acceptance,
stale writes, OTP consumption, payout/refund accounting, human decisions, appeal
reversals, scheduler deadlines, photo download/deletion, input validation, rating
aggregates and migration idempotence. AI and external services are mocked. Test
databases and photo files are isolated from the working project data.

Run from the project folder:

    python -B -m pytest tests -q

pytest.ini limits discovery to tests/ so the older root-level AI scripts do not
accidentally call external services during regression testing.

## Limits and remaining decisions

- Real AI photo accuracy, real SMS and real payment transfers are not verified by
  this suite. Money remains bookkeeping until a gateway is integrated.
- Monetary database columns still use the existing float schema; accounting
  conversion now uses Decimal and integer paise. A full integer-column migration
  remains a separate change.
- Duplicate AI requests can still incur duplicate provider costs before a stale
  write is rejected. A durable AI task/idempotency system is still future work.
- The scheduler is still intended for one server process. Version checks prevent
  stale state overwrites but do not replace a multi-worker scheduler lock.
- Address privacy, upfront pricing, evidence provenance, cancellation policies,
  notification delivery, provider onboarding and production infrastructure remain
  separate product or production work.
- Dependency deprecation warnings remain; they are not test failures.

## Schema warning cleanup

Replaced eight deprecated class Config declarations across seven schema files
with ConfigDict(from_attributes=True). This preserves ORM response serialization.
The installed Starlette/AnyIO dependency warning remains visible.
