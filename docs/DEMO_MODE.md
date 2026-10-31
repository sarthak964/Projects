# TruStay demo labels

This backend demonstrates inspection workflows with simulated payment bookkeeping.
It is not connected to a payment or SMS provider. Labels describe current behavior;
they do not enable a new payment mode or bypass authentication and authorization.

GET /health retains status, app and env, and adds demo_mode: true.
GET /demo-info is public and provides notices for the future frontend:

- banner: show on the application shell and demo entry screen.
- payment_mode and payment_notice: show beside prices, fees, payment statuses,
  refunds and ledger balances. No actual money is collected or transferred.
- login_mode and login_notice: show on the login screen. In development, request
  a fresh OTP and use dev_otp from that response. No fixed OTP or SMS is used.
  Outside development, the metadata says SMS is not configured; it exposes no OTP.
- inspection_notice: show beside demonstration reports and sample evidence.
  This is a demo-wide notice, not a per-record claim of verified sample provenance.
- ai_notice: notes-only initial verification and rejected-photo analysis are
  distinct. AI provider charges can be real despite simulated payments.

The development OTP response message now says that a code was generated and no
SMS was sent. API documentation at /docs also describes the demo limitations.
The new endpoint returns no user, token, OTP, provider credentials or photo data.

There is no database migration and no relabeling or rewriting of stored jobs,
reports, payment amounts, account roles or ledger entries. No sample data is
created in this step. Frontend banners will be implemented when the UI is built.

Remaining demo preparation, in order:
1. Completed: summaries explicitly describe notes-only assessment, reported outcomes
   and incomplete notes. Summaries are built from validated results with no extra
   language-model call. Existing saved summaries are retained unchanged.
2. Completed: trimmed addresses up to 500 characters; 1-30 unique checklist
   items of 1-200 characters each; required trimmed notes of 10-10000 characters
   containing at least one letter or digit. Positive job IDs are required.
   Invalid new submissions return 422 before saving or calling external services.
   These checks do not prove that the notes are truthful or cover every item;
   checklist coverage remains part of AI assessment. Saved reports remain readable.
3. Completed: seed_demo.py creates ten sample scenarios in a separate owned
   demo_data/trustay_demo.db, with marked placeholder evidence and balanced
   simulated ledger records. run_demo.py serves it on port 8001. See DEMO_DATA.md
   for accounts, setup, safe reset and backup instructions.
Then build the frontend and exercise the rejection/re-upload flow through it.
