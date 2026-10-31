# Repeatable local demonstration

Your existing trustay.db, uploads/ and .env are not modified by these commands.
From C:\Users\Sarthak\TruStay with .venv active:

    python -B seed_demo.py
    python -B run_demo.py

The demo runs on http://127.0.0.1:8001 and its interactive API is /docs.
It uses demo_data/trustay_demo.db and demo_data/uploads. Your normal server on
port 8000 can keep running against its existing database. Login tokens and job
IDs from one database must not be reused against the other.
The demo launcher uses a separate development signing key, so normal-server
login tokens do not authenticate against the demo. Log in on port 8001 afresh.

Accounts (request a fresh development OTP, then verify it normally):

| Role | Phone | User ID |
| --- | --- | --- |
| Renter | 9000000001 | 4 |
| Reviewer | 9000000002 | 5 |
| Admin | 9999999999 | 1 |

All properties and the reviewer's saved location are near Connaught Place,
New Delhi. Addresses, findings, fixed INR 150 payment examples, images, AI
results and notifications are sample fixtures. Later real job acceptances use
the existing distance-based calculation and 50 km service-radius rule.

| Job | Demo scenario |
| --- | --- |
| 1 | Open job ready for reviewer acceptance |
| 2 | Accepted, waiting for visit |
| 3 | Visited with sample photos, ready for report submission |
| 4 | Submitted report ready for AI assessment |
| 5 | Needs report correction and resubmission |
| 6 | Verified report ready for renter photo approval/rejection |
| 7 | Rejected photos awaiting reviewer replacement |
| 8 | Human-review queue with simulated fees held |
| 9 | Approved with simulated reviewer payout and commission |
| 10 | Human refund decision with a pending reviewer appeal |

Placeholder images visibly say DEMO and are not real inspection evidence. Each
photo record has its own file, so deleting one does not break another job.
Seeding makes no provider/network calls. Precomputed summaries are labelled.
Using verification or rejection endpoints afterward can call the configured AI
provider and incur actual usage charges. Without a provider key those actions
will fail, but seeded browsing and manual approval remain available.

Rerunning seed_demo.py preserves edits. To restore the fixtures:

1. Stop run_demo.py with Ctrl+C.
2. Run python -B seed_demo.py --reset.
3. Run python -B run_demo.py again.

Reset verifies a database ownership marker and refuses unmarked databases.
It backs up the old demo database under demo_data/backups before replacement.
Existing uploaded files are retained; reset does not recursively delete uploads.
Only the fixed demo database is replaced. There is no arbitrary --database path.
The launcher uses a lock file to block reset while it runs. If the launcher was
forcibly killed, first verify no demo server is still running before manually
removing a stale demo_data/server.lock. Always use the launcher for this demo.

The launcher pauses the scheduler so sample stages do not change automatically.
Deadlines are created relative to seed/reset time; reset before a demonstration
if they have elapsed. The normal application's scheduler is unaffected.
Demo admin settings and database/upload paths are scoped to its subprocess;
the normal .env file is never edited.
