# TruStay API reference for demo testing

Generated from the current local router source on October 26, 2026.

Use http://127.0.0.1:8001/docs for the interactive request schemas.
These are backend routes. Many do not yet have frontend controls.
Role information below shows the declared dependency only. Additional
ownership, job status, time-window, fee and payment guards apply.
A listed endpoint is not a promise that any account can call it in any state.

See DEMO_USER_GUIDE.md for the ordered tests and expected outcomes.

AI verification, photo rejection, support chat and legacy triage can call
external AI services. Payments recorded by these routes remain simulated.

## admin appeals

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/admin/appeals` | admin | list appeals |
| GET | `/admin/appeals/{job_id}` | admin | get appeal detail |
| POST | `/admin/appeals/{job_id}/decide` | admin | decide appeal |
| GET | `/admin/reviewers/suspended` | admin | list suspended reviewers |
| POST | `/admin/reviewers/{user_id}/unsuspend` | admin | unsuspend reviewer |

## admin review

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/admin/photo-reviews` | admin | list photo reviews |
| GET | `/admin/photo-reviews/{job_id}` | admin | get photo review detail |
| POST | `/admin/photo-reviews/{job_id}/decide` | admin | decide photo review |

## admin scheduler

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/admin/scheduler/status` | admin | scheduler status |
| POST | `/admin/scheduler/run` | admin | run scheduler now |

## appeal

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/jobs/{job_id}/appeal` | Logged-in user (see ownership rules) | get appeal status |
| POST | `/jobs/{job_id}/appeal` | renter, reviewer | file appeal |

## auth

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/auth/request-otp` | Public | request otp |
| POST | `/auth/verify-otp` | Public | verify otp |
| GET | `/auth/me` | Logged-in user (see ownership rules) | me |

## dispute

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/disputes/` | renter | file dispute |
| GET | `/disputes/{dispute_id}` | Logged-in user (see ownership rules) | get dispute |
| POST | `/disputes/{dispute_id}/triage` | Logged-in user (see ownership rules) | triage dispute |
| POST | `/disputes/{dispute_id}/resolve` | admin | resolve dispute |

## job

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/jobs/` | renter | create job |
| GET | `/jobs/open` | reviewer | list open jobs |
| GET | `/jobs/{job_id}` | Logged-in user (see ownership rules) | get job |
| POST | `/jobs/{job_id}/accept` | reviewer | accept job |
| POST | `/jobs/{job_id}/visit` | reviewer | mark visited |

## job lists

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/jobs/mine` | renter, reviewer | my jobs |
| GET | `/admin/jobs` | admin | admin jobs |

## ledger

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/ledger/me` | renter, reviewer | my ledger |
| GET | `/admin/ledger/jobs/{job_id}` | admin | job ledger |
| GET | `/admin/ledger/summary` | admin | platform summary |
| POST | `/admin/ledger/backfill` | admin | run backfill |

## notification

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/notifications` | Logged-in user (see ownership rules) | list notifications |
| GET | `/notifications/unread-count` | Logged-in user (see ownership rules) | unread count |
| POST | `/notifications/read-all` | Logged-in user (see ownership rules) | mark all read |
| POST | `/notifications/{notification_id}/read` | Logged-in user (see ownership rules) | mark read |

## payment

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/payments/{payment_id}/release` | renter, admin | release payment (deprecated; direct release is disabled) |

## photo

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/jobs/{job_id}/photos` | reviewer | upload photo |
| GET | `/jobs/{job_id}/photos` | Logged-in user (see ownership rules) | list job photos |
| GET | `/photos/{photo_id}` | Logged-in user (see ownership rules) | get photo file |
| DELETE | `/photos/{photo_id}` | reviewer | delete photo |

## photo review

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/jobs/{job_id}/photo-review` | Logged-in user (see ownership rules) | get photo review |
| GET | `/jobs/{job_id}/photo-review/fee-quote` | renter | fee quote |
| POST | `/jobs/{job_id}/photo-review/approve` | renter | approve photos |
| POST | `/jobs/{job_id}/photo-review/reject` | renter | reject photos |
| POST | `/jobs/{job_id}/photo-review/accept-ai-result` | renter | accept ai result |
| POST | `/jobs/{job_id}/photo-review/dispute-ai-result` | renter | dispute ai result |
| POST | `/jobs/{job_id}/photo-review/reupload-complete` | reviewer | reupload complete |
| POST | `/jobs/{job_id}/photo-review/recheck/approve` | renter | recheck approve |
| POST | `/jobs/{job_id}/photo-review/recheck/reject` | renter | recheck reject |

## rating

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/ratings/` | renter | submit rating |
| GET | `/ratings/{rating_id}` | Logged-in user (see ownership rules) | get rating |

## report

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/reports/` | reviewer | submit report |
| POST | `/reports/{report_id}/verify` | Logged-in user (see ownership rules) | verify report |
| GET | `/reports/{report_id}` | Logged-in user (see ownership rules) | get report |

## reviewer profile

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/reviewers/{user_id}/location` | reviewer, admin | set reviewer location |

## support

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| POST | `/support/chat` | renter | support chat |

## user

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/users/{user_id}` | Logged-in user (see ownership rules) | get user |

## main

| Method | Path | Declared access | Operation |
| --- | --- | --- | --- |
| GET | `/health` | Public | health check |
| GET | `/demo-info` | Public | demo info |

## Reading results

State-changing POST/DELETE operations alter the separate demo dataset.
Several GET endpoints also process overdue lifecycle transitions.
Always inspect the current state before repeating a failed-looking action.
401 means login is missing/invalid; 403 is access denied; 422 identifies
invalid inputs; 409 can indicate a state conflict or a blocked legacy bypass.
Exact input and output models are shown in the interactive API documentation.


## Frontend completion additions (October 30, 2026)

- GET /reviewers/{user_id}/profile: own reviewer profile or admin inspection; returns
  null when no profile exists, 403 for another reviewer, 404 for a non-reviewer.
  Profile responses now include strikes and suspended.
- GET /ratings/job/{job_id}: existing rating or null; job participants/admin only.
- Photo responses now include round: original or reupload.

The modern workflows now have browser controls; the earlier UI-availability notes
are superseded by DEMO_USER_GUIDE.md and END_TO_END_TEST_WORKFLOWS.md.


## Remaining frontend controls — October 31, 2026

GET /disputes/ lists retained older-job cases with limit (1–100), offset and optional job_id. Renters see only their own records; admins see all; reviewers are denied. New browser screens expose filing, triage and admin resolution through the existing guarded write APIs. Notifications expose paging, unread_only, read-all and individual mark-read operations.
