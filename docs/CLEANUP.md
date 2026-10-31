# Cleanup and pending policy decisions

Completed independent fixes:

- Jobs with missing, non-finite or out-of-range coordinates return HTTP 409 on
  acceptance before creating payments or ledger entries.
- Invalid reviewer home coordinates are rejected before distance calculations.
- Open-job lists skip rows with invalid property coordinates.
- Haversine calculations clamp floating-point boundary drift for antipodal points.
- Distance-based pricing keeps the 100 INR + 10 INR/km rule and uses Decimal
  half-up rounding into paise, consistent with accounting calculations.
- The inactive duplicate venv was archived under _backups after verifying that
  no running process used it. The app continues to use .venv.

No existing addresses, coordinates, prices, payments or dispute records are
rewritten by these code fixes. No database migration is required.

Confirmed product choices:

1. Keep the full address visible to reviewers before acceptance.
2. Keep the existing distance-based price set when a reviewer accepts.

Confirmed: retain the separate 30-day legacy dispute route for eligible older
paid jobs without a photo-review record. Historical cases remain available.

The initial cleanup passed 160 regression tests. See TEST_COVERAGE.md for the
subsequent expanded workflow audit.

The audit found four historical disputes, all already resolved. History will be
preserved regardless of the new-case policy.

Tests: python -B -m pytest tests -q
