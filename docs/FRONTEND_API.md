# Frontend-support APIs

## Job lists

GET /jobs/mine

- Renter tokens return jobs created by that renter.
- Reviewer tokens return jobs assigned to that reviewer, including completed jobs.
- Admins use the admin list instead.
- Optional query parameters: status, limit (1-100, default 20), offset (0 or more).
- The owner ID always comes from the token. Sending renter_id/reviewer_id to this
  endpoint does not change the ownership filter.

GET /admin/jobs

- Admin tokens only.
- Optional filters: status, renter_id and reviewer_id (positive integers).
- Filters combine, and the same limit/offset pagination applies.

Both endpoints return:

    {"items": [...], "total": 0, "limit": 20, "offset": 0}

Items are sorted by created_at descending, then id descending. total counts all
matches before pagination. Items contain the existing JobOut fields plus:

- accept_deadline, submit_deadline, verified_at
- report_id, check_score, payment_status
- photo_review_status, appeal_status
- review_deadline, ai_result_deadline, reupload_deadline, recheck_deadline,
  appeal_deadline

Related values are null when unavailable. A verified job without a photo-review
record has photo_review_status = "pending". Amounts retain the existing API's INR
representation. Timestamps retain the backend's naive-UTC convention.

Lists are read-only and show saved state; the existing scheduler applies due
deadlines. Individual job detail also applies its existing lifecycle checks.
Suspended reviewers can still read their assigned job history.

## Report detail

GET /reports/{report_id}

Returns the existing ReportOut schema, including inspection notes, photo URLs,
AI results, summary and check score. Only that job's renter, assigned reviewer,
or an admin can read the report. Photo URLs still require bearer authentication.

## Application error format

Application HTTP errors use a stable object:

    {
      "error": {
        "code": "forbidden",
        "message": "This action requires one of these roles: admin",
        "details": []
      },
      "detail": "This action requires one of these roles: admin"
    }

The legacy detail field remains for existing callers. Validation errors use code
validation_error and details entries with field, code and message. For example,
field can be body.checklist or query.limit. Submitted values, file bytes, OTPs
and exception context are not echoed in validation errors.

HTTP status codes remain meaningful: 401 authentication, 403 permissions,
404 missing resources, 409 conflicting state, 422 invalid input, 429 rate limit,
502 upstream service failure and 503 retryable database contention. Retry-After
and other exception headers are retained. Unexpected failures return a generic
500 response, with diagnostic information confined to server logs.

The OpenAPI schema documents the shared error model. CORS preflight responses
use the middleware's standard protocol responses. Streaming failures after
headers are sent cannot be replaced with a new JSON response.

## Browser origins (CORS)

Development defaults allow these exact origins:

- http://localhost:3000
- http://127.0.0.1:3000
- http://localhost:5173
- http://127.0.0.1:5173

Set CORS_ALLOWED_ORIGINS to a comma-separated list in the environment or .env to
override the defaults, then restart the server. Example:

    CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com

An empty value allows no browser origins. Outside development there are no
default allowed origins. Values must be explicit http(s) origins: no paths,
credentials or wildcards. Authorization and Content-Type headers are allowed;
GET, POST, DELETE and OPTIONS are enabled. Authentication uses the existing
Authorization: Bearer token. Cookie credentials are not enabled.

Allowed origins receive CORS headers on application errors as well as successful
responses. Unlisted origins receive no Access-Control-Allow-Origin header.

## Verification

Run python -B -m pytest tests -q. The new tests cover ownership, filters,
pagination, report access, CORS, consistent errors and compatibility with prior
backend behavior. Tests use isolated databases and mocked external services.

No database migration or changes to existing job/payment data are required.
