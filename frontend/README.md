# TruStay complete local demo frontend

React + TypeScript + Vite interface for the separate FastAPI demo on port 8001.
Start the backend with `python -B run_demo.py` from the project root, then run
`npm.cmd run dev` here. Open http://127.0.0.1:5173/. Dependencies are already installed.

All modern renter/reviewer/admin inspection workflows have screens. See
../docs/DEMO_USER_GUIDE.md for the feature map and ../docs/END_TO_END_TEST_WORKFLOWS.md
for a complete role-by-role walkthrough. Historical maintenance APIs and database
resets remain Swagger/CLI operations.

Payments are simulated. Explicit AI actions/address lookup can use external services.
The token is tab-scoped sessionStorage; protected photos use temporary blob URLs.
No server credentials are bundled in the client. Stock photos are decorative,
stored locally, credited in ASSET_CREDITS.md, and separate from inspection evidence.

Checks: `npm.cmd test` (14 tests), `npm.cmd run build` (TypeScript + production build).
The normal proxy target remains http://127.0.0.1:8001. TRUSTAY_API_TARGET is an
optional local QA override; no QA provider fixtures are shipped as app behavior.
