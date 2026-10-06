"""Open Food Facts (OFF) client - free, open product database (no API key).

Rate limits (per IP): 15 product reads/min, 10 searches/min. That is why every
result is cached in DynamoDB and the store catalog is pre-seeded by
scripts/seed_catalog.py instead of hitting OFF on every page view.
"""
import json
import re
import urllib.parse
import urllib.request

from common import config

FIELDS = [
    "code", "product_name", "product_name_en", "brands", "quantity", "image_front_small_url",
    "image_front_url", "nutriscore_grade", "nova_group", "additives_tags", "allergens_tags",
    "traces_tags", "ingredients_text", "ingredients_text_en", "ingredients_analysis_tags",
    "labels_tags", "categories_tags", "stores", "stores_tags", "nutriments",
]
NUTRIENTS = ["energy-kcal_100g", "sugars_100g", "salt_100g", "sodium_100g", "saturated-fat_100g",
             "fat_100g", "fiber_100g", "proteins_100g", "caffeine_100g"]
BARCODE_RE = re.compile(r"^\d{6,14}$")


def _get(path, params=None, timeout=20):
    url = f"{config.OFF_BASE_URL}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": config.OFF_USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - fixed https host
        return json.loads(resp.read().decode("utf-8"))


def normalize(p):
    """Reduce a raw OFF product to the fields PhyTro uses (keeps raw ingredient text as-is)."""
    nutr = p.get("nutriments") or {}
    grade = (p.get("nutriscore_grade") or "").lower()
    return {
        "barcode": str(p.get("code", "")),
        "name": (p.get("product_name_en") or p.get("product_name") or "Unnamed product").strip(),
        "brand": (p.get("brands") or "").split(",")[0].strip(),
        "quantity": p.get("quantity") or "",
        "image": p.get("image_front_small_url") or p.get("image_front_url") or "",
        "nutriscore": grade if grade in {"a", "b", "c", "d", "e"} else None,
        "nova": p.get("nova_group") if p.get("nova_group") in (1, 2, 3, 4) else None,
        "additives": p.get("additives_tags") or [],
        "allergens": p.get("allergens_tags") or [],
        "traces": p.get("traces_tags") or [],
        "ingredients_text": p.get("ingredients_text_en") or p.get("ingredients_text") or "",
        "analysis_tags": p.get("ingredients_analysis_tags") or [],
        "labels": p.get("labels_tags") or [],
        "categories": p.get("categories_tags") or [],
        "stores": p.get("stores") or "",
        "store_tags": p.get("stores_tags") or [],
        "nutriments": {k: nutr[k] for k in NUTRIENTS if isinstance(nutr.get(k), (int, float))},
    }


def get_product(barcode):
    """Fetch one product by barcode. Returns normalized dict or None."""
    if not BARCODE_RE.match(str(barcode)):
        raise ValueError("barcode must be 6-14 digits")
    data = _get(f"/api/v2/product/{barcode}.json", {"fields": ",".join(FIELDS)})
    if data.get("status") != 1 or not data.get("product"):
        return None
    prod = data["product"]
    prod.setdefault("code", barcode)
    return normalize(prod)


def text_search(query, page_size=24, timeout=10):
    """Full-text search by product name / brand / description (US products).

    Only the v1 search endpoint supports free text (v2 is tag filters only). Shares the
    10 searches/min limit, so callers cache results and never search-as-you-type.
    """
    params = {
        "search_terms": query, "search_simple": 1, "action": "process", "json": 1,
        "page_size": page_size, "fields": ",".join(FIELDS),
        "tagtype_0": "countries", "tag_contains_0": "contains", "tag_0": "united-states",
        "sort_by": "unique_scans_n",
    }
    data = _get("/cgi/search.pl", params, timeout=timeout)
    return [normalize(p) for p in data.get("products", []) if p.get("code")]


def search(category_tag, store=None, page_size=40, page=1, timeout=12):
    """Search products in a category, optionally filtered to one store. Sold in the US only."""
    params = {
        "categories_tags": category_tag,
        "countries_tags": "en:united-states",
        "fields": ",".join(FIELDS),
        "page_size": page_size,
        "page": page,
        "sort_by": "unique_scans_n",  # most-scanned first = most commonly bought
    }
    if store and store != "any":
        params["stores_tags"] = store
    data = _get("/api/v2/search", params, timeout=timeout)
    return [normalize(p) for p in data.get("products", []) if p.get("code")]
