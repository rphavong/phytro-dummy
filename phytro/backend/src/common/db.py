"""DynamoDB single-table access.

Key design (table: PK, SK, optional ttl):
  USER#<sub>        PROFILE              saved preferences (allergens, avoid list, store...)
  USER#<sub>        LIST#<barcode>       shopping-list item
  USER#<sub>        REPORT#<barcode>     last AI report for that product (per user = private)
  USER#<sub>        JOB#<id>             live agent run (steps appended as agents work), ttl 24h
  CATALOG#<store>   CAT#<category>       ranked product list (seeded or cached from OFF)
  PRODUCT#<barcode> DETAIL               cached OFF product, ttl 72h
Every user record is keyed by the Cognito `sub` taken from the verified JWT,
so one account can never read another account's data.
"""
import json
import time
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from common import config

_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(config.TABLE_NAME)
    return _table


def _to_ddb(obj):
    return json.loads(json.dumps(obj), parse_float=Decimal)


def _from_ddb(obj):
    def default(o):
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        raise TypeError
    return json.loads(json.dumps(obj, default=default))


def _ttl(hours):
    return int(time.time() + hours * 3600)


# ---------- profile ----------
DEFAULT_PROFILE = {"display_name": "", "allergens": [], "avoid": [], "diet": [],
                   "default_store": "walmart", "auto_add_best": False}


def get_profile(sub):
    item = table().get_item(Key={"PK": f"USER#{sub}", "SK": "PROFILE"}).get("Item")
    return {**DEFAULT_PROFILE, **(_from_ddb(item["data"]) if item else {})}


def put_profile(sub, profile):
    table().put_item(Item={"PK": f"USER#{sub}", "SK": "PROFILE", "data": _to_ddb(profile),
                           "updated": int(time.time())})
    return profile


# ---------- shopping list ----------
def list_items(sub):
    resp = table().query(KeyConditionExpression=Key("PK").eq(f"USER#{sub}") & Key("SK").begins_with("LIST#"))
    return sorted((_from_ddb(i["data"]) for i in resp.get("Items", [])), key=lambda x: x.get("added", 0))


def put_list_item(sub, item):
    item = {**item, "added": item.get("added") or int(time.time()), "checked": bool(item.get("checked"))}
    table().put_item(Item={"PK": f"USER#{sub}", "SK": f"LIST#{item['barcode']}", "data": _to_ddb(item)})
    return item


def delete_list_item(sub, barcode):
    table().delete_item(Key={"PK": f"USER#{sub}", "SK": f"LIST#{barcode}"})


# ---------- reports ----------
def save_report(sub, barcode, report):
    table().put_item(Item={"PK": f"USER#{sub}", "SK": f"REPORT#{barcode}", "data": _to_ddb(report),
                           "created": int(time.time())})


def get_report(sub, barcode):
    item = table().get_item(Key={"PK": f"USER#{sub}", "SK": f"REPORT#{barcode}"}).get("Item")
    return _from_ddb(item["data"]) if item else None


# ---------- agent jobs ----------
def create_job(sub, job_id, barcode):
    table().put_item(Item={"PK": f"USER#{sub}", "SK": f"JOB#{job_id}", "status": "queued",
                           "barcode": barcode, "steps": [], "created": int(time.time()),
                           "ttl": _ttl(config.JOB_TTL_HOURS)})


def append_step(sub, job_id, step):
    step = {**step, "t": round(time.time(), 2)}
    table().update_item(
        Key={"PK": f"USER#{sub}", "SK": f"JOB#{job_id}"},
        UpdateExpression="SET steps = list_append(steps, :s), #st = :running",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={":s": [_to_ddb(step)], ":running": "running"},
    )


def finish_job(sub, job_id, status, report=None, error=None):
    table().update_item(
        Key={"PK": f"USER#{sub}", "SK": f"JOB#{job_id}"},
        UpdateExpression="SET #st = :s, report = :r, #err = :e",
        ExpressionAttributeNames={"#st": "status", "#err": "error"},
        ExpressionAttributeValues={":s": status, ":r": _to_ddb(report), ":e": error},
    )


def get_job(sub, job_id):
    item = table().get_item(Key={"PK": f"USER#{sub}", "SK": f"JOB#{job_id}"}).get("Item")
    if not item:
        return None
    item = _from_ddb(item)
    return {k: item.get(k) for k in ("status", "barcode", "steps", "report", "error", "created")}


# ---------- caches ----------
def get_catalog(store, category):
    item = table().get_item(Key={"PK": f"CATALOG#{store}", "SK": f"CAT#{category}"}).get("Item")
    if not item or (item.get("ttl") and item["ttl"] < time.time()):
        return None
    return _from_ddb(item["products"])


def put_catalog(store, category, products, ttl_hours=None):
    item = {"PK": f"CATALOG#{store}", "SK": f"CAT#{category}", "products": _to_ddb(products),
            "updated": int(time.time())}
    if ttl_hours:
        item["ttl"] = _ttl(ttl_hours)
    table().put_item(Item=item)


_catalog_index = {"at": 0, "items": None}


def catalog_index(max_age_s=600):
    """Every product in every stored store/aisle list, de-duplicated, with the stores it's listed at.

    One Scan (filtered to CATALOG# rows) cached in Lambda memory for 10 minutes, so name
    search is instant and costs ~nothing. Returns {barcode: product_with_'listed_at'}.
    """
    if _catalog_index["items"] is not None and time.time() - _catalog_index["at"] < max_age_s:
        return _catalog_index["items"]
    from boto3.dynamodb.conditions import Attr
    items, kwargs = {}, {"FilterExpression": Attr("PK").begins_with("CATALOG#"),
                         "ProjectionExpression": "PK, products"}
    while True:
        resp = table().scan(**kwargs)
        for row in resp.get("Items", []):
            store = row["PK"].split("#", 1)[1]
            for p in _from_ddb(row.get("products") or []):
                prev = items.setdefault(p["barcode"], {**p, "listed_at": []})
                if store != "any" and store not in prev["listed_at"]:
                    prev["listed_at"].append(store)
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    _catalog_index.update(at=time.time(), items=items)
    return items


def get_search(query):
    item = table().get_item(Key={"PK": f"SEARCH#{query}", "SK": "RESULTS"}).get("Item")
    if not item or item.get("ttl", 0) < time.time():
        return None
    return _from_ddb(item["products"])


def put_search(query, products, ttl_hours=24):
    table().put_item(Item={"PK": f"SEARCH#{query}", "SK": "RESULTS", "products": _to_ddb(products),
                           "ttl": _ttl(ttl_hours)})


def get_cached_product(barcode):
    item = table().get_item(Key={"PK": f"PRODUCT#{barcode}", "SK": "DETAIL"}).get("Item")
    if not item or item.get("ttl", 0) < time.time():
        return None
    return _from_ddb(item["data"])


def put_cached_product(product):
    table().put_item(Item={"PK": f"PRODUCT#{product['barcode']}", "SK": "DETAIL", "data": _to_ddb(product),
                           "ttl": _ttl(config.CACHE_TTL_HOURS)})
