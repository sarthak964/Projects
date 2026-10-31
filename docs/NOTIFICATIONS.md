# Database-backed notifications

Notifications are created automatically for new job states, photo-review states,
human-review queues and appeal submissions/decisions. Renters and assigned
reviewers receive relevant updates; all admins receive new human-review and
appeal queue alerts. Open-job posting does not broadcast to every reviewer.

Each authenticated user can only read and mark their own notifications. Admin
credentials do not grant access to another user's notification inbox.

## Endpoints

- GET /notifications?unread_only=false&limit=20&offset=0
  returns items, total, limit and offset, newest first. Limit is 1-100.
- GET /notifications/unread-count returns unread_count.
- POST /notifications/{id}/read marks an owned notification read and returns it.
  Repeating the request preserves the original read_at timestamp.
- POST /notifications/read-all returns marked_read for this user's unread items.

Items contain id, job_id, event_type, title, message, deadline_at, is_read, read_at
and created_at. Event types include job.accepted, job.verified,
photo_review.awaiting_reupload, photo_review.awaiting_human and appeal.pending.
Timestamps use the same naive-UTC convention as the existing backend.

## Transaction behavior

The SQLAlchemy hooks collect state transitions before flush and create alerts
after generated IDs are available. Notifications and business changes commit or
roll back together. Event keys are unique per job version, event and recipient.
Repeated flushes, failed requests and repeated scheduler sweeps do not create
duplicate alerts. One specific review/appeal event replaces overlapping generic
job alerts in the same flush.

The hooks run from the web application and standalone scheduler imports. They
observe ORM changes; direct SQL/bulk updates to job or review state bypass them.
No email, SMS or push messages are sent. Notification data is ready for a future
frontend bell; a visual bell is not part of this backend module.

## Installation and tests

Run migrate_notifications.py before connecting the new models and hooks. The
migration backs up the SQLite database, creates only the new table/indexes, and
can be repeated. It does not recreate alerts for historical jobs.

Run python -B -m pytest tests -q from the project folder. Tests use isolated
databases and mocked external services.
