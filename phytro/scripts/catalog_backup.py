#!/usr/bin/env python3
"""Back up / restore PhyTro's shared product data (store aisle lists, product cache, search cache).

User data (profiles, lists, reports) is NOT copied - it belongs to Cognito accounts, which are
per-deployment. Typical use: keep your seeded aisles when the DynamoDB table is replaced
(e.g. renaming the project, or moving to a new AWS account).

    python scripts/catalog_backup.py dump catalog-backup.json --table safecart-robby
    python scripts/catalog_backup.py load catalog-backup.json --table phytro-robby
"""
import argparse
import json
import sys
import time

import boto3

SHARED_PREFIXES = ("CATALOG#", "PRODUCT#", "SEARCH#")


def dump(table, path, region):
    ddb = boto3.client("dynamodb", region_name=region)
    items, kwargs = [], {"TableName": table}
    while True:
        resp = ddb.scan(**kwargs)
        items += [i for i in resp["Items"] if i["PK"]["S"].startswith(SHARED_PREFIXES)]
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(items, fh)  # DynamoDB-typed JSON: round-trips numbers exactly
    lists = sum(i["PK"]["S"].startswith("CATALOG#") for i in items)
    print(f"✅ saved {len(items)} rows ({lists} store/aisle lists) from {table} -> {path}")


def load(table, path, region):
    ddb = boto3.client("dynamodb", region_name=region)
    with open(path, encoding="utf-8") as fh:
        items = json.load(fh)
    for start in range(0, len(items), 25):  # BatchWriteItem max 25
        batch = [{"PutRequest": {"Item": i}} for i in items[start:start + 25]]
        req = {table: batch}
        for attempt in range(8):
            resp = ddb.batch_write_item(RequestItems=req)
            req = resp.get("UnprocessedItems") or {}
            if not req:
                break
            time.sleep(0.5 * 2 ** attempt)
        else:
            sys.exit("❌ DynamoDB kept throttling; re-run the same command (it is safe to repeat).")
    print(f"✅ restored {len(items)} rows into {table}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["dump", "load"])
    ap.add_argument("file")
    ap.add_argument("--table", required=True)
    ap.add_argument("--region", default="us-east-1")
    a = ap.parse_args()
    (dump if a.action == "dump" else load)(a.table, a.file, a.region)
