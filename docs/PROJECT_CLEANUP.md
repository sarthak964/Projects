# Project cleanup — October 31, 2026

Detailed guides moved into docs/. The root README is the entry point.
Obsolete manual AI/geocoding experiment scripts, blank.jpg, database snapshots,
source backup copies and generated caches/build output were archived at:

C:\Users\Sarthak\OneDrive\Tài liệu\ChatGPT\TruStay\project_cleanup_archive_20261031_115144

The archive contains manifest.json with original and destination paths. No files
were permanently deleted. Active .env, databases, evidence uploads, Python and
Node dependencies, IDE settings, demo lock and running-server logs were retained.
They are excluded from Git. Fresh builds/tests may recreate ignored dist/caches.
Historical migration scripts remain in place because regression tests import them.
httpx, used by FastAPI TestClient, is now an explicit pinned dependency.

Commit README.md, .gitignore, .env.example, app/, tests/, docs/, frontend source,
frontend/public/images/, package.json, package-lock.json, TypeScript/Vite config,
requirements.txt, pytest.ini, create_tables.py, run_demo.py, seed_demo.py and
migrate_*.py. Do not upload .env, databases, uploads, demo_data, installed
dependencies, generated output, runtime logs, backups or personal editor settings.
