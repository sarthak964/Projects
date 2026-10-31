"""Seed only demo_data/trustay_demo.db. Never selects DATABASE_URL as a target."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset', action='store_true', help='Back up and replace the owned demo database; stop the demo server first')
    args = parser.parse_args()
    # App imports need a configured AI client, but seeding never invokes it.
    import os
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parent
    load_dotenv(root / '.env')
    os.environ.setdefault('OPENAI_API_KEY', 'demo-no-provider-configured')
    from app.services.demo_seed import prepare_demo
    try:
        print(json.dumps(prepare_demo(root, reset=args.reset), indent=2))
    except ValueError as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
