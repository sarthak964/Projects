# TruStay demo: complete browser testing guide

Updated October 30, 2026. Project: C:\Users\Sarthak\TruStay.

## Start and log in

Keep two terminals running:

```powershell
# Terminal A
Set-Location 'C:\Users\Sarthak\TruStay'
.\.venv\Scripts\Activate.ps1
python -B run_demo.py
```

```powershell
# Terminal B
Set-Location 'C:\Users\Sarthak\TruStay\frontend'
npm.cmd run dev
```

Open http://127.0.0.1:5173/. The interface proxies the separate demo backend
on port 8001. Port 8000 and its tokens belong to the older normal database.

| Role | Demo phone | Main screens |
| --- | --- | --- |
| Renter | 9000000001 | My inspections, Support, Notifications, Payment history |
| Reviewer | 9000000002 | My inspections, Nearby jobs, My location & profile, Notifications, Payment history |
| Admin | 9999999999 | Overview, Human reviews, Appeals, Reviewer standing, Admin tools, Notifications, Platform ledger |

Select a role, click **Get development OTP**, then **Enter your workspace**.
No SMS is sent. The temporary code is filled into the visible field. Use Log out
to switch accounts. Wait 30 seconds before requesting another code for the same
phone. Codes expire in five minutes; tokens expire after 24 hours. A 401 returns
you to login. The token stays in sessionStorage in that browser tab.

For a fresh renter/reviewer, select the role and replace the phone with an unused
test number. An optional name field is available. Admin privileges come from the
backend allowlist, never an arbitrary role selection. New reviewers must save
their home location before searching for jobs. Existing accounts keep their role.

## What you can now do in the browser

| Feature | Where |
| --- | --- |
| Create jobs with an address and editable checklist | Renter: New inspection |
| Browse, filter and paginate job records | All roles: workspace |
| Set reviewer location and see rating, jobs, strikes and suspension | Reviewer: My location & profile |
| Search within 5, 15, 30 or 50 km, inspect full address and estimate, accept | Reviewer: Nearby jobs |
| Mark visited, upload evidence, delete editable photos | Assigned reviewer: inspection detail |
| Submit or correct report notes; explicitly run/retry notes assessment | Assigned reviewer: inspection detail |
| Read notes, scoped AI summary, score and protected original/replacement photos | Participants/admin: inspection detail |
| Approve original photos or reject selected items after a fee quote | Renter: inspection detail |
| Accept AI support or dispute it with the additional human-review fee | Renter: inspection detail, when eligible |
| Upload replacement evidence and complete the round | Reviewer: inspection detail, when requested |
| Approve replacements or escalate their rejection to a human | Renter: inspection detail, during recheck |
| Read decisions and file one eligible appeal | Losing participant: inspection detail |
| Compare evidence, save a reason and decide genuine/not genuine | Admin: Human reviews |
| Uphold/overturn a decision and its financial/strike effects | Admin: Appeals |
| Inspect suspended reviewers and unsuspend with a reason | Admin: Reviewer standing |
| Read personal payment entries or platform balances | Payment history / Platform ledger |
| Look up a job's accounting and manually sweep due deadlines | Admin tools |
| Rate a fully paid inspection once | Renter: inspection detail |
| Read notifications and mark them read | Notifications |
| Ask AI support with an optional owned job | Renter: Support |

Buttons appear only for eligible saved stages and roles. After a change the
inspection reloads. Refresh inspection/Refresh queue reloads the server state.
Important decisions show a confirmation before submitting. No unconditional
reviewer payout control exists: approval, deadlines or an admin decision release
the simulated payment.

## Workflow rules

- A job is an inspection request, not a rental advertisement or booking.
- Full addresses remain visible before acceptance. Final pricing is set at
  acceptance: base ₹100 plus ₹10/km; maximum service distance 50 km.
- Requested jobs have a 24-hour acceptance window. Report submission has its
  own 48-hour window after acceptance. Check the current API/record for deadlines.
- Checklist: 1–30 unique nonblank items, up to 200 characters each; address up to
  500 characters. Related checks about one appliance are allowed.
- Upload JPEG, PNG or WebP, up to 8 MiB each, at most three photos per checklist
  item in each round. Every item needs evidence before report submission.
- Notes need 10–10,000 characters and meaningful letter/digit content. Explain
  every item, including defects. A failed result is different from missing coverage.
- Initial AI verification checks notes only. Incomplete coverage requires correction;
  provider failures permit retry without partial result saving. No photos go to
  that initial check. A score does not certify the property's actual condition.
- Verified reports start the renter photo-review window (normally 48 hours).
  Rejection sends only selected evidence to photo analysis after a quoted fee.
  Current photo-check fees range ₹25–₹60, depending on selected photo count.
- Follow the actual returned result. Replacement upload and recheck windows are
  normally 24 hours. Replacement evidence must cover every rejected item in a new
  round. Rejected replacements go to a human without another AI call.
- Disputing an AI-supported result holds an additional simulated ₹75 human fee.
- Human decisions settle/refund simulated amounts and may affect strikes or
  suspension. The losing side can appeal once within the saved 48-hour window.
- A paid inspection can be rated once. Platform commission is currently 15%.
- The demo background scheduler is paused. Opening records can still apply due
  deadlines. Admin tools can explicitly sweep due records. Old seeded scenarios
  may therefore have moved on; use fresh jobs for a new full walkthrough.

## Demo boundaries

Accounts, permission checks, uploads, notifications, reports and ledger entries
are real local application records. All payments, fees, refunds and payouts are
simulated; no payment gateway, SMS, identity provider or real deposit collection
is connected. Address lookup, AI verification, photo analysis and support can use
external providers and incur real provider charges. AI actions are explicit.
Seeded notes/results and labelled placeholder photos are sample data.

The new housing/people photographs are decorative stock imagery, not photographs
of the listed inspection address or evidence. Credits and license links are in
frontend/ASSET_CREDITS.md and the in-app **How to test & photo credits** page.

Support can save a local escalation ticket, but there is no external agent delivery
or live conversation history endpoint. Modern disputes use inspection controls.
The retained 30-day legacy dispute API is for eligible older paid jobs without a
modern photo-review record; historical maintenance and migrations remain API/CLI
operations. No rental catalogue, landlord portal, tenancy contract or booking
calendar is part of this inspection demo.

The frontend uses React, TypeScript, Vite and React Router. The API uses FastAPI,
SQLAlchemy and SQLite with existing AI services. No new production integrations
or deployment infrastructure were added. Existing .env, trustay.db, uploads and
the separate demo database were preserved during this update.

## Troubleshooting

- Backend unreachable: keep python -B run_demo.py running; check
  http://127.0.0.1:8001/health. Restart after backend source updates.
- Port already in use: use the existing intended server; do not start duplicates.
- Login failure: request a fresh OTP on port 8001; respect resend cooldown.
- No nearby jobs: save reviewer location, check distance and requested deadlines.
- Missing action: check active account, assignment, saved stage and deadline.
- AI failure: read the error, refresh and retry only if the operation remains eligible.
- Do not paste tokens, API keys or .env content into feedback.

Follow END_TO_END_TEST_WORKFLOWS.md to test each branch and record feedback.


## Completed remaining controls

Renter and admin navigation now includes **30-day disputes**: browse cases, file an eligible older-job case, request AI triage, read recommendations and resolve escalated cases as admin. Modern jobs remain in their photo-review workflow. Notifications now have paging, unread filtering, refresh and Mark all read. Admin inspection details link directly to pending human reviews and appeals. These screens supersede earlier statements that legacy disputes were API-only. Database repair/backfill and migrations remain maintenance operations.
