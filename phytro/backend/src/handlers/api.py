"""HTTP API Lambda (API Gateway HTTP API, payload v2, Cognito JWT authorizer).

The user id ALWAYS comes from the verified JWT (`sub` claim) - never from the request body -
so each account can only see its own profile, list and reports.
"""
import json
import re
import urllib.error
import uuid

import boto3

from common import config, db, products, scoring

_lambda = None
BARCODE_RE = re.compile(r"^\d{6,14}$")


def _resp(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, default=str)}


def _sub(event):
    claims = (((event.get("requestContext") or {}).get("authorizer") or {}).get("jwt") or {}).get("claims") or {}
    return claims.get("sub")


def _body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64
        raw = base64.b64decode(raw).decode()
    return json.loads(raw)


def clean_profile(data):
    """Whitelist profile fields so the client can't write arbitrary attributes."""
    allergens = [a for a in data.get("allergens", []) if a in scoring.ALLERGENS]
    avoid = [a for a in data.get("avoid", []) if a in scoring.AVOID_GROUPS]
    diet = [d for d in data.get("diet", []) if d in scoring.DIETS]
    store = data.get("default_store") if data.get("default_store") in config.STORES else "walmart"
    return {"display_name": str(data.get("display_name", ""))[:60], "allergens": allergens, "avoid": avoid,
            "diet": diet, "default_store": store, "auto_add_best": bool(data.get("auto_add_best"))}


def meta():
    return {
        "stores": [{"id": k, "label": v} for k, v in config.STORES.items()],
        "categories": [{"id": k, **v} for k, v in config.CATEGORIES.items()],
        "allergens": [{"id": k, "label": v} for k, v in scoring.ALLERGENS.items()],
        "avoid": [{"id": k, "label": v["label"]} for k, v in scoring.AVOID_GROUPS.items()],
        "diets": list(scoring.DIETS),
    }


def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    route = event.get("routeKey", "")
    params = event.get("queryStringParameters") or {}
    path = event.get("pathParameters") or {}

    if route == "GET /health":
        return _resp(200, {"ok": True})
    sub = _sub(event)
    if not sub:
        return _resp(401, {"error": "not signed in"})

    try:
        if route == "GET /meta":
            return _resp(200, meta())

        if route == "GET /profile":
            return _resp(200, db.get_profile(sub))
        if route == "PUT /profile":
            return _resp(200, db.put_profile(sub, clean_profile(_body(event))))

        if route == "GET /browse":
            profile = db.get_profile(sub)
            store = params.get("store") or profile["default_store"]
            items, source, note = products.browse(store, params.get("category", ""), profile)
            return _resp(200, {"store": store, "category": params.get("category"), "source": source,
                               "note": note, "products": items})

        if route == "GET /search":
            profile = db.get_profile(sub)
            store = params.get("store") if params.get("store") in config.STORES else profile["default_store"]
            items, sources, note = products.search_by_name(params.get("q", ""), store, profile)
            return _resp(200, {"query": params.get("q", ""), "store": store, "sources": sources,
                               "note": note, "products": items})

        if route == "GET /products/{barcode}":
            code = path.get("barcode", "")
            if not BARCODE_RE.match(code):
                return _resp(400, {"error": "barcode must be 6-14 digits"})
            product = products.get_product(code)
            if not product:
                return _resp(404, {"error": "Product not found in Open Food Facts"})
            profile = db.get_profile(sub)
            return _resp(200, {"product": product, "phytro": scoring.score_product(product, profile),
                               "category": products.category_for(product), "report": db.get_report(sub, code)})

        if route == "GET /list":
            return _resp(200, {"items": db.list_items(sub)})
        if route == "PUT /list/{barcode}":
            code = path.get("barcode", "")
            if not BARCODE_RE.match(code):
                return _resp(400, {"error": "bad barcode"})
            b = _body(event)
            item = {"barcode": code, "name": str(b.get("name", ""))[:120], "brand": str(b.get("brand", ""))[:80],
                    "store": b.get("store") if b.get("store") in config.STORES else "any",
                    "image": str(b.get("image", ""))[:400], "score": b.get("score"),
                    "note": str(b.get("note", ""))[:200], "checked": bool(b.get("checked")),
                    "added": b.get("added"), "added_by": "user" if b.get("added_by") != "agent" else "agent"}
            return _resp(200, db.put_list_item(sub, item))
        if route == "DELETE /list/{barcode}":
            db.delete_list_item(sub, path.get("barcode", ""))
            return _resp(200, {"ok": True})

        if route == "POST /analyze":
            b = _body(event)
            code = str(b.get("barcode", ""))
            if not BARCODE_RE.match(code):
                return _resp(400, {"error": "barcode must be 6-14 digits"})
            store = b.get("store") if b.get("store") in config.STORES else None
            job_id = uuid.uuid4().hex[:12]
            db.create_job(sub, job_id, code)
            global _lambda
            _lambda = _lambda or boto3.client("lambda")
            _lambda.invoke(FunctionName=config.WORKER_FUNCTION, InvocationType="Event",  # async
                           Payload=json.dumps({"sub": sub, "job_id": job_id, "barcode": code, "store": store,
                                               "auto_add": b.get("auto_add")}).encode())
            return _resp(202, {"job_id": job_id})
        if route == "GET /jobs/{id}":
            job = db.get_job(sub, path.get("id", ""))
            return _resp(200, job) if job else _resp(404, {"error": "job not found"})

        return _resp(404, {"error": f"no route {method} {route}"})
    except ValueError as exc:
        return _resp(400, {"error": str(exc)})
    except (urllib.error.URLError, TimeoutError) as exc:
        print(json.dumps({"level": "error", "route": route, "error": repr(exc)}))
        return _resp(502, {"error": "The Open Food Facts product database is slow or rate-limited. "
                                    "Try again in a minute."})
    except Exception as exc:  # keep the client error generic, log the detail
        print(json.dumps({"level": "error", "route": route, "error": repr(exc)}))
        return _resp(500, {"error": "Internal error"})
