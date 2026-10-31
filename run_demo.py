"""Run the separate demo on port 8001, without modifying .env."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8001)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('port must be between 1 and 65535')
    root = Path(__file__).resolve().parent
    from app.services.demo_seed import demo_paths, require_owned
    database, uploads = demo_paths(root)
    if not database.exists():
        parser.exit(1, 'Run python -B seed_demo.py first.\n')
    require_owned(database)
    env = os.environ.copy()
    from dotenv import dotenv_values
    if not env.get('OPENAI_API_KEY') and not dotenv_values(root / '.env').get('OPENAI_API_KEY'):
        env['OPENAI_API_KEY'] = 'demo-no-provider-configured'
    env.update(DATABASE_URL='sqlite:///' + database.as_posix(), UPLOAD_DIR=str(uploads),
               ENVIRONMENT='development', ADMIN_PHONES='9999999999',
               JWT_SECRET='trustay-separate-local-demo-key',
               SCHEDULER_ENABLED='false', PLATFORM_COMMISSION_RATE='0.15',
               MAX_SERVICE_DISTANCE_KM='50', PHOTO_REVIEW_WINDOW_HOURS='48',
               HUMAN_REVIEW_FEE='75', AI_COST_PER_PHOTO_INR='0.5',
               PHOTO_REVIEW_FEE_MULTIPLIER='6', PHOTO_REVIEW_FEE_MIN='25',
               PHOTO_REVIEW_FEE_MAX='60', STRIKES_BEFORE_SUSPENSION='3')
    lock = database.parent / 'server.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        parser.exit(1, 'Demo is already running, or a stale demo_data/server.lock needs inspection.\n')
    try:
        os.write(descriptor, str(os.getpid()).encode('ascii'))
        os.close(descriptor)
        print(f'TruStay demo: http://127.0.0.1:{args.port} - separate sample database; scheduler paused.', flush=True)
        result = subprocess.run([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(args.port)], cwd=root, env=env)
        return result.returncode
    except KeyboardInterrupt:
        return 0
    finally:
        lock.unlink(missing_ok=True)


if __name__ == '__main__':
    raise SystemExit(main())
