#!/usr/bin/env python3
"""Pre-load store x category product lists from Open Food Facts into DynamoDB.

Why: OFF allows only ~10 searches/minute and is sometimes overloaded (HTTP 503). Seeding once
means shoppers browse instantly from DynamoDB instead of waiting on OFF.

    export TABLE_NAME=$(terraform -chdir=infra output -raw table_name)
    python scripts/seed_catalog.py                                  # everything (~15-25 min)
    python scripts/seed_catalog.py --only-missing                   # just retry what failed/is empty
    python scripts/seed_catalog.py --stores walmart target --categories coffee cereal

Rules:
- A FAILED fetch never overwrites what is already stored (it used to write an empty list).
- Small store lists (<5 items) ARE stored; the app tops them up from the 'any' list at read time.
- 'any' is seeded first, because every other store falls back to it.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "src"))
from common import config, db, off_client  # noqa: E402

PAUSE = 7          # seconds between searches -> stays under 10/min
BACKOFF = [20, 45, 90, 180]  # waits after each failure (OFF 503s usually clear within a few minutes)


def fetch(tag, store, page_size):
    for attempt, wait in enumerate(BACKOFF, start=1):
        try:
            return off_client.search(tag, store, page_size=page_size, timeout=60)
        except Exception as exc:
            print(f"   ↻ attempt {attempt} failed ({exc}); waiting {wait}s")
            time.sleep(wait)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stores", nargs="*", default=list(config.STORES))
    ap.add_argument("--categories", nargs="*", default=list(config.CATEGORIES))
    ap.add_argument("--page-size", type=int, default=60)
    ap.add_argument("--only-missing", action="store_true", help="skip lists already stored with items")
    a = ap.parse_args()
    if config.TABLE_NAME == "phytro-local":
        sys.exit("Set TABLE_NAME (terraform -chdir=infra output -raw table_name)")

    stores = sorted(a.stores, key=lambda s: s != "any")  # 'any' first
    failed, done = [], 0
    for store in stores:
        for cat in a.categories:
            if a.only_missing and db.get_catalog(store, cat):
                continue
            items = fetch(config.CATEGORIES[cat]["tag"], store, a.page_size)
            if items is None:
                failed.append(f"{store}/{cat}")
                print(f"✗ {store:14s} {cat:14s} FAILED - kept whatever was stored before")
            elif not items and store == "any":
                failed.append(f"{store}/{cat}")
                print(f"✗ {store:14s} {cat:14s} 0 products - not stored (the app will fetch it live)")
            else:
                db.put_catalog(store, cat, items)  # no TTL: seeded data persists
                done += 1
                extra = "  (app tops this up from 'any')" if len(items) < 5 and store != "any" else ""
                print(f"✓ {store:14s} {cat:14s} {len(items):3d} products{extra}")
            time.sleep(PAUSE)

    print(f"\n{done} list(s) stored, {len(failed)} failed.")
    if failed:
        print("Re-run later with:  python scripts/seed_catalog.py --only-missing")
        print("Failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
