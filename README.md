# TruStay

A local demo of a rental-property inspection service, with renter, reviewer and admin workflows, checklist evidence, AI-assisted report assessment, disputes and simulated payment accounting.

TruStay explores how someone can request a property inspection when they cannot visit in person. It is an inspection application: an inspection card is a job, rather than an accommodation listing or booking.

## Project status

- Complete browser controls for the implemented modern inspection workflows and retained older-job disputes.
- React/TypeScript frontend with a red theme, responsive layouts, protected evidence galleries, decorative housing photography and subtle hover effects.
- FastAPI backend, SQLite persistence, permission checks, deadline handling and simulated ledger.
- Latest functional verification: **352 backend tests**, **14 frontend tests**, and a successful frontend build.
- Manually tested normal journey: request, acceptance, visit, two checklist photo uploads, report submission, notes assessment, renter approval, payout, rating and admin accounting.
- Historical dispute screens are implemented, but a full browser submission/triage/resolution walkthrough with an eligible historical case remains to be performed. The automated suite checks backend behavior with isolated databases and mocked external services.

This is a portfolio/demo application. Payments, escrow, fees, deposits, refunds and payouts do not transfer real money. Development OTP login sends no SMS. External AI calls can incur actual provider charges.

## Contents

- [Features and roles](#features-and-roles)
- [Architecture](#architecture)
- [Installation](#installation)
- [Run the application](#run-the-application)
- [Test a complete inspection](#test-a-complete-inspection)
- [Evidence, AI and decisions](#evidence-ai-and-decisions)
- [Pricing and accounting](#pricing-and-accounting)
- [Configuration](#configuration)
- [API overview](#api-overview)
- [Tests](#tests)
- [Data and maintenance](#data-and-maintenance)
- [Repository contents and Git](#repository-contents-and-git)
- [Troubleshooting](#troubleshooting)
- [Detailed documentation](#detailed-documentation)

## Features and roles

| Role | Capabilities |
| --- | --- |
| Renter | Create an address/checklist inspection, view jobs/reports/photos, approve or reject evidence, request human review, review replacement photos, file eligible appeals, rate paid jobs, inspect payment history, ask support, manage notifications and file eligible older-job disputes |
| Reviewer | Save a home location, browse nearby requests, inspect full addresses and estimated prices, accept jobs, mark visits, upload checklist evidence, submit/correct reports, run notes assessment, supply replacement evidence, file eligible losing-side appeals and view earnings/profile standing |
| Admin | Browse all jobs, inspect human-review and appeal queues, compare evidence, record decisions, uphold/overturn appeals, inspect suspended reviewers and unsuspend with a reason, review platform/job accounting, inspect/run deadline sweeps and resolve escalated older-job disputes |

All roles have login/logout, session restoration, role-specific navigation, job loading/error/empty states and notifications with paging, unread filtering and mark-read controls. Server permissions and saved state determine which actions are allowed.

## Architecture

```text
Browser (React + TypeScript + React Router)
    │ HTTP /api/*; tab-scoped bearer token
    ▼
Vite development/preview proxy (127.0.0.1:5173)
    │ strips /api prefix
    ▼
FastAPI (separate demo: 127.0.0.1:8001)
    ├── Routers → request schemas → authorization and workflow guards
    ├── SQLAlchemy models/services → SQLite database and ledger
    ├── Local protected photo storage → authenticated photo responses
    ├── Deadline scheduler / request-time deadline handling
    ├── LangGraph + LangChain → configured OpenAI provider
    └── Nominatim address lookup → coordinates and distance-based matching
```

Backend code is organized into `app/core` (settings/auth/database/errors), `app/models` (persistent records), `app/schemas` (validation/response types), `app/routers` (HTTP operations) and `app/services` (workflow, AI, images, pricing, accounting and demo fixtures).

Principal records include users, reviewer profiles, jobs, photos, reports, payments, photo-review cases, older disputes, ratings, notifications, support tickets and ledger entries. Photo-review records also carry human decisions and appeal state. Optimistic job versions protect concurrent updates; relevant money calculations and ledger entries use integer paise.

The frontend keeps its bearer token in `sessionStorage`, clears it on logout/401 and fetches evidence with authorization headers. Temporary blob URLs display protected photos. Server API keys stay on the backend.

### Stack

Python 3.12 was used for local verification; dependencies are in `requirements.txt`. The backend uses FastAPI, Uvicorn, SQLAlchemy, Pydantic, PyJWT, Pillow, LangChain and LangGraph. Verification currently configures `gpt-4o-mini` in source.

The frontend was verified with Node.js 24 and npm 11. Exact package versions are recorded in `frontend/package.json` and `frontend/package-lock.json`: React 19, React Router 7, TypeScript 6 and Vite 7. Use the committed lockfile for reproducible dependency installation.

## Installation

Run from the repository root. For the existing local checkout, that is `C:\Users\Sarthak\TruStay`.

```powershell
Set-Location 'C:\Users\Sarthak\TruStay'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Copy the example only on a new checkout; preserve an existing `.env`. Add your own `OPENAI_API_KEY` to `.env` when testing real AI calls. Without a provider key, demo seeding and basic browsing work, but real AI actions cannot complete.

```powershell
Set-Location 'C:\Users\Sarthak\TruStay\frontend'
npm.cmd ci
```

Do not recreate a working virtual environment or reinstall dependencies merely to start the app.

## Run the application

For a new checkout, prepare the separate sample database once:

```powershell
Set-Location 'C:\Users\Sarthak\TruStay'
.\.venv\Scripts\Activate.ps1
python -B seed_demo.py
```

Seeding is offline and repeatable; it leaves an existing owned demo database intact unless `--reset` is explicitly supplied.

**Terminal A — demo backend:**

```powershell
Set-Location 'C:\Users\Sarthak\TruStay'
.\.venv\Scripts\Activate.ps1
python -B run_demo.py
```

**Terminal B — frontend:**

```powershell
Set-Location 'C:\Users\Sarthak\TruStay\frontend'
npm.cmd run dev
```

| URL | Purpose |
| --- | --- |
| http://127.0.0.1:5173/ | Browser application |
| http://127.0.0.1:8001/docs | Interactive demo API documentation |
| http://127.0.0.1:8001/openapi.json | Generated API contract |
| http://127.0.0.1:8001/health | Backend health |
| http://127.0.0.1:5173/api/health | Frontend proxy/backend connectivity |
| http://127.0.0.1:8001/demo-info | Demo notices |

Keep both services running; Ctrl+C stops a terminal-owned process. An occupied port may mean the intended service is already running. The frontend deliberately uses a fixed port and does not silently switch.

### Demo identities

| Role | Phone |
| --- | --- |
| Renter | `9000000001` |
| Reviewer | `9000000002` |
| Admin | `9999999999` |

Choose a role, request a fresh development OTP and click **Enter your workspace**. The UI fills the temporary OTP; no SMS is sent. Role selection does not change an existing account's role. New renter/reviewer accounts can use unused test numbers and an optional name. Admin access is allowlisted by the backend.

### Build and preview

```powershell
Set-Location 'C:\Users\Sarthak\TruStay\frontend'
npm.cmd run build
npm.cmd run preview
```

Stop the development server before previewing on the same port. The backend must also be running. `TRUSTAY_API_TARGET` is an optional Vite QA proxy override; its default is `http://127.0.0.1:8001`. No public hosting is configured.

## Test a complete inspection

1. Log in as renter and create a fresh inspection with a searchable address, for example Connaught Place, New Delhi, India. Keep the walls/taps checklist and record the job ID.
2. Log in as reviewer. Save a nearby home location if needed, open Nearby jobs, accept that job and confirm its price.
3. Mark the visit. Select the walls checklist item, choose an image and click **Upload photo**. Repeat for taps. Selecting a local file alone does not upload it.
4. Confirm that each checklist item has evidence in the gallery. Describe every item in the report and submit it.
5. Explicitly run **Assess report notes**. Read the actual result; correct missing coverage or retry a provider failure when eligible.
6. Log in as renter, read the report, inspect both photos and approve them.
7. Verify Paid/Released, submit a rating and refresh to confirm persistence.
8. As reviewer, inspect Payment history. As admin, look up the job ledger and verify the payout, commission and remaining escrow.

The local test of job #012 used ₹100.66: reviewer payout ₹85.56, commission ₹15.10 and final escrow ₹0. Job IDs and history are not bundled with a new Git checkout.

See [the workflow workbook](docs/END_TO_END_TEST_WORKFLOWS.md) for photo rejection, reupload, human review, appeals, older-job disputes and permission tests. Use fresh jobs for fresh deadlines.

## Evidence, AI and decisions

- Addresses allow up to 500 characters. Checklists require 1–30 unique nonblank items, up to 200 characters per item.
- Photos must be JPEG/PNG/WebP, at most 8 MiB each, with at most three photos per item per round. Every checklist item needs at least one saved photo before report submission.
- Notes require 10–10,000 characters and meaningful letter/digit content. A reported defect can be a valid completed check; omitted coverage requires correction.
- Initial AI assessment reads **notes only**. Complete, validated results produce a checklist outcome score and scoped summary. A score is not independent property certification.
- Renter rejection quotes a simulated fee before selected images are sent to the provider. Follow the actual result: accept AI support, provide replacement evidence or escalate to human review.
- Replacement photos are explicitly linked to the replacement round. Existing originals do not satisfy a new-round upload requirement. The renter can approve replacements or escalate a recheck rejection without another AI analysis.
- A human decision can release/refund amounts and affect reviewer strikes. The losing side has one eligible appeal; an admin can uphold or overturn it.
- The separate 30-day dispute route remains for eligible older paid jobs without a modern photo-review record. It does not bypass modern case guards.
- Support can answer questions or save a local ticket. There is no external live-agent delivery or implemented conversation-history dashboard.

Visits are self-reported. Seeded images/results are labelled sample fixtures. Decorative housing and moving-day imagery is not inspection evidence or a property listing photograph. Photo sources/license links are recorded in [asset credits](frontend/ASSET_CREDITS.md).

## Pricing and accounting

Default demo price is ₹100 + ₹10 per km, finalized when the reviewer accepts. Full addresses are visible before acceptance. Matching uses straight-line distance and a maximum 50 km radius. The platform commission is 15%.

Photo-check fee defaults to ₹25–₹60 based on selected photo count; the exact quote must be confirmed. Disputing an AI-supported result adds a simulated ₹75 human-review fee. Fee retention/refunds follow the saved workflow outcome.

The ledger records movements between renter/reviewer accounts, escrow and platform. Approval/allowed deadlines/admin outcomes determine settlement. There is no unconditional reviewer payout button. Appeal reversal keeps compensating accounting history. All monetary movements are local simulated records.

## Configuration

Use `.env.example` as a safe template. The complete settings source is `app/core/config.py`.

| Setting | Default / meaning |
| --- | --- |
| `OPENAI_API_KEY` | Your provider credential; needed for real AI calls |
| `DATABASE_URL` | Normal mode: `sqlite:///./trustay.db` |
| `ENVIRONMENT` | `development` |
| `JWT_SECRET`, `JWT_EXPIRE_MINUTES` | Local token signing; expiry 1440 minutes |
| `ADMIN_PHONES` | Comma-separated admin allowlist |
| `OTP_EXPIRE_MINUTES`, `OTP_MAX_ATTEMPTS`, `OTP_RESEND_COOLDOWN_SECONDS` | 5 minutes / 5 attempts / 30 seconds |
| `UPLOAD_DIR`, `MAX_PHOTO_BYTES`, `MAX_PHOTOS_PER_ITEM` | Local storage / 8388608 bytes / 3 |
| `MAX_SERVICE_DISTANCE_KM` | 50 |
| `ACCEPT_WINDOW_HOURS`, `SUBMIT_WINDOW_HOURS` | 24 / 48 |
| `PHOTO_REVIEW_WINDOW_HOURS` | 48 |
| `REUPLOAD_WINDOW_HOURS`, `RECHECK_WINDOW_HOURS` | 24 / 24 |
| `APPEAL_WINDOW_HOURS`, `STRIKES_BEFORE_SUSPENSION` | 48 / 3 |
| `DISPUTE_WINDOW_DAYS`, `DISPUTE_AUTO_RESOLVE_CONFIDENCE` | 30 / legacy setting 0.8; current triage still requires a human before settlement |
| `PLATFORM_COMMISSION_RATE` | 0.15 |
| `AI_COST_PER_PHOTO_INR`, `PHOTO_REVIEW_FEE_MULTIPLIER` | 0.5 / 6; simulated quote inputs, not provider billing estimates |
| `PHOTO_REVIEW_FEE_MIN`, `PHOTO_REVIEW_FEE_MAX`, `HUMAN_REVIEW_FEE` | 25 / 60 / 75 |
| `SCHEDULER_ENABLED`, `SCHEDULER_INTERVAL_SECONDS` | Normal defaults true / 60 |
| `CORS_ALLOWED_ORIGINS` | Development localhost origins on ports 3000/5173; comma-separated |

`run_demo.py` intentionally overrides database/uploads, admin allowlist, local JWT key, scheduler and selected policy settings for the separate demo. Inspect that launcher when comparing modes; editing `.env` does not override its explicit values. The demo background scheduler is paused, but reading/acting on records can still apply due deadlines. Admin tools can explicitly run a sweep affecting several due records.

## API overview

| Area | Routes |
| --- | --- |
| Login and identities | `/auth/request-otp`, `/auth/verify-otp`, `/auth/me`, `/users/{user_id}` |
| Jobs | `/jobs/`, `/jobs/open`, `/jobs/mine`, `/jobs/{job_id}`, `/jobs/{job_id}/accept`, `/jobs/{job_id}/visit`, `/admin/jobs` |
| Reviewer location/profile | `/reviewers/{user_id}/location`, `/reviewers/{user_id}/profile` |
| Evidence | `/jobs/{job_id}/photos`, `/photos/{photo_id}` |
| Reports | `/reports/`, `/reports/{report_id}`, `/reports/{report_id}/verify` |
| Renter review | `/jobs/{job_id}/photo-review` and fee-quote/approve/reject/accept-ai-result/dispute-ai-result/reupload-complete/recheck subroutes |
| Human decisions | `/admin/photo-reviews`, `/admin/photo-reviews/{job_id}`, `/admin/photo-reviews/{job_id}/decide` |
| Appeals/standing | `/jobs/{job_id}/appeal`, `/admin/appeals`, case detail/decision subroutes, `/admin/reviewers/suspended`, `/admin/reviewers/{user_id}/unsuspend` |
| Retained older disputes | `/disputes/`, `/disputes/{dispute_id}`, `/triage` and `/resolve` subroutes |
| Ratings/support | `/ratings/`, `/ratings/{rating_id}`, `/ratings/job/{job_id}`, `/support/chat` |
| Notifications | `/notifications`, `/notifications/unread-count`, `/notifications/read-all`, `/notifications/{notification_id}/read` |
| Accounting/scheduler | `/ledger/me`, `/admin/ledger/jobs/{job_id}`, `/admin/ledger/summary`, `/admin/ledger/backfill`, `/admin/scheduler/status`, `/admin/scheduler/run` |

Authenticated requests use `Authorization: Bearer <token>`. The direct payment-release route is retained but blocked; use the review workflow. Normalized errors provide an error code/message/details and a compatibility `detail` field. Request conflicts require refresh; provider failures can return 502 without partial result saving. Use the running `/docs` or `/openapi.json` for exact methods, request bodies, parameters and response schemas; see [API reference](docs/API_REFERENCE.md).

## Tests

```powershell
# Repository root, activated Python environment
python -B -m pytest tests -q

# Frontend folder
npm.cmd test
npm.cmd run build
```

Backend tests use isolated SQLite databases and mock AI/geocoding. They cover authorization, validation, workflow guards, provider failures/retries, concurrent updates, paise accounting, ledger reversals, deadlines, notifications, demo seed ownership and dispute-list scoping. Frontend tests cover API behavior, optional-null responses, role/stage permissions and input preflight. A Starlette/AnyIO dependency deprecation warning may appear.

Automated tests and controlled QA do not establish real-world AI accuracy. Browser testing of actual external provider responses remains useful.

## Data and maintenance

| Local item | Purpose |
| --- | --- |
| `trustay.db`, `uploads/` | Original/normal-mode data; preserved locally |
| `demo_data/trustay_demo.db`, `demo_data/uploads/` | Separate demo history and evidence |
| `demo_data/server.lock` | Prevents duplicate demo launch/seed/reset |
| `demo_data/backups/` | Demo reset backups |
| `.env`, `.venv/`, `frontend/node_modules/` | Local configuration and installed dependencies |

Stop the demo server before an intentional reset:

```powershell
python -B seed_demo.py --reset
```

Reset backs up the owned demo database and rebuilds sample scenarios. Do not reset to run an ordinary new inspection. The seeder refuses unowned databases and redirected paths.

Normal backend mode uses the separate original database. For a fresh normal database, `python create_tables.py` creates tables; `python -m uvicorn app.main:app --reload` starts it on port 8000. This is not the default frontend target. Existing databases require their applicable `migrate_*.py` upgrades after a backup; `create_all` does not upgrade existing tables. Keep these migration scripts at the root because regression tests import some of them. Consult the change notes before historical upgrades; do not run migrations blindly against a working database.

## Repository contents and Git

```text
TruStay/
├── README.md, .gitignore, .env.example
├── requirements.txt, pytest.ini
├── app/                 Backend source
├── tests/               Isolated backend regression suite
├── frontend/
│   ├── src/             Screens, API client, workflow controls and styles
│   ├── public/images/   Decorative photographs and SVG illustration
│   ├── tests/           Frontend tests
│   ├── package.json, package-lock.json, tsconfig.json, vite.config.ts
│   └── README.md, ASSET_CREDITS.md, VERIFICATION.md
├── docs/                Detailed user, API, workflow and engineering guides
├── run_demo.py, seed_demo.py, create_tables.py
├── migrate_*.py         Historical schema/data maintenance
└── Local ignored files  .env, dependencies, databases, uploads and caches
```

Commit source, tests, docs, dependency manifests/lockfile, configuration templates and decorative assets with credits. `.gitignore` excludes credentials, SQLite data/sidecars, uploads, demo runtime data, environments, dependencies, build output, caches, logs, backups and editor metadata. Keep `frontend/package-lock.json`; do not use a blanket `*.lock` rule.

Ignored files still exist locally and keep the app working. Git ignores do not remove files already tracked; check `git ls-files` before publishing. The cleanup archive is outside the project and is not a repository dependency.

## Troubleshooting

- **Port 5173 occupied:** open the existing application first; avoid duplicate servers.
- **Backend unreachable:** check backend terminal, port 8001 health and `/api/health`; both frontend and backend must run.
- **No development OTP:** use the demo backend/development mode, respect cooldown and request a fresh code. Tokens from normal port 8000 do not authenticate against the separate demo.
- **No nearby jobs:** save reviewer location, check the 50 km service radius and job deadline.
- **Submission needs photos:** every item must have a saved upload. Choose the correct checklist item and click Upload photo; inspect the gallery.
- **Missing action:** check role, assignment, saved stage and deadline. Refresh to see current eligibility.
- **Provider error:** check the configured API key/provider account; retry only when the saved workflow remains eligible.
- **Demo lock:** check that its process and port have stopped before treating it as stale. Never delete the lock of an active server/seed.

## Detailed documentation

- [Demo user guide](docs/DEMO_USER_GUIDE.md)
- [Complete role-by-role workflow workbook](docs/END_TO_END_TEST_WORKFLOWS.md)
- [API reference](docs/API_REFERENCE.md) and [frontend API notes](docs/FRONTEND_API.md)
- [Demo data/seeding](docs/DEMO_DATA.md) and [demo boundaries](docs/DEMO_MODE.md)
- [Notifications](docs/NOTIFICATIONS.md), [service radius](docs/SERVICE_RADIUS.md)
- [Reliability changes](docs/RELIABILITY_CHANGES.md) and [test coverage notes](docs/TEST_COVERAGE.md)
- [Frontend setup](frontend/README.md), [verification history](frontend/VERIFICATION.md), [asset credits](frontend/ASSET_CREDITS.md)
- [Cleanup record](docs/PROJECT_CLEANUP.md)

The older engineering notes describe their particular milestones. Current source, generated OpenAPI contract and the latest verification entry take precedence where earlier notes differ.
